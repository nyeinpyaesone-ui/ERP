"""
Test Fixtures for ERP System
=============================
Common fixtures used across all tests.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def sample_user(db):
    """Create a sample user for testing."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpassword123'
    )


@pytest.fixture
def sample_superuser(db):
    """Create a sample superuser for testing."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpassword123'
    )


@pytest.fixture
def api_client():
    """Return an API client instance."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, sample_user):
    """Return an authenticated API client."""
    api_client.force_authenticate(user=sample_user)
    return api_client
