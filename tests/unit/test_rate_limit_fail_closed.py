"""Rate limiting must honour RATE_LIMIT__FAIL_OPEN when Redis is unreachable."""

from types import SimpleNamespace

import pytest

from utils import rate_limit_dependency as rld
from utils.api_errors import APIHTTPException


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="203.0.113.7"))


@pytest.fixture
def redis_down(monkeypatch):
    monkeypatch.setattr(rld.RedisClient, "test_connection", staticmethod(lambda: False))


def test_redis_down_fail_closed_rejects_with_503(monkeypatch, redis_down):
    monkeypatch.setattr(rld.settings.rate_limit, "fail_open", False)
    check = rld.RateLimitDependency.check_rate_limit("login", require_auth=False)

    with pytest.raises(APIHTTPException) as exc:
        check(_request(), db=None)

    assert exc.value.status_code == 503
    assert exc.value.headers["Retry-After"] == "5"


def test_redis_down_fail_open_allows(monkeypatch, redis_down):
    monkeypatch.setattr(rld.settings.rate_limit, "fail_open", True)
    check = rld.RateLimitDependency.check_rate_limit("login", require_auth=False)

    assert check(_request(), db=None) is None
