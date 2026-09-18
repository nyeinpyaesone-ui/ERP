import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
def client():
    """Create a test client for the FastAPI app."""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
async def async_client():
    """Create an async test client for the FastAPI app."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac