import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/encryptochat")

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_database():
    """Create database tables"""
    Base.metadata.create_all(bind=engine)


def get_database() -> Session:
    """Dependency to get DB session for FastAPI routes"""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()