import os
import json
from typing import Any, Dict, Optional

# Workaround for ChromaDB 0.5.3 v1 API limitation
# Create a custom client that bypasses tenant validation
try:  # pragma: no cover
	from chromadb import HttpClient  # type: ignore
	from chromadb.api.client import Client  # type: ignore
	from chromadb.config import Settings  # type: ignore
except Exception:  # pragma: no cover
	HttpClient = None  # type: ignore
	Client = None  # type: ignore
	Settings = None  # type: ignore


def _env_bool(name: str, default: str = "false") -> bool:
	val = os.getenv(name, default).strip().lower()
	return val in {"1", "true", "yes", "on"}


def _load_headers() -> Optional[Dict[str, str]]:
	# Prefer explicit JSON headers
	raw = os.getenv("CHROMA_HEADERS")
	if raw:
		try:
			parsed = json.loads(raw)
			return parsed if isinstance(parsed, dict) else None
		except Exception:
			return None
	# Fallback: Authorization from CHROMA_API_KEY
	api_key = os.getenv("CHROMA_API_KEY")
	if api_key and api_key.strip():
		return {"Authorization": f"Bearer {api_key.strip()}"}
	return None


class V2ChromaClient:
	"""Custom Chroma client that works with v2 APIs by bypassing tenant validation."""
	
	def __init__(self, host: str, port: int, tenant: str, database: str, ssl: bool = False, headers: Optional[Dict[str, str]] = None):
		self.host = host
		self.port = port
		self.tenant = tenant
		self.database = database
		self.ssl = ssl
		self.headers = headers or {}
		self._base_url = f"{'https' if ssl else 'http'}://{host}:{port}/api/v2"
		self._collections = {}  # Cache for collections
	
	def _make_request(self, method: str, endpoint: str, json_data: Optional[Dict] = None, retries: int = 3):
		"""Make HTTP request to v2 API with retry logic for external Chroma."""
		import httpx
		import time
		url = f"{self._base_url}{endpoint}"
		headers = {**self.headers, "Content-Type": "application/json"}
		
		# Longer timeout for external connections
		timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)
		
		last_exception = None
		for attempt in range(retries + 1):
			try:
				with httpx.Client(timeout=timeout) as client:
					if method.upper() == "GET":
						resp = client.get(url, headers=headers)
					elif method.upper() == "POST":
						resp = client.post(url, headers=headers, json=json_data)
					elif method.upper() == "PUT":
						resp = client.put(url, headers=headers, json=json_data)
					else:
						raise ValueError(f"Unsupported method: {method}")
					
					resp.raise_for_status()
					return resp.json() if resp.content else {}
			except (httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException) as e:
				last_exception = e
				if attempt < retries:
					wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
					print(f"Chroma connection failed (attempt {attempt + 1}/{retries + 1}), retrying in {wait_time}s: {e}")
					time.sleep(wait_time)
					continue
				# Final attempt failed
				raise Exception(f"Chroma database connection failed after {retries + 1} attempts. Last error: {e}")
			except Exception as e:
				# Include response text for debugging
				if hasattr(e, 'response') and e.response:
					error_text = e.response.text
					raise Exception(f"API request failed: {e} - Response: {error_text}")
				raise Exception(f"API request failed: {e}")
		
		# This should never be reached, but just in case
		raise Exception(f"Chroma database connection failed after {retries + 1} attempts. Last error: {last_exception}")
	
	def heartbeat(self):
		"""Call heartbeat via v2 API."""
		return self._make_request("GET", "/heartbeat")
	
	def health_check(self, max_retries: int = 10) -> bool:
		"""Check if Chroma is healthy and ready, with retries."""
		import time
		for attempt in range(max_retries):
			try:
				self.heartbeat()
				print(f"Chroma health check passed on attempt {attempt + 1}")
				return True
			except Exception as e:
				if attempt < max_retries - 1:
					wait_time = 2 ** min(attempt, 5)  # Cap at 32 seconds
					print(f"Chroma health check failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
					time.sleep(wait_time)
				else:
					print(f"Chroma health check failed after {max_retries} attempts: {e}")
		return False
	
	def get_or_create_collection(self, name: str):
		"""Get or create collection using v2 API."""
		# Check if collection exists
		try:
			collections = self._make_request("GET", f"/tenants/{self.tenant}/databases/{self.database}/collections")
			for col in collections:
				if col.get("name") == name:
					return V2Collection(self, name, col.get("id"))
		except Exception:
			pass
		
		# Create collection if it doesn't exist (metadata cannot be empty)
		create_data = {
			"name": name,
			"metadata": {"created_by": "agentic-memories"}
		}
		result = self._make_request("POST", f"/tenants/{self.tenant}/databases/{self.database}/collections", create_data)
		collection_id = result.get("id")
		return V2Collection(self, name, collection_id)
	
	def get_collection(self, name: str):
		"""Get collection using v2 API."""
		collections = self._make_request("GET", f"/tenants/{self.tenant}/databases/{self.database}/collections")
		for col in collections:
			if col.get("name") == name:
				return V2Collection(self, name, col.get("id"))
		raise ValueError(f"Collection {name} not found")
	
	def list_collections(self):
		"""List collections using v2 API."""
		result = self._make_request("GET", f"/tenants/{self.tenant}/databases/{self.database}/collections")
		return [V2Collection(self, col.get("name"), col.get("id")) for col in result]


class V2Collection:
	"""Minimal collection wrapper for v2 API."""
	
	def __init__(self, client: V2ChromaClient, name: str, collection_id: str):
		self.client = client
		self.name = name
		self.id = collection_id
		self._endpoint_base = f"/tenants/{client.tenant}/databases/{client.database}/collections/{collection_id}"
	
	def get(self, ids: Optional[list] = None, where: Optional[Dict] = None, limit: Optional[int] = None, offset: Optional[int] = None, include: Optional[list] = None):
		"""Fetch items by ID or metadata filter using v2 API.

		Args:
			ids: Optional list of IDs to fetch (takes precedence over where)
			where: Optional metadata filter (used if ids not provided)
			limit: Maximum number of items to return
			offset: Number of items to skip
			include: List of fields to include in response (e.g., ["documents", "metadatas"])

		Returns:
			Dict with ids, documents, metadatas based on include parameter
		"""
		# Chroma v2 does not support 'ids' in include; ids are returned by default.
		data: Dict[str, Any] = {
			"include": include or ["documents", "metadatas"],
		}
		# IDs take precedence over where filter
		if ids is not None:
			data["ids"] = ids
		elif where is not None:
			data["where"] = where
		else:
			data["where"] = {}
		if limit is not None:
			data["limit"] = limit
		if offset is not None:
			data["offset"] = offset
		return self.client._make_request("POST", f"{self._endpoint_base}/get", data)
	
	def upsert(self, ids: list, documents: list, embeddings: list, metadatas: list):
		"""Upsert documents to collection."""
		# Coerce metadata values to scalars (v2 requires scalar values). Lists/dicts -> JSON strings.
		coerced_metadatas = []
		for md in metadatas or []:
			fixed = {}
			for k, v in (md or {}).items():
				if isinstance(v, (list, dict)):
					fixed[k] = json.dumps(v)
				else:
					fixed[k] = v
			coerced_metadatas.append(fixed)
		data = {
			"ids": ids,
			"documents": documents,
			"embeddings": embeddings,
			"metadatas": coerced_metadatas
		}
		return self.client._make_request("POST", f"{self._endpoint_base}/upsert", data)

	def delete(self, ids: Optional[list] = None, where: Optional[Dict[str, Any]] = None):
		"""Delete items by ids or where filter using v2 API.
		Exactly one of ids or where should be provided.
		"""
		if (ids is None and where is None) or (ids is not None and where is not None):
			raise ValueError("Provide either ids or where, exclusively")
		payload: Dict[str, Any] = {}
		if ids is not None:
			payload["ids"] = ids
		if where is not None:
			payload["where"] = where
		return self.client._make_request("POST", f"{self._endpoint_base}/delete", payload)
	
	def query(self, query_texts: list = None, query_embeddings: list = None, n_results: int = 10, where: Optional[Dict] = None):
		"""Query collection.
		Supports either query_texts (if server embeds) or query_embeddings (preferred)."""
		data: Dict[str, Any] = {
			"n_results": n_results,
			"where": where or {},
		}
		if query_embeddings is not None:
			data["query_embeddings"] = query_embeddings
		elif query_texts is not None:
			data["query_texts"] = query_texts
		else:
			raise ValueError("Either query_embeddings or query_texts must be provided")
		return self.client._make_request("POST", f"{self._endpoint_base}/query", data)


def get_chroma_client() -> Any:
	"""Create a Chroma v2 client that works with v2-only servers.
	
	Workaround for ChromaDB 0.5.3 v1 API limitation.
	"""
	if Client is None or Settings is None:
		return None

	host = os.getenv("CHROMA_HOST", "localhost")
	try:
		port = int(os.getenv("CHROMA_PORT", "8000"))
	except ValueError:
		port = 8000
	tenant = os.getenv("CHROMA_TENANT", "default_tenant")
	database = os.getenv("CHROMA_DATABASE", "default_database")
	ssl = _env_bool("CHROMA_SSL", "false")
	headers = _load_headers()

	try:
		return V2ChromaClient(
			host=host,
			port=port,
			tenant=tenant,
			database=database,
			ssl=ssl,
			headers=headers,
		)
	except Exception:
		return None

