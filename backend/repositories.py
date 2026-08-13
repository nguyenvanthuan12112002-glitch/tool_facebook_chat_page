from sqlalchemy.orm import Session
from typing import List, Optional
from backend.models import Account, Page, Message, Notification
from backend.schemas import PageCreate, AccountCreate

class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_facebook_user_id(self, facebook_user_id: str) -> Optional[Account]:
        """Query Facebook User Account from database using the facebook_user_id."""
        return self.db.query(Account).filter(Account.facebook_user_id == facebook_user_id).first()

    def create_or_update_account(self, account_in: AccountCreate) -> Account:
        """Create or update a Facebook User Account. Useful for setup and verification."""
        account = self.get_by_facebook_user_id(account_in.facebook_user_id)
        if account:
            account.name = account_in.name
            account.user_access_token = account_in.user_access_token
        else:
            account = Account(
                facebook_user_id=account_in.facebook_user_id,
                name=account_in.name,
                user_access_token=account_in.user_access_token
            )
            self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update_long_lived_token(self, facebook_user_id: str, long_lived_token: str) -> Optional[Account]:
        """Updates the account's long-lived access token."""
        account = self.get_by_facebook_user_id(facebook_user_id)
        if account:
            account.user_access_token_long_lived = long_lived_token
            self.db.commit()
            self.db.refresh(account)
        return account


class PageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_page_id(self, page_id: str) -> Optional[Page]:
        """Fetch page metadata using Facebook's page_id."""
        return self.db.query(Page).filter(Page.page_id == page_id).first()

    def get_pages_by_facebook_user_id(self, facebook_user_id: str) -> List[Page]:
        """Fetch all pages associated with a specific Facebook User ID."""
        return self.db.query(Page).filter(Page.facebook_user_id == facebook_user_id).all()

    def upsert_page(self, page_in: PageCreate) -> Page:
        """
        Implements an UPSERT mechanism based on page_id.
        Updates details if page exists, otherwise registers a new entry.
        """
        page = self.get_by_page_id(page_in.page_id)
        if page:
            page.page_name = page_in.page_name
            page.page_access_token = page_in.page_access_token
            page.facebook_user_id = page_in.facebook_user_id
            page.avatar_url = page_in.avatar_url
            page.status = page_in.status
        else:
            page = Page(
                page_id=page_in.page_id,
                page_name=page_in.page_name,
                page_access_token=page_in.page_access_token,
                facebook_user_id=page_in.facebook_user_id,
                avatar_url=page_in.avatar_url,
                status=page_in.status
            )
            self.db.add(page)
        
        self.db.commit()
        self.db.refresh(page)
        return page


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_fb_message_id(self, facebook_message_id: str) -> Optional[Message]:
        """Fetch message by its unique Facebook Message ID."""
        return self.db.query(Message).filter(Message.facebook_message_id == facebook_message_id).first()

    def save_webhook_message(
        self, facebook_message_id: str, page_id: str, sender_id: str, text: str, timestamp: int, direction: str = "inbound", reply_to_message_id: Optional[str] = None
    ) -> Message:
        """Saves a message received via the Facebook webhook. Prevents duplicates using facebook_message_id."""
        message = self.get_by_fb_message_id(facebook_message_id)
        if not message:
            message = Message(
                facebook_message_id=facebook_message_id,
                page_id=page_id,
                sender_id=sender_id,
                text=text,
                timestamp=timestamp,
                direction=direction,
                reply_to_message_id=reply_to_message_id
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
        return message

    def save_reaction(self, facebook_message_id: str, emoji: Optional[str]) -> Optional[Message]:
        """Save or clear reaction on a message."""
        message = self.get_by_fb_message_id(facebook_message_id)
        if message:
            message.reactions = emoji
            self.db.commit()
            self.db.refresh(message)
        return message

    def delete_message(self, facebook_message_id: str) -> bool:
        """Deletes a message from local database (unsend)."""
        message = self.get_by_fb_message_id(facebook_message_id)
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False

    def get_messages_by_page_id(self, page_id: str, limit: int = 50) -> List[Message]:
        """Fetch recent messages received by a specific page ID."""
        return self.db.query(Message).filter(Message.page_id == page_id).order_by(Message.created_at.desc()).limit(limit).all()

    def get_messages_by_facebook_user_id(self, facebook_user_id: str, limit: int = 50) -> List[Message]:
        """
        Fetch recent messages received by all pages owned by a specific Facebook User ID.
        Uses a SQL JOIN across v_messages and v_pages.
        """
        return self.db.query(Message)\
            .join(Page, Page.page_id == Message.page_id)\
            .filter(Page.facebook_user_id == facebook_user_id)\
            .order_by(Message.created_at.desc())\
            .limit(limit)\
            .all()


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_fb_notification_id(self, facebook_notification_id: str) -> Optional[Notification]:
        """Fetch notification by its unique Facebook Notification ID."""
        return self.db.query(Notification).filter(Notification.facebook_notification_id == facebook_notification_id).first()

    def get_notifications_by_facebook_user_id(self, facebook_user_id: str, limit: int = 50) -> List[Notification]:
        """
        Fetch recent notifications received by all pages owned by a specific Facebook User ID.
        Uses a SQL JOIN across v_notifications and v_pages.
        """
        return self.db.query(Notification)\
            .join(Page, Page.page_id == Notification.page_id)\
            .filter(Page.facebook_user_id == facebook_user_id)\
            .order_by(Notification.created_time.desc())\
            .limit(limit)\
            .all()

    def save_historical_notification(self, facebook_notification_id: str, page_id: str, title: str, link: str, created_time) -> Notification:
        notif = self.get_by_fb_notification_id(facebook_notification_id)
        if not notif:
            notif = Notification(
                facebook_notification_id=facebook_notification_id,
                page_id=page_id,
                title=title,
                link=link,
                created_time=created_time,
                unread=False,  # Historical notifications are considered read
                is_replied=False
            )
            self.db.add(notif)
            self.db.commit()
            self.db.refresh(notif)
        return notif
