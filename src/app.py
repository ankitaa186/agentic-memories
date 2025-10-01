from datetime import datetime, timezone
import logging
import os
from typing import List, Optional
import json

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
    PortfolioSummaryResponse,
    FinanceAggregate,
    FinanceGoal,
)
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_openai_api_key, get_chroma_host, get_chroma_port, is_llm_configured, get_llm_provider, is_scheduled_maintenance_enabled
from src.config import get_extraction_model_name, get_embedding_model_name
from src.config import get_xai_base_url
import httpx
from src.services.extraction import extract_from_transcript
from src.services.storage import upsert_memories
from src.services.retrieval import search_memories
from src.services.extract_utils import _call_llm_json
from src.dependencies.cloudflare_access import verify_cf_access_token, extract_token_from_headers
from src.dependencies.redis_client import get_redis_client
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None  # type: ignore
from datetime import datetime as _dt, timezone as _tz
from src.services.forget import run_compaction_for_user

app = FastAPI(title="Agentic Memories API", version="0.1.0")
# Scheduler: daily midnight UTC compaction trigger (conditional on recent activity)
_scheduler: Optional[BackgroundScheduler] = None

def _run_daily_compaction() -> None:
    r = get_redis_client()
    if r is None:
        logger.info("[maint.compaction] skipped: redis unavailable")
        return
    # Look at yesterday's activity set
    day_key = (_dt.now(_tz.utc)).strftime("%Y%m%d")
    # Run for yesterday too in case of clock skew
    keys = [f"recent_users:{day_key}"]
    users: set[str] = set()
    for k in keys:
        try:
            members = r.smembers(k) or []
            users.update(members)
        except Exception as exc:
            logger.info("[maint.compaction] failed to read %s: %s", k, exc)
    if not users:
        logger.info("[maint.compaction] no active users in last 24h")
        return
    # TODO: enqueue compaction graph per user (placeholder log)
    for uid in sorted(users):
        try:
            stats = run_compaction_for_user(uid)
            logger.info("[maint.compaction.done] user_id=%s stats=%s", uid, stats)
        except Exception as exc:
            logger.info("[maint.compaction.error] user_id=%s %s", uid, exc)

def _start_scheduler() -> None:
    global _scheduler
    try:
        if _scheduler is None and is_scheduled_maintenance_enabled() and BackgroundScheduler is not None:
            _scheduler = BackgroundScheduler(timezone="UTC")  # type: ignore
            _scheduler.add_job(_run_daily_compaction, "cron", hour=0, minute=0, id="daily_compaction")
            _scheduler.start()
            logger.info("[sched] started APScheduler with daily compaction job at 00:00 UTC")
        elif _scheduler is None:
            if not is_scheduled_maintenance_enabled():
                logger.info("[sched] disabled via env; not starting scheduler")
            else:
                logger.info("[sched] APScheduler not installed; scheduled jobs disabled")
    except Exception as exc:
        logger.info("[sched] failed to start: %s", exc)

@app.on_event("startup")
def _on_startup() -> None:
    _start_scheduler()
logger = logging.getLogger("agentic_memories.api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(_handler)
_level_name = getenv("LOG_LEVEL", "INFO").upper()
try:
    _level = getattr(logging, _level_name, logging.INFO)
except Exception:
    _level = logging.INFO
logger.setLevel(_level)
logger.propagate = True

# Root logger fallback (so module loggers without handlers still emit)
_root = logging.getLogger()
if not _root.handlers:
    _root_handler = logging.StreamHandler()
    _root_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _root.addHandler(_root_handler)
    _root.setLevel(_level)

# Request/response logging middleware (minimal, no bodies)
import time as _time

@app.middleware("http")
async def _log_requests(request: Request, call_next):
    start = _time.perf_counter()
    path = request.url.path
    method = request.method
    client = request.client.host if request.client else "-"
    try:
        response = await call_next(request)
        status = getattr(response, "status_code", 200)
    except Exception as exc:  # pragma: no cover
        elapsed_ms = int(((_time.perf_counter() - start) * 1000))
        logger.exception("[http] %s %s error=%s client=%s latency_ms=%s", method, path, exc.__class__.__name__, client, elapsed_ms)
        raise
    elapsed_ms = int(((_time.perf_counter() - start) * 1000))
    logger.info("[http] %s %s status=%s client=%s latency_ms=%s", method, path, status, client, elapsed_ms)
    return response
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
		with httpx.Client(timeout=180.0) as client:
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
			# Record daily activity for compaction trigger (UTC date key)
			day_key = datetime.now(timezone.utc).strftime("%Y%m%d")
			redis.sadd(f"recent_users:{day_key}", body.user_id)
			# Also track all users set
			redis.sadd("all_users", body.user_id)
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
	# Build finance aggregate (lightweight) from current page results
	fin_holdings: List[dict] = []
	counts_by_asset_type: dict[str, int] = {}
	goals: List[FinanceGoal] = []
	for r in results:
		meta = r.get("metadata", {})
		p = meta.get("portfolio")
		try:
			if isinstance(p, str):
				p = json.loads(p)
		except Exception:
			p = None
		if isinstance(p, dict):
			base = {
				"asset_type": None,
				"ticker": p.get("ticker"),
				"name": None,
				"shares": p.get("shares"),
				"avg_price": p.get("avg_price"),
				"position": p.get("position"),
				"intent": p.get("intent"),
				"target_price": p.get("target_price"),
				"stop_loss": p.get("stop_loss"),
				"time_horizon": p.get("time_horizon"),
				"notes": p.get("notes"),
				"source_memory_id": r.get("id"),
				"updated_at": meta.get("timestamp"),
			}
			h = p.get("holdings")
			if isinstance(h, list) and h:
				for one in h:
					if not isinstance(one, dict):
						continue
					row = {
						**base,
						"asset_type": one.get("asset_type"),
						"ticker": one.get("ticker") or base.get("ticker"),
						"name": one.get("name"),
						"shares": one.get("shares", base.get("shares")),
						"avg_price": one.get("avg_price", base.get("avg_price")),
						"ownership_pct": one.get("ownership_pct"),
					}
					fin_holdings.append(row)
					at = row.get("asset_type") or "unknown"
					counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1
			else:
				if base.get("ticker") or base.get("shares"):
					fin_holdings.append(base)
					at = base.get("asset_type") or ("public_equity" if base.get("ticker") else "unknown")
					counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1

		# Extract finance goals hints from tags or content
		tags_json = meta.get("tags")
		tags: List[str] = []
		try:
			if isinstance(tags_json, str):
				tags = json.loads(tags_json)
			elif isinstance(tags_json, list):
				tags = [str(t) for t in tags_json]
		except Exception:
			tags = []
		if any(t for t in tags if t.startswith("ticker:")) or "finance" in tags:
			goals.append(FinanceGoal(text=r.get("content", ""), source_memory_id=r.get("id")))

	finance_agg = FinanceAggregate(
		portfolio=PortfolioSummaryResponse(user_id=user_id, holdings=fin_holdings, counts_by_asset_type=counts_by_asset_type),
		goals=goals,
	) if (fin_holdings or goals) else None

	return RetrieveResponse(results=items, pagination={"limit": limit, "offset": offset, "total": total}, finance=finance_agg)


# Advanced structured retrieval endpoint
@app.post("/v1/retrieve/structured", response_model=StructuredRetrieveResponse)
def retrieve_structured(body: StructuredRetrieveRequest) -> StructuredRetrieveResponse:
	if not is_llm_configured():
		raise HTTPException(status_code=400, detail="LLM is not configured")

	# Pull ALL memories for the user (paginate with empty query)
	all_results: List[dict] = []
	batch_limit = max(10000, body.limit)
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

	SYSTEM_PROMPT = """
	You are a retrieval organizer for a personal memory system.
	You will be given an optional user query and ALL candidate memories for that user.
	If the query is present, select and categorize the most relevant memories into these buckets: 
	- emotions
	- behaviors
	- personal
	- professional
	- habits
	- skills_tools
	- projects
	- relationships
	- learning_journal
	- other
	Additionally, build a finance aggregate that summarizes portfolio holdings and finance goals if present.
	Finance aggregate JSON schema (keys): {"portfolio_ids": string[], "goal_ids": string[]}.
	- portfolio_ids: ids of memories containing metadata.portfolio or tags including 'ticker:'
	- goal_ids: ids of memories describing finance goals, risk tolerance, targets, watchlists.
	If the query is empty, categorize candidates into the buckets based on their content and metadata (do not drop items unless they fit nowhere; use 'other').
	Return strict JSON with keys exactly as above PLUS a top-level key 'finance' with shape {portfolio_ids:[], goal_ids:[]}. For each category key, return an array of memory ids from the candidates (do not invent ids).
	Favor precision but include relevant context. Do not exceed 25 items per category.
	"""

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

	# Build finance aggregate from ids if present
	fin_ids = (resp.get("finance") or {}) if isinstance(resp, dict) else {}
	portfolio_ids = list(fin_ids.get("portfolio_ids", [])) if isinstance(fin_ids, dict) else []
	goal_ids = list(fin_ids.get("goal_ids", [])) if isinstance(fin_ids, dict) else []

	id_to_item2 = {r["id"]: r for r in all_results}
	# Portfolio holdings summary from selected ids
	fin_holdings2: List[dict] = []
	counts_by_asset_type2: dict[str, int] = {}
	for _id in portfolio_ids:
		src = id_to_item2.get(_id) or {}
		meta = src.get("metadata", {})
		p = meta.get("portfolio")
		try:
			if isinstance(p, str):
				p = json.loads(p)
		except Exception:
			p = None
		if isinstance(p, dict):
			base = {
				"asset_type": None,
				"ticker": p.get("ticker"),
				"name": None,
				"shares": p.get("shares"),
				"avg_price": p.get("avg_price"),
				"position": p.get("position"),
				"intent": p.get("intent"),
				"target_price": p.get("target_price"),
				"stop_loss": p.get("stop_loss"),
				"time_horizon": p.get("time_horizon"),
				"notes": p.get("notes"),
				"source_memory_id": src.get("id"),
				"updated_at": meta.get("timestamp"),
			}
			h = p.get("holdings")
			if isinstance(h, list) and h:
				for one in h:
					if not isinstance(one, dict):
						continue
					row = {
						**base,
						"asset_type": one.get("asset_type"),
						"ticker": one.get("ticker") or base.get("ticker"),
						"name": one.get("name"),
						"shares": one.get("shares", base.get("shares")),
						"avg_price": one.get("avg_price", base.get("avg_price")),
						"ownership_pct": one.get("ownership_pct"),
					}
					fin_holdings2.append(row)
					at = row.get("asset_type") or "unknown"
					counts_by_asset_type2[at] = counts_by_asset_type2.get(at, 0) + 1
			else:
				if base.get("ticker") or base.get("shares"):
					fin_holdings2.append(base)
					at = base.get("asset_type") or ("public_equity" if base.get("ticker") else "unknown")
					counts_by_asset_type2[at] = counts_by_asset_type2.get(at, 0) + 1

	goals_items: List[RetrieveItem] = []
	for _id in goal_ids:
		src = id_to_item2.get(_id)
		if not src:
			continue
		goals_items.append(
			RetrieveItem(
				id=src["id"],
				content=src["content"],
				layer=src["metadata"].get("layer", "semantic"),
				type=src["metadata"].get("type", "explicit"),
				score=float(src.get("score", 0.0)),
			)
		)

	finance_agg2 = FinanceAggregate(
		portfolio=PortfolioSummaryResponse(user_id=body.user_id, holdings=fin_holdings2, counts_by_asset_type=counts_by_asset_type2),
		goals=[FinanceGoal(text=i.content, source_memory_id=i.id) for i in goals_items],
	) if (portfolio_ids or goal_ids) else None

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
		finance=finance_agg2,
	)


@app.post("/v1/forget")
def forget(body: ForgetRequest) -> dict:
	return {"jobs_enqueued": ["ttl_cleanup", "promotion"], "dry_run": body.dry_run}


@app.post("/v1/maintenance", response_model=MaintenanceResponse)
def maintenance(body: MaintenanceRequest) -> MaintenanceResponse:
    jobs = body.jobs or ["compaction"]
    if "compaction" in jobs:
        try:
            _run_daily_compaction()
        except Exception as exc:
            logger.info("[maint.api] compaction trigger failed: %s", exc)
    return MaintenanceResponse(jobs_started=jobs, status="running")


@app.get("/v1/portfolio/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary(user_id: str = Query(...), limit: int = Query(default=200, ge=1, le=1000)) -> PortfolioSummaryResponse:
    # Fetch a broad set of finance-related memories and aggregate portfolio metadata
    # Strategy: pull without query to get all, then filter client-side for metadata.portfolio
    # Pagination in chunks to cover more items than default limits
    all_results: List[dict] = []
    offset = 0
    batch_limit = min(200, limit)
    while len(all_results) < limit:
        batch, _ = search_memories(user_id=user_id, query="", filters={}, limit=batch_limit, offset=offset)
        if not batch:
            break
        all_results.extend(batch)
        if len(batch) < batch_limit:
            break
        offset += batch_limit

    # Aggregate holdings
    holdings: List[dict] = []
    counts_by_asset_type: dict[str, int] = {}
    for item in all_results:
        meta = item.get("metadata") or {}
        portfolio_raw = meta.get("portfolio")
        try:
            # Handle JSON-string serialized fields
            if isinstance(portfolio_raw, str):
                portfolio = json.loads(portfolio_raw)
            else:
                portfolio = portfolio_raw
        except Exception:
            portfolio = None
        if not portfolio or not isinstance(portfolio, dict):
            continue

        base = {
            "asset_type": None,
            "ticker": portfolio.get("ticker"),
            "name": None,
            "shares": portfolio.get("shares"),
            "avg_price": portfolio.get("avg_price"),
            "current_value": portfolio.get("current_value"),
            "cost_basis": portfolio.get("cost_basis"),
            "ownership_pct": portfolio.get("ownership_pct"),
            "position": portfolio.get("position"),
            "intent": portfolio.get("intent"),
            "target_price": portfolio.get("target_price"),
            "stop_loss": portfolio.get("stop_loss"),
            "time_horizon": portfolio.get("time_horizon"),
            "notes": portfolio.get("notes"),
            "source_memory_id": item.get("id"),
            "updated_at": meta.get("timestamp"),
        }

        # If holdings array exists, expand it; otherwise treat base as a single holding (if ticker or shares present)
        hlist = portfolio.get("holdings")
        if isinstance(hlist, list) and hlist:
            for h in hlist:
                if not isinstance(h, dict):
                    continue
                row = {
                    **base,
                    "asset_type": h.get("asset_type"),
                    "ticker": h.get("ticker") or base.get("ticker"),
                    "name": h.get("name"),
                    "shares": h.get("shares", base.get("shares")),
                    "avg_price": h.get("avg_price", base.get("avg_price")),
                    "current_value": h.get("current_value", base.get("current_value")),
                    "cost_basis": h.get("cost_basis", base.get("cost_basis")),
                    "ownership_pct": h.get("ownership_pct", base.get("ownership_pct")),
                    "notes": h.get("notes", base.get("notes")),
                }
                holdings.append(row)
                at = row.get("asset_type") or "unknown"
                counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1
        else:
            if base.get("ticker") or base.get("shares"):
                holdings.append(base)
                at = base.get("asset_type") or ("public_equity" if base.get("ticker") else "unknown")
                counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1

    # Sort holdings by ticker then name for stable output
    holdings.sort(key=lambda x: (str(x.get("ticker") or ""), str(x.get("name") or "")))

    # Shape into response model
    # Note: Pydantic will coerce the list of dicts into PortfolioHolding items
    return PortfolioSummaryResponse(user_id=user_id, holdings=holdings[:limit], counts_by_asset_type=counts_by_asset_type)


@app.post("/v1/maintenance/compact_all", response_model=MaintenanceResponse)
def compact_all_users() -> MaintenanceResponse:
    r = get_redis_client()
    users: List[str] = []
    try:
        if r is not None:
            users = list(r.smembers("all_users") or [])
    except Exception as exc:
        logger.info("[maint.compact_all] failed to read all_users: %s", exc)
    if not users:
        logger.info("[maint.compact_all] no users found")
        return MaintenanceResponse(jobs_started=["compaction-none"], status="running")
    for uid in sorted(users):
        try:
            stats = run_compaction_for_user(uid)
            logger.info("[maint.compaction.done] user_id=%s (manual) stats=%s", uid, stats)
        except Exception as exc:
            logger.info("[maint.compaction.error] user_id=%s (manual) %s", uid, exc)
    return MaintenanceResponse(jobs_started=["compaction_all"], status="running")
