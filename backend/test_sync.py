import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import backend elements
from backend.database import Base
from backend.models import Account, Page
from backend.repositories import AccountRepository, PageRepository
from backend.schemas import AccountCreate
from backend.services import (
    FacebookSyncService,
    AccountNotFoundError,
    FacebookAuthError,
    FacebookAPIError
)

class TestFacebookPageSync(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        
        self.account_repo = AccountRepository(self.db)
        self.page_repo = PageRepository(self.db)
        self.sync_service = FacebookSyncService(self.db)

        # Patch exchange_token to return token as-is during tests
        patcher = patch.object(FacebookSyncService, "exchange_token", side_effect=lambda token: token)
        self.mock_exchange = patcher.start()
        self.addCleanup(patcher.stop)

        # Seed initial test account
        self.test_user_id = "fb_user_test_999"
        self.account_repo.create_or_update_account(AccountCreate(
            facebook_user_id=self.test_user_id,
            name="John Test Doe",
            user_access_token="EAA_VALID_TEST_TOKEN"
        ))

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch("requests.post")
    @patch("requests.get")
    def test_sync_success_and_upsert(self, mock_get, mock_post):
        """Test syncing pages successfully and verifying the UPSERT database logic."""
        # Mock requests.post to avoid real network attempts during webhook auto-subscription
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"success": True}
        mock_post.return_value = mock_post_resp

        # 1. Setup mocks for first run (/me profile call, then /me/accounts pages call)
        mock_me = MagicMock()
        mock_me.json.return_value = {"id": self.test_user_id, "name": "John Test Doe"}
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "page_id_A",
                    "name": "Shop A (Original Name)",
                    "access_token": "page_token_A",
                    "picture": {
                        "data": {
                            "url": "https://avatar.url/shopA.jpg"
                        }
                    }
                },
                {
                    "id": "page_id_B",
                    "name": "Shop B",
                    "access_token": "page_token_B",
                    "picture": {
                        "data": {
                            "url": "https://avatar.url/shopB.jpg"
                        }
                    }
                }
            ]
        }
        
        mock_get.side_effect = [mock_me, mock_response]

        # Execute first sync
        count, pages = self.sync_service.sync_pages(self.test_user_id)
        self.assertEqual(count, 2)
        
        # Verify they are written to the database
        db_pages = self.page_repo.get_pages_by_facebook_user_id(self.test_user_id)
        self.assertEqual(len(db_pages), 2)
        
        page_a = next(p for p in db_pages if p.page_id == "page_id_A")
        self.assertEqual(page_a.page_name, "Shop A (Original Name)")
        self.assertEqual(page_a.avatar_url, "https://avatar.url/shopA.jpg")

        # 2. Setup mocks for second run (1. /me profile call, 2. /me/accounts pages call with updates)
        mock_me_second = MagicMock()
        mock_me_second.json.return_value = {"id": self.test_user_id, "name": "John Test Doe"}

        mock_response_second = MagicMock()
        mock_response_second.json.return_value = {
            "data": [
                {
                    "id": "page_id_A",
                    "name": "Shop A (Updated Name)",  # Name changed
                    "access_token": "page_token_A_new",
                    "picture": {
                        "data": {
                            "url": "https://avatar.url/shopA_new.jpg"
                        }
                    }
                },
                {
                    "id": "page_id_B",
                    "name": "Shop B",
                    "access_token": "page_token_B",
                    "picture": {
                        "data": {
                            "url": "https://avatar.url/shopB.jpg"
                        }
                    }
                },
                {
                    "id": "page_id_C",
                    "name": "Shop C (New)",  # New page added
                    "access_token": "page_token_C",
                    "picture": {
                        "data": {
                            "url": "https://avatar.url/shopC.jpg"
                        }
                    }
                }
            ]
        }
        
        mock_get.side_effect = [mock_me_second, mock_response_second]

        # Execute second sync
        count_2, pages_2 = self.sync_service.sync_pages(self.test_user_id)
        self.assertEqual(count_2, 3)

        # Verify database is updated correctly (UPSERT verified: total entries should be 3, not 5)
        db_pages_after = self.page_repo.get_pages_by_facebook_user_id(self.test_user_id)
        self.assertEqual(len(db_pages_after), 3)

        # Confirm Shop A is updated
        updated_page_a = next(p for p in db_pages_after if p.page_id == "page_id_A")
        self.assertEqual(updated_page_a.page_name, "Shop A (Updated Name)")
        self.assertEqual(updated_page_a.page_access_token, "page_token_A_new")
        self.assertEqual(updated_page_a.avatar_url, "https://avatar.url/shopA_new.jpg")

    def test_sync_account_not_found(self):
        """Test sync fails with AccountNotFoundError when facebook_user_id does not exist."""
        with self.assertRaises(AccountNotFoundError):
            self.sync_service.sync_pages("fb_user_missing_999")

    @patch("requests.get")
    def test_sync_token_expired(self, mock_get):
        """Test sync raises FacebookAuthError when Facebook Graph API reports invalid token."""
        mock_me = MagicMock()
        mock_me.json.return_value = {
            "error": {
                "message": "Error validating access token: The session has been invalidated.",
                "type": "OAuthException",
                "code": 190,
                "fbtrace_id": "FxxTESTID"
            }
        }
        mock_get.return_value = mock_me

        with self.assertRaises(FacebookAuthError) as context:
            self.sync_service.sync_pages(self.test_user_id)
        
        self.assertIn("Token expired or revoked", str(context.exception))

    @patch("requests.post")
    def test_send_attachment_success(self, mock_post):
        """Test sending file attachments successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message_id": "mid.attachment_test_123"}
        mock_post.return_value = mock_response

        # Seed page
        from backend.schemas import PageCreate
        self.page_repo.upsert_page(PageCreate(
            page_id="page_123",
            page_name="Test Page",
            page_access_token="EAA_PAGE_TOKEN",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        # We need a dummy file path
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"dummy content")
            tmp_path = tmp.name

        try:
            import asyncio
            msg = asyncio.run(self.sync_service.send_page_attachment(
                page_id="page_123",
                recipient_id="customer_psid_123",
                attachment_type="image",
                file_path=tmp_path,
                filename="test.png",
                local_url="http://localhost:8000/uploads/test.png"
            ))

            self.assertIsNotNone(msg)
            self.assertEqual(msg.facebook_message_id, "mid.attachment_test_123")
            self.assertEqual(msg.text, "[image] http://localhost:8000/uploads/test.png")
            self.assertEqual(msg.direction, "outbound")
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    @patch("requests.post")
    def test_send_attachment_url_success(self, mock_post):
        """Test sending attachment via URL successfully (Sticker, GIF)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message_id": "mid.url_attachment_test_789"}
        mock_post.return_value = mock_response

        # Seed page
        from backend.schemas import PageCreate
        self.page_repo.upsert_page(PageCreate(
            page_id="page_456",
            page_name="URL Test Page",
            page_access_token="EAA_PAGE_TOKEN_URL",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        import asyncio
        msg = asyncio.run(self.sync_service.send_page_attachment_url(
            page_id="page_456",
            recipient_id="customer_psid_456",
            attachment_type="image",
            attachment_url="https://media.giphy.com/media/l3q2XhfQ8oCkm1K7m/giphy.gif"
        ))

        self.assertIsNotNone(msg)
        self.assertEqual(msg.facebook_message_id, "mid.url_attachment_test_789")
        self.assertEqual(msg.text, "[image] https://media.giphy.com/media/l3q2XhfQ8oCkm1K7m/giphy.gif")
        self.assertEqual(msg.direction, "outbound")

    @patch("requests.post")
    def test_react_message_success(self, mock_post):
        """Test adding and removing message reactions successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        # Seed page
        from backend.schemas import PageCreate
        from backend.repositories import MessageRepository
        message_repo = MessageRepository(self.db)
        
        self.page_repo.upsert_page(PageCreate(
            page_id="page_react",
            page_name="React Page",
            page_access_token="EAA_PAGE_REACT_TOKEN",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        # Seed message to react to
        message_repo.save_webhook_message(
            facebook_message_id="mid.target_msg_1",
            page_id="page_react",
            sender_id="customer_psid_react",
            text="hello react",
            timestamp=1234567,
            direction="inbound"
        )

        import asyncio
        msg = asyncio.run(self.sync_service.react_to_message(
            page_id="page_react",
            recipient_id="customer_psid_react",
            facebook_message_id="mid.target_msg_1",
            emoji="❤️"
        ))

        self.assertIsNotNone(msg)
        self.assertEqual(msg.reactions, "❤️")

    def test_delete_message_success(self):
        """Test deleting message (unsend) successfully."""
        # Seed page and message
        from backend.schemas import PageCreate
        from backend.repositories import MessageRepository
        message_repo = MessageRepository(self.db)
        
        self.page_repo.upsert_page(PageCreate(
            page_id="page_delete",
            page_name="Delete Page",
            page_access_token="EAA_PAGE_DELETE_TOKEN",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        message_repo.save_webhook_message(
            facebook_message_id="mid.to_be_deleted",
            page_id="page_delete",
            sender_id="customer_psid_delete",
            text="goodbye",
            timestamp=1234567,
            direction="outbound"
        )

        import asyncio
        success = asyncio.run(self.sync_service.delete_page_message(
            page_id="page_delete",
            facebook_message_id="mid.to_be_deleted"
        ))

        self.assertTrue(success)
        # Verify message is gone from repo
        msg = message_repo.get_by_fb_message_id("mid.to_be_deleted")
        self.assertIsNone(msg)

    @patch("requests.post")
    def test_reply_to_comment_success(self, mock_post):
        """Test replying to a comment successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "122095078959402237_2989637557912774"}
        mock_post.return_value = mock_response

        # Seed page
        from backend.schemas import PageCreate
        self.page_repo.upsert_page(PageCreate(
            page_id="page_comment",
            page_name="Comment Page",
            page_access_token="EAA_PAGE_COMMENT_TOKEN",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        import asyncio
        res = asyncio.run(self.sync_service.reply_to_comment(
            comment_id="comment_123",
            page_id="page_comment",
            text="hello reply"
        ))

        self.assertEqual(res["id"], "122095078959402237_2989637557912774")

    @patch("requests.post")
    def test_react_to_comment_success(self, mock_post):
        """Test reacting to a comment successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        # Seed page
        from backend.schemas import PageCreate
        self.page_repo.upsert_page(PageCreate(
            page_id="page_comment",
            page_name="Comment Page",
            page_access_token="EAA_PAGE_COMMENT_TOKEN",
            facebook_user_id=self.test_user_id,
            avatar_url=None,
            status="active"
        ))

        import asyncio
        res = asyncio.run(self.sync_service.react_to_comment(
            comment_id="comment_123",
            page_id="page_comment",
            reaction="LOVE"
        ))

        self.assertTrue(res["success"])

if __name__ == "__main__":
    unittest.main()
