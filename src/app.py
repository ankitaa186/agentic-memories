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

app = FastAPI(title="Agentic Memories API", version="0.1.0")


@app.get("/health")
def health() -> dict:
	return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


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
