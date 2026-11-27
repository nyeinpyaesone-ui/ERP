from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def normalize_database_url(database_url: str) -> str:
    """Select the installed PostgreSQL DBAPI explicitly.

    SQLAlchemy 2.1 defaults driver-less PostgreSQL URLs to psycopg 3. This
    project currently ships psycopg2-binary, so normalize the default URL while
    preserving explicitly selected drivers such as postgresql+psycopg.
    """
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + database_url.removeprefix("postgresql://")
    return database_url


def build_engine(database_url: str | None = None):
    """Create an engine from Settings.

    Test environments (ENVIRONMENT=test) get NullPool so SQLite in-memory
    databases are not shared across connections; everything else uses a
    tuned pool (POOL_SIZE/POOL_MAX_OVERFLOW/POOL_RECYCLE from config.py).
    """
    url = normalize_database_url(database_url or settings.DATABASE_URL)
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
