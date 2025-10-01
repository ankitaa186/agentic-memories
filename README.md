#Happy Birthday Annie!!

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
  - [Phase 7: Web UI and Developer Console](#phase-7-web-ui-and-developer-console)
    - [Subphase 7.1: Scaffolding, Health, and Retrieve (empty query)](#subphase-71-scaffolding-health-and-retrieve-empty-query)
    - [Subphase 7.2: Store Transcript and Memory Browser](#subphase-72-store-transcript-and-memory-browser)
    - [Subphase 7.3: Structured Retrieve and Debug Tools](#subphase-73-structured-retrieve-and-debug-tools)
    - [Subphase 7.4: Polish, Accessibility, and Playwright E2E](#subphase-74-polish-accessibility-and-playwright-e2e)
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

4) Configure LLM provider and key (required)
```bash
# Choose provider: openai (default) or xai (Grok)
export LLM_PROVIDER=openai
export OPENAI_API_KEY=YOUR_REAL_KEY
# For xAI:
# export LLM_PROVIDER=xai
# export XAI_API_KEY=YOUR_XAI_KEY
```

5) Run the API
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

## Local Development (venv)

### Ubuntu/Debian prerequisites
- Ensure system packages for venv and builds (for `chroma-hnswlib`) are installed:
```bash
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-dev build-essential cmake
```

### Create and use a local virtual environment
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
```

### Environment variables
- Required LLM config:
  - `LLM_PROVIDER` = `openai` | `xai` (alias `grok` accepted)
  - If `openai`: `OPENAI_API_KEY` (default model: `gpt-4o` unless `EXTRACTION_MODEL` set)
  - If `xai`: `XAI_API_KEY` (default model: `grok-4-fast-reasoning` unless `EXTRACTION_MODEL` set). Optional: `XAI_BASE_URL` (default `https://api.x.ai/v1`).
  - Timeouts: `EXTRACTION_TIMEOUT_MS` default `180000` (3 minutes). xAI calls enforce a minimum of 180 seconds.
- External ChromaDB (recommended for local):
  - `CHROMA_HOST=localhost`
  - `CHROMA_PORT=8000`
  - `CHROMA_TENANT=agentic-memories`
  - `CHROMA_DATABASE=memories`
 - Cloudflare Access (optional; for auth):
   - `CF_ACCESS_AUD=<Access App Audience UUID>`
   - `CF_ACCESS_TEAM_DOMAIN=<team subdomain, e.g., memoryforge>`

You can place these in `.env` (the app auto-loads it):
```bash
cp env.example .env
echo "LLM_PROVIDER=openai" >> .env
echo "OPENAI_API_KEY=your_key_here" >> .env
# For xAI:
# echo "LLM_PROVIDER=xai" >> .env
# echo "XAI_API_KEY=your_xai_key_here" >> .env
```

### Run locally (without Docker)
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

### Run tests
```bash
pytest -q
```

### Troubleshooting
- If installation fails building `chroma-hnswlib` wheels, install system build tools:
```bash
sudo apt-get install -y build-essential python3-dev cmake
```
- Ensure the external ChromaDB server is reachable at `http://localhost:8000`.

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
- AI/ML: OpenAI and xAI (Grok) for LLMs; LangChain; LangGraph for state machines
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

Phase 2 extraction pipeline (LLM-only) now uses a LangGraph state machine:
- Nodes: worthiness → extraction → end
- Worthiness: classify if memory-worthy (aggressive recall allowed)
- Extraction: produce atomic memories with tags and metadata; we normalize outputs (prefix "User ", present tense, preserve temporal phrases) and derive a `next_action` memory when a project provides one.
Finance/Portfolio-aware extraction (2025‑10‑01): prompts extended to extract finance intent and portfolio structure. New `portfolio` object supports fields like `ticker`, `intent` (buy/sell/hold/watch), `position`, `shares`, `avg_price`, `target_price`, `stop_loss`, `time_horizon`, `concern`, `goal`, `risk_tolerance`, `notes`, and `holdings[]` (public/private equity, ETFs, funds, bonds, crypto, cash). Worthiness rules prioritize stock/trading content; tags include `finance` and `ticker:<SYMBOL>`.

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
- `GET /retrieve` — Query params: `query`, `user_id` (required), optional `layer`, `type`; returns ranked memories
- `GET /retrieve` — Query params: `user_id` (required), optional `query`, `layer`, `type`; returns ranked memories. If `query` is omitted or empty, all memories for the user are returned.
- `POST /retrieve/structured` — LLM-organized, category-based retrieval (emotions, behaviors, personal, professional, habits, skills_tools, projects, relationships, learning_journal, other). If `query` is empty, the service aggregates ALL memories for the user and categorizes them.
- `GET /v1/me` — Returns the authenticated user's identity (when Cloudflare Access is configured).
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

### Environment Setup (.env)
- Copy `env.example` to `.env` and fill in values:
```bash
# PowerShell
Copy-Item env.example .env
# bash
cp env.example .env
```
- Required: `OPENAI_API_KEY`
- Optional: `CHROMA_HOST`, `CHROMA_PORT`, `REDIS_URL`, `CHROMA_TENANT`, `CHROMA_DATABASE`
- The app auto-loads `.env` at startup.

### Configuration Wrapper
- Centralized in `src/config.py` and auto-loads `.env` via `python-dotenv`.
- Getters (cached): `get_openai_api_key()`, `get_chroma_host()`, `get_chroma_port()`, `get_redis_url()`.
- Dependencies (`chroma`, `redis_client`) and `/health/full` use these getters, ensuring consistent config.

### Run
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

### Testing
```bash
# Run unit tests
pytest -q

# Run E2E tests against deployed app
./tests/e2e/run_e2e_tests.sh

# Or use Makefile
make test          # Unit tests
make test-e2e      # E2E tests
```

Targets: unit, integration, and E2E (>80% coverage), including multi‑user isolation, short‑term persistence/expiration, and forgetting logic.

## Phased Build Plan
Iterative development using Cursor. Each phase lists objective, tasks, deliverables, dependencies, and a sample prompt.

### Phase 7: Web UI and Developer Console (1-2 weeks)
Objective: Provide a simple, beautiful, and productive UI for interacting with the APIs without altering backend contracts. Focus on fast iteration, observability, and zero-config local use against a running Docker deployment.

Subphases:

#### Subphase 7.1: Scaffolding, Health, and Retrieve (empty query)
Objective: Establish the UI skeleton and validate connectivity to the running API; enable core retrieval flows including empty `query` path.

Tasks:
- Create React + Vite + TypeScript app with Tailwind CSS and Radix UI primitives.
- Configure `VITE_API_BASE_URL` (fallback to `/`). Add `.env.example` for UI.
- Global layout: top bar with environment indicator and `user_id` selector (persist to URL + localStorage, default `test_user_22`).
- Health screen: call `GET /health` (and optionally `/health/full` when available); show status cards.
- Retrieve screen: form with `user_id` (required) and optional `query`, `layer`, `type`, `limit`, `offset`; results list with score and metadata chips; raw JSON toggle; supports empty `query` to list all.
- API client: React Query hooks with retries and error toasts; shared headers; timing metrics per call.

Deliverables:
- `ui/` project scaffold; working Health and Retrieve screens.
- Docs for `VITE_API_BASE_URL` and local run.

Cursor Prompt:
"Scaffold a React + Vite + TS app under `ui/` with Tailwind and Radix. Add Health and Retrieve screens calling `/v1/retrieve` with required `user_id` and optional `query`. Persist `user_id` in URL and localStorage."

#### Subphase 7.2: Store Transcript and Memory Browser
Objective: Enable storing conversations and browsing all memories for a user.

Tasks:
- Store Transcript screen: multi-turn composer (append user/assistant turns), submit to `POST /v1/store` with `user_id`, show extracted memories and metrics (`duplicates_avoided`, `updates_made`, `existing_memories_checked`).
- Memory Browser screen: paginated table/list of all memories for a `user_id`; filters by `layer`, `type`; copy ID; export JSON/CSV; raw JSON toggle per row.
- Utilities: clipboard copy, JSON viewer component, date/time formatting.

Deliverables:
- Store flow wired with response rendering and metrics chips.
- Browser with pagination, filters, and export.

Cursor Prompt:
"Add Store Transcript and Memory Browser screens. POST `/v1/store` renders extracted memories and three metrics. Browser lists all memories for `user_id` with filters and pagination, plus export and copy."

#### Subphase 7.3: Structured Retrieve and Debug Tools
Objective: Visualize LLM-organized retrieval and provide developer observability.

Tasks:
- Structured Retrieve screen: call `POST /v1/retrieve/structured` with `user_id` and optional `query` (allow empty to categorize ALL). Render category sections with counts; collapsible accordions; raw JSON view.
- Developer Console panel (toggle): timeline of last N API calls with status, duration, request/response sizes; copy request/response; redaction for secrets.
- Advanced filters UI: add query param controls for `layer`, `type`, `limit`, `offset` across relevant screens.

Deliverables:
- Structured categories UI with stable layout and JSON toggle.
- Developer Console panel integrated globally.

Cursor Prompt:
"Implement Structured Retrieve UI for `/v1/retrieve/structured`, rendering fixed categories and handling empty `query` by categorizing all memories. Add a developer console panel that logs API calls with durations and allows copying."

#### Subphase 7.4: Polish, Accessibility, and Playwright E2E
Objective: Make the UI accessible, resilient, and covered by E2E tests.

Tasks:
- Accessibility: keyboard navigation, focus rings, color contrast; aria labels on interactive elements; screen-reader-friendly JSON sections.
- Error/empty states: friendly guidance and sample payloads; debounced inputs; disable submit while in-flight.
- Testing: MSW for integration tests; Playwright E2E against deployed API (reuse existing Docker stack). CI job to build UI and run tests.
- Deployment: `vite build`; serve static assets from FastAPI at `/static/ui` or via separate Nginx container. Add compose override example.

Deliverables:
- Playwright E2E suite covering Health, Retrieve (empty and non-empty), Store, Structured.
- Documented deployment options and CI integration.

Cursor Prompt:
"Add Playwright E2E tests for Health, Retrieve (empty and non-empty), Store, and Structured screens. Configure CI to run MSW-based integration tests and Playwright against a running API. Provide a FastAPI static-files option for serving the built UI."

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
Objective: Persist extracted memories to ChromaDB and retrieve efficiently with caching.

Data model & schema:
- Collection: `memories_3072` (standardized by embedding dimension)
- Embedding model: `text-embedding-3-large` (3072 dims)
- Document: `content`
- IDs: `mem_<uuid>`
- Metadata: `user_id`, `layer`, `type`, `timestamp`, `ttl_epoch?`, `confidence`, `relevance_score`, `usage_count`, `tags` (stored as JSON string), `project?`, `relationship?`, `learning_journal?`

Services:
- `services/storage.py`
  - `init_chroma_collection(name)` using Chroma v2 HTTP APIs
  - `upsert_memories(user_id, memories: List[Memory]) -> List[str]` (batch embeddings; compute `ttl_epoch` for short‑term)
  - `increment_usage_count(ids: List[str])`
- `services/retrieval.py`
  - `search_memories(user_id, query, filters: {layer?, type?}, limit=10, offset=0)`
    - Semantic search via query embeddings (local) + keyword fallback; hybrid scoring
    - Filters by `user_id` (mandatory), optional `layer`/`type`; best‑effort tags filter (tags stored as JSON string)
    - Pagination; optional Redis cache for short‑term

API wiring:
- `POST /v1/store`: run context-aware extraction (considers existing memories), persist to Chroma, return real IDs; bump user cache namespace
- `GET /v1/retrieve`: query Chroma with query embeddings; apply filters; cache + paginate; requires user_id
- `POST /v1/retrieve/structured`: LLM organizes candidate memories into predefined categories and returns structured sets

Performance targets:
- Retrieve p95: <150ms warm, <400ms cold; Store p95: <800ms (5 memories)

Observability:
- Logs: user_id, request_id, latency, cache hit/miss; Metrics: store/retrieve latency, cache hit‑rate, avg results; Tracing around Chroma/Redis

Testing:
- Integration tests: multi‑user isolation; filters; pagination; short‑term TTL; cache hit/invalidations; hybrid search behavior

Dependencies: Phases 1‑2.

Deliverables: `services/storage.py`, `services/retrieval.py`; endpoint wiring; integration tests; perf smoke.

Step-by-step implementation sequence:
1) ChromaDB collection setup (v2)
2) Upsert pipeline (store)
3) Retrieval pipeline with query embeddings
4) Usage tracking
5) Redis cache (short‑term acceleration)
6) Wire API endpoints
7) Integration tests
8) Observability & perf smoke
9) Docs & examples

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

