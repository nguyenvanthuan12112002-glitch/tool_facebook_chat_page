import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import Base, engine
from backend.routers import router as facebook_router

# Initialize database tables on application start with self-healing migration checks
from sqlalchemy import text
from backend.database import SessionLocal

try:
    db = SessionLocal()
    
    # Safely migrate new columns without dropping data
    try:
        db.execute(text("ALTER TABLE v_messages ADD COLUMN is_read BOOLEAN DEFAULT 0"))
        db.commit()
    except Exception:
        pass
    try:
        db.execute(text("ALTER TABLE v_messages ADD COLUMN is_replied BOOLEAN DEFAULT 0"))
        db.commit()
    except Exception:
        pass
    try:
        db.execute(text("ALTER TABLE v_notifications ADD COLUMN is_replied BOOLEAN DEFAULT 0"))
        db.commit()
    except Exception:
        pass

    # Try querying new columns to verify schema is up-to-date
    db.execute(text("SELECT user_access_token_long_lived FROM v_accounts LIMIT 1"))
    db.execute(text("SELECT avatar_url, status FROM v_pages LIMIT 1"))
    db.execute(text("SELECT direction, reactions, reply_to_message_id, is_read, is_replied FROM v_messages LIMIT 1"))
    db.execute(text("SELECT id, unread, is_replied FROM v_notifications LIMIT 1"))
    db.close()
    Base.metadata.create_all(bind=engine)
except Exception as e:
    err_msg = str(e).lower()
    is_schema_mismatch = "no such column" in err_msg or "no such table" in err_msg
    try:
        db.close()
    except:
        pass
    if is_schema_mismatch:
        print("[Database] Schema mismatch or outdated tables detected. Recreating database tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        print(f"[Database Error] Non-schema error detected during startup check: {str(e)}. Attempting to create missing tables...")
        Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Omnichannel Facebook Sync API",
    description="Backend API to synchronize Facebook Pages for an Omnichannel Sales Management system.",
    version="1.0.0"
)

# CORS configuration to allow local development with Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import asyncio
from backend.queue_worker import start_queue_worker

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_queue_worker())

import os
from fastapi.staticfiles import StaticFiles

# Mount local uploads directory to serve images and files
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Register routers
app.include_router(facebook_router)

# Mount Next.js static export at root
# Path points to frontend/out relative to backend/main.py
frontend_out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/out"))

if os.path.exists(frontend_out_path):
    app.mount("/", StaticFiles(directory=frontend_out_path, html=True), name="frontend")
else:
    @app.get("/")
    def read_root():
        return {
            "name": "Omnichannel FB Sync Service",
            "status": "online (Warning: Frontend build not found. Run 'npm run build')",
            "docs_url": "/docs"
        }

if __name__ == "__main__":
    # Standard port 8000 for development
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
