import threading
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, WebSocket, WebSocketDisconnect, UploadFile, File, Form
import os
import shutil
import time
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.config import settings
from backend.schemas import (
    SyncResponse,
    PageOut,
    AccountCreate,
    AccountOut,
    TokenInput,
    SyncByTokenResponse,
    MessageOut,
    NotificationOut,
    SendReplyInput,
    ReactInput,
    CommentReplyInput,
    CommentReactInput,
    PushSubscriptionInput
)
from backend.repositories import AccountRepository, PageRepository, MessageRepository, NotificationRepository
from backend.services import (
    FacebookSyncService,
    AccountNotFoundError,
    FacebookAuthError,
    FacebookAPIError
)
from backend.websocket import manager
from backend.queue_worker import event_queue
from backend.models import Page, Message, Notification, PushSubscription

router = APIRouter(prefix="/api/facebook", tags=["Facebook Webhook & Sync"])

@router.websocket("/ws/{facebook_user_id}")
async def websocket_endpoint(websocket: WebSocket, facebook_user_id: str):
    """
    WebSocket endpoint for real-time frontend notifications and chat messages.
    Handshakes connection and registers clients by their Facebook User ID.
    Supports ping/pong keepalive to prevent idle connection timeouts.
    """
    await manager.connect(facebook_user_id, websocket)
    try:
        while True:
            # Receive messages from frontend (ping keepalive or control frames)
            data = await websocket.receive_text()
            try:
                import json
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass  # ignore non-JSON or unrecognized messages
    except WebSocketDisconnect:
        manager.disconnect(facebook_user_id, websocket)
    except Exception as e:
        print(f"[WebSocket Endpoint Exception] {str(e)}")
        manager.disconnect(facebook_user_id, websocket)


@router.get("/webhook")
def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """Facebook Webhook verification handshake."""
    if mode == "subscribe" and token == settings.FACEBOOK_WEBHOOK_VERIFY_TOKEN:
        print(f"[Webhook] Verification successful. Challenge: {challenge}")
        return Response(content=challenge, media_type="text/plain")
    
    print("[Webhook] Verification failed. Token mismatch.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid mode"
    )


@router.post("/webhook")
async def receive_webhook_event(
    payload: dict
):
    """
    Facebook Webhook event receiver.
    Puts the payload immediately into the async Event Queue and returns HTTP 200 OK instantly.
    """
    if payload.get("object") == "page":
        # Put event into Queue asynchronously (non-blocking)
        await event_queue.put(payload)
        return Response(content="EVENT_RECEIVED", status_code=200)

    raise HTTPException(status_code=404, detail="Unknown event subscription object")


@router.post("/push/subscribe")
def subscribe_push(payload: PushSubscriptionInput, db: Session = Depends(get_db)):
    """API to receive Push Subscription from Frontend"""
    existing_sub = db.query(PushSubscription).filter(
        PushSubscription.facebook_user_id == payload.facebook_user_id,
        PushSubscription.endpoint == payload.endpoint
    ).first()
    if not existing_sub:
        new_sub = PushSubscription(
            facebook_user_id=payload.facebook_user_id,
            endpoint=payload.endpoint,
            p256dh=payload.p256dh,
            auth=payload.auth
        )
        db.add(new_sub)
        db.commit()
    return {"success": True, "message": "Subscription stored"}



@router.post("/send-reply")
async def send_reply(
    payload: SendReplyInput,
    db: Session = Depends(get_db)
):
    """Sends an outbound reply message to a customer on behalf of a page."""
    sync_service = FacebookSyncService(db)
    try:
        msg = await sync_service.send_page_message(
            page_id=payload.page_id,
            recipient_id=payload.recipient_id,
            text=payload.text,
            reply_to_message_id=payload.reply_to_message_id
        )
        return {
            "success": True,
            "message": "Tin nhắn đã được gửi thành công.",
            "data": {
                "id": msg.id,
                "facebook_message_id": msg.facebook_message_id,
                "page_id": msg.page_id,
                "sender_id": msg.sender_id,
                "text": msg.text,
                "timestamp": msg.timestamp,
                "direction": msg.direction,
                "reactions": msg.reactions,
                "reply_to_message_id": msg.reply_to_message_id,
                "created_at": msg.created_at.isoformat()
            }
        }
    except FacebookAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản bị mất kết nối, vui lòng xác thực lại. " + str(e)
        )
    except FacebookAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi gửi tin: {str(e)}"
        )


