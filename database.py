from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.database_models import Base
from settings import settings

engine = create_engine(settings.database_url, echo=False)
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