#### Maintenance: LangGraph Compaction Graph (Design)
Objective: Prune, deduplicate, recategorize, and promote/demote memories using a resumable LangGraph pipeline, with finance-aware consolidation.

State:
- `user_id`, `dry_run`, `page_offset`, `page_size`
- `candidates: List[Memory]`
- `clusters_by_bucket: Dict[bucket, List[Memory]]`
- `dedup_actions`, `recat_actions`, `finance_actions`, `promote_actions`, `prune_actions`, `upserts`, `deletes`
- `report`

Buckets:
- `emotions`, `behaviors`, `personal`, `professional`, `habits`, `skills_tools`, `projects`, `relationships`, `learning_journal`, `other`, `finance`

Nodes (in order):
- `load_candidates`: page memories (age/TTL filters)
- `ensure_embeddings`: backfill/re-embed changed items
- `bucketize`: heuristics; mark `uncertain`
- `recategorize_llm`: LLM pass for `uncertain`/misfiled
- `deduplicate_bucket` (parallel map): cluster by cosine, select canonical, merge tags/metadata, mark dups
- `finance_consolidate`: group by `ticker`, consolidate holdings/goals, collapse chatter, preserve sources
- `ttl_and_promotion`: expire/prune, promote enduring short-term to semantic, demote/snapshot outdated goals
- `summarize_long_term`: cluster old semantic → long-term summaries; archive originals
- `write_changes`: upsert edits/new, delete pruned, bump cache namespace (skip if `dry_run`)
- `paginate_or_end`: next page or `audit_report`
- `audit_report`: metrics and sample diffs

