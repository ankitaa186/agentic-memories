from datetime import datetime, timezone
import logging
import os
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException, Header, Cookie, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from os import getenv

from src.schemas import (
	ForgetRequest,
	MaintenanceRequest,
	MaintenanceResponse,
	RetrieveItem,
	RetrieveResponse,
	StoreResponse,
	StoreMemoryItem,
	TranscriptRequest,
	StructuredRetrieveRequest,
	StructuredRetrieveResponse,
)
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_openai_api_key, get_chroma_host, get_chroma_port, is_llm_configured, get_llm_provider
from src.config import get_extraction_model_name, get_embedding_model_name
from src.config import get_xai_base_url
import httpx
from src.services.extraction import extract_from_transcript
from src.services.storage import upsert_memories
from src.services.retrieval import search_memories
from src.services.extract_utils import _call_llm_json
from src.dependencies.cloudflare_access import verify_cf_access_token, extract_token_from_headers

app = FastAPI(title="Agentic Memories API", version="0.1.0")
logger = logging.getLogger("agentic_memories.api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False
# Auth dependency: validate Cloudflare Access JWT if provided
def get_identity(
    cf_access_jwt_assertion: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    cf_authorization_cookie: Optional[str] = Cookie(default=None, alias="CF_Authorization"),
    cf_authorization_cookie_lower: Optional[str] = Cookie(default=None, alias="cf_authorization"),
    request: Request = None,
) -> Optional[dict]:
    # Debug: log cookies reaching the API (redacted)
    try:
        cookie_preview = {k: (v[:12] + f"...({len(v)}B)") for k, v in (request.cookies or {}).items()}
        logger.info("[auth] cookies preview: %s", cookie_preview)
    except Exception:
        pass
    headers = {}
    if cf_access_jwt_assertion:
        headers["cf-access-jwt-assertion"] = cf_access_jwt_assertion
    if authorization:
        headers["authorization"] = authorization
    token = extract_token_from_headers(headers)
    # Fallback to Cloudflare cookie (browser -> UI -> API)
    if not token:
        token = cf_authorization_cookie or cf_authorization_cookie_lower
    if not token:
        return None
    try:
        claims = verify_cf_access_token(token)
        return claims
    except Exception as exc:
        # For now, treat invalid tokens as anonymous; endpoints may enforce later
        logger.info("[auth] CF Access verification failed: %s", exc)
        return None

# CORS: allow UI origin (dev server and dockerized UI)
_ui_origin = getenv("UI_ORIGIN")
allow_origins = [
	"http://localhost:5173",
	"http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
	"http://192.168.1.220",
    "http://192.168.1.220:5173",
]
if _ui_origin and _ui_origin not in allow_origins:
	allow_origins.append(_ui_origin)

# Broadly allow common local network origins via regex (HTTP/HTTPS, any port)
# - 127.0.0.1 / localhost
# - 192.168.x.x
# - 10.x.x.x
# - 172.16.x.x - 172.31.x.x
# - memoryforge.io and subdomains
LAN_ORIGIN_REGEX = r"^https?://(localhost|127\\.0\\.0\\.1|192\\.168\\.\\d{1,3}\\.\\d{1,3}|10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|172\\\.(1[6-9]|2[0-9]|3[0-1])\\.\\d{1,3}\\.\\d{1,3}|([a-zA-Z0-9-]+\\.)*memoryforge\\.io)(:\\d+)?$"

app.add_middleware(
	CORSMiddleware,
    allow_origins=allow_origins + ["http://localhost:8080", "http://127.0.0.1:8080", "https://memoryforge.io"],
	allow_origin_regex=LAN_ORIGIN_REGEX,
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"]
)


@app.on_event("startup")
def require_llm_key() -> None:
	# Provider-aware LLM configuration check
	if not is_llm_configured():
		raise RuntimeError("LLM not configured. Set LLM_PROVIDER and corresponding API key.")
	# Log selected provider and models for observability
	try:
		provider = get_llm_provider()
		extraction_model = get_extraction_model_name()
		embedding_model = get_embedding_model_name()
		chroma_host, chroma_port = get_chroma_host(), get_chroma_port()
		if provider == "openai":
			key_present = bool(get_openai_api_key())
			logger.info("[startup] LLM provider=openai model=%s embedding_model=%s openai_key_present=%s",
				extraction_model, embedding_model, key_present)
		elif provider == "xai":
			# Do not log the API key; only presence and base URL
			key_present = bool(get_openai_api_key())  # placeholder to avoid unused var if refactor; we won't use it
			xai_key_present = bool(os.getenv("XAI_API_KEY"))
			xai_base = get_xai_base_url()
			logger.info("[startup] LLM provider=xai model=%s embedding_model=%s xai_key_present=%s xai_base=%s",
				extraction_model, embedding_model, xai_key_present, xai_base)
		else:
			logger.info("[startup] LLM provider=%s model=%s embedding_model=%s", provider, extraction_model, embedding_model)
		logger.info("[startup] Chroma host=%s port=%s", chroma_host, chroma_port)
	except Exception as _exc:  # pragma: no cover
		logger.info("[startup] config logging failed: %s", _exc)


@app.get("/health")
def health() -> dict:
	return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
@app.get("/v1/me")
def me(identity: Optional[dict] = Depends(get_identity)) -> dict:
    if identity is None:
        return {"authenticated": False}
    # Log key identity parameters for debugging
    logger.info("[auth] Authenticated identity: sub=%s email=%s name=%s aud=%s exp=%s iss=%s",
                identity.get("sub"),
                identity.get("email"),
                identity.get("name") or identity.get("common_name"),
                identity.get("aud"),
                identity.get("exp"),
                identity.get("iss"))
    # Useful fields from CF Access token
    return {
        "authenticated": True,
        "sub": identity.get("sub"),
        "email": identity.get("email"),
        "name": identity.get("name") or identity.get("common_name"),
        "id": identity.get("id"),
        "aud": identity.get("aud"),
        "exp": identity.get("exp"),
        "iss": identity.get("iss"),
    }


@app.get("/health/full")
def health_full() -> dict:
	checks = {}

	# Env check (provider-aware)
	provider = get_llm_provider()
	required_envs = ["OPENAI_API_KEY"] if provider == "openai" else (["XAI_API_KEY"] if provider == "xai" else [])
	missing_envs = [] if is_llm_configured() else required_envs
	checks["env"] = {"required": required_envs, "missing": missing_envs, "provider": provider}

	# ChromaDB check (active heartbeat)
	chroma_ok = False
	chroma_error: Optional[str] = None
	try:
		host = get_chroma_host()
		port = get_chroma_port()
		url = f"http://{host}:{port}/api/v2/heartbeat"
		with httpx.Client(timeout=2.0) as client:
			resp = client.get(url)
			chroma_ok = resp.status_code == 200
	except Exception as exc:  # pragma: no cover
		chroma_error = str(exc)
	checks["chroma"] = {"ok": chroma_ok, "error": chroma_error}

	# Redis check (optional)
	redis_ok = None
	redis_error: Optional[str] = None
	try:
		redis_client = get_redis_client()
		if redis_client is None:
			redis_ok = None  # not configured
		else:
			redis_ok = bool(redis_client.ping())
	except Exception as exc:  # pragma: no cover
		redis_ok = False
		redis_error = str(exc)
	checks["redis"] = {"ok": redis_ok, "error": redis_error}

	overall_ok = chroma_ok and (redis_ok is None or redis_ok) and len(missing_envs) == 0
	return {
		"status": "ok" if overall_ok else "degraded",
		"time": datetime.now(timezone.utc).isoformat(),
		"checks": checks,
	}


@app.post("/v1/store", response_model=StoreResponse)
def store_transcript(body: TranscriptRequest) -> StoreResponse:
	# Guard: enforce LLM configuration
	if not is_llm_configured():
		raise HTTPException(status_code=400, detail="LLM is not configured")
	# Phase 2: Extract memories only (no persistence yet)
	result = extract_from_transcript(body)
	# Phase 3: Persist to ChromaDB
	ids = upsert_memories(body.user_id, result.memories)
	# Bump Redis namespace for this user to invalidate short-term caches
	try:
		redis = get_redis_client()
		if redis is not None:
			redis.incr(f"mem:ns:{body.user_id}")
	except Exception:
		pass
	items = [
		StoreMemoryItem(
			id=ids[i],
			content=m.content,
			layer=m.layer,
			type=m.type,
			confidence=m.confidence,
			ttl=m.ttl,
			timestamp=m.timestamp,
			metadata=m.metadata,
		)
		for i, m in enumerate(result.memories)
	]
	return StoreResponse(
		memories_created=len(ids), 
		ids=ids, 
		summary=result.summary, 
		memories=items,
		duplicates_avoided=result.duplicates_avoided,
		updates_made=result.updates_made,
		existing_memories_checked=result.existing_memories_checked
	)


@app.get("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(
	user_id: str = Query(...),
	query: Optional[str] = Query(default=None, description="Search query (optional - omit to get all memories)"),
	layer: Optional[str] = Query(default=None),
	type: Optional[str] = Query(default=None),
	limit: int = Query(default=10, ge=1, le=50),
	offset: int = Query(default=0, ge=0),
) -> RetrieveResponse:
	filters: dict = {}
	if layer:
		filters["layer"] = layer
	if type:
		filters["type"] = type
	results, total = search_memories(user_id=user_id, query=query or "", filters=filters, limit=limit, offset=offset)  # Phase 4 will enforce auth-derived user_id
	items = [
		RetrieveItem(
			id=r["id"],
			content=r["content"],
			layer=r["metadata"].get("layer", "semantic"),
			type=r["metadata"].get("type", "explicit"),
			score=float(r.get("score", 0.0)),
			metadata=r.get("metadata", {}),
		)
		for r in results
	]
	return RetrieveResponse(results=items, pagination={"limit": limit, "offset": offset, "total": total})


# Advanced structured retrieval endpoint
@app.post("/v1/retrieve/structured", response_model=StructuredRetrieveResponse)
def retrieve_structured(body: StructuredRetrieveRequest) -> StructuredRetrieveResponse:
	if not is_llm_configured():
		raise HTTPException(status_code=400, detail="LLM is not configured")

	# Pull ALL memories for the user (paginate with empty query)
	all_results: List[dict] = []
	batch_limit = max(100, body.limit)
	offset = 0
	while True:
		batch, _ = search_memories(user_id=body.user_id, query="", filters={}, limit=batch_limit, offset=offset)
		if not batch:
			break
		all_results.extend(batch)
		if len(batch) < batch_limit:
			break
		offset += batch_limit

	# Map candidates into a lightweight payload
	candidates = [
		{
			"id": r["id"],
			"content": r["content"],
			"metadata": r.get("metadata", {}),
			"score": float(r.get("score", 0.0)),
		}
		for r in all_results
	]

	SYSTEM_PROMPT = (
		"You are a retrieval organizer for a personal memory system.\n"
		"You will be given an optional user query and ALL candidate memories for that user.\n"
		"If the query is present, select and categorize the most relevant memories into these buckets: \n"
		"- emotions\n- behaviors\n- personal\n- professional\n- habits\n- skills_tools\n- projects\n- relationships\n- learning_journal\n- other\n"
		"If the query is empty, categorize candidates into the buckets based on their content and metadata (do not drop items unless they fit nowhere; use 'other').\n"
		"Return strict JSON with keys exactly as above. For each key, return an array of memory ids from the candidates (do not invent ids).\n"
		"Favor precision but include relevant context. Do not exceed 25 items per category."
	)
	payload = {"query": (body.query or ""), "candidates": candidates}
	resp = _call_llm_json(SYSTEM_PROMPT, payload)
	if not isinstance(resp, dict):
		resp = {}

	# Helper to map ids -> RetrieveItem
	id_to_item = {r["id"]: r for r in all_results}
	def build_items(id_list: List[str]) -> List[RetrieveItem]:
		items: List[RetrieveItem] = []
		for _id in id_list or []:
			src = id_to_item.get(_id)
			if not src:
				continue
			items.append(
				RetrieveItem(
					id=src["id"],
					content=src["content"],
					layer=src["metadata"].get("layer", "semantic"),
					type=src["metadata"].get("type", "explicit"),
					score=float(src.get("score", 0.0)),
					#metadata=src.get("metadata", {}),
				)
			)
		return items

	return StructuredRetrieveResponse(
		emotions=build_items(list(resp.get("emotions", []))),
		behaviors=build_items(list(resp.get("behaviors", []))),
		personal=build_items(list(resp.get("personal", []))),
		professional=build_items(list(resp.get("professional", []))),
		habits=build_items(list(resp.get("habits", []))),
		skills_tools=build_items(list(resp.get("skills_tools", []))),
		projects=build_items(list(resp.get("projects", []))),
		relationships=build_items(list(resp.get("relationships", []))),
		learning_journal=build_items(list(resp.get("learning_journal", []))),
		other=build_items(list(resp.get("other", []))),
	)


@app.post("/v1/forget")
def forget(body: ForgetRequest) -> dict:
	return {"jobs_enqueued": ["ttl_cleanup", "promotion"], "dry_run": body.dry_run}


@app.post("/v1/maintenance", response_model=MaintenanceResponse)
def maintenance(body: MaintenanceRequest) -> MaintenanceResponse:
	return MaintenanceResponse(jobs_started=body.jobs or ["compaction"], status="running")
