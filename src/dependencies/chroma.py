import os
from typing import Any

import httpx

try:
	from chromadb import HttpClient
except Exception:  # pragma: no cover
	HttpClient = None  # type: ignore[assignment]


def get_chroma_client() -> Any:
	"""Create and return a ChromaDB HTTP client using environment variables.

	Environment:
	- CHROMA_HOST (default: localhost)
	- CHROMA_PORT (default: 8000)
	"""
	host = os.getenv("CHROMA_HOST", "localhost")
	port = int(os.getenv("CHROMA_PORT", "8000"))
	base_url = f"http://{host}:{port}"

	if HttpClient is None:  # Fallback to settings-based client if needed
		from chromadb import Client  # type: ignore
		from chromadb.config import Settings  # type: ignore
		return Client(
			Settings(
				chroma_api_impl="rest",
				chroma_server_host=host,
				chroma_server_http_port=port,
			)
		)

	http_client = httpx.Client(base_url=base_url)
	return HttpClient(http_client=http_client)

