"""
Pytest Configuration and Fixtures
==================================
Global test configuration, fixtures, and settings.
"""
import pytest
import os

# Configure Django settings before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'is_staff': False,
        'is_superuser': False
    }


@pytest.fixture
def admin_user():
    """Create an admin user for testing."""
    return {
        'username': 'admin',
        'email': 'admin@example.com',
        'is_staff': True,
        'is_superuser': True
    }
