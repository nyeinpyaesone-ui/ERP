import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_root_endpoint(self, async_client: AsyncClient):
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"