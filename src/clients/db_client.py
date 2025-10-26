import os
from contextlib import contextmanager
from typing import Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# SQLAlchemy picks a PostgreSQL driver based on the URL scheme. Our dependency
# graph installs psycopg (v3), so we need to make sure the connection URL asks
# for that driver explicitly; otherwise SQLAlchemy will attempt to import the
# psycopg2 package, which is not installed in the containers.
def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

# Load .env from config dir relative to project root
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/epistemology_engine")
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def db_session():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Basic helpers for M1 (replace with proper ORM/Core usage later)
def execute_sql(session, sql: str, params: Optional[Dict] = None):
    session.execute(text(sql), params or {})


def fetch_one_sql(session, sql: str, params: Optional[Dict] = None):
    result = session.execute(text(sql), params or {}).mappings().fetchone()
    return result # Returns a dictionary-like object or None
