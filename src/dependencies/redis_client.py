from typing import Optional

from redis import Redis

from src.config import get_redis_url


def get_redis_client() -> Optional[Redis]:
	"""Return a Redis client if REDIS_URL is configured; otherwise None."""
	redis_url = get_redis_url()
	if not redis_url:
		return None
	return Redis.from_url(redis_url, decode_responses=True)
