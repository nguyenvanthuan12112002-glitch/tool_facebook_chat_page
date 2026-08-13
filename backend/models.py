from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class Account(Base):
    __tablename__ = "v_accounts"

    id = Column(Integer, primary_key=True, index=True)
    # Facebook User ID is a string since FB IDs exceed integer ranges
    facebook_user_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    user_access_token = Column(Text, nullable=False)
    user_access_token_long_lived = Column(Text, nullable=True) # Long-lived token (60 days)

    # Relationship to Pages owned by this account
    pages = relationship("Page", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account {self.name} (ID: {self.facebook_user_id})>"


class Page(Base):
    __tablename__ = "v_pages"

    id = Column(Integer, primary_key=True, index=True)
    # Page ID returned by Facebook Graph API
    page_id = Column(String(100), unique=True, index=True, nullable=False)
    page_name = Column(String(255), nullable=False)
    page_access_token = Column(Text, nullable=False)
    
    # Foreign key linking the page to the account that owns it
    facebook_user_id = Column(String(100), ForeignKey("v_accounts.facebook_user_id", ondelete="CASCADE"), nullable=False)
    
    avatar_url = Column(Text, nullable=True)
    # Status of the Page (e.g. 'active', 'inactive', 'disconnected')
    status = Column(String(50), default="active", nullable=False)

    # Back-relationship to Account
    account = relationship("Account", back_populates="pages")

    def __repr__(self):
        return f"<Page {self.page_name} (ID: {self.page_id})>"


class Message(Base):
    __tablename__ = "v_messages"

    id = Column(Integer, primary_key=True, index=True)
    facebook_message_id = Column(String(100), unique=True, index=True, nullable=False)
    page_id = Column(String(100), index=True, nullable=False)
    sender_id = Column(String(100), index=True, nullable=False)
    text = Column(Text, nullable=True)
    timestamp = Column(Integer, nullable=True) # milliseconds epoch
    direction = Column(String(50), default="inbound", nullable=False) # 'inbound' (customer -> page) or 'outbound' (page -> customer)
    reactions = Column(String(50), nullable=True)
    reply_to_message_id = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_replied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Message {self.text[:20] if self.text else ''} ({self.direction} - From: {self.sender_id} -> Page: {self.page_id})>"


class Notification(Base):
    __tablename__ = "v_notifications"

    id = Column(Integer, primary_key=True, index=True)
    facebook_notification_id = Column(String(100), unique=True, index=True, nullable=False)
    page_id = Column(String(100), index=True, nullable=False)
    title = Column(Text, nullable=False)
    link = Column(Text, nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow)
    unread = Column(Boolean, default=True, nullable=False)
    is_replied = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Notification {self.title[:30]}... (Page: {self.page_id})>"

class PushSubscription(Base):
    __tablename__ = "v_push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    facebook_user_id = Column(String(100), ForeignKey("v_accounts.facebook_user_id", ondelete="CASCADE"), nullable=False)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PushSubscription (User: {self.facebook_user_id})>"