@router.post("/messages/{facebook_message_id}/react")
async def react_message(
    facebook_message_id: str,
    payload: ReactInput,
    db: Session = Depends(get_db)
):
    """Sends reaction emoji to the message via Facebook Send API and saves to database."""
    sync_service = FacebookSyncService(db)
    try:
        msg = await sync_service.react_to_message(
            page_id=payload.page_id,
            recipient_id=payload.recipient_id,
            facebook_message_id=facebook_message_id,
            emoji=payload.reaction
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn.")
        return {"success": True, "reactions": msg.reactions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages/{facebook_message_id}")
async def unsend_message(
    facebook_message_id: str,
    page_id: str = Query(..., description="The ID of the Facebook page"),
    db: Session = Depends(get_db)
):
    """Deletes message from local database and triggers WebSocket broadcast to unsend in UI."""
    sync_service = FacebookSyncService(db)
    try:
        success = await sync_service.delete_page_message(
            page_id=page_id,
            facebook_message_id=facebook_message_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn.")
        return {"success": True, "message": "Tin nhắn đã được gỡ bỏ."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/conversations")
def get_conversations(
    facebook_user_id: str = Query(..., description="The FB User ID to load chat threads for"),
    db: Session = Depends(get_db)
):
    """
    Retrieves all conversation thread groups (Page + Customer) for the user,
    summarizing the last chat text and timestamp, sorted by active date.
    """
    message_repo = MessageRepository(db)
    # Fetch latest 250 chats for this account
    messages = message_repo.get_messages_by_facebook_user_id(facebook_user_id, limit=250)
    
    threads = {}
    for msg in messages:
        key = (msg.page_id, msg.sender_id)
        if key not in threads:
            page = db.query(Page).filter(Page.page_id == msg.page_id).first()
            page_name = page.page_name if page else f"Page {msg.page_id}"
            avatar_url = page.avatar_url if page else None
            threads[key] = {
                "page_id": msg.page_id,
                "page_name": page_name,
                "avatar_url": avatar_url,
                "sender_id": msg.sender_id,
                "last_message": msg.text,
                "timestamp": msg.timestamp,
                "direction": msg.direction,
                "created_at": datetime.fromtimestamp(msg.timestamp / 1000).isoformat(),
                "is_read": True,
                "is_replied": True
            }
            
        if msg.direction == "inbound":
            if getattr(msg, "is_read", False) == False:
                threads[key]["is_read"] = False
            if getattr(msg, "is_replied", False) == False:
                threads[key]["is_replied"] = False
            
    # Sort threads list by timestamp descending
    thread_list = list(threads.values())
    thread_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return thread_list


@router.put("/conversations/{page_id}/{sender_id}/read")
def mark_conversation_read(page_id: str, sender_id: str, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.page_id == page_id, 
        Message.sender_id == sender_id,
        Message.direction == "inbound"
    ).update({"is_read": True})
    db.commit()
    return {"success": True}


@router.put("/conversations/{page_id}/{sender_id}/replied")
def mark_conversation_replied(page_id: str, sender_id: str, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.page_id == page_id, 
        Message.sender_id == sender_id,
        Message.direction == "inbound"
    ).update({"is_replied": True})
    db.commit()
    return {"success": True}


@router.put("/notifications/{facebook_notification_id}/read")
def mark_notification_read(facebook_notification_id: str, db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.facebook_notification_id == facebook_notification_id
    ).update({"unread": False})
    db.commit()
    return {"success": True}


@router.put("/notifications/{facebook_notification_id}/replied")
def mark_notification_replied(facebook_notification_id: str, db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.facebook_notification_id == facebook_notification_id
    ).update({"is_replied": True})
    db.commit()
    return {"success": True}


@router.get("/messages", response_model=List[MessageOut])
def get_messages(
    facebook_user_id: str = Query(..., description="Filter messages by facebook user id"),
    page_id: str = Query(None, description="Optional page filter"),
    sender_id: str = Query(None, description="Optional customer sender id filter"),
    limit: int = Query(50, description="Limit messages"),
    db: Session = Depends(get_db)
):
    """
    Fetches message history logs. If page_id and sender_id are specified,
    returns the exact conversation history thread between that Page and Customer.
    """
    message_repo = MessageRepository(db)
    if page_id and sender_id:
        return db.query(Message)\
            .filter(Message.page_id == page_id, Message.sender_id == sender_id)\
            .order_by(Message.created_at.asc())\
            .limit(limit)\
            .all()
            
    return message_repo.get_messages_by_facebook_user_id(facebook_user_id, limit=limit)


@router.get("/notifications", response_model=List[NotificationOut])
def get_notifications(
    facebook_user_id: str = Query(..., description="The FB User ID to load notifications for"),
    limit: int = Query(30, description="Max notifications to retrieve"),
    db: Session = Depends(get_db)
):
    """Retrieve recent notifications received via Webhook (comments, likes) from database."""
    notif_repo = NotificationRepository(db)
    return notif_repo.get_notifications_by_facebook_user_id(facebook_user_id, limit=limit)


@router.post("/sync-by-token", response_model=SyncByTokenResponse)
def sync_by_token(
    payload: TokenInput,
    db: Session = Depends(get_db)
):
    """Directly sync Facebook Pages using a raw Facebook Access Token."""
    sync_service = FacebookSyncService(db)
    try:
        user_id, count, pages = sync_service.sync_by_token(payload.access_token)
        # Trigger background historical sync for all newly synced pages
        for p in pages:
            threading.Thread(target=sync_service.sync_historical_data, args=(p.page_id, user_id), daemon=True).start()
            
        return SyncByTokenResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            facebook_user_id=user_id,
            synced_count=count,
            pages=pages
        )
    except FacebookAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản bị mất kết nối, vui lòng xác thực lại. " + str(e)
        )
    except FacebookAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}"
        )


