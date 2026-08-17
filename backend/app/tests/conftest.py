"""
Pytest configuration and fixtures for ERP SOLUTION tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings with isolated configuration."""
    settings = Settings()
    settings.DATABASE_URL = "sqlite:///./test_erp.db"
    settings.DEBUG = True
    return settings


@pytest.fixture(scope="function")
def db_engine(test_settings):
    """Create a test database engine."""
    engine = create_engine(
        test_settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = Mock()
    user.id = 1
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.role = "user"
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user object."""
    user = Mock()
    user.id = 2
    user.email = "admin@example.com"
    user.full_name = "Admin User"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session():
    """Create a mock database session for testing without actual DB."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.count.return_value = 0
    session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    return session
