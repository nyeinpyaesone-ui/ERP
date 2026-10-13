"""Tests for the Prometheus /metrics endpoint (app/routers/metrics.py)."""

import pytest
from httpx import AsyncClient


class TestMetricsEndpoint:
    async def test_metrics_returns_prometheus_format(self, async_client: AsyncClient):
        response = await async_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    async def test_metrics_exposes_app_series(self, async_client: AsyncClient):
        # Generate traffic first so counters/histograms have samples.
        await async_client.get("/health")
        body = (await async_client.get("/metrics")).text
        assert "erp_http_requests_total" in body
        assert "erp_http_request_duration_seconds" in body
        assert "erp_http_requests_inflight" in body
        assert "erp_db_connections" in body

    async def test_metrics_counts_other_endpoints_not_itself(self, async_client: AsyncClient):
        await async_client.get("/health")
        body = (await async_client.get("/metrics")).text
        # The scrape path itself must not be instrumented (avoids feedback loop).
        assert 'endpoint="/metrics"' not in body
        assert 'endpoint="/health"' in body

    async def test_metrics_hides_process_noise_collectors(self, async_client: AsyncClient):
        body = (await async_client.get("/metrics")).text
        assert "process_cpu_seconds_total" not in body
        assert "python_gc_objects_collected_total" not in body
