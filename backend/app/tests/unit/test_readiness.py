from unittest.mock import Mock

import pytest

from app.routers import health, health_root

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("module", [health, health_root], ids=["versioned", "root"])
async def test_liveness_is_independent_of_dependencies(
    module, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis = Mock(side_effect=AssertionError("Liveness must not connect to Redis"))
    monkeypatch.setattr(module.redis, "from_url", redis)
    assert await module.health_check() == {"status": "healthy"}
    redis.assert_not_called()


@pytest.mark.parametrize("module", [health, health_root], ids=["versioned", "root"])
@pytest.mark.parametrize(
    "db_failed,redis_failed",
    [(False, False), (True, False), (False, True), (True, True)],
)
async def test_readiness_reports_each_dependency_even_when_another_fails(
    module,
    db: Mock,
    monkeypatch: pytest.MonkeyPatch,
    db_failed: bool,
    redis_failed: bool,
) -> None:
    if db_failed:
        db.execute.side_effect = RuntimeError("database offline")
    redis = Mock()
    if redis_failed:
        redis.ping.side_effect = RuntimeError("redis offline")
    factory = Mock(return_value=redis)
    monkeypatch.setattr(module.redis, "from_url", factory)

    result = await module.readiness_check(db)

    assert result == {
        "status": "not_ready" if db_failed or redis_failed else "ready",
        "checks": {
            "database": "failed: database offline" if db_failed else "ok",
            "redis": "failed: redis offline" if redis_failed else "ok",
        },
    }
    assert str(db.execute.call_args.args[0]) == "SELECT 1"
    factory.assert_called_once_with(module.settings.REDIS_URL)
    redis.ping.assert_called_once_with()