Parallelism:
- Parallel over buckets; inside finance, parallel over tickers.

Thresholds (tunable):
- duplicate: cosine ≥ 0.88
- promotion window: short-term age ≥ N days and usage_count ≥ M
- prune low-signal: confidence < 0.3 and usage_count == 0 (except finance)

Finance guardrails:
- never drop last canonical per ticker; maintain `source_memory_id`s and timestamps
- coalesce repeated watchlist chatter into one canonical `intent=watch` per ticker

Triggers & Scheduling:
- Daily at UTC midnight; run only for users active in last 24h
- On `/v1/store`, add `user_id` to Redis set `recent_users:<UTC_YYYYMMDD>`; scheduler reads set and enqueues graph
- Fallback (no Redis): metadata check via Chroma where `timestamp` ≥ now−24h

Safety:
- `dry_run` shows diff previews and counts; max ops per run; per-user rate limits; resumable checkpoints

```python
from langgraph.graph import StateGraph, END

def build_compaction_graph():
    g = StateGraph(dict)
    g.add_node("load_candidates", load_candidates)
    g.add_node("ensure_embeddings", ensure_embeddings)
    g.add_node("bucketize", bucketize)
    g.add_node("recategorize_llm", recategorize_llm)
    g.add_node("dedup_buckets", dedup_buckets_parallel)
    g.add_node("finance_consolidate", finance_consolidate)
    g.add_node("ttl_and_promotion", ttl_and_promotion)
    g.add_node("summarize_long_term", summarize_long_term)
    g.add_node("write_changes", write_changes)
    g.add_node("paginate_or_end", paginate_or_end)
    g.add_node("audit_report", audit_report)

    g.set_entry_point("load_candidates")
    g.add_edge("load_candidates", "ensure_embeddings")
    g.add_edge("ensure_embeddings", "bucketize")
    g.add_edge("bucketize", "recategorize_llm")
    g.add_edge("recategorize_llm", "dedup_buckets")
    g.add_edge("dedup_buckets", "finance_consolidate")
    g.add_edge("finance_consolidate", "ttl_and_promotion")
    g.add_edge("ttl_and_promotion", "summarize_long_term")
    g.add_edge("summarize_long_term", "write_changes")
    g.add_edge("write_changes", "paginate_or_end")
    g.add_conditional_edges(
        "paginate_or_end",
        lambda s: "load_candidates" if s.get("has_more") else "audit_report",
        {"load_candidates": "load_candidates", "audit_report": "audit_report"},
    )
    g.add_edge("audit_report", END)
    return g
```

