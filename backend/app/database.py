from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Optimized connection pool for production peak loads
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=50,           # Increased from 20 for peak concurrency
    max_overflow=100,       # Increased from 30 to handle traffic spikes
    pool_pre_ping=True,     # Keep existing - validates connections
    pool_recycle=3600,      # Recycle connections every hour to prevent stale connections
    pool_timeout=30,        # Timeout waiting for connection from pool
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

