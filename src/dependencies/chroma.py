import os
from typing import Any

from src.config import get_chroma_host, get_chroma_port

try:
	from chromadb import HttpClient, Client  # type: ignore
	exists_httpclient = True
except Exception:  # pragma: no cover
	HttpClient = None  # type: ignore
	Client = None  # type: ignore
	exists_httpclient = False


def get_chroma_client() -> Any:
	"""Create and return a ChromaDB HTTP client using environment variables.

	Environment:
	- CHROMA_HOST (default: localhost)
	- CHROMA_PORT (default: 8000)
	"""
	host = get_chroma_host()
	port = get_chroma_port()

	# Prefer HttpClient(host=..., port=...) if available
	if exists_httpclient and HttpClient is not None:
		try:
			return HttpClient(host=host, port=port)  # newer signature
		except TypeError:
			# Fall through to Settings-based Client
			pass
		except Exception:
			# Fall through
			pass

	# Fallback to Settings-based REST client
	try:
		from chromadb.config import Settings  # type: ignore
		return Client(
			Settings(
				chroma_api_impl="rest",
				chroma_server_host=host,
				chroma_server_http_port=port,
			)
		)
	except Exception:
		return None

