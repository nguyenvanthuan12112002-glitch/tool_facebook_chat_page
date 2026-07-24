import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./facebook_sync.db")
    FACEBOOK_API_VERSION: str = os.getenv("FACEBOOK_API_VERSION", "v19.0")
    FACEBOOK_BASE_URL: str = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}"
    FACEBOOK_WEBHOOK_VERIFY_TOKEN: str = os.getenv("FACEBOOK_WEBHOOK_VERIFY_TOKEN", "omnichannel_verify_token_2026")
    FACEBOOK_APP_ID: str = os.getenv("FACEBOOK_APP_ID", "")
    FACEBOOK_APP_SECRET: str = os.getenv("FACEBOOK_APP_SECRET", "")
    NGROK_AUTHTOKEN: str = os.getenv("NGROK_AUTHTOKEN", "")

settings = Settings()