### Phase 6: Security, Testing, Optimization, and Deployment (2-3 days)
Objective: Polish for production readiness.

Tasks:
- Add security: Rate limiting, encryption for sensitive data.
- Comprehensive testing: Unit/integration/E2E (Pytest >80% coverage); Simulate multi-user, forgetting scenarios (including short‑term persistence and expiration).
- Optimize: Batch embeddings, pagination for large retrievals; Ensure Redis‑ChromaDB sync for short‑term.
- Dockerize app; Deployment guide (run with ChromaDB on port 8000).

Dependencies: All prior.

Deliverables: Test suite; Dockerfile; README updates with run instructions.

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
- Purpose: Retrieve ranked memories for a query (or all if no query provided).
- Query params: `user_id` (required), `query` (optional), `layer` (optional), `type` (optional), `limit` (default 10), `offset` (default 0). If `query` is omitted or empty, all memories for the user are returned.
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

### POST /v1/retrieve/structured
- Purpose: Retrieve and organize memories into categories via LLM.
- Request body:
```json
{"user_id":"user-123","query":"reading preferences","limit":50}
```
- Response body (keys always present):
```json
{
  "emotions": [], "behaviors": [], "personal": [], "professional": [],
  "habits": [], "skills_tools": [], "projects": [], "relationships": [],
  "learning_journal": [], "other": [ { "id": "mem_01", "content": "...", ... } ],
  "finance": {
    "portfolio": {"user_id": "user-123", "holdings": [
      {"asset_type": "public_equity", "ticker": "TSLA", "shares": 10}
    ], "counts_by_asset_type": {"public_equity": 1}},
    "goals": [ { "text": "User watches TSLA for a pullback.", "source_memory_id": "mem_xyz" } ]
  }
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

curl "http://localhost:8080/v1/retrieve?query=sci-fi&user_id=user-123&limit=5" \
  -H "X-API-KEY: $API_KEY"

# Retrieve ALL memories (no query)
curl -s "http://localhost:8080/v1/retrieve?user_id=user-123&limit=10" \
  -H "X-API-KEY: $API_KEY"

curl -s -X POST http://localhost:8080/v1/retrieve/structured \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-123","query":"reading preferences"}'

# Structured retrieval across ALL memories (empty query)
curl -s -X POST http://localhost:8080/v1/retrieve/structured \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-123","query":"","limit":100}'
```