@router.get("/sync-pages", response_model=SyncResponse)
def sync_pages(
    facebook_user_id: str = Query(..., description="The ID of the Facebook User account to sync"),
    db: Session = Depends(get_db)
):
    """Trigger a manual sync of pages managed by the given Facebook User ID."""
    sync_service = FacebookSyncService(db)
    try:
        count, pages = sync_service.sync_pages(facebook_user_id)
        # Trigger background historical sync for all newly synced pages
        for p in pages:
            threading.Thread(target=sync_service.sync_historical_data, args=(p.page_id, facebook_user_id), daemon=True).start()
            
        return SyncResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            synced_count=count,
            pages=pages
        )
    except AccountNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except FacebookAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản bị mất kết nối, vui lòng xác thực lại. " + str(e)
        )
    except FacebookAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}"
        )


@router.get("/pages", response_model=List[PageOut])
def get_pages(
    facebook_user_id: str = Query(..., description="Filter pages by facebook user id"),
    db: Session = Depends(get_db)
):
    """Retrieve existing Facebook Pages from database without triggering a live external sync API call."""
    page_repo = PageRepository(db)
    return page_repo.get_pages_by_facebook_user_id(facebook_user_id)


# Helper endpoint for seeding accounts in testing
@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_or_update_account(
    account_in: AccountCreate,
    db: Session = Depends(get_db)
):
    """Create or update a Facebook Account token. Used for seeding mock records in development/test."""
    account_repo = AccountRepository(db)
    return account_repo.create_or_update_account(account_in)


