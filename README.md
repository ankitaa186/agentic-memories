# Agentic Memories: Memory Module for Chatbot Hyperpersonalization

A modular, scalable memory system that extracts, stores, retrieves, and maintains user memories (explicit and implicit) across short‑term, semantic, and long‑term layers to deliver truly personalized chatbot interactions.

## Table of Contents
- [Quickstart](#quickstart)
- [Project Overview](#project-overview)
  - [Purpose](#purpose)
  - [Key Motivations](#key-motivations)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [API Endpoints](#api-endpoints)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Environment](#environment)
  - [Run](#run)
  - [Testing](#testing)
- [Phased Build Plan](#phased-build-plan)
  - [Phase 1: Project Setup and Core Models](#phase-1-project-setup-and-core-models)
  - [Phase 2: Memory Extraction Engine](#phase-2-memory-extraction-engine)
  - [Phase 3: Storage and Retrieval Services](#phase-3-storage-and-retrieval-services)
  - [Phase 4: User Identification and Interfaces](#phase-4-user-identification-and-interfaces)
  - [Phase 5: Forget Module and Maintenance](#phase-5-forget-module-and-maintenance)
  - [Phase 6: Security, Testing, Optimization, and Deployment](#phase-6-security-testing-optimization-and-deployment)
- [Milestones and Timeline](#milestones-and-timeline)

## Quickstart
1) Create and activate a virtual environment
```bash
python -m venv .venv && \
  (source .venv/bin/activate || .\.venv\Scripts\Activate.ps1)
```
2) Install dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
3) Ensure services are running
- ChromaDB server at `http://localhost:8000`
- (Optional) Redis at `redis://localhost:6379/0`

4) Run the API
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

## Project Overview

### Purpose
Stateless AI agents easily lose context across sessions. This project introduces hierarchical memory—short‑term (immediate recall), semantic (conceptual understanding), and long‑term (archival)—and distinguishes explicit facts from implicit inferences to deliver nuanced personalization.

### Key Motivations
- Hyperpersonalization: Capture deep details (preferences, behaviors, personality) for intuitive interactions.
- Modularity & Integration: Standalone service via FastAPI and MCP tool exposure.
- Efficiency & Sustainability: Forgetting (TTL, promotion, compaction, pruning) prevents data bloat and reduces costs.
- Security & Scalability: Multi‑user isolation via `user_id`, basic GDPR‑like expiration.

## Tech Stack
- Backend: Python 3.12+, FastAPI, Uvicorn
- Vector DB: ChromaDB (localhost:8000) for all layers (incl. short‑term persistence)
- AI/ML: OpenAI (embeddings, extraction, summarization), LangChain
- Cache: Redis (optional; accelerates short‑term retrieval)
- Scheduling: APScheduler (maintenance jobs)
- Security: API keys/JWT
- Tooling: Docker, Pytest

## Architecture
- Input: Conversation transcripts (JSON with `user_id`, `history`).
- Extraction: LLM prompts extract explicit/implicit memories and assign layers.
- Storage: Single ChromaDB collection; metadata (`user_id`, `layer`, `type`); short‑term persisted with TTL.
- Retrieval: Semantic search (embeddings + cosine) with keyword fallback; filters by `user_id`, `layer`, `type`; increments `usage_count`; Redis cache for short‑term (optional).
- Forgetting: Time‑based expiration, promotion (short→long summarization), compaction (cluster + summarize), implicit pattern pruning.
- Interfaces: FastAPI REST endpoints + MCP tools.

ChromaDB client example (HTTP server on localhost:8000):
```python
from chromadb import HttpClient
import httpx

http_client = httpx.Client(base_url="http://localhost:8000")
client = HttpClient(http_client=http_client)
# or using the Chroma convenience wrapper, if available:
# from chromadb import Client
# client = Client(http_client=http_client)
```

## Data Model
Pydantic `Memory` (planned):
- `user_id: str`
- `content: str`
- `layer: Literal["short-term", "semantic", "long-term"]`
- `type: Literal["explicit", "implicit"]`
- `embedding: list[float] | None`
- `timestamp: datetime`
- `confidence: float`
- `ttl: int | None`
- `usage_count: int`
- `relevance_score: float`
- `metadata: dict[str, Any]`

## API Endpoints
- `GET /health` — Liveness check
- `POST /store` — Input: transcript JSON; runs extraction → storage
- `GET /retrieve` — Query params: `query`, optional `layer`, `type`; returns ranked memories
- `POST /forget` — Manually trigger pruning/expiration
- `POST /maintenance` — Trigger scheduled jobs on demand

All operations are scoped by `user_id` derived from `X-API-KEY` (or JWT) and must be enforced server‑side.

## Development

### Project Structure
```
src/
  app.py
  models.py
  services/
    extraction.py
    storage.py
    retrieval.py
    forget.py
  dependencies/
    user_id.py
tests/
Dockerfile
requirements.txt
```

### Environment
Required variables:
- `OPENAI_API_KEY`
- `CHROMA_HOST=localhost`, `CHROMA_PORT=8000`
- `REDIS_URL=redis://localhost:6379/0` (optional)

### Run
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

### Testing
```bash
pytest -q
```
Targets: unit, integration, and E2E (>80% coverage), including multi‑user isolation, short‑term persistence/expiration, and forgetting logic.

## Phased Build Plan
Iterative development using Cursor. Each phase lists objective, tasks, deliverables, dependencies, and a sample prompt.

### Phase 1: Project Setup and Core Models (1-2 days)
Objective: Establish the foundation with repo structure, dependencies, and data models.

Tasks:
- Create repo and structure: `/src` (`app.py`, `models.py`, `services/`, `dependencies/`), `/tests`, `Dockerfile`, `requirements.txt`.
- Install deps: fastapi, uvicorn, chromadb, openai, langchain, langchain-openai, redis, pydantic, apscheduler.
- Define Pydantic `Memory` model with fields above.
- Set up FastAPI app with `/health` endpoint.
- Configure ChromaDB client to `localhost:8000` for storage of all layers.

Dependencies: None.

Deliverables: Repo skeleton; Running app (`uvicorn src.app:app --reload`); Validated models.

Cursor Prompt: "Generate a FastAPI project structure in Python for an AI memory module. Include Pydantic models for hierarchical memories with explicit/implicit types, TTL, and relevance scores. Set up ChromaDB client connecting to localhost:8000 for persistent storage of all layers, including short-term."

### Phase 2: Memory Extraction Engine (2-3 days)
Objective: Build logic to extract and classify memories from conversations.

Tasks:
- Implement extraction service using OpenAI prompts (explicit/implicit, assign layers, short‑term defaults with short TTL).
- Generate embeddings (e.g., `text-embedding-3-small`).
- Use LangChain for summarization chains if needed.
- Handle edge cases: No new info, ambiguous inferences (confidence scoring).

Dependencies: Phase 1 models.

Deliverables: `services/extraction.py`; Unit tests with 10+ sample transcripts; Extraction accuracy >85% on mocks.

Cursor Prompt: "Implement a memory extraction service using OpenAI and LangChain. From a conversation transcript, extract explicit/implicit memories, assign to short-term/semantic/long-term layers, generate embeddings, and add TTL/scores (short TTL for short-term). Include tests."

### Phase 3: Storage and Retrieval Services (3-4 days)
Objective: Enable persistent storage and efficient querying across hierarchies.

Tasks:
- Set up ChromaDB collections (unified with layer metadata; use filters for separation).
- Storage: Upsert memories with metadata (user_id and layer enforced); persist short‑term in ChromaDB with TTL for later expiration.
- Retrieval: Semantic search (cosine) with keyword fallback; Filter by user_id, layer, type; Increment usage_count; Cache short‑term results in Redis for speed.
- Integrate Redis as cache layer for short‑term (sync with ChromaDB).

Dependencies: Phases 1-2.

Deliverables: `services/storage.py`, `services/retrieval.py`; Integration tests; <150ms retrieval latency.

Cursor Prompt: "Build storage and retrieval services with ChromaDB (localhost:8000) persisting all layers including short-term (with TTL metadata), and Redis as cache for short-term. Support hierarchical layers, user_id partitioning via metadata filters, and hybrid semantic/keyword search. Include usage tracking and cache sync."

### Phase 4: User Identification and Interfaces (3-4 days)
Objective: Secure multi-user support and expose APIs/MCP.

Tasks:
- Implement user ID dependency: extract/validate from `X-API-KEY`.
- Add FastAPI endpoints: `POST /store` (transcript input), `GET /retrieve` (query, layer, type params).
- Integrate MCP: expose operations as tools with schemas.
- Enforce user_id in all operations.

Dependencies: Phases 1-3.

Deliverables: `dependencies/user_id.py`, `app.py` with routes; Swagger docs; MCP tool definitions.

Cursor Prompt: "Add user identification dependency with APIKeyHeader for multi-user support. Implement FastAPI endpoints for store/retrieve with user_id injection. Add MCP-compatible tool exposures for memory ops."

### Phase 5: Forget Module and Maintenance (3-4 days)
Objective: Add dynamic memory management for efficiency.

Tasks:
- Implement forgetting mechanisms: TTL expiration (auto‑expire short‑term), promotion (summarize short→long), compaction (cluster + LLM summarize long‑term), pattern pruning (LLM evaluate implicit relevance).
- Use APScheduler for periodic jobs (daily prune, focus on short‑term cleanup from ChromaDB).
- Add endpoints: `POST /forget` (manual), `POST /maintenance` (trigger jobs).
- Integrate feedback loop: Update relevance scores on contradictions.

Dependencies: Phases 1-4.

Deliverables: `services/forget.py`; Tests for pruning accuracy; Scheduled jobs running.

Cursor Prompt: "Implement a forget module with APScheduler jobs for TTL expiration (prioritize short-term cleanup), short-to-long promotion via summarization, long-term compaction, and adaptive implicit pattern pruning using OpenAI prompts."

### Phase 6: Security, Testing, Optimization, and Deployment (2-3 days)
Objective: Polish for production readiness.

Tasks:
- Add security: Rate limiting, encryption for sensitive data.
- Comprehensive testing: Unit/integration/E2E (Pytest >80% coverage); Simulate multi-user, forgetting scenarios (including short‑term persistence and expiration).
- Optimize: Batch embeddings, pagination for large retrievals; Ensure Redis‑ChromaDB sync for short‑term.
- Dockerize app; Deployment guide (run with ChromaDB on port 8000).

Dependencies: All prior.

Deliverables: Test suite; Dockerfile; README updates with run instructions.

Cursor Prompt: "Add security middleware, full Pytest suite for multi-user isolation, short-term persistence, and forgetting logic. Optimize services and Dockerize the FastAPI app."

## Milestones and Timeline
- MVP Milestone: End of Phase 4 (core store/retrieve working; short‑term persisted).
- Full Build: 3–4 weeks total.
- Post‑Build: Monitor and iterate based on usage.


## API Contracts

### Versioning
- Base path: `/v1`
- Media type: `application/json`

### Common Fields
- Headers: `X-API-KEY: <string>` (required)
- Error shape:
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {"any": "optional"}
  }
}
```

### POST /v1/store
- Purpose: Extract memories from a transcript and persist them.
- Request body:
```json
{
  "user_id": "user-123",
  "history": [
    {"role": "user", "content": "I love sci-fi books."},
    {"role": "assistant", "content": "Noted. Any favorite authors?"}
  ],
  "metadata": {"conversation_id": "abc-123"}
}
```
- Response body:
```json
{
  "memories_created": 2,
  "ids": ["mem_01", "mem_02"],
  "summary": "Extracted explicit preference for sci-fi; created short-term memory."
}
```
- Errors: `400` invalid schema, `401` unauthorized, `429` rate limit, `500` internal.

### GET /v1/retrieve
- Purpose: Retrieve ranked memories for a query.
- Query params: `query` (required), `layer` (optional), `type` (optional), `limit` (default 10), `offset` (default 0)
- Response body:
```json
{
  "results": [
    {
      "id": "mem_01",
      "content": "User prefers sci-fi books",
      "layer": "semantic",
      "type": "explicit",
      "score": 0.83,
      "metadata": {"source": "extraction"}
    }
  ],
  "pagination": {"limit": 10, "offset": 0, "total": 1}
}
```

### POST /v1/forget
- Purpose: Trigger forgetting flows manually.
- Request body:
```json
{"scopes": ["short-term", "semantic"], "dry_run": false}
```
- Response body:
```json
{"jobs_enqueued": ["ttl_cleanup", "promotion"], "dry_run": false}
```

### POST /v1/maintenance
- Purpose: Run scheduled maintenance jobs on demand.
- Request body:
```json
{"jobs": ["compaction"], "since_hours": 24}
```
- Response body:
```json
{"jobs_started": ["compaction"], "status": "running"}
```

### Curl examples
```bash
curl -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{"user_id":"user-123","history":[{"role":"user","content":"I love sci-fi books."}]}'

curl "http://localhost:8080/v1/retrieve?query=sci-fi&limit=5" \
  -H "X-API-KEY: $API_KEY"
```


## Storage & Retrieval Details

### ChromaDB Collections
- Collection: `memories`
- Embedding model: `text-embedding-3-small` (1536 dims)
- Document: `content`
- IDs: `mem_<uuid>`
- Metadata keys:
  - `user_id: str`
  - `layer: "short-term"|"semantic"|"long-term"`
  - `type: "explicit"|"implicit"`
  - `ttl_epoch: int` (optional; for short-term expiration)
  - `timestamp: iso8601`
  - `confidence: float`
  - `relevance_score: float`

### Indexing & Filters
- Filter by `user_id` for isolation; combine with `layer`/`type` as needed.
- Create secondary keyword index via stored metadata fields for fallback search.

### Ranking
- Hybrid score = `0.8 * semantic_similarity + 0.2 * keyword_overlap`
- Minimum score cutoff: `0.35`; ties broken by `usage_count` and recency.
- Pagination: `limit` (<=50), `offset`.


## Caching Policy (Redis)
- What: Cache top-N short-term retrieval results per `(user_id, query_hash)`.
- TTLs: 60–300 seconds configurable; align with short-term TTL policy.
- Invalidation: On `store` upserts for same `user_id`, evict matching keys.
- Keys: `mem:srch:{user_id}:{hash(query)}` → JSON list of results.


## Scheduler Jobs (APScheduler)
- `ttl_cleanup` (every 15m): Remove expired short-term docs from ChromaDB; evict cache.
- `promotion` (daily): Summarize frequently used short-term into long-term; preserve provenance.
- `compaction` (weekly): Cluster long-term; LLM summarize clusters; archive originals.
- Concurrency limits: Max 1 job per type; batch size default 500 docs.
- Rollback: Keep snapshots of affected IDs; on failure, restore originals.


## Auth & Multitenancy
- Authentication: `X-API-KEY` (or JWT) required for all endpoints.
- Rate limits: Default 60 req/min per key; `429` on exceed with `Retry-After`.
- Isolation: All reads/writes filter by `user_id` at query time; reject cross-user IDs.
- User lifecycle: Support export/delete on request (basic GDPR consideration).


## Security & Compliance
- Secrets: `.env` for local only; use a secrets manager in deployed envs.
- Transport: HTTPS/TLS recommended; do not log sensitive content.
- Storage: Optionally encrypt embeddings and PII at rest.
- PII: Minimize retention; configurable retention windows per layer.
- Audit: Log auth events and admin operations with redaction.


## Reliability
- Retries/backoff for OpenAI/Chroma/Redis (exponential, jitter; max 3).
- Idempotency for `POST /store` via `X-Idempotency-Key` header (optional).
- Dead-letter: Persist failed maintenance jobs with reason and retry window.


## Observability & Performance
- Logging: Structured JSON; include `user_id`, request_id, latency.
- Metrics: p95 latency (store/retrieve), cache hit rate, extraction success %, job durations.
- Tracing: Instrument FastAPI handlers and Chroma/OpenAI calls (OpenTelemetry).
- Targets: p95 retrieve <150ms (warm cache), <400ms (cold); store <800ms.


## Local Orchestration (Docker Compose)
```yaml
version: "3.9"
services:
  api:
    build: .
    command: uvicorn src.app:app --host 0.0.0.0 --port 8080
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8080:8080"
    depends_on:
      - chroma
      - redis
  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```


## CI/CD & Environments
- CI: Lint, type-check, tests, build image; push on main.
- CD: Deploy to dev → stage → prod with env-specific configs.
- Config: `.env.development`, `.env.staging`, `.env.production` (or secrets manager).


## Governance
- LICENSE: Choose permissive (e.g., MIT) or copyleft as needed.
- CONTRIBUTING: PR process, coding standards, commit guidelines.
- CODE_OF_CONDUCT: Expected behavior, reporting process.


## Progress Tracker
- [x] Phase 1 — Project Setup & Models
- [ ] Phase 2 — Extraction Engine
- [ ] Phase 3 — Storage & Retrieval
- [ ] Phase 4 — Auth & Interfaces
- [ ] Phase 5 — Forgetting & Maintenance
- [ ] Phase 6 — Security, Testing, Deployment
- [x] API Contracts implemented
- [x] Docker Compose validated locally
- [ ] Metrics & dashboards in place
- [x] CI/CD pipeline green

 
### Local Build & Run
- Build Docker image:
```bash
docker build -t agentic-memories:local .
```
- Run with Docker Compose (API + Chroma + Redis):
```bash
docker compose up --build
```
API will be available at http://localhost:8080, ChromaDB at http://localhost:8000.

### CI Notes
- GitHub Actions workflow at `.github/workflows/ci.yml`:
  - Installs dependencies, runs tests (`pytest`), and builds the Docker image.
  - Triggers on pushes/PRs to `main`.

### OpenAPI Docs
- Local docs available when running the API:
  - Swagger UI: http://localhost:8080/docs
  - ReDoc: http://localhost:8080/redoc

### Verification Steps
- Start locally: `uvicorn src.app:app --reload`
- Visit `/docs` and execute `GET /health` and `GET /v1/retrieve` with a sample query.
- With Docker Compose: `docker compose up --build` then open the same URLs.

## Progress Log
- 2025-09-11: Phase 1 started. Added `requirements.txt`, FastAPI app with `/health` (`src/app.py`), Pydantic `Memory` model (`src/models.py`), ChromaDB client helper (`src/dependencies/chroma.py`), basic health test (`tests/test_health.py`), `Dockerfile`, GitHub Actions CI, and `docker-compose.yml` for local run.
- 2025-09-11: Added /v1 API skeleton with stubbed `POST /v1/store`, `GET /v1/retrieve`, `POST /v1/forget`, `POST /v1/maintenance`; introduced request/response schemas in `src/schemas.py`; added tests in `tests/test_api.py`.
- 2025-09-11: Phase 1 completed. Local tests passing; OpenAPI docs available at `/docs`. CI workflow added and Compose in place for local deployment.

 