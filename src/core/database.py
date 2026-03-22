"""
database.py — Level 5 SQLAlchemy Session Factory

Provides the engine, session factory, and FastAPI dependency
for injecting database sessions into route handlers.

Connection priority:
  1. DATABASE_URL (Supabase/Postgres) — tries to connect
  2. If connection fails (e.g., local WiFi blocks outbound Postgres),
     falls back to local SQLite at data/quantprime.db

This ensures local dev always works, while production uses Supabase.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL, PROJECT_ROOT

logger = logging.getLogger(__name__)

# SQLite fallback path
_SQLITE_PATH = os.path.join(PROJECT_ROOT, "data", "quantprime.db")
_SQLITE_URL = f"sqlite:///{_SQLITE_PATH}"


def _build_engine():
    """Build the SQLAlchemy engine, falling back to SQLite if Postgres is unreachable."""
    url = DATABASE_URL

    # If Postgres URL, try to connect — fall back to SQLite on failure
    if url.startswith("postgresql"):
        try:
            connect_args = {"connect_timeout": 5}
            # Supabase pooler requires SSL
            if "supabase" in url:
                connect_args["sslmode"] = "require"

            test_engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Connected to Supabase Postgres")
            return test_engine

        except Exception as e:
            logger.warning(f"⚠ Postgres connection failed: {e}")
            logger.warning(f"⚠ Falling back to local SQLite at {_SQLITE_PATH}")
            url = _SQLITE_URL

    # SQLite path
    os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Auto-create tables in SQLite (Supabase tables created via SQL Editor)
if str(engine.url).startswith("sqlite"):
    from src.core.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("✅ SQLite tables created/verified")


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
