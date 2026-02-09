"""Redis mock fixtures for testing."""

from typing import Any, Dict, Optional, Union


class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}

    def get(self, key: str) -> Optional[bytes]:
        """Mock get method."""
        if key in self._expires and self._expires[key] < 0:  # Simple expiration check
            del self._data[key]
            del self._expires[key]
            return None
        return self._data.get(key)

    def set(
        self,
        key: str,
        value: Union[str, bytes],
        ex: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Mock set method."""
        if nx and key in self._data:
            return False
        if xx and key not in self._data:
            return False

        self._data[key] = value if isinstance(value, bytes) else value.encode()
        if ex:
            self._expires[key] = ex
        return True

    def delete(self, *keys: str) -> int:
        """Mock delete method."""
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                if key in self._expires:
                    del self._expires[key]
                count += 1
        return count

    def exists(self, *keys: str) -> int:
        """Mock exists method."""
        return sum(1 for key in keys if key in self._data)

    def keys(self, pattern: str = "*") -> list:
        """Mock keys method."""
        if pattern == "*":
            return list(self._data.keys())
        # Simple pattern matching
        import fnmatch

        return [key for key in self._data.keys() if fnmatch.fnmatch(key, pattern)]

    def flushdb(self) -> bool:
        """Mock flushdb method."""
        self._data.clear()
        self._expires.clear()
        return True


def create_mock_redis_client() -> MockRedisClient:
    """Create a mock Redis client."""
    return MockRedisClient()
