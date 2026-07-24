import asyncio
from backend.queue_worker import process_webhook_event

real_payload = {
    "entry": [
        {
            "id": "1117284361478973",
            "time": 1784467128,
            "changes": [
                {
                    "value": {
                        "from": {
                            "id": "38246189218313641",
                            "name": "Phạm Trường"
                        },
                        "post": {
                            "status_type": "added_photos",
                            "is_published": True,
                            "updated_time": "2026-07-19T13:18:44+0000",
                            "permalink_url": "https://www.facebook.com/photo/?fbid=122095078959402237&set=a.122095079019402237",
                            "promotion_status": "ineligible",
                            "id": "1117284361478973_122095078959402237"
                        },
                        "message": "hi",
                        "post_id": "1117284361478973_122095078959402237",
                        "comment_id": "122095078959402237_2989637557912774",
                        "created_time": 1784467124,
                        "item": "comment",
                        "parent_id": "27721710007482521_122095078959402237",
                        "verb": "add"
                    },
                    "field": "feed"
                }
            ]
        }
    ],
    "object": "page"
}

async def run():
    print("Running process_webhook_event with real payload...")
    try:
        await process_webhook_event(real_payload)
        print("Success! Checking DB...")
        from backend.database import SessionLocal
        from backend.models import Notification
        db = SessionLocal()
        notifs = db.query(Notification).all()
        print("Notifications in DB:", notifs)
        db.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
