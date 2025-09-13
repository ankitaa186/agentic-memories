import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

# Load .env once when module is imported
load_dotenv()


@lru_cache(maxsize=1)
def get_openai_api_key() -> Optional[str]:
	return os.getenv("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_chroma_host() -> str:
	return os.getenv("CHROMA_HOST", "localhost")


@lru_cache(maxsize=1)
def get_chroma_port() -> int:
	try:
		return int(os.getenv("CHROMA_PORT", "8000"))
	except ValueError:
		return 8000


@lru_cache(maxsize=1)
def get_redis_url() -> Optional[str]:
	return os.getenv("REDIS_URL")
