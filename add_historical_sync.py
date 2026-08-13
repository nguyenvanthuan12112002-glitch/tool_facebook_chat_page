import os

# 1. Update backend/repositories.py
repo_path = "backend/repositories.py"
with open(repo_path, "r", encoding="utf-8") as f:
    repo_content = f.read()

if "save_historical_notification" not in repo_content:
    new_notif_method = """
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
"""
    repo_content += new_notif_method
    with open(repo_path, "w", encoding="utf-8") as f:
        f.write(repo_content)
    print("Updated backend/repositories.py")

# 2. Update backend/services.py
services_path = "backend/services.py"
with open(services_path, "r", encoding="utf-8") as f:
    services_content = f.read()

if "sync_historical_data" not in services_content:
    imports_to_add = "import threading\nfrom dateutil import parser\n"
    if "from dateutil" not in services_content:
        services_content = imports_to_add + services_content

    # Add the method to FacebookSyncService
    # Find the end of FacebookSyncService class
    historical_sync_method = """
    def sync_historical_data(self, page_id: str, facebook_user_id: str):
        \"\"\"
        Runs in background to fetch historical conversations and feed for a page.
        \"\"\"
        try:
            # Re-create a new DB session for the background thread since sqlalchemy sessions are not thread-safe
            from backend.database import SessionLocal
            from backend.repositories import PageRepository, MessageRepository, NotificationRepository
            
            db = SessionLocal()
            try:
                page_repo = PageRepository(db)
                message_repo = MessageRepository(db)
                notif_repo = NotificationRepository(db)
                
                page = page_repo.get_by_page_id(page_id)
                if not page or not page.page_access_token:
                    return
                
                token = page.page_access_token
                
                # 1. Fetch Conversations
                conv_url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}/conversations"
                params = {
                    "fields": "messages{id,message,created_time,from,to}",
                    "access_token": token,
                    "limit": 20
                }
                
                resp = requests.get(conv_url, params=params, timeout=20)
                if resp.status_code == 200:
                    conv_data = resp.json().get("data", [])
                    for conv in conv_data:
                        messages_data = conv.get("messages", {}).get("data", [])
                        for msg in messages_data:
                            fb_message_id = msg.get("id")
                            text = msg.get("message", "")
                            created_time_str = msg.get("created_time")
                            from_obj = msg.get("from", {})
                            to_data = msg.get("to", {}).get("data", [])
                            
                            if not fb_message_id or not created_time_str:
                                continue
                                
                            try:
                                dt = parser.parse(created_time_str)
                                timestamp = int(dt.timestamp() * 1000)
                            except:
                                timestamp = int(datetime.utcnow().timestamp() * 1000)
                                
                            direction = "inbound"
                            if from_obj.get("id") == page_id:
                                direction = "outbound"
                                sender_id = to_data[0].get("id") if to_data else ""
                            else:
                                sender_id = from_obj.get("id", "")
                                
                            if not sender_id:
                                continue
                                
                            # Check if exists
                            if not message_repo.get_by_fb_message_id(fb_message_id):
                                new_msg = __import__('backend.models', fromlist=['Message']).Message(
                                    facebook_message_id=fb_message_id,
                                    page_id=page_id,
                                    sender_id=sender_id,
                                    text=text,
                                    timestamp=timestamp,
                                    direction=direction,
                                    is_read=True,
                                    is_replied=True
                                )
                                db.add(new_msg)
                    db.commit()
                
                # 2. Fetch Feed/Comments
                feed_url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}/feed"
                feed_params = {
                    "fields": "comments{id,message,created_time,from}",
                    "access_token": token,
                    "limit": 20
                }
                resp = requests.get(feed_url, params=feed_params, timeout=20)
                if resp.status_code == 200:
                    feed_data = resp.json().get("data", [])
                    for post in feed_data:
                        comments_data = post.get("comments", {}).get("data", [])
                        for comment in comments_data:
                            c_id = comment.get("id")
                            c_msg = comment.get("message", "")
                            c_time = comment.get("created_time")
                            c_from = comment.get("from", {}).get("name", "Người dùng")
                            
                            if not c_id:
                                continue
                            
                            try:
                                dt = parser.parse(c_time)
                            except:
                                dt = datetime.utcnow()
                                
                            title = f"{c_from} đã bình luận: {c_msg}"
                            link = f"https://facebook.com/{c_id}"
                            
                            notif_repo.save_historical_notification(
                                facebook_notification_id=c_id,
                                page_id=page_id,
                                title=title,
                                link=link,
                                created_time=dt
                            )
            finally:
                db.close()
        except Exception as e:
            print(f"[Historical Sync Error] For page {page_id}: {str(e)}")
"""
    
    # We will inject this before the CUSTOMER_PROFILE_CACHE definition
    insertion_point = "CUSTOMER_PROFILE_CACHE:"
    if insertion_point in services_content:
        services_content = services_content.replace(insertion_point, historical_sync_method + "\n\n" + insertion_point)
        with open(services_path, "w", encoding="utf-8") as f:
            f.write(services_content)
        print("Updated backend/services.py")

# 3. Update backend/routers.py
routers_path = "backend/routers.py"
with open(routers_path, "r", encoding="utf-8") as f:
    routers_content = f.read()

if "threading.Thread(target=sync_service.sync_historical_data" not in routers_content:
    if "import threading" not in routers_content:
        routers_content = "import threading\n" + routers_content

    # Patch sync_by_token
    target_by_token = """        return SyncByTokenResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            facebook_user_id=user_id,
            synced_count=count,
            pages=pages
        )"""
    replacement_by_token = """        # Trigger background historical sync for all newly synced pages
        for p in pages:
            threading.Thread(target=sync_service.sync_historical_data, args=(p.page_id, user_id), daemon=True).start()
            
        return SyncByTokenResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            facebook_user_id=user_id,
            synced_count=count,
            pages=pages
        )"""
    routers_content = routers_content.replace(target_by_token, replacement_by_token)
    
    # Patch sync_pages
    target_pages = """        return SyncResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            synced_count=count,
            pages=pages
        )"""
    replacement_pages = """        # Trigger background historical sync for all newly synced pages
        for p in pages:
            threading.Thread(target=sync_service.sync_historical_data, args=(p.page_id, facebook_user_id), daemon=True).start()
            
        return SyncResponse(
            success=True,
            message=f"Đồng bộ thành công {count} trang",
            synced_count=count,
            pages=pages
        )"""
    routers_content = routers_content.replace(target_pages, replacement_pages)
    
    with open(routers_path, "w", encoding="utf-8") as f:
        f.write(routers_content)
    print("Updated backend/routers.py")
