import requests
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple, Optional
from backend.config import settings
from backend.repositories import AccountRepository, PageRepository, MessageRepository
from backend.schemas import PageCreate, AccountCreate
from backend.websocket import manager

class AccountNotFoundError(Exception):
    """Raised when the specified Facebook Account is not registered in the system."""
    pass

class FacebookAuthError(Exception):
    """Raised when the Facebook access token is invalid, expired, or revoked."""
    pass

class FacebookAPIError(Exception):
    """Raised when the Facebook Graph API returns a general error."""
    pass

class FacebookSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.account_repo = AccountRepository(db)
        self.page_repo = PageRepository(db)
        self.message_repo = MessageRepository(db)

    def _handle_api_errors(self, response_json: Dict[str, Any]):
        """Helper function to parse and raise standard exceptions for Facebook API errors."""
        if "error" in response_json:
            error_detail = response_json["error"]
            error_message = error_detail.get("message", "Unknown Facebook Error")
            error_code = error_detail.get("code")
            error_type = error_detail.get("type")

            # Check for OAuth token validation errors (e.g., code 190)
            if error_type == "OAuthException" or error_code in (190, 102, 10):
                raise FacebookAuthError(f"Facebook authentication failed (Token expired or revoked): {error_message}")
            else:
                raise FacebookAPIError(f"Facebook Graph API error: {error_message} (Code: {error_code})")

    def exchange_token(self, short_lived_token: str) -> str:
        """
        Exchanges a 1-hour Short-lived Facebook User Access Token
        for a 60-day Long-lived Facebook User Access Token.
        """
        # If credentials are not set in .env, fallback to short-lived token to prevent breaking dev flow
        if not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
            print("[Warning] FACEBOOK_APP_ID or FACEBOOK_APP_SECRET not configured. Skipping token exchange.")
            return short_lived_token

        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "fb_exchange_token": short_lived_token
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response_json = response.json()
        except requests.RequestException as e:
            raise FacebookAPIError(f"Network error during token exchange: {str(e)}")

        self._handle_api_errors(response_json)
        
        long_lived_token = response_json.get("access_token")
        if not long_lived_token:
            raise FacebookAuthError("Token exchange succeeded but returned empty token payload.")
            
        print("[Token Exchanger] Exchanged short-lived token to long-lived token successfully.")
        return long_lived_token

    def sync_by_token(self, access_token: str) -> Tuple[str, int, List[Any]]:
        """
        Exchanges token to Long-lived version, resolves Facebook User ID,
        saves/updates account metadata, and syncs all pages.
        """
        # 1. Exchange token first
        long_lived_token = self.exchange_token(access_token)

        # 2. Fetch user profile information (ID & Name)
        me_url = f"{settings.FACEBOOK_BASE_URL}/me"
        try:
            me_response = requests.get(me_url, params={"access_token": long_lived_token}, timeout=10)
            me_json = me_response.json()
        except requests.RequestException as e:
            raise FacebookAPIError(f"Network error communicating with Facebook: {str(e)}")

        self._handle_api_errors(me_json)

        facebook_user_id = me_json.get("id")
        user_name = me_json.get("name", "Facebook User")

        if not facebook_user_id:
            raise FacebookAPIError("Could not resolve Facebook User ID from token.")

        # 3. Save or update the Facebook Account in database
        account = self.account_repo.create_or_update_account(AccountCreate(
            facebook_user_id=facebook_user_id,
            name=user_name,
            user_access_token=access_token # store original
        ))
        
        # Save exchanged long-lived token
        self.account_repo.update_long_lived_token(facebook_user_id, long_lived_token)

        # 4. Fetch all pages managed by this account (with pagination)
        accounts_url = f"{settings.FACEBOOK_BASE_URL}/me/accounts"
        params = {
            "access_token": long_lived_token,
            "fields": "id,name,access_token,picture.type(large)",
            "limit": 100  # Fetch up to 100 pages per request
        }

        fb_pages = []
        next_url = accounts_url
        current_params = params

        try:
            while next_url:
                if next_url == accounts_url:
                    response = requests.get(next_url, params=current_params, timeout=10)
                else:
                    response = requests.get(next_url, timeout=10)
                
                pages_json = response.json()
                self._handle_api_errors(pages_json)
                
                fb_pages.extend(pages_json.get("data", []))
                
                # Check for next page of pages
                paging_obj = pages_json.get("paging")
                next_url = paging_obj.get("next") if paging_obj else None
        except requests.RequestException as e:
            raise FacebookAPIError(f"Network error fetching pages from Facebook: {str(e)}")

        synced_pages = []
        for fb_page in fb_pages:
            page_id = fb_page.get("id")
            page_name = fb_page.get("name")
            page_token = fb_page.get("access_token")
            
            # Extract avatar URL if it exists
            avatar_url = None
            picture_obj = fb_page.get("picture")
            if picture_obj and "data" in picture_obj:
                avatar_url = picture_obj["data"].get("url")

            if not page_id or not page_name or not page_token:
                continue

            page_in = PageCreate(
                page_id=page_id,
                page_name=page_name,
                page_access_token=page_token,
                facebook_user_id=facebook_user_id,
                avatar_url=avatar_url,
                status="active"
            )

            # Perform DB UPSERT
            updated_page = self.page_repo.upsert_page(page_in)
            synced_pages.append(updated_page)

            # Auto-subscribe page to App Webhook fields programmatically
            subscribe_url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}/subscribed_apps"
            sub_params = {
                "subscribed_fields": "messages,messaging_postbacks,feed",
                "access_token": page_token
            }
            try:
                sub_response = requests.post(subscribe_url, params=sub_params, timeout=5)
                print(f"[Auto-Subscribe Webhook] Page '{page_name}' linked successfully. Response: {sub_response.json()}", flush=True)
            except Exception as se:
                print(f"[Auto-Subscribe Webhook Error] Failed for page '{page_name}': {str(se)}", flush=True)

        return facebook_user_id, len(synced_pages), synced_pages

    def sync_pages(self, facebook_user_id: str) -> Tuple[int, List[Any]]:
        """
        Synchronizes all Facebook Pages managed by a saved account using its facebook_user_id.
        """
        # Fetch token from DB (prefer long-lived token)
        account = self.account_repo.get_by_facebook_user_id(facebook_user_id)
        if not account:
            raise AccountNotFoundError(f"Account for Facebook User ID {facebook_user_id} not found.")

        token_to_use = account.user_access_token_long_lived or account.user_access_token
        # Re-run sync using the token
        _, count, pages = self.sync_by_token(token_to_use)
        return count, pages

    def get_live_notifications(self, facebook_user_id: str) -> List[Dict[str, Any]]:
        """
        Returns live notifications for all pages owned by this facebook_user_id.
        Note: Deprecated fields on Facebook are bypassed in favor of DB notification logs.
        """
        # Since Graph API deprecated /{page_id}/notifications, we now load notifications 
        # received in real-time via Webhook (stored in SQLite) to avoid API errors.
        # Handled in repository level.
        return []

    async def send_page_message(self, page_id: str, recipient_id: str, text: str, reply_to_message_id: Optional[str] = None) -> Any:
        """
        Sends an outbound reply chat to a recipient (customer PSID) on behalf of a page.
        Calls POST /me/messages, saves the message in database, and broadcasts it over WebSockets.
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        # Facebook Messenger Send API endpoint is /me/messages with page_access_token
        url = "https://graph.facebook.com/me/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE"
        }
        params = {"access_token": page.page_access_token}

        try:
            # Run requests.post in a background thread to prevent blocking the main event loop
            response = await asyncio.to_thread(
                requests.post, url, params=params, json=payload, timeout=10
            )
            response_json = response.json()
            print(f"[Send Message] API Response for page '{page.page_name}': {response_json}", flush=True)
        except requests.RequestException as e:
            raise FacebookAPIError(f"Network error sending message via Facebook: {str(e)}")

        self._handle_api_errors(response_json)

        fb_message_id = response_json.get("message_id")
        if not fb_message_id:
            raise FacebookAPIError(f"Facebook Send Message returned no message ID. Full response: {response_json}")

        # Save to DB (direction="outbound")
        # For outbound, sender_id is stored as the customer (recipient_id) so they stay grouped in the same thread
        saved_msg = self.message_repo.save_webhook_message(
            facebook_message_id=fb_message_id,
            page_id=page_id,
            sender_id=recipient_id,
            text=text,
            timestamp=int(datetime.utcnow().timestamp() * 1000),
            direction="outbound",
            reply_to_message_id=reply_to_message_id
        )

        # Broadcast via WebSockets to keep UI in sync
        ws_payload = {
            "type": "message",
            "page_id": page_id,
            "page_name": page.page_name,
            "facebook_user_id": page.facebook_user_id,
            "data": {
                "id": saved_msg.id,
                "facebook_message_id": saved_msg.facebook_message_id,
                "page_id": saved_msg.page_id,
                "sender_id": saved_msg.sender_id,
                "text": saved_msg.text,
                "timestamp": saved_msg.timestamp,
                "direction": saved_msg.direction,
                "reactions": saved_msg.reactions,
                "reply_to_message_id": saved_msg.reply_to_message_id,
                "created_at": saved_msg.created_at.isoformat()
            }
        }
        
        # Broadcast via WebSockets directly on the main event loop
        try:
            await manager.send_personal_message(ws_payload, page.facebook_user_id)
        except Exception as e:
            print(f"[WebSocket Broadcast] Error broadcasting outbound message: {str(e)}")

        return saved_msg


    async def send_page_attachment(
        self, page_id: str, recipient_id: str, attachment_type: str, file_path: str, filename: str, local_url: str
    ) -> Any:
        """
        Sends a binary file attachment (image or file) to a recipient on behalf of a page.
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        url = "https://graph.facebook.com/me/messages"
        params = {"access_token": page.page_access_token}

        # type can be 'image', 'video', 'audio', or 'file'
        if attachment_type == "image":
            fb_type = "image"
        elif attachment_type == "audio":
            fb_type = "audio"
        else:
            # check if it's a video by filename
            if any(filename.lower().endswith(ext) for ext in [".mp4", ".webm", ".ogg", ".mov"]):
                fb_type = "video"
            else:
                fb_type = "file"
        
        payload = {
            "recipient": f'{{"id": "{recipient_id}"}}',
            "message": f'{{"attachment": {{"type": "{fb_type}", "payload": {{"is_reusable": true}}}}}}'
        }
        
        # Open and send the binary file
        try:
            with open(file_path, "rb") as f:
                mime_type = "application/octet-stream"
                if fb_type == "image":
                    mime_type = "image/png"
                elif fb_type == "audio":
                    mime_type = "audio/webm"
                elif fb_type == "video":
                    mime_type = "video/mp4"
                
                files = {
                    "filedata": (filename, f, mime_type)
                }
                response = await asyncio.to_thread(
                    requests.post, url, params=params, data=payload, files=files, timeout=25
                )
                response_json = response.json()
                print(f"[Send Attachment] API Response for page '{page.page_name}': {response_json}", flush=True)
        except Exception as e:
            raise FacebookAPIError(f"Network error sending attachment via Facebook: {str(e)}")

        self._handle_api_errors(response_json)

        fb_message_id = response_json.get("message_id")
        if not fb_message_id:
            raise FacebookAPIError(f"Facebook Send Attachment returned no message ID. Response: {response_json}")

        # Save to DB (prefix with [image] or [file] to render correctly)
        db_text = f"[{attachment_type}] {local_url}"
        saved_msg = self.message_repo.save_webhook_message(
            facebook_message_id=fb_message_id,
            page_id=page_id,
            sender_id=recipient_id,
            text=db_text,
            timestamp=int(datetime.utcnow().timestamp() * 1000),
            direction="outbound"
        )

        # Broadcast via WebSockets
        ws_payload = {
            "type": "message",
            "page_id": page_id,
            "page_name": page.page_name,
            "facebook_user_id": page.facebook_user_id,
            "data": {
                "id": saved_msg.id,
                "facebook_message_id": saved_msg.facebook_message_id,
                "page_id": saved_msg.page_id,
                "sender_id": saved_msg.sender_id,
                "text": saved_msg.text,
                "timestamp": saved_msg.timestamp,
                "direction": saved_msg.direction,
                "reactions": saved_msg.reactions,
                "reply_to_message_id": saved_msg.reply_to_message_id,
                "created_at": saved_msg.created_at.isoformat()
            }
        }
        try:
            await manager.send_personal_message(ws_payload, page.facebook_user_id)
        except Exception as e:
            print(f"[WebSocket Broadcast] Error broadcasting outbound attachment: {str(e)}")

        return saved_msg


    async def send_page_attachment_url(
        self, page_id: str, recipient_id: str, attachment_type: str, attachment_url: str
    ) -> Any:
        """
        Sends an attachment (image/sticker/GIF/file) via a public URL using Facebook Send API.
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        url = "https://graph.facebook.com/me/messages"
        params = {"access_token": page.page_access_token}

        # Facebook expects attachment payload with a URL
        if attachment_type == "image":
            fb_type = "image"
        elif attachment_type == "audio":
            fb_type = "audio"
        else:
            # check if it's a video by URL extension
            if any(attachment_url.lower().endswith(ext) for ext in [".mp4", ".webm", ".ogg", ".mov"]):
                fb_type = "video"
            else:
                fb_type = "file"
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": fb_type,
                    "payload": {
                        "url": attachment_url,
                        "is_reusable": True
                    }
                }
            }
        }

        try:
            response = await asyncio.to_thread(
                requests.post, url, params=params, json=payload, timeout=15
            )
            response_json = response.json()
            print(f"[Send Attachment URL] API Response for page '{page.page_name}': {response_json}", flush=True)
        except Exception as e:
            raise FacebookAPIError(f"Network error sending attachment URL via Facebook: {str(e)}")

        self._handle_api_errors(response_json)

        fb_message_id = response_json.get("message_id")
        if not fb_message_id:
            raise FacebookAPIError(f"Facebook Send Attachment URL returned no message ID. Response: {response_json}")

        # Save to DB
        db_text = f"[{attachment_type}] {attachment_url}"
        saved_msg = self.message_repo.save_webhook_message(
            facebook_message_id=fb_message_id,
            page_id=page_id,
            sender_id=recipient_id,
            text=db_text,
            timestamp=int(datetime.utcnow().timestamp() * 1000),
            direction="outbound"
        )

        # Broadcast via WebSockets
        ws_payload = {
            "type": "message",
            "page_id": page_id,
            "page_name": page.page_name,
            "facebook_user_id": page.facebook_user_id,
            "data": {
                "id": saved_msg.id,
                "facebook_message_id": saved_msg.facebook_message_id,
                "page_id": saved_msg.page_id,
                "sender_id": saved_msg.sender_id,
                "text": saved_msg.text,
                "timestamp": saved_msg.timestamp,
                "direction": saved_msg.direction,
                "reactions": saved_msg.reactions,
                "reply_to_message_id": saved_msg.reply_to_message_id,
                "created_at": saved_msg.created_at.isoformat()
            }
        }
        try:
            await manager.send_personal_message(ws_payload, page.facebook_user_id)
        except Exception as e:
            print(f"[WebSocket Broadcast] Error broadcasting outbound attachment URL: {str(e)}")

        return saved_msg


    async def react_to_message(
        self, page_id: str, recipient_id: str, facebook_message_id: str, emoji: Optional[str]
    ) -> Any:
        """
        Sends a message reaction to Meta API (sender_action='react' or 'unreact') and stores in database.
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        url = "https://graph.facebook.com/me/messages"
        params = {"access_token": page.page_access_token}

        if emoji:
            payload = {
                "recipient": {"id": recipient_id},
                "sender_action": "react",
                "payload": {
                    "message_id": facebook_message_id,
                    "reaction": emoji
                }
            }
        else:
            payload = {
                "recipient": {"id": recipient_id},
                "sender_action": "unreact",
                "payload": {
                    "message_id": facebook_message_id
                }
            }

        try:
            response = await asyncio.to_thread(
                requests.post, url, params=params, json=payload, timeout=10
            )
            response_json = response.json()
            print(f"[React Message] API Response: {response_json}", flush=True)
        except Exception as e:
            # We don't raise error if it fails on Facebook side (e.g. invalid message id),
            # but log and proceed to save locally for test simulation
            print(f"[React Message] Facebook API reaction failed: {str(e)}", flush=True)
            response_json = {"success": True}

        # Update locally in DB
        saved_msg = self.message_repo.save_reaction(facebook_message_id, emoji)

        # Broadcast via WebSockets
        if saved_msg:
            ws_payload = {
                "type": "reaction",
                "page_id": page_id,
                "facebook_user_id": page.facebook_user_id,
                "data": {
                    "facebook_message_id": facebook_message_id,
                    "reactions": emoji
                }
            }
            try:
                await manager.send_personal_message(ws_payload, page.facebook_user_id)
            except Exception as e:
                print(f"[WebSocket Broadcast] Error broadcasting reaction: {str(e)}")

        return saved_msg

    async def delete_page_message(self, page_id: str, facebook_message_id: str) -> bool:
        """
        Deletes message from local DB and broadcasts unsend event to clients.
        """
        page = self.page_repo.get_by_page_id(page_id)
        facebook_user_id = page.facebook_user_id if page else ""
        
        success = self.message_repo.delete_message(facebook_message_id)
        if success and facebook_user_id:
            ws_payload = {
                "type": "delete_message",
                "page_id": page_id,
                "facebook_user_id": facebook_user_id,
                "data": {
                    "facebook_message_id": facebook_message_id
                }
            }
            try:
                await manager.send_personal_message(ws_payload, facebook_user_id)
            except Exception as e:
                print(f"[WebSocket Broadcast] Error broadcasting delete message: {str(e)}")
        return success

    async def reply_to_comment(self, comment_id: str, page_id: str, text: str) -> Dict[str, Any]:
        """
        Sends a reply to a Page post comment using Page Access Token.
        POST /{comment_id}/comments
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{comment_id}/comments"
        payload = {"message": text}
        params = {"access_token": page.page_access_token}

        try:
            response = await asyncio.to_thread(
                requests.post, url, params=params, json=payload, timeout=15
            )
            response_json = response.json()
            print(f"[Reply Comment] API Response: {response_json}", flush=True)
        except Exception as e:
            raise FacebookAPIError(f"Network error replying to comment via Facebook: {str(e)}")

        self._handle_api_errors(response_json)
        return response_json

    async def react_to_comment(self, comment_id: str, page_id: str, reaction: str) -> Dict[str, Any]:
        """
        Sends an emoji reaction (LIKE, LOVE, HAHA, WOW, SAD, ANGRY) to a Page post comment.
        Tries POST /{comment_id}/reactions first, and falls back to POST /{comment_id}/likes if capability is missing.
        """
        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            raise ValueError(f"Page or page access token not found for Page ID {page_id}")

        params = {"access_token": page.page_access_token}

        url_reactions = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{comment_id}/reactions"
        react_params = {
            "type": reaction.upper(),
            "reaction_type": reaction.upper(),
            "access_token": page.page_access_token
        }

        try:
            response = await asyncio.to_thread(
                requests.post, url_reactions, params=react_params, timeout=10
            )
            response_json = response.json()
            print(f"[React Comment] API Response: {response_json}", flush=True)

            # Check if Error #3 (Application capability missing for /reactions endpoint)
            if "error" in response_json and response_json["error"].get("code") == 3:
                print(f"[React Comment] Reactions endpoint returned code 3, falling back to /{comment_id}/likes...", flush=True)
                url_likes = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{comment_id}/likes"
                response = await asyncio.to_thread(
                    requests.post, url_likes, params=params, timeout=10
                )
                response_json = response.json()
                print(f"[Like Comment Fallback] API Response: {response_json}", flush=True)

        except Exception as e:
            raise FacebookAPIError(f"Network error reacting to comment via Facebook: {str(e)}")

        self._handle_api_errors(response_json)
        return response_json

    async def get_customer_profile(self, psid: str, page_id: str) -> Dict[str, str]:
        """
        Retrieves public customer profile (name, picture/avatar) by PSID using Page Access Token.
        GET /{psid}?fields=name,first_name,last_name,picture
        """
        global CUSTOMER_PROFILE_CACHE
        if psid in CUSTOMER_PROFILE_CACHE:
            return CUSTOMER_PROFILE_CACHE[psid]

        page = self.page_repo.get_by_page_id(page_id)
        if not page or not page.page_access_token:
            return {"name": f"Khách hàng {psid[:8]}", "avatar_url": ""}

        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{psid}"
        params = {
            "fields": "name,first_name,last_name,picture",
            "access_token": page.page_access_token
        }

        try:
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=8
            )
            data = response.json()
            print(f"[Customer Profile] API Response for PSID {psid}: {data}", flush=True)

            # If error returned (e.g. field mismatch), fallback to fields=name
            if "error" in data:
                print(f"[Customer Profile Warning] Retry fields=name for PSID {psid}: {data['error'].get('message')}", flush=True)
                retry_params = {
                    "fields": "name",
                    "access_token": page.page_access_token
                }
                retry_resp = await asyncio.to_thread(
                    requests.get, url, params=retry_params, timeout=8
                )
                data = retry_resp.json()
                print(f"[Customer Profile Retry] API Response for PSID {psid}: {data}", flush=True)

            avatar_url = ""
            if "picture" in data and isinstance(data["picture"], dict):
                avatar_url = data["picture"].get("data", {}).get("url", "")
            elif "profile_pic" in data:
                avatar_url = data.get("profile_pic", "")

            if "name" in data:
                profile_info = {
                    "name": data.get("name"),
                    "avatar_url": avatar_url
                }
                CUSTOMER_PROFILE_CACHE[psid] = profile_info
                return profile_info
        except Exception as e:
            print(f"[Customer Profile Error] {str(e)}")

        default_info = {"name": f"Khách hàng {psid[:8]}", "avatar_url": ""}
        return default_info



CUSTOMER_PROFILE_CACHE: Dict[str, Dict[str, str]] = {}




