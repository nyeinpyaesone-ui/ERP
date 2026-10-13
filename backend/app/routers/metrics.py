"""Prometheus instrumentation.

Exposes ``GET /metrics`` in the standard Prometheus text format and an ASGI
middleware that records request count / duration / in-flight gauge per
endpoint. Mounted with no auth so scrapers work out of the box; lock it down
at the reverse-proxy layer (see nginx/) if the deployment requires it.
"""

import time

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# prometheus-client auto-registers the platform/process/GC noise collectors at
# import time; unregister them so /metrics only exposes app-level series.
try:
    from prometheus_client.registry import REGISTRY as _REGISTRY

    for _coll in list(_REGISTRY._collector_to_names):
        if type(_coll).__name__ in ("GCCollector", "PlatformCollector", "ProcessCollector"):
            _REGISTRY.unregister(_coll)
except Exception:  # pragma: no cover - best-effort cleanup across versions
    pass

REQUEST_COUNT = Counter(
    "erp_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "erp_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
INFLIGHT = Gauge(
    "erp_http_requests_inflight",
    "Number of HTTP requests currently in flight",
    ["method"],
)
DB_CONNECTIONS = Gauge(
    "erp_db_connections",
    "SQLAlchemy pool connections (checked_out / total)",
    ["state"],
)

router = APIRouter(tags=["Metrics"])


def _route_label(request: Request) -> str:
    """Use the templated path (e.g. /api/v1/crm/{id}) to bound cardinality."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip instrumenting the scrape endpoint itself.
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        INFLIGHT.labels(method=method).inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            INFLIGHT.labels(method=method).dec()
            duration = time.perf_counter() - start
            endpoint = _route_label(request)
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status_code=response.status_code
            ).inc()
        return response


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Prometheus scrape endpoint."""
    # Refresh DB pool gauges on each scrape (cheap, pull-time only).
    try:
        from app.database import engine

        pool = engine.pool
        DB_CONNECTIONS.labels(state="checked_out").set(pool.checkedout())
        DB_CONNECTIONS.labels(state="total").set(pool.size())
    except Exception:  # pragma: no cover - pool stats are best-effort
        pass

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