@router.post("/send-attachment")
async def send_attachment(
    page_id: str = Form(...),
    recipient_id: str = Form(...),
    attachment_type: str = Form(...), # "image" or "file"
    file: UploadFile = File(...),
    is_comment: bool = Form(False),
    reply_to_message_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Uploads a local file, saves it, and sends it as an attachment to the customer or comment."""
    # 1. Save file locally to serve in chat history
    filename = f"{int(time.time())}_{file.filename}"
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
    file_path = os.path.join(uploads_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    local_url = f"/uploads/{filename}"
    
    # 2. Call service to send it via Facebook API
    sync_service = FacebookSyncService(db)
    try:
        if is_comment:
            res = await sync_service.reply_to_comment_with_attachment(
                comment_id=recipient_id,
                page_id=page_id,
                attachment_type=attachment_type,
                file_path=file_path,
                local_url=local_url
            )
            return {
                "success": True, 
                "data": res
            }
        else:
            msg = await sync_service.send_page_attachment(
                page_id=page_id,
                recipient_id=recipient_id,
                attachment_type=attachment_type,
                file_path=file_path,
                filename=file.filename,
                local_url=local_url,
                reply_to_message_id=reply_to_message_id
            )
            return {
                "success": True, 
                "data": {
                    "id": msg.id,
                    "facebook_message_id": msg.facebook_message_id,
                    "page_id": msg.page_id,
                    "sender_id": msg.sender_id,
                    "text": msg.text,
                    "timestamp": msg.timestamp,
                    "direction": msg.direction,
                    "reactions": msg.reactions,
                    "reply_to_message_id": msg.reply_to_message_id,
                    "created_at": msg.created_at.isoformat()
                }
            }
    except Exception as e:
        # cleanup local file if failed
        try:
            os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-attachment-url")
async def send_attachment_url(
    page_id: str = Form(...),
    recipient_id: str = Form(...),
    attachment_type: str = Form(...), # "image" or "file"
    url: str = Form(...),
    reply_to_message_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Sends an attachment to the customer using a public URL (Stickers, GIFs)."""
    sync_service = FacebookSyncService(db)
    try:
        msg = await sync_service.send_page_attachment_url(
            page_id=page_id,
            recipient_id=recipient_id,
            attachment_type=attachment_type,
            attachment_url=url,
            reply_to_message_id=reply_to_message_id
        )
        return {
            "success": True,
            "data": {
                "id": msg.id,
                "facebook_message_id": msg.facebook_message_id,
                "page_id": msg.page_id,
                "sender_id": msg.sender_id,
                "text": msg.text,
                "timestamp": msg.timestamp,
                "direction": msg.direction,
                "created_at": msg.created_at.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
def reset_db(db: Session = Depends(get_db)):
    """Delete all accounts and pages to reset the database to a clean slate."""
    from backend.models import Account, Page, Message, Notification
    try:
        db.query(Page).delete()
        db.query(Account).delete()
        db.query(Message).delete()
        db.query(Notification).delete()
        db.commit()
        return {"success": True, "message": "Đã xóa toàn bộ tài khoản, tin nhắn và trang thành công."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comments/{comment_id}/reply")
async def reply_comment(
    comment_id: str,
    payload: CommentReplyInput,
    db: Session = Depends(get_db)
):
    """Public reply to a Page comment."""
    sync_service = FacebookSyncService(db)
    try:
        res = await sync_service.reply_to_comment(
            comment_id=comment_id,
            page_id=payload.page_id,
            text=payload.text
        )
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comments/{comment_id}/react")
async def react_comment(
    comment_id: str,
    payload: CommentReactInput,
    db: Session = Depends(get_db)
):
    """Public emoji reaction to a Page comment."""
    sync_service = FacebookSyncService(db)
    try:
        res = await sync_service.react_to_comment(
            comment_id=comment_id,
            page_id=payload.page_id,
            reaction=payload.reaction
        )
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer_profile/{psid}")
async def get_customer_profile(
    psid: str,
    page_id: str = Query(..., description="The Page ID to use for token authentication"),
    db: Session = Depends(get_db)
):
    """Retrieve public customer profile (name, avatar) from Facebook Graph API."""
    sync_service = FacebookSyncService(db)
    return await sync_service.get_customer_profile(psid=psid, page_id=page_id)