## Storage & Retrieval Details

### ChromaDB Collections
- Collection: `memories_3072` (standardized by embedding dimension)
- Embedding model: `text-embedding-3-large` (3072 dims)
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
  - `usage_count: int`
  - `tags: string (JSON-serialized list)`
  - `project: string (JSON)`
  - `relationship: string (JSON)`
  - `learning_journal: string (JSON)`
  - `portfolio: string (JSON)`

### Indexing & Filters
- Filter by `user_id` for isolation; combine with `layer`/`type` as needed.
- Tags are stored as JSON string; filtering is best‑effort via `$contains` on the string.

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
- `compaction` (daily, conditional): Run at UTC midnight only for users who created memories in the last 24 hours. `/v1/store` should add `user_id` to `recent_users:<UTC_YYYYMMDD>` in Redis; the scheduler reads this set and enqueues LangGraph compaction per user. Fallback if Redis unavailable: sample-check via Chroma `timestamp` ≥ now−24h.
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
    image: agentic-memories:local
    restart: unless-stopped
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - XAI_API_KEY=${XAI_API_KEY}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - CHROMA_HOST=${CHROMA_HOST:-host.docker.internal}
      - CHROMA_PORT=${CHROMA_PORT:-8000}
      - CHROMA_TENANT=${CHROMA_TENANT:-agentic-memories}
      - CHROMA_DATABASE=${CHROMA_DATABASE:-memories}
      - REDIS_URL=redis://redis:6379/0
      - CF_ACCESS_AUD=${CF_ACCESS_AUD}
      - CF_ACCESS_TEAM_DOMAIN=${CF_ACCESS_TEAM_DOMAIN}
    ports:
      - "8080:8080"
    depends_on:
      - redis
  ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL:-}
    image: agentic-memories-ui:local
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - api
  redis:
    image: redis:7-alpine
    restart: unless-stopped
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
- [x] Phase 2 — Extraction Engine
- [x] Phase 3 — Storage & Retrieval
- [x] Phase 4 — Auth & Interfaces (user_id mandatory, context-aware extraction, optional retrieval query)
- [ ] Phase 5 — Forgetting & Maintenance
- [ ] Phase 6 — Security, Testing, Deployment
- [ ] Phase 7 — Web UI and Developer Console (Subphases 7.1–7.4)
- [x] API Contracts implemented
- [x] Docker Compose validated locally
- [ ] Metrics & dashboards in place
- [x] CI/CD pipeline green

 
### Local Build & Run
- Recommended: helper script
```bash
./run_docker.sh
```
This will interactively create `.env` if missing (prompts with sensible defaults), auto-detect your host IP for `CHROMA_HOST` when unset, and start the stack with restart policies.

