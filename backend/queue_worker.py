import os
import asyncio
from datetime import datetime
from typing import Dict, Any
from backend.database import SessionLocal
from backend.repositories import MessageRepository
from backend.websocket import manager
from backend.models import Page, Notification

# Safe import for native Windows notifications
try:
    from plyer import notification as win_notifier
except ImportError:
    win_notifier = None

# Safe import for Web Push (Service Worker)
try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None

import json

async def trigger_web_push(db, facebook_user_id: str, title: str, body: str):
    if not webpush:
        return
    
    from backend.models import PushSubscription
    subs = db.query(PushSubscription).filter(PushSubscription.facebook_user_id == facebook_user_id).all()
    if not subs:
        return
        
    payload = json.dumps({"title": title, "body": body})
    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "RsKKNPMXmx54MxdpTTTLWRV8rsLLidhcwfKE93MFKFQ")
    if not vapid_private_key:
        return
        
    for sub in subs:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
        except Exception as e:
            print(f"[WebPush Error] {e}")


# In-memory Async Event Queue
event_queue = asyncio.Queue()

async def process_webhook_event(event: Dict[str, Any]):
    """Processes a single queued webhook payload from Facebook."""
    db = SessionLocal()
    try:
        obj_type = event.get("object")
        if obj_type != "page":
            return

        entries = event.get("entry", [])
        for entry in entries:
            page_id = entry.get("id")
            
            # 1. Parse real-time messages
            messagings = entry.get("messaging", [])
            for messaging in messagings:
                sender_obj = messaging.get("sender", {})
                sender_id = sender_obj.get("id")
                msg_sender_name = sender_obj.get("name") or (f"Khách hàng {sender_id[:8]}" if sender_id else "Khách hàng")
                recipient_id = messaging.get("recipient", {}).get("id")
                timestamp = messaging.get("timestamp")
                
                message_obj = messaging.get("message", {})
                message_id = message_obj.get("mid")
                text = message_obj.get("text")
                
                # Support incoming attachments (images/files) from customer
                attachments = message_obj.get("attachments", [])
                if not text and attachments:
                    att = attachments[0]
                    att_type = att.get("type")
                    att_url = att.get("payload", {}).get("url")
                    if att_url:
                        import uuid
                        import requests
                        
                        file_ext = ".bin"
                        if att_type == "image": file_ext = ".jpg"
                        elif att_type == "audio": file_ext = ".mp4"
                        elif att_type == "video": file_ext = ".mp4"
                        
                        local_filename = f"fb_incoming_{uuid.uuid4().hex}{file_ext}"
                        uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
                        os.makedirs(uploads_dir, exist_ok=True)
                        local_filepath = os.path.join(uploads_dir, local_filename)
                        
                        try:
                            resp = await asyncio.to_thread(requests.get, att_url, timeout=15)
                            if resp.status_code == 200:
                                with open(local_filepath, "wb") as f:
                                    f.write(resp.content)
                                att_url = f"/uploads/{local_filename}"
                        except Exception as e:
                            print(f"Error downloading incoming attachment: {e}")

                    if att_type == "image":
                        text = f"[image] {att_url}"
                    elif att_type == "audio":
                        text = f"[audio] {att_url}"
                    elif att_type in ("video", "file"):
                        text = f"[file] {att_url}"
                
                if message_id and sender_id and recipient_id and text:
                    direction = "outbound" if sender_id == page_id else "inbound"
                    active_customer_id = sender_id if direction == "inbound" else recipient_id
                    
                    message_repo = MessageRepository(db)
                    saved_msg = message_repo.save_webhook_message(
                        facebook_message_id=message_id,
                        page_id=page_id,
                        sender_id=active_customer_id,
                        text=text,
                        timestamp=timestamp,
                        direction=direction
                    )
                    
                    # Resolve Page mapping
                    page_record = db.query(Page).filter(Page.page_id == page_id).first()
                    if page_record:
                        # Resolve real customer profile from Graph API
                        from backend.services import FacebookSyncService
                        sync_service = FacebookSyncService(db)
                        profile_info = await sync_service.get_customer_profile(active_customer_id, page_id)
                        real_customer_name = profile_info.get("name") or msg_sender_name

                        # Broadcast message packet to WebSocket clients
                        ws_payload = {
                            "type": "message",
                            "page_id": page_id,
                            "page_name": page_record.page_name,
                            "facebook_user_id": page_record.facebook_user_id,
                            "data": {
                                "id": saved_msg.id,
                                "facebook_message_id": saved_msg.facebook_message_id,
                                "page_id": saved_msg.page_id,
                                "sender_id": saved_msg.sender_id,
                                "text": saved_msg.text,
                                "timestamp": saved_msg.timestamp,
                                "direction": saved_msg.direction,
                                "created_at": saved_msg.created_at.isoformat(),
                                "sender_name": real_customer_name,
                                "avatar_url": profile_info.get("avatar_url", "")
                            }
                        }
                        await manager.send_personal_message(ws_payload, page_record.facebook_user_id)
                        
                        # Trigger native Windows notifications for inbound client messages
                        if direction == "inbound" and win_notifier:
                            try:
                                icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../app_logo.ico"))
                                icon_to_use = icon_path if os.path.exists(icon_path) else None
                                msg_preview = text[:50] if text else "[Hình ảnh/Tệp đính kèm]"
                                await asyncio.to_thread(
                                    win_notifier.notify,
                                    title=f"💬 Tin nhắn từ {real_customer_name} ({page_record.page_name})",
                                    message=f"{real_customer_name}: {msg_preview}",
                                    app_name="Hội thoại Đa kênh (Omnichannel)",
                                    app_icon=icon_to_use,
                                    timeout=6
                                )
                            except Exception as ne:
                                print(f"[Notifier Error] {str(ne)}")

                        # Trigger Service Worker push notification
                        if direction == "inbound":
                            msg_preview = text[:50] if text else "[Hình ảnh/Tệp đính kèm]"
                            await trigger_web_push(db, page_record.facebook_user_id, f"💬 Tin nhắn từ {real_customer_name}", f"{page_record.page_name}: {msg_preview}")
            
            # 2. Parse feed changes (Likes/Comments -> Notifications)
            changes = entry.get("changes", [])
            for change in changes:
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    item = value.get("item") # comment, like, post
                    verb = value.get("verb") # add, edit, remove
                    from_obj = value.get("from", {})
                    sender_id = from_obj.get("id") or value.get("sender_id") or "anonymous"
                    sender_name = from_obj.get("name") or value.get("sender_name") or "Khách hàng"
                    message_text = value.get("message", "")
                    post_id = value.get("post_id")
                    comment_id = value.get("comment_id")
                    
                    if verb == "add" and sender_id and page_id:
                        title = ""
                        if item == "comment":
                            title = f"{sender_name} đã bình luận: \"{message_text}\""
                        elif item in ("like", "reaction"):
                            reaction_type = value.get("reaction_type", "like")
                            react_map = {
                                "like": "thích",
                                "love": "yêu thích",
                                "haha": "haha",
                                "wow": "wow",
                                "sad": "buồn",
                                "angry": "phẫn nộ"
                            }
                            viet_react = react_map.get(reaction_type.lower(), reaction_type)
                            title = f"{sender_name} đã bày tỏ cảm xúc \"{viet_react}\" về bài viết của bạn"
                        elif item == "post":
                            title = f"{sender_name} đã đăng một bài viết mới"
                        elif item == "follow":
                            title = f"{sender_name} đã bắt đầu theo dõi trang của bạn"
                        else:
                            title = f"{sender_name} đã có tương tác \"{item}\" trên trang của bạn"
                            
                        # Generate unique notification key
                        notif_id = comment_id if comment_id else f"{post_id}_{item}_{sender_id}"
                        link = f"https://facebook.com/{post_id}"
                        
                        db_notif = db.query(Notification).filter(
                            Notification.facebook_notification_id == notif_id
                        ).first()
                        
                        if not db_notif:
                            db_notif = Notification(
                                facebook_notification_id=notif_id,
                                page_id=page_id,
                                title=title,
                                link=link,
                                created_time=datetime.utcnow(),
                                unread=True
                            )
                            db.add(db_notif)
                            db.commit()
                            db.refresh(db_notif)
                            
                            # Resolve Page mapping
                            page_record = db.query(Page).filter(Page.page_id == page_id).first()
                            if page_record:
                                # Broadcast notification alert to WebSocket
                                ws_payload = {
                                    "type": "notification",
                                    "page_id": page_id,
                                    "page_name": page_record.page_name,
                                    "facebook_user_id": page_record.facebook_user_id,
                                    "data": {
                                        "id": db_notif.id,
                                        "facebook_notification_id": db_notif.facebook_notification_id,
                                        "page_id": db_notif.page_id,
                                        "page_name": page_record.page_name,
                                        "title": db_notif.title,
                                        "link": db_notif.link,
                                        "created_time": db_notif.created_time.isoformat(),
                                        "unread": db_notif.unread
                                    }
                                }
                                await manager.send_personal_message(ws_payload, page_record.facebook_user_id)
                                
                                # Trigger native Windows toast for feed interaction
                                if win_notifier:
                                    try:
                                        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../app_logo.ico"))
                                        icon_to_use = icon_path if os.path.exists(icon_path) else None
                                        await asyncio.to_thread(
                                            win_notifier.notify,
                                            title=f"🔔 Tương tác mới - {page_record.page_name}",
                                            message=title,
                                            app_name="Hội thoại Đa kênh (Omnichannel)",
                                            app_icon=icon_to_use,
                                            timeout=6
                                        )
                                    except Exception as ne:
                                        print(f"[Notifier Error] {str(ne)}")

                                # Trigger Service Worker push notification
                                await trigger_web_push(db, page_record.facebook_user_id, f"🔔 Tương tác mới", title)
                                
    except Exception as e:
        print(f"[Queue Worker] Error parsing webhook item: {str(e)}")
    finally:
        db.close()

async def start_queue_worker():
    """Background loop daemon for event parsing consumer."""
    print("[Queue Worker] Event loop consumer initiated successfully.")
    while True:
        try:
            event = await event_queue.get()
            await process_webhook_event(event)
            event_queue.task_done()
        except asyncio.CancelledError:
            print("[Queue Worker] Worker loop cancelled.")
            break
        except Exception as e:
            print(f"[Queue Worker] Consumer exception occurred: {str(e)}")
            await asyncio.sleep(1)
