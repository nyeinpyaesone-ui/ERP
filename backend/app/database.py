from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def build_engine(database_url: str | None = None):
    """Create an engine from Settings.

    Test environments (ENVIRONMENT=test) get NullPool so SQLite in-memory
    databases are not shared across connections; everything else uses a
    tuned pool (POOL_SIZE/POOL_MAX_OVERFLOW/POOL_RECYCLE from config.py).
    """
    url = database_url or settings.DATABASE_URL
    if settings.ENVIRONMENT == "test" or url.startswith("sqlite"):
        return create_engine(
            url, poolclass=NullPool, connect_args={"check_same_thread": False}
        )
    return create_engine(
        url,
        pool_size=settings.POOL_SIZE,
        max_overflow=settings.POOL_MAX_OVERFLOW,
        pool_recycle=settings.POOL_RECYCLE,
        pool_pre_ping=True,
    )


engine = build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
