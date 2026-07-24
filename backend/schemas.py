from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

# Base schemas
class PageBase(BaseModel):
    page_id: str
    page_name: str
    avatar_url: Optional[str] = None
    status: str = "active"

class PageCreate(PageBase):
    page_access_token: str
    facebook_user_id: str

class PageUpdate(BaseModel):
    page_name: str
    page_access_token: str
    facebook_user_id: str
    avatar_url: Optional[str] = None
    status: Optional[str] = None

# API Response schema for pages
class PageOut(PageBase):
    id: int
    facebook_user_id: str

    class Config:
        from_attributes = True

# API Response schema for Sync process
class SyncResponse(BaseModel):
    success: bool
    message: str
    synced_count: int
    pages: List[PageOut]

# Schema for direct token-based sync
class TokenInput(BaseModel):
    access_token: str

class SyncByTokenResponse(BaseModel):
    success: bool
    message: str
    facebook_user_id: str
    synced_count: int
    pages: List[PageOut]

# Schema for Messages
class MessageOut(BaseModel):
    id: int
    facebook_message_id: str = ""
    page_id: str
    sender_id: str
    text: Optional[str] = None
    timestamp: Optional[int] = None
    direction: str = "inbound" # 'inbound' or 'outbound'
    reactions: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    is_read: bool = False
    is_replied: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

# Schema for Notifications
class NotificationOut(BaseModel):
    id: int
    facebook_notification_id: str
    page_id: str
    title: str
    link: Optional[str] = None
    created_time: datetime
    unread: bool
    is_replied: bool = False

    class Config:
        from_attributes = True

# Schema for replying/sending message
class SendReplyInput(BaseModel):
    page_id: str
    recipient_id: str
    text: str
    reply_to_message_id: Optional[str] = None

# Schema for Accounts (for setup/viewing)
class AccountBase(BaseModel):
    facebook_user_id: str
    name: str

class AccountCreate(AccountBase):
    user_access_token: str

class AccountOut(AccountBase):
    id: int

    class Config:
        from_attributes = True


class ReactInput(BaseModel):
    page_id: str
    recipient_id: str
    reaction: Optional[str] = None


class CommentReplyInput(BaseModel):
    page_id: str
    text: str


class CommentReactInput(BaseModel):
    page_id: str
    reaction: str  # LIKE, LOVE, HAHA, WOW, SAD, ANGRY

