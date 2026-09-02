import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base

# 1. Load environment variables (to read DATABASE_URL if defined)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 2. Database Connection URL
# Defaults to SQLite database file named 'archaeon.db' in the project root
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./archaeon.db")

# 3. Create SQLAlchemy Engine
# connect_args={"check_same_thread": False} is REQUIRED for SQLite when used with FastAPI
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# 4. Create Session Factory
# SessionLocal will be instantiated to create individual database sessions for API requests
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 5. Helper Function: Create Tables
def init_db():
    """Creates all database tables defined in models.py if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


# 6. FastAPI Dependency Generator
def get_db():
    """
    FastAPI dependency that yields a database session per request,
    and ensures the session is cleanly closed when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()