- Manual build:
```bash
docker build -t agentic-memories:local .
```
- Manual run (API + Redis; ChromaDB external):
```bash
docker compose up -d --build
```
API: http://localhost:8080. ChromaDB: `http://${CHROMA_HOST:-127.0.0.1}:${CHROMA_PORT:-8000}` (external).

### Web UI
- Local development (requires Node 18+):
  ```bash
  cd ui
  npm install
  # optionally set API base, defaults to http://localhost:8080
  echo "VITE_API_BASE_URL=http://localhost:8080" > .env  # or export before running
  npm run dev
  # open http://localhost:5173
  ```
- Docker (production build via Nginx):
  ```bash
  # builds UI and API; UI at http://localhost:5173
  docker compose up -d --build
  ```
- Pages: Health, Retrieve (supports empty query), Store (shows extraction metrics), Structured (categorizes all when query empty), Browser (paginate/filter). A Developer Console logs API calls and latencies.

#### Deployment modes & API base resolution
- LAN/local: UI targets `http://<host>:8080`.
- Public (Cloudflare): UI uses same-origin `${location.origin}/api`, with Nginx proxying `/api/*` → API.
- Override with `VITE_API_BASE_URL` if needed.

Nginx proxy in `ui/nginx.conf`:
```nginx
location /api/ {
    proxy_pass http://api:8080/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Cf-Access-Jwt-Assertion $http_cf_access_jwt_assertion;
    proxy_set_header Authorization $http_authorization;
}
```

