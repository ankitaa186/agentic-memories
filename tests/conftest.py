from importlib import reload
import warnings
from types import SimpleNamespace
from typing import Dict, Set
from unittest.mock import MagicMock

warnings.filterwarnings(
    "ignore",
    category=PendingDeprecationWarning,
    module=r"starlette\\.formparsers",
)
warnings.filterwarnings(
    "ignore",
    category=PendingDeprecationWarning,
    message=r"Please use `import python_multipart` instead\.",
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"pydantic\\.v1\\.typing",
)

import pytest
from fastapi.testclient import TestClient


class _RedisStub:
    """Minimal Redis stub used to observe cache invalidation behaviour."""

    def __init__(self) -> None:
        self.counters: Dict[str, int] = {}
        self.sets: Dict[str, Set[str]] = {}
        self.values: Dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def sadd(self, key: str, member: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.add(member)
        return 1 if len(bucket) > before else 0

    def smembers(self, key: str) -> Set[str]:
        return set(self.sets.get(key, set()))

    # Methods used by persona state store
    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def _prepare_app(monkeypatch: pytest.MonkeyPatch, redis_stub: _RedisStub):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CHROMA_HOST", "localhost")
    monkeypatch.setenv("CHROMA_PORT", "8000")

    class _PoolStub:
        def __init__(self, *_, **__):
            pass

        def getconn(self):
            return None

        def putconn(self, _conn):
            return None

    monkeypatch.setattr("src.dependencies.timescale.ConnectionPool", _PoolStub)
    monkeypatch.setattr("src.dependencies.timescale.get_timescale_pool", lambda: None)
    monkeypatch.setattr("src.dependencies.timescale.get_timescale_conn", lambda: None)
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: False)

    import src.app as app_module
    reload(app_module)

    monkeypatch.setattr(app_module, "_start_scheduler", lambda: None)
    monkeypatch.setattr(app_module, "is_llm_configured", lambda: True)

    collection_name = "unit_test_collection"
    chroma_client = MagicMock()
    chroma_client.health_check.return_value = True
    chroma_client.list_collections.return_value = [SimpleNamespace(name=collection_name)]
    monkeypatch.setattr(app_module, "get_chroma_client", lambda: chroma_client)
    monkeypatch.setattr(app_module, "_standard_collection_name", lambda: collection_name)

    monkeypatch.setattr(app_module, "ping_timescale", lambda: (True, None))
    monkeypatch.setattr(app_module, "get_redis_client", lambda: redis_stub)

    class _HTTPXStub:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def get(self, _url: str):
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(app_module.httpx, "Client", lambda timeout=180.0: _HTTPXStub())

    return app_module


@pytest.fixture
def redis_stub() -> _RedisStub:
    return _RedisStub()


@pytest.fixture
def app_module(monkeypatch: pytest.MonkeyPatch, redis_stub: _RedisStub):
    return _prepare_app(monkeypatch, redis_stub)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, redis_stub: _RedisStub) -> TestClient:
    app_module = _prepare_app(monkeypatch, redis_stub)
    with TestClient(app_module.app) as client:
        yield client
