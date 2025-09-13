from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Query

from src.schemas import (
	ForgetRequest,
	MaintenanceRequest,
	MaintenanceResponse,
	RetrieveItem,
	RetrieveResponse,
	StoreResponse,
	TranscriptRequest,
)
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_openai_api_key, get_chroma_host, get_chroma_port
import httpx

app = FastAPI(title="Agentic Memories API", version="0.1.0")


@app.get("/health")
def health() -> dict:
	return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/health/full")
def health_full() -> dict:
	checks = {}

	# Env check
	required_envs = ["OPENAI_API_KEY"]
	missing_envs = [k for k in required_envs if (get_openai_api_key() is None and k == "OPENAI_API_KEY")]
	checks["env"] = {"required": required_envs, "missing": missing_envs}

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
	# Stub: return mocked extraction result
	return StoreResponse(memories_created=1, ids=["mem_01"], summary="Stub: extracted 1 memory")


@app.get("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(
	query: str = Query(...),
	layer: Optional[str] = Query(default=None),
	type: Optional[str] = Query(default=None),
	limit: int = Query(default=10, ge=1, le=50),
	offset: int = Query(default=0, ge=0),
) -> RetrieveResponse:
	# Stub: return a single mocked result
	item = RetrieveItem(
		id="mem_01",
		content="User prefers sci-fi books",
		layer=layer or "semantic",
		type=type or "explicit",
		score=0.9,
		metadata={"source": "stub"},
	)
	return RetrieveResponse(results=[item], pagination={"limit": limit, "offset": offset, "total": 1})


@app.post("/v1/forget")
def forget(body: ForgetRequest) -> dict:
	return {"jobs_enqueued": ["ttl_cleanup", "promotion"], "dry_run": body.dry_run}


@app.post("/v1/maintenance", response_model=MaintenanceResponse)
def maintenance(body: MaintenanceRequest) -> MaintenanceResponse:
	return MaintenanceResponse(jobs_started=body.jobs or ["compaction"], status="running")