#### Logs & Tail
Follow API logs and filter auth lines:
```bash
docker compose -f /home/ankit/dev/agentic-memories/docker-compose.yml logs -f --tail=200 api
docker compose -f /home/ankit/dev/agentic-memories/docker-compose.yml logs -f --tail=200 api | stdbuf -o0 grep -i "\\[auth\\]"
```

### Cloudflare Access Integration
The API validates Cloudflare Access JWTs and exposes identity via `GET /v1/me`.

- Env vars:
  - `CF_ACCESS_AUD`: Access app Audience (UUID)
  - `CF_ACCESS_TEAM_DOMAIN`: Team domain (e.g., `memoryforge`)
- Token sources accepted:
  - Header: `Cf-Access-Jwt-Assertion`
  - Cookie: `CF_Authorization` (or lowercase `cf_authorization`)
  - Authorization header: `Bearer <token>`
- Endpoint:
  - `GET /v1/me`: returns `{ authenticated, sub, email, name, aud, exp, iss }`. Logs include `[auth]` cookie previews and verification status.
- The UI proxy forwards these headers to the API.

Troubleshooting:
- If logs show missing CF envs, define `CF_ACCESS_AUD` and `CF_ACCESS_TEAM_DOMAIN` (see `env.example`).
- To verify cookies arrive, hit `/v1/me` and watch for `[auth] cookies preview:`.

### CORS Configuration
The API permits local/LAN origins and `https://memoryforge.io` and subdomains via regex.

#### Quick curl checks
```bash
# Preference
curl -s -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-123","history":[{"role":"user","content":"I love sci-fi books."}]}' | jq .

# Project + next action + learning
curl -s -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-456","history":[{"role":"user","content":"Planning a vacation to Japan next month; need to book flights and hotels. I’m trying to get better at Figma."}]}' | jq .
```

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
- 2025-09-13: Health check verified locally at http://localhost:8080/health (status ok).
- 2025-09-13: Stub retrieval verified at /v1/retrieve?query=hello&limit=1 (1 result returned).
- 2025-09-13: Added comprehensive `GET /health/full` (env, ChromaDB, Redis checks) and tests.

- 2025-09-14: Docker updates for external ChromaDB: added `restart: unless-stopped`, removed Chroma service, kept Redis, and introduced `run_docker.sh` (interactive `.env` creation with defaults, host IP auto-detection for `CHROMA_HOST`, compose up/build).

- 2025-09-14: Phase 2 started. Added `src/services/extraction.py` with heuristic explicit/implicit detection, layer assignment with TTL for short-term, and embeddings (OpenAI when configured, deterministic fallback otherwise). Wired `/v1/store` to call extractor and return counts/ids/summary. Added tests (`tests/test_extraction.py`), updated Dockerfile to include tests and `PYTHONPATH`, ensured imports work in container. All tests passing.

- 2025-09-14: Phase 2 upgrade to LLM-only with LangGraph. Removed heuristic path; added strict prompts (worthiness/typing/extraction), normalization (prefix "User ", present tense, temporal retention), derived `next_action` memory, eval harness smoke passing. Added `src/services/graph_extraction.py` and `src/services/extract_utils.py`. `OPENAI_API_KEY` now required at startup and for `/v1/store`.

- 2025-09-14: Phase 3 – Storage/Retrieval upgraded to Chroma v2 HTTP. Standardized collection per embedding dimension (`memories_3072`), serialized complex metadata (e.g., tags) as JSON strings, switched retrieval to local query embeddings, and added an LLM-powered structured retrieval endpoint `/v1/retrieve/structured`. Created tenant/database via v2 where required.

