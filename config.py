import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    raw_url = os.environ.get("DATABASE_URL", "").strip()

    if not raw_url:
        # No DATABASE_URL set — use local SQLite
        db_url = "sqlite:///atmiya.db"
        print("WARNING: DATABASE_URL not set, using SQLite")
    elif raw_url.startswith("postgres://"):
        # Render gives postgres:// — SQLAlchemy needs postgresql://
        db_url = raw_url.replace("postgres://", "postgresql://", 1)
    elif raw_url.startswith("postgresql://"):
        db_url = raw_url
    else:
        print(f"WARNING: Unexpected DATABASE_URL format: {raw_url[:30]}...")
        db_url = "sqlite:///atmiya.db"

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }