from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from zoneinfo import ZoneInfo
import os
from typing import Any, Dict, List, Optional
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
    OrchestratorMessageRequest,
    OrchestratorStreamResponse,
    OrchestratorTranscriptResponse,
    OrchestratorRetrieveRequest,
    OrchestratorRetrieveResponse,
    MemoryInjectionPayload,
    StructuredRetrieveRequest,
    StructuredRetrieveResponse,
    PortfolioSummaryResponse,
    FinanceAggregate,
    FinanceGoal,
    NarrativeRequest,
    NarrativeResponse,
    PersonaRetrieveRequest,
    PersonaRetrieveResponse,
    PersonaRetrieveResults,
    PersonaSelection,
    PersonaExplainability,
)
from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import ping_timescale
from src.dependencies.redis_client import get_redis_client
from src.config import (
    get_openai_api_key,
    get_chroma_host,
    get_chroma_port,
    is_llm_configured,
    get_llm_provider,
    is_scheduled_maintenance_enabled,
)
from src.config import get_extraction_model_name, get_embedding_model_name
from src.config import get_xai_base_url, get_chroma_tenant, get_chroma_database
import httpx
from src.services.reconstruction import ReconstructionService
from src.services.retrieval import search_memories, _standard_collection_name as _standard_collection_name  # noqa: F401 — used by test monkeypatch
from src.services.extract_utils import _call_llm_json
from src.dependencies.cloudflare_access import (
    verify_cf_access_token,
    extract_token_from_headers,
)
from src.memory_orchestrator import (
    AdaptiveMemoryOrchestrator,
    MessageEvent,
    MessageRole,
    MemoryInjection,
)
from src.services.chat_runtime import ChatRuntimeBridge

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None  # type: ignore
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
from src.services.forget import run_compaction_for_user
from src.services.persona_retrieval import PersonaCoPilot
from src.routers import profile, portfolio, intents, memories

# LLM connectivity cache (avoid hitting external API on every health check)
_llm_cache: Dict[str, Any] = {
    "ok": None,
    "error": None,
    "endpoint": None,
    "checked_at": None,
}
_LLM_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_llm_check() -> Optional[Dict[str, Any]]:
    """Return cached LLM check if still valid, None otherwise."""
    if _llm_cache["checked_at"] is None:
        return None
    age = (datetime.now(timezone.utc) - _llm_cache["checked_at"]).total_seconds()
    if age < _LLM_CACHE_TTL_SECONDS:
        return {
            "ok": _llm_cache["ok"],
            "error": _llm_cache["error"],
            "endpoint": _llm_cache["endpoint"],
            "cached": True,
            "cache_age_seconds": int(age),
        }
    return None


def _update_llm_cache(
    ok: Optional[bool], error: Optional[str], endpoint: Optional[str]
) -> None:
    """Update LLM connectivity cache."""
    _llm_cache["ok"] = ok
    _llm_cache["error"] = error
    _llm_cache["endpoint"] = endpoint
    _llm_cache["checked_at"] = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Check LLM configuration
    if not is_llm_configured():
        raise RuntimeError(
            "LLM not configured. Set LLM_PROVIDER and corresponding API key."
        )

    # Startup: Log configuration
    try:
        provider = get_llm_provider()
        extraction_model = get_extraction_model_name()
        embedding_model = get_embedding_model_name()
        chroma_host, chroma_port = get_chroma_host(), get_chroma_port()
        if provider == "openai":
            key_present = bool(get_openai_api_key())
            logging.getLogger("agentic_memories.api").info(
                "[startup] LLM provider=openai model=%s embedding_model=%s openai_key_present=%s",
                extraction_model,
                embedding_model,
                key_present,
            )
        elif provider == "xai":
            from src.config import get_xai_api_key

            key_present = bool(get_xai_api_key())
            base_url = get_xai_base_url()
            logging.getLogger("agentic_memories.api").info(
                "[startup] LLM provider=xai model=%s embedding_model=%s xai_key_present=%s base_url=%s",
                extraction_model,
                embedding_model,
                key_present,
                base_url,
            )
        logging.getLogger("agentic_memories.api").info(
            "[startup] ChromaDB=%s:%s", chroma_host, chroma_port
        )
    except Exception as exc:
        logging.getLogger("agentic_memories.api").warning(
            "[startup] config log error: %s", exc
        )

    # Startup: Check Chroma connectivity
    logging.getLogger("agentic_memories.api").info("Starting Agentic Memories API...")
    try:
        client = get_chroma_client()
        if client is None:
            logging.getLogger("agentic_memories.api").warning(
                "Chroma client not available - some features may not work"
            )
        else:
            collections = client.list_collections()
            logging.getLogger("agentic_memories.api").info(
                f"Chroma connected. Collections: {len(collections)}"
            )
    except Exception as e:
        logging.getLogger("agentic_memories.api").warning(
            f"Chroma connection warning: {e}"
        )

    # Startup: Start scheduler
    _start_scheduler()

    yield

    # Shutdown: Close memory orchestrator
    await _memory_orchestrator.shutdown()


app = FastAPI(title="Agentic Memories API", version="0.1.0", lifespan=lifespan)

# Include routers
app.include_router(profile.router)
app.include_router(portfolio.router)
app.include_router(intents.router)
app.include_router(memories.router)
# Scheduler: daily midnight UTC compaction trigger (conditional on recent activity)
_scheduler: Optional[BackgroundScheduler] = None


def _run_daily_compaction() -> None:
    r = get_redis_client()
    if r is None:
        logger.info("[maint.compaction] skipped: redis unavailable")
        return

    # Use Redis Lock object for safe distributed locking
    # - blocking=False: Don't wait if lock is held
    # - timeout: Lock auto-expires if holder crashes
    # - Lock.release() uses Lua script to atomically verify ownership
    lock_key = "compaction_lock:daily"
    lock_ttl = 3600  # 1 hour max lock duration
    worker_id = f"worker-{os.getpid()}"

    lock = r.lock(lock_key, timeout=lock_ttl, blocking=False)
    acquired = lock.acquire()
    if not acquired:
        logger.info("[maint.compaction] skipped: another worker holds lock")
        return

    logger.info("[maint.compaction] lock acquired by %s", worker_id)

    try:
        _execute_compaction(r)
    finally:
        try:
            lock.release()
            logger.info("[maint.compaction] lock released by %s", worker_id)
        except Exception as release_err:
            # Lock may have expired - that's OK, just log it
            logger.info(
                "[maint.compaction] lock release skipped (may have expired): %s",
                release_err,
            )


def _execute_compaction(r) -> None:
    """Execute the actual compaction logic."""
    # Look at yesterday's activity set (the day we intend to compact)
    now = _dt.now(_tz.utc)
    day_key = (now - _td(days=1)).strftime("%Y%m%d")
    keys = [f"recent_users:{day_key}"]
    # Also include today's key so retries pick up any missed users
    today_key = now.strftime("%Y%m%d")
    if today_key != day_key:
        keys.append(f"recent_users:{today_key}")
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
        if (
            _scheduler is None
            and is_scheduled_maintenance_enabled()
            and BackgroundScheduler is not None
        ):
            _scheduler = BackgroundScheduler(timezone="UTC")  # type: ignore
            _scheduler.add_job(
                _run_daily_compaction, "cron", hour=0, minute=0, id="daily_compaction"
            )
            _scheduler.start()
            logger.info(
                "[sched] started APScheduler with daily compaction job at 00:00 UTC"
            )
        elif _scheduler is None:
            if not is_scheduled_maintenance_enabled():
                logger.info("[sched] disabled via env; not starting scheduler")
            else:
                logger.info(
                    "[sched] APScheduler not installed; scheduled jobs disabled"
                )
    except Exception as exc:
        logger.info("[sched] failed to start: %s", exc)


# Startup and shutdown events moved to lifespan context manager


# Custom formatter to use America/Los_Angeles timezone
class LATimezoneFormatter(logging.Formatter):
    """Formatter that converts timestamps to America/Los_Angeles timezone."""

    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.tz = ZoneInfo("America/Los_Angeles")

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


logger = logging.getLogger("agentic_memories.api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        LATimezoneFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
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
    _root_handler.setFormatter(
        LATimezoneFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    _root.addHandler(_root_handler)
    _root.setLevel(_level)

# Memory orchestrator services
_memory_orchestrator = AdaptiveMemoryOrchestrator()
_chat_runtime_bridge = ChatRuntimeBridge(_memory_orchestrator)


def _serialize_injection(injection: MemoryInjection) -> MemoryInjectionPayload:
    metadata = {
        str(key): str(value) for key, value in (injection.metadata or {}).items()
    }
    return MemoryInjectionPayload(
        memory_id=injection.memory_id,
        content=injection.content,
        source=injection.source.value,
        channel=injection.channel.value,
        score=injection.score,
        metadata=metadata,
    )


# Services
_reconstruction = ReconstructionService()
_persona_copilot = PersonaCoPilot()

# Request/response logging middleware (minimal, no bodies)
import time as _time  # noqa: E402


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
        logger.exception(
            "[http] %s %s error=%s client=%s latency_ms=%s",
            method,
            path,
            exc.__class__.__name__,
            client,
            elapsed_ms,
        )
        raise
    elapsed_ms = int(((_time.perf_counter() - start) * 1000))
    logger.info(
        "[http] %s %s status=%s client=%s latency_ms=%s",
        method,
        path,
        status,
        client,
        elapsed_ms,
    )
    return response


@app.post("/v1/orchestrator/message", response_model=OrchestratorStreamResponse)
async def stream_orchestrator_message(
    body: OrchestratorMessageRequest,
) -> OrchestratorStreamResponse:
    """Stream a single chat message through the adaptive orchestrator."""

    captured: List[MemoryInjection] = []

    def _listener(injection: MemoryInjection) -> None:
        captured.append(injection)

    subscription = _memory_orchestrator.subscribe_injections(
        _listener, conversation_id=body.conversation_id
    )
    try:
        timestamp = body.timestamp or datetime.now(timezone.utc)
        event = MessageEvent(
            conversation_id=body.conversation_id,
            message_id=body.message_id,
            role=MessageRole(body.role),
            content=body.content,
            timestamp=timestamp,
            metadata=dict(body.metadata or {}),
        )
        await _memory_orchestrator.stream_message(event)
        if body.flush:
            await _memory_orchestrator.flush()
    finally:
        subscription.close()

    return OrchestratorStreamResponse(
        injections=[_serialize_injection(item) for item in captured]
    )


@app.post("/v1/orchestrator/retrieve", response_model=OrchestratorRetrieveResponse)
async def fetch_orchestrator_memories(
    body: OrchestratorRetrieveRequest,
) -> OrchestratorRetrieveResponse:
    """Return memory injections for a conversation without streaming a new turn."""

    metadata = {str(key): str(value) for key, value in (body.metadata or {}).items()}
    injections = await _memory_orchestrator.fetch_memories(
        conversation_id=body.conversation_id,
        query=body.query,
        metadata=metadata,
        limit=body.limit,
        offset=body.offset,
    )

    return OrchestratorRetrieveResponse(
        injections=[_serialize_injection(item) for item in injections]
    )


@app.post("/v1/orchestrator/transcript", response_model=OrchestratorTranscriptResponse)
async def stream_orchestrator_transcript(
    body: TranscriptRequest,
) -> OrchestratorTranscriptResponse:
    """Ingest a transcript via the orchestrator and return emitted memories."""

    injections = await _chat_runtime_bridge.run_with_injections(body)
    return OrchestratorTranscriptResponse(
        injections=[_serialize_injection(item) for item in injections]
    )


def _convert_to_retrieve_items(raw_items: List[Dict[str, Any]]) -> List[RetrieveItem]:
    items: List[RetrieveItem] = []
    for r in raw_items:
        meta = r.get("metadata", {}) if isinstance(r, dict) else {}
        if not isinstance(meta, dict):
            meta = {"raw": meta}
        persona_tags = r.get("persona_tags") if isinstance(r, dict) else None
        if isinstance(persona_tags, str):
            try:
                persona_tags = json.loads(persona_tags)
            except Exception:
                persona_tags = []
        elif not isinstance(persona_tags, list):
            persona_tags = (
                meta.get("persona_tags")
                if isinstance(meta.get("persona_tags"), list)
                else None
            )
        emotional_signature = (
            r.get("emotional_signature") if isinstance(r, dict) else None
        )
        if isinstance(emotional_signature, str):
            try:
                emotional_signature = json.loads(emotional_signature)
            except Exception:
                emotional_signature = {}
        elif not isinstance(emotional_signature, dict):
            candidate = meta.get("emotional_signature")
            emotional_signature = candidate if isinstance(candidate, dict) else None
        importance = r.get("importance") if isinstance(r, dict) else None
        if importance is None and isinstance(meta.get("importance"), (int, float)):
            importance = meta.get("importance")
        try:
            importance_val = float(importance) if importance is not None else None
        except Exception:
            importance_val = None
        item = RetrieveItem(
            id=str(r.get("id", "")) if isinstance(r, dict) else "",
            content=r.get("content") if isinstance(r, dict) else "",
            layer=meta.get("layer", "semantic"),
            type=meta.get("type", "explicit"),
            score=float(r.get("score", 0.0)) if isinstance(r, dict) else 0.0,
            metadata=meta,
            importance=importance_val,
            persona_tags=persona_tags if isinstance(persona_tags, list) else None,
            emotional_signature=emotional_signature
            if isinstance(emotional_signature, dict)
            else None,
        )
        items.append(item)
    return items


# Chroma connectivity check moved to lifespan context manager
# Auth dependency: validate Cloudflare Access JWT if provided
def get_identity(
    cf_access_jwt_assertion: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    cf_authorization_cookie: Optional[str] = Cookie(
        default=None, alias="CF_Authorization"
    ),
    cf_authorization_cookie_lower: Optional[str] = Cookie(
        default=None, alias="cf_authorization"
    ),
    request: Request = None,
) -> Optional[dict]:
    # Debug: log cookies reaching the API (redacted)
    try:
        cookie_preview = {
            k: (v[:12] + f"...({len(v)}B)") for k, v in (request.cookies or {}).items()
        }
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
    allow_origins=allow_origins
    + ["http://localhost:8080", "http://127.0.0.1:8080", "https://memoryforge.io"],
    allow_origin_regex=LAN_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# LLM configuration check moved to lifespan context manager


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/me")
def me(identity: Optional[dict] = Depends(get_identity)) -> dict:
    if identity is None:
        return {"authenticated": False}
    # Log key identity parameters for debugging
    logger.info(
        "[auth] Authenticated identity: sub=%s email=%s name=%s aud=%s exp=%s iss=%s",
        identity.get("sub"),
        identity.get("email"),
        identity.get("name") or identity.get("common_name"),
        identity.get("aud"),
        identity.get("exp"),
        identity.get("iss"),
    )
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
    required_envs = (
        ["OPENAI_API_KEY"]
        if provider == "openai"
        else (["XAI_API_KEY"] if provider == "xai" else [])
    )
    missing_envs = [] if is_llm_configured() else required_envs
    checks["env"] = {
        "required": required_envs,
        "missing": missing_envs,
        "provider": provider,
    }

    # ChromaDB check (active heartbeat)
    chroma_ok = False
    chroma_error: Optional[str] = None
    chroma_host = get_chroma_host()
    chroma_port = get_chroma_port()
    try:
        url = f"http://{chroma_host}:{chroma_port}/api/v2/heartbeat"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            chroma_ok = resp.status_code == 200
    except Exception as exc:  # pragma: no cover
        chroma_error = str(exc)
    checks["chroma"] = {"ok": chroma_ok, "error": chroma_error}

    # ChromaDB collections check (use configured tenant/database)
    collections_ok = False
    collections_error: Optional[str] = None
    collections_list: List[str] = []
    chroma_tenant = get_chroma_tenant()
    chroma_db = get_chroma_database()
    try:
        if chroma_ok:
            url = f"http://{chroma_host}:{chroma_port}/api/v2/tenants/{chroma_tenant}/databases/{chroma_db}/collections"
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    cols = resp.json()
                    collections_list = (
                        [c.get("name", "") for c in cols]
                        if isinstance(cols, list)
                        else []
                    )
                    # Check for any memories collection (dimension-specific naming)
                    collections_ok = any(
                        c.startswith("memories_") for c in collections_list
                    )
                    if not collections_ok and collections_list:
                        collections_error = "No memories_* collection found"
                    elif not collections_list:
                        collections_error = "No collections exist"
                else:
                    collections_error = f"HTTP {resp.status_code}"
    except Exception as exc:
        collections_error = str(exc)
    checks["chroma_collections"] = {
        "ok": collections_ok,
        "error": collections_error,
        "collections": collections_list,
        "tenant": chroma_tenant,
        "database": chroma_db,
    }

    # Timescale/Postgres check
    ts_ok = False
    ts_error: Optional[str] = None
    try:
        ts_ok, ts_error = ping_timescale()
    except Exception as exc:  # pragma: no cover
        ts_ok = False
        ts_error = str(exc)
    checks["timescale"] = {"ok": ts_ok, "error": ts_error}

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

    # Database tables check (all critical tables in one query)
    from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

    conn = None
    all_tables: List[str] = []
    try:
        conn = get_timescale_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
					SELECT table_name FROM information_schema.tables
					WHERE table_schema = 'public'
					ORDER BY table_name
				""")
                all_tables = [row["table_name"] for row in cur.fetchall()]
    except Exception:
        pass  # Individual checks will report errors

    # Memory tables check (core)
    memory_tables_required = [
        "episodic_memories",
        "emotional_memories",
        "procedural_memories",
    ]
    memory_tables_found = [t for t in memory_tables_required if t in all_tables]
    memory_tables_ok = len(memory_tables_found) == len(memory_tables_required)
    memory_tables_missing = list(set(memory_tables_required) - set(memory_tables_found))
    checks["memory_tables"] = {
        "ok": memory_tables_ok,
        "error": f"Missing: {memory_tables_missing}" if memory_tables_missing else None,
        "tables": memory_tables_found,
    }

    # Intents tables check (Epic 6)
    intents_tables_required = ["scheduled_intents", "intent_executions"]
    intents_tables_found = [t for t in intents_tables_required if t in all_tables]
    intents_tables_ok = len(intents_tables_found) == len(intents_tables_required)
    intents_tables_missing = list(
        set(intents_tables_required) - set(intents_tables_found)
    )
    checks["intents_tables"] = {
        "ok": intents_tables_ok,
        "error": f"Missing: {intents_tables_missing}"
        if intents_tables_missing
        else None,
        "tables": intents_tables_found,
    }

    # Profile tables check
    profile_tables_required = [
        "user_profiles",
        "profile_fields",
        "profile_confidence_scores",
        "profile_sources",
    ]
    profile_tables_found = [t for t in profile_tables_required if t in all_tables]
    profile_tables_ok = len(profile_tables_found) == len(profile_tables_required)
    profile_tables_missing = list(
        set(profile_tables_required) - set(profile_tables_found)
    )
    checks["profile_tables"] = {
        "ok": profile_tables_ok,
        "error": f"Missing: {profile_tables_missing}"
        if profile_tables_missing
        else None,
        "tables": profile_tables_found,
    }

    # Portfolio tables check (Postgres)
    portfolio_tables_required = [
        "portfolio_holdings",
        "portfolio_transactions",
        "portfolio_preferences",
    ]
    portfolio_tables_found = [t for t in portfolio_tables_required if t in all_tables]
    portfolio_ok = len(portfolio_tables_found) == len(portfolio_tables_required)
    portfolio_tables_missing = list(
        set(portfolio_tables_required) - set(portfolio_tables_found)
    )
    checks["portfolio_tables"] = {
        "ok": portfolio_ok,
        "error": f"Missing: {portfolio_tables_missing}"
        if portfolio_tables_missing
        else None,
        "tables": portfolio_tables_found,
    }

    # Hypertable check (TimescaleDB specific)
    hypertables_ok = False
    hypertables_error: Optional[str] = None
    hypertables_found: List[str] = []
    hypertables_required = [
        "episodic_memories",
        "emotional_memories",
        "portfolio_snapshots",
    ]
    try:
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
					SELECT hypertable_name FROM timescaledb_information.hypertables
					WHERE hypertable_schema = 'public'
					ORDER BY hypertable_name
				""")
                hypertables_found = [row["hypertable_name"] for row in cur.fetchall()]
                hypertables_ok = all(
                    h in hypertables_found
                    for h in hypertables_required
                    if h in all_tables
                )
                if not hypertables_ok:
                    missing_hypertables = [
                        h
                        for h in hypertables_required
                        if h in all_tables and h not in hypertables_found
                    ]
                    if missing_hypertables:
                        hypertables_error = (
                            f"Tables exist but not hypertables: {missing_hypertables}"
                        )
    except Exception as exc:
        hypertables_error = str(exc)
    checks["hypertables"] = {
        "ok": hypertables_ok,
        "error": hypertables_error,
        "hypertables": hypertables_found,
        "required": [h for h in hypertables_required if h in all_tables],
    }

    # Migration version check
    migrations_ok = False
    migrations_error: Optional[str] = None
    latest_migration: Optional[str] = None
    migration_count: int = 0
    try:
        if conn:
            with conn.cursor() as cur:
                # Check if migration_history table exists
                if "migration_history" in all_tables:
                    cur.execute("""
						SELECT migration_file, database_type, applied_at 
						FROM migration_history 
						WHERE success = true
						ORDER BY applied_at DESC 
						LIMIT 1
					""")
                    row = cur.fetchone()
                    if row:
                        latest_migration = (
                            f"{row['database_type']}/{row['migration_file']}"
                        )
                    cur.execute(
                        "SELECT COUNT(*) as cnt FROM migration_history WHERE success = true"
                    )
                    migration_count = cur.fetchone()["cnt"]
                    migrations_ok = migration_count > 0
                else:
                    migrations_error = "migration_history table not found"
    except Exception as exc:
        migrations_error = str(exc)
    checks["migrations"] = {
        "ok": migrations_ok,
        "error": migrations_error,
        "latest": latest_migration,
        "total_applied": migration_count,
    }

    # Record counts (observability stats)
    record_counts: Dict[str, Any] = {}
    try:
        if conn:
            with conn.cursor() as cur:
                count_tables = [
                    "episodic_memories",
                    "emotional_memories",
                    "procedural_memories",
                    "scheduled_intents",
                    "user_profiles",
                ]
                for table in count_tables:
                    if table in all_tables:
                        try:
                            cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                            result = cur.fetchone()
                            record_counts[table] = result["cnt"] if result else 0
                        except Exception as e:
                            record_counts[table] = f"error: {str(e)[:50]}"
    except Exception:
        pass  # Non-critical, just stats
    checks["record_counts"] = record_counts

    # Release connection after all table checks
    if conn:
        release_timescale_conn(conn)

    # LLM endpoint connectivity check (cached for 60s to avoid hitting external API)
    cached_llm = _get_cached_llm_check()
    if cached_llm:
        llm_ok = cached_llm["ok"]
        checks["llm_connectivity"] = cached_llm
    else:
        llm_ok = None
        llm_error: Optional[str] = None
        llm_endpoint: Optional[str] = None
        try:
            if provider == "openai":
                llm_endpoint = "https://api.openai.com/v1/models"
                api_key = get_openai_api_key()
                if api_key:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get(
                            llm_endpoint, headers={"Authorization": f"Bearer {api_key}"}
                        )
                        llm_ok = resp.status_code == 200
                        if not llm_ok:
                            llm_error = f"HTTP {resp.status_code}"
                else:
                    llm_error = "API key not configured"
            elif provider == "xai":
                from src.config import get_xai_api_key

                base_url = get_xai_base_url()
                llm_endpoint = f"{base_url}/models"
                api_key = get_xai_api_key()
                if api_key:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get(
                            llm_endpoint, headers={"Authorization": f"Bearer {api_key}"}
                        )
                        llm_ok = resp.status_code == 200
                        if not llm_ok:
                            llm_error = f"HTTP {resp.status_code}"
                else:
                    llm_error = "API key not configured"
            else:
                llm_error = f"Unknown provider: {provider}"
        except httpx.TimeoutException:
            llm_ok = False
            llm_error = "Connection timeout"
        except Exception as exc:
            llm_ok = False
            llm_error = str(exc)
        # Update cache
        _update_llm_cache(llm_ok, llm_error, llm_endpoint)
        checks["llm_connectivity"] = {
            "ok": llm_ok,
            "error": llm_error,
            "endpoint": llm_endpoint,
            "cached": False,
        }

    # Langfuse check (optional - tracing)
    langfuse_ok = None
    langfuse_error: Optional[str] = None
    try:
        from src.dependencies.langfuse_client import ping_langfuse
        from src.config import is_langfuse_enabled

        if is_langfuse_enabled():
            langfuse_ok = ping_langfuse()
            if not langfuse_ok:
                langfuse_error = "Client initialization failed"
        else:
            langfuse_ok = None  # not configured
    except Exception as exc:
        langfuse_ok = False
        langfuse_error = str(exc)
    checks["langfuse"] = {
        "ok": langfuse_ok,
        "error": langfuse_error,
        "enabled": is_langfuse_enabled(),
    }

    # Overall status calculation
    # Critical: chroma, timescale, memory_tables, llm_connectivity
    # Important: intents_tables, profile_tables, portfolio_tables, chroma_collections, hypertables, migrations
    # Optional (None=not configured is OK): redis, langfuse
    # Informational (no impact on status): record_counts
    critical_ok = chroma_ok and ts_ok and memory_tables_ok and (llm_ok is True)
    important_ok = (
        intents_tables_ok
        and profile_tables_ok
        and portfolio_ok
        and collections_ok
        and hypertables_ok
        and migrations_ok
    )
    optional_ok = (redis_ok is None or redis_ok) and (
        langfuse_ok is None or langfuse_ok
    )

    if critical_ok and important_ok and optional_ok and len(missing_envs) == 0:
        status = "ok"
    elif critical_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return {
        "status": status,
        "time": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@app.post("/v1/store", response_model=StoreResponse)
def store_transcript(body: TranscriptRequest) -> StoreResponse:
    # Guard: enforce LLM configuration
    if not is_llm_configured():
        raise HTTPException(status_code=400, detail="LLM is not configured")

    # Use unified ingestion graph (replaces old extraction + routing)
    from src.services.unified_ingestion_graph import run_unified_ingestion

    final_state = run_unified_ingestion(body)

    # Extract results from final state
    memories = final_state.get("memories", [])
    ids = final_state.get("memory_ids", [])

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
        for i, m in enumerate(memories)
    ]

    # Get storage results
    storage_results = final_state.get("storage_results", {})

    # Build summary
    summary_parts = []
    if len(memories) > 0:
        layers = set(m.layer for m in memories)
        types = set(m.type for m in memories)
        summary_parts.append(
            f"Extracted {len(memories)} memories ({', '.join(types)}) across layers: {', '.join(layers)}."
        )

    if storage_results.get("episodic_stored", 0) > 0:
        summary_parts.append(f"{storage_results['episodic_stored']} episodic")
    if storage_results.get("emotional_stored", 0) > 0:
        summary_parts.append(f"{storage_results['emotional_stored']} emotional")
    if storage_results.get("procedural_stored", 0) > 0:
        summary_parts.append(f"{storage_results['procedural_stored']} procedural")
    if storage_results.get("portfolio_stored", 0) > 0:
        summary_parts.append(f"{storage_results['portfolio_stored']} portfolio")

    if len(summary_parts) > 1:
        summary = summary_parts[0] + " Stored: " + ", ".join(summary_parts[1:]) + "."
    else:
        summary = summary_parts[0] if summary_parts else "No memories extracted."

    response = StoreResponse(
        memories_created=len(ids),
        ids=ids,
        summary=summary,
        memories=items,
        duplicates_avoided=0,
        updates_made=0,
        existing_memories_checked=len(final_state.get("existing_memories", [])),
    )

    return response


@app.get("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(
    user_id: str = Query(...),
    query: Optional[str] = Query(
        default=None, description="Search query (optional - omit to get all memories)"
    ),
    layer: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    persona: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(
        default=None, description="Sort order: 'newest' or 'oldest' (by timestamp)"
    ),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> RetrieveResponse:
    from src.services.tracing import start_trace, end_trace

    # Start trace for this request
    trace = start_trace(
        name="retrieve_memories",
        user_id=user_id,
        metadata={
            "query": query[:100] if query else None,
            "limit": limit,
            "endpoint": "/v1/retrieve",
        },
    )

    metadata_filters: Dict[str, Any] = {}
    if layer:
        metadata_filters["layer"] = layer
    if type:
        metadata_filters["type"] = type
    persona_context: Dict[str, Any] = {}
    if persona:
        persona_context["forced_persona"] = persona
        metadata_filters.setdefault("persona_tags", [persona])

    # When sorting by timestamp, fetch a large pool so we can sort before paginating.
    # ChromaDB .get() returns records in arbitrary order, so a small limit would
    # miss recent memories.
    sorting = sort in ("newest", "oldest")
    fetch_limit = max(limit + offset, 1000) if sorting else limit + offset

    persona_results = _persona_copilot.retrieve(
        user_id=user_id,
        query=query or "",
        limit=fetch_limit,
        persona_context=persona_context or None,
        metadata_filters=metadata_filters if metadata_filters else None,
        include_summaries=False,
    )

    selected_persona = persona or (next(iter(persona_results.keys()), None))
    raw_items: List[dict] = []
    total = 0

    # Define timestamp key extractor once (avoid duplication)
    def _ts_key(r: dict) -> str:
        meta = r.get("metadata", {}) if isinstance(r, dict) else {}
        return meta.get("timestamp", "") if isinstance(meta, dict) else ""

    if selected_persona and selected_persona in persona_results:
        persona_payload = persona_results[selected_persona]
        pool = persona_payload.items

        # Sort the full pool first, then paginate
        if sorting:
            pool.sort(key=_ts_key, reverse=(sort == "newest"))

        total = len(pool)
        raw_items = pool[offset : offset + limit]
    else:
        fallback_filters = dict(metadata_filters)
        # When sorting, fetch a larger pool first, sort, then paginate
        # (Fixes bug: previously sorted only the paginated page, not full results)
        if sorting:
            pool, total = search_memories(
                user_id=user_id,
                query=query or "",
                filters=fallback_filters,
                limit=fetch_limit,
                offset=0,
            )
            pool.sort(key=_ts_key, reverse=(sort == "newest"))
            raw_items = pool[offset : offset + limit]
        else:
            raw_items, total = search_memories(
                user_id=user_id,
                query=query or "",
                filters=fallback_filters,
                limit=limit,
                offset=offset,
            )

    items = _convert_to_retrieve_items(raw_items)

    # Build finance aggregate (lightweight) from current page results
    fin_holdings: List[dict] = []
    counts_by_asset_type: dict[str, int] = {}
    goals: List[FinanceGoal] = []
    for r in raw_items:
        meta = r.get("metadata", {}) if isinstance(r, dict) else {}
        p = meta.get("portfolio") if isinstance(meta, dict) else None
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
                "source_memory_id": r.get("id") if isinstance(r, dict) else None,
                "updated_at": meta.get("timestamp") if isinstance(meta, dict) else None,
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
                    at = base.get("asset_type") or (
                        "public_equity" if base.get("ticker") else "unknown"
                    )
                    counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1

        tags_json = meta.get("tags") if isinstance(meta, dict) else None
        tags: List[str] = []
        try:
            if isinstance(tags_json, str):
                tags = json.loads(tags_json)
            elif isinstance(tags_json, list):
                tags = [str(t) for t in tags_json]
        except Exception:
            tags = []
        if any(t for t in tags if t.startswith("ticker:")) or "finance" in tags:
            content = r.get("content", "") if isinstance(r, dict) else ""
            goals.append(
                FinanceGoal(
                    text=content,
                    source_memory_id=r.get("id") if isinstance(r, dict) else None,
                )
            )

    finance_agg = (
        FinanceAggregate(
            portfolio=PortfolioSummaryResponse(
                user_id=user_id,
                holdings=fin_holdings,
                counts_by_asset_type=counts_by_asset_type,
            ),
            goals=goals,
        )
        if (fin_holdings or goals)
        else None
    )

    response = RetrieveResponse(
        results=items,
        pagination={"limit": limit, "offset": offset, "total": total},
        finance=finance_agg,
    )

    if trace:
        try:
            trace.update(output={"results_count": len(items), "total": total})
        except Exception:
            pass
        end_trace()

    return response


@app.post("/v1/retrieve", response_model=PersonaRetrieveResponse)
def retrieve_persona(body: PersonaRetrieveRequest) -> PersonaRetrieveResponse:
    metadata_filters: Dict[str, Any] = dict(body.filters or {})
    if body.persona_context:
        if hasattr(body.persona_context, "model_dump"):
            persona_context = body.persona_context.model_dump()
        else:
            persona_context = body.persona_context.dict()
    else:
        persona_context = {}
    limit_with_offset = body.limit + body.offset
    persona_results = _persona_copilot.retrieve(
        user_id=body.user_id,
        query=body.query or "",
        limit=limit_with_offset,
        persona_context=persona_context or None,
        metadata_filters=metadata_filters if metadata_filters else None,
        include_summaries=True,
        granularity=body.granularity,
    )

    selected_persona = persona_context.get("forced_persona") or (
        next(iter(persona_results.keys()), None)
    )
    persona_payload = (
        persona_results.get(selected_persona) if selected_persona else None
    )
    if persona_payload is None and persona_results:
        selected_persona, persona_payload = next(iter(persona_results.items()))
    if selected_persona is None:
        selected_persona = persona_context.get("forced_persona") or "identity"

    if persona_payload is None:
        fallback_filters = dict(metadata_filters)
        raw_page, total_count = search_memories(
            user_id=body.user_id,
            query=body.query or "",
            filters=fallback_filters,
            limit=body.limit,
            offset=body.offset,
        )
        summaries = []
        weight_profile: Dict[str, float] = {}
    else:
        _total_count = len(persona_payload.items)
        raw_page = persona_payload.items[body.offset : body.offset + body.limit]
        summaries = persona_payload.summaries
        weight_profile = persona_payload.weight_profile

    items = _convert_to_retrieve_items(raw_page)
    tier_value = _persona_copilot.summary_manager.resolve_tier(body.granularity).value

    confidence = 0.0
    if raw_page:
        try:
            score_sum = sum(
                float(mem.get("score", 0.0) or 0.0)
                for mem in raw_page
                if isinstance(mem, dict)
            )
            confidence = max(0.0, min(1.0, score_sum / max(len(raw_page), 1)))
        except Exception:
            confidence = 0.0

    state_snapshot_id = None
    try:
        state = _persona_copilot.state_store.get_state(body.user_id)
        state_snapshot_id = f"{state.user_id}:{int(state.updated_at.timestamp())}"
    except Exception:
        state_snapshot_id = None

    narrative_text = None
    if body.include_narrative and raw_page:
        narrative = _reconstruction.build_narrative(
            user_id=body.user_id,
            query=body.query,
            limit=body.limit,
            prefetched_memories=raw_page,
            summaries=summaries,
            persona=selected_persona,
        )
        narrative_text = narrative.text

    explainability = None
    if body.explain:
        source_links = []
        for mem in raw_page:
            if isinstance(mem, dict):
                try:
                    score_val = float(mem.get("score", 0.0) or 0.0)
                except Exception:
                    score_val = 0.0
                source_links.append({"id": mem.get("id"), "score": score_val})
        explainability = PersonaExplainability(
            weights=weight_profile, source_links=source_links
        )

    response = PersonaRetrieveResponse(
        persona=PersonaSelection(
            selected=selected_persona,
            confidence=confidence,
            state_snapshot_id=state_snapshot_id,
        ),
        results=PersonaRetrieveResults(
            granularity=tier_value,
            memories=items,
            summaries=summaries,
            narrative=narrative_text,
        ),
        explainability=explainability,
    )

    return response


# Advanced structured retrieval endpoint
@app.post("/v1/retrieve/structured", response_model=StructuredRetrieveResponse)
def retrieve_structured(body: StructuredRetrieveRequest) -> StructuredRetrieveResponse:
    from src.services.tracing import start_trace, end_trace

    # Start trace for this request
    trace = start_trace(
        name="retrieve_structured",
        user_id=body.user_id,
        metadata={"limit": body.limit, "endpoint": "/v1/retrieve/structured"},
    )

    if not is_llm_configured():
        raise HTTPException(status_code=400, detail="LLM is not configured")

    # Pull ALL memories for the user (paginate with empty query)
    all_results: List[dict] = []
    batch_limit = max(10000, body.limit)
    offset = 0
    while True:
        batch, _ = search_memories(
            user_id=body.user_id, query="", filters={}, limit=batch_limit, offset=offset
        )
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
                    # metadata=src.get("metadata", {}),
                )
            )
        return items

    # Build finance aggregate from ids if present
    fin_ids = (resp.get("finance") or {}) if isinstance(resp, dict) else {}
    portfolio_ids = (
        list(fin_ids.get("portfolio_ids", [])) if isinstance(fin_ids, dict) else []
    )
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
                    at = base.get("asset_type") or (
                        "public_equity" if base.get("ticker") else "unknown"
                    )
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

    finance_agg2 = (
        FinanceAggregate(
            portfolio=PortfolioSummaryResponse(
                user_id=body.user_id,
                holdings=fin_holdings2,
                counts_by_asset_type=counts_by_asset_type2,
            ),
            goals=[
                FinanceGoal(text=i.content, source_memory_id=i.id) for i in goals_items
            ],
        )
        if (portfolio_ids or goal_ids)
        else None
    )

    response = StructuredRetrieveResponse(
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

    # Update trace with output
    if trace:
        try:
            total_items = sum(
                len(build_items(list(resp.get(k, []))))
                for k in [
                    "emotions",
                    "behaviors",
                    "personal",
                    "professional",
                    "habits",
                    "skills_tools",
                    "projects",
                    "relationships",
                    "learning_journal",
                    "other",
                ]
            )
            trace.update(output={"total_structured_items": total_items})
        except Exception:
            pass
        end_trace()

    return response


# Narrative endpoint
@app.post("/v1/narrative", response_model=NarrativeResponse)
def narrative(body: NarrativeRequest) -> NarrativeResponse:
    from src.services.tracing import start_trace, end_trace

    # Start trace for this request
    trace = start_trace(
        name="narrative_generation",
        user_id=body.user_id,
        metadata={
            "query": body.query[:100] if body.query else None,
            "limit": body.limit,
            "endpoint": "/v1/narrative",
        },
    )

    start = None
    end = None
    try:
        if body.start_time:
            start = datetime.fromisoformat(body.start_time)
        if body.end_time:
            end = datetime.fromisoformat(body.end_time)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid ISO8601 for start_time/end_time"
        )

    ntv = _reconstruction.build_narrative(
        user_id=body.user_id,
        query=body.query,
        time_range=(start, end) if start and end else None,
        limit=body.limit,
    )

    response = NarrativeResponse(
        user_id=ntv.user_id,
        narrative=ntv.text,
        summary=ntv.summary,
        sources=ntv.sources,
    )

    # Update trace with output
    if trace:
        try:
            trace.update(output={"sources_count": len(ntv.sources)})
        except Exception:
            pass
        end_trace()

    return response


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
def portfolio_summary(
    user_id: str = Query(...), limit: int = Query(default=200, ge=1, le=1000)
) -> PortfolioSummaryResponse:
    from src.services.tracing import start_trace, end_trace

    # Start trace for this request
    trace = start_trace(
        name="portfolio_summary",
        user_id=user_id,
        metadata={"limit": limit, "endpoint": "/v1/portfolio/summary"},
    )

    # NEW: Fetch from dedicated portfolio_holdings table (primary source)
    holdings: List[dict] = []
    counts_by_asset_type: dict[str, int] = {}

    try:
        from src.services.portfolio_service import PortfolioService

        portfolio_service = PortfolioService()
        db_holdings = portfolio_service.get_holdings(user_id)

        # Convert DB holdings to response format
        for h in db_holdings[:limit]:
            holding_dict = {
                "asset_type": h.get("asset_type"),
                "ticker": h.get("ticker"),
                "name": h.get("asset_name"),
                "shares": h.get("shares"),
                "avg_price": h.get("avg_price"),
                "current_price": h.get("current_price"),
                "current_value": h.get("current_value"),
                "cost_basis": h.get("cost_basis"),
                "ownership_pct": h.get("ownership_pct"),
                "position": h.get("position"),
                "intent": h.get("intent"),
                "target_price": h.get("target_price"),
                "stop_loss": h.get("stop_loss"),
                "time_horizon": h.get("time_horizon"),
                "notes": h.get("notes"),
                "source_memory_id": h.get("source_memory_id"),
                "updated_at": h.get("last_updated"),
            }
            holdings.append(holding_dict)
            at = holding_dict.get("asset_type") or "unknown"
            counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1

        # Sort by last_updated for most recent first
        holdings.sort(key=lambda x: x.get("updated_at") or datetime.min, reverse=True)

        response = PortfolioSummaryResponse(
            user_id=user_id,
            holdings=holdings[:limit],
            counts_by_asset_type=counts_by_asset_type,
        )

        # Update trace with output
        if trace:
            try:
                trace.update(
                    output={"holdings_count": len(holdings), "source": "postgres"}
                )
            except Exception:
                pass
            end_trace()

        return response
    except Exception as exc:
        logger.warning(
            "[portfolio.summary] Failed to fetch from DB, falling back to ChromaDB: %s",
            exc,
        )

    # FALLBACK: Fetch from ChromaDB metadata (legacy/backup)
    all_results: List[dict] = []
    offset = 0
    batch_limit = min(200, limit)
    while len(all_results) < limit:
        batch, _ = search_memories(
            user_id=user_id, query="", filters={}, limit=batch_limit, offset=offset
        )
        if not batch:
            break
        all_results.extend(batch)
        if len(batch) < batch_limit:
            break
        offset += batch_limit

    # Aggregate holdings from ChromaDB
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
                at = base.get("asset_type") or (
                    "public_equity" if base.get("ticker") else "unknown"
                )
                counts_by_asset_type[at] = counts_by_asset_type.get(at, 0) + 1

    # Sort holdings by ticker then name for stable output
    holdings.sort(key=lambda x: (str(x.get("ticker") or ""), str(x.get("name") or "")))

    # Shape into response model
    # Note: Pydantic will coerce the list of dicts into PortfolioHolding items
    response = PortfolioSummaryResponse(
        user_id=user_id,
        holdings=holdings[:limit],
        counts_by_asset_type=counts_by_asset_type,
    )

    # Update trace with output
    if trace:
        try:
            trace.update(
                output={"holdings_count": len(holdings), "source": "chromadb_fallback"}
            )
        except Exception:
            pass
        end_trace()

    return response


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
            logger.info(
                "[maint.compaction.done] user_id=%s (manual) stats=%s", uid, stats
            )
        except Exception as exc:
            logger.info("[maint.compaction.error] user_id=%s (manual) %s", uid, exc)
    return MaintenanceResponse(jobs_started=["compaction_all"], status="running")


@app.post("/v1/maintenance/compact")
def compact_single_user(
    user_id: str = Query(...),
    skip_reextract: bool = Query(
        default=True, description="Skip expensive LLM re-extraction (default: true)"
    ),
    skip_consolidate: bool = Query(
        default=False,
        description="Skip memory consolidation into golden records (default: false - consolidation runs)",
    ),
) -> dict:
    """Run compaction for a single user.

    By default, runs TTL cleanup, deduplication, and consolidation.
    Set skip_reextract=false to enable full LLM re-extraction (slow, expensive).
    Set skip_consolidate=true to disable memory consolidation.
    """
    try:
        stats = run_compaction_for_user(
            user_id, skip_reextract=skip_reextract, skip_consolidate=skip_consolidate
        )
        logger.info(
            "[maint.compaction.done] user_id=%s skip_reextract=%s skip_consolidate=%s stats=%s",
            user_id,
            skip_reextract,
            skip_consolidate,
            stats,
        )
        return {
            "user_id": user_id,
            "skip_reextract": skip_reextract,
            "skip_consolidate": skip_consolidate,
            "status": "completed",
            "stats": stats,
        }
    except Exception as exc:
        logger.error(
            "[maint.compaction.error] user_id=%s %s", user_id, exc, exc_info=True
        )
        return {
            "user_id": user_id,
            "skip_reextract": skip_reextract,
            "skip_consolidate": skip_consolidate,
            "status": "failed",
            "error": str(exc),
        }
