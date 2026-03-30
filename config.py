import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # Get database URL from environment (Render sets this automatically)
    db_url = os.environ.get("DATABASE_URL", "sqlite:///atmiya.db")

    # Render PostgreSQL gives postgres:// but SQLAlchemy 2.x needs postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # PostgreSQL connection pool settings (ignored for SQLite)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # test connection before using
        "pool_recycle": 300,         # recycle connections every 5 mins
    }