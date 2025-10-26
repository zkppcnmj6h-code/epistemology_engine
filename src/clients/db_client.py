from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os
from dotenv import load_dotenv

# Load .env from config dir relative to project root
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/epistemology_engine")

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
def execute_sql(session, sql: str, params: dict = None):
    session.execute(text(sql), params or {})

def fetch_one_sql(session, sql: str, params: dict = None):
    result = session.execute(text(sql), params or {}).mappings().fetchone()
    return result # Returns a dictionary-like object or None
