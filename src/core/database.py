"""
database.py — Level 5 SQLAlchemy Session Factory

Provides the engine, session factory, and FastAPI dependency
for injecting database sessions into route handlers.

Supports both PostgreSQL (production) and SQLite (local dev fallback)
based on the DATABASE_URL environment variable.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL


# pool_pre_ping keeps connections healthy across container restarts
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency for DB sessions.

    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