- 2025-09-15: Retrieval updates
- 2025-09-28: Web UI deployment, CORS, and Cloudflare Access
  - UI API base auto-resolution: `host:8080` on LAN, same-origin `/api` on public; removed forcing `:8080` over HTTPS to fix SSL error.
  - UI container now includes Nginx reverse proxy to route `/api/*` → API; `ui` service exposed on port 80.
  - Implemented safe UUID fallback in UI when `crypto.randomUUID` is unavailable.
  - Added CORS for `https://memoryforge.io` and subdomains; LAN origin regex.
  - Retrieval: ensured optional `query` and full-user categorization in structured retrieval; fixed Chroma v2 `get()` include fields; neutral similarity for metadata-only retrieval.
  - Cloudflare Access auth: verify token from header or `CF_Authorization` cookie; added `/v1/me` endpoint; structured `[auth]` logs; documented `CF_ACCESS_AUD` and `CF_ACCESS_TEAM_DOMAIN`.
  - Docker Compose: added `ui` service; `VITE_API_BASE_URL` build arg optional; CF env vars passed to API.
  - `GET /v1/retrieve`: `query` is optional. When omitted/empty, retrieval uses metadata-only path to return all user memories; `user_id` always required.
  - `POST /v1/retrieve/structured`: If `query` is empty, the service aggregates ALL user memories (paged) and categorizes them; if present, focuses on relevancy to the query.
  - Chroma v2 `get`: request supported fields (`documents`, `metadatas`); IDs are mapped from the server response.

- 2025-09-15: Enhanced Memory Extraction with Context Awareness. Added context-aware memory extraction that considers existing memories during extraction to avoid duplicates and capture distinct new preferences. Key improvements:
 - 2025-10-01: Finance portfolio analyzer, provider options, and timeouts
   - LLM provider configurability: `LLM_PROVIDER=openai|xai`, added `XAI_API_KEY` and optional `XAI_BASE_URL`.
   - Extraction prompts: added finance/portfolio schema (`portfolio` with `holdings[]`) and worthiness rules prioritizing stock/trading content with `ticker:<SYMBOL>` tags.
   - Retrieval: `GET /v1/retrieve` and `POST /v1/retrieve/structured` now return a `finance` aggregate (portfolio summary + goals) when applicable.
   - New endpoint: `GET /v1/portfolio/summary` aggregates holdings (public & private) and counts by asset type.
   - Timeouts: increased default `EXTRACTION_TIMEOUT_MS` to 180000 (3 minutes); xAI path enforces 180s min; raised httpx timeouts for Chroma heartbeat and CF JWKS.
   - Scheduler: documented daily-compaction trigger at UTC midnight for users active in the last 24 hours using a Redis activity set.
  - **Memory Context Retrieval**: Created `src/services/memory_context.py` with functions to retrieve relevant existing memories based on conversation topics
  - **Enhanced Prompts**: Updated extraction prompts to handle existing memory context and extract distinct preferences as separate atomic items
  - **Mandatory user_id**: Made `user_id` required for all retrieval operations (GET `/v1/retrieve`)
  - **Multi-preference Extraction**: Enhanced prompts to parse coordinated lists (e.g., "mystery novels and thrillers") into separate memories
  - **Extraction Metrics**: Added `duplicates_avoided`, `updates_made`, and `existing_memories_checked` to API responses
  - **Fixed Circular Imports**: Resolved import issues by creating `src/services/embedding_utils.py`
  - **Comprehensive Testing**: Verified retrieval works with user_id, multi-preference extraction, and context awareness

### ChromaDB Host Configuration
- Set `CHROMA_HOST` and `CHROMA_PORT` for your environment.
- If using Chroma v2 multi-tenancy, also set `CHROMA_TENANT` and `CHROMA_DATABASE` (ensure both exist on the server).
- The app checks Chroma connectivity via `GET /api/v2/heartbeat`.

 
