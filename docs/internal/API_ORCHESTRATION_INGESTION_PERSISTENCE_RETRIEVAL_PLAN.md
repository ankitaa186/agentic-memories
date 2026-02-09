# Remediation Plan for API Orchestration, Ingestion, Persistence, and Retrieval Gaps

## Issue 1 – API surface & orchestration gaps
The FastAPI service centralizes ingestion, retrieval, narrative, forgetting, and portfolio endpoints (`src/api/routes/memory_routes.py`, `src/api/routes/maintenance_routes.py`), but health checks, dependency validation, and scheduler triggers are inconsistent. Maintenance tasks such as compaction (`src/core/maintenance/scheduler.py`) still contain TODOs, and there is no unified startup routine to verify external services (Timescale, Neo4j, Redis, Chroma) before exposing endpoints. Observability is limited to ad-hoc logging without structured tracing or metrics.

:::task-stub{title="Harden FastAPI orchestration and maintenance scheduler"}
1. Add a startup hook in `src/main.py` to validate connectivity to Timescale, Neo4j, Redis, and Chroma via their respective service factories, surfacing actionable errors before the API starts.
2. Expand `src/api/routes/maintenance_routes.py` to expose explicit compaction/forgetting triggers and status endpoints, backed by real scheduler jobs in `src/core/maintenance/scheduler.py`.
3. Replace the TODO in the scheduler with a concrete queueing implementation (e.g., Redis-based work queue) and unit tests in `tests/api/test_scheduler.py`.
4. Introduce structured logging/tracing middleware in `src/api/deps/logging.py` and ensure every route emits request/response spans with correlation IDs.
5. Document operational expectations in `README.md` (API section) for dependencies, maintenance cadence, and monitoring.
:::

## Issue 2 – Ingestion pipeline robustness
`run_unified_ingestion` (`src/core/ingestion/pipeline.py`) orchestrates worthiness checks, extraction, enrichment, and routing, yet failure handling is shallow: missing downstream services fail silently, sentiment enrichment lacks retries, and instrumentation is minimal. The pipeline does not emit per-layer success/failure metrics or support backpressure when downstream stores are unavailable.

:::task-stub{title="Fortify ingestion pipeline error handling and observability"}
1. Refactor `run_unified_ingestion` to wrap each stage (worthiness, extraction, enrichment, routing) in explicit try/except blocks with structured error reports and configurable retry policies (using `tenacity`) stored in `src/core/ingestion/config.py`.
2. Implement per-layer status objects returned from routing functions in `src/core/ingestion/routes/*.py`, capturing success/failure reasons.
3. Emit ingestion metrics (counters, timers) via a new `src/core/telemetry/metrics.py` abstraction with Prometheus exporters; cover worthiness rejections and downstream failures.
4. Add integration tests in `tests/ingestion/test_pipeline.py` simulating missing Neo4j/Timescale services to ensure the pipeline degrades gracefully while still persisting to available stores.
5. Update developer docs (`README_DETAILED.md` ingestion section) to describe the new failure semantics and monitoring hooks.
:::

## Issue 3 – Persistence layer single-path limitation
`upsert_memories` (`src/core/persistence/chroma_store.py`) is the only guaranteed write path. Service classes for Timescale (`src/core/persistence/timescale_service.py`) and Neo4j (`src/core/persistence/graph_service.py`) expect live connections but default to logging errors, leading to silent data loss for episodic/emotional/procedural layers.

:::task-stub{title="Implement resilient multi-store persistence"}
1. Introduce a persistence orchestrator (`src/core/persistence/orchestrator.py`) that fans out writes to Chroma, Timescale, Neo4j, and Redis, capturing per-store outcomes.
2. Enhance Timescale/Neo4j service classes to surface connection status and retry logic; ensure they raise typed exceptions consumed by the orchestrator.
3. Provide fallback storage (e.g., local Postgres tables or file-based queue) when Timescale/Neo4j are down, with reconciliation jobs in `src/core/maintenance/reconciliation.py`.
4. Extend schema migrations under `migrations/` to support any new tables/queues and document deployment steps.
5. Add persistence integration tests in `tests/persistence/test_orchestrator.py` and fixture updates under `tests/fixtures/persistence/`.
6. Update operational documentation (`COMPREHENSIVE_DATA_SOURCES.md`) to explain required credentials, fallback behavior, and recovery workflows.
:::

## Issue 4 – Retrieval & narrative degradation without external DBs
Hybrid retrieval (`src/core/retrieval/hybrid_service.py`) and narrative reconstruction (`src/core/narratives/builder.py`) fall back to no-ops when Timescale/Neo4j are absent, leaving only Chroma semantic search active. Emotional, procedural, and temporal branches return empty results, and the API does not warn callers when responses are partial.

:::task-stub{title="Deliver graceful, transparent hybrid retrieval"}
1. Modify retrieval services to detect unavailable backends and return structured partial results with diagnostic metadata surfaced through the API layer (`src/api/routes/retrieval_routes.py`).
2. Implement cached synthetic features (e.g., precomputed timelines stored in Redis/Postgres) to approximate temporal/graph retrieval when Timescale/Neo4j are offline, updated by background jobs.
3. Upgrade narrative builder logic to consume the new partial-result metadata and adjust storyline construction accordingly, logging explicit gaps.
4. Add user-facing docs in `ui/README.md` and API schema updates (`src/api/schemas/retrieval.py`) to describe partial responses and client handling.
5. Expand test coverage in `tests/retrieval/test_hybrid.py` and `tests/narratives/test_builder.py` to validate fallback pathways and metadata propagation.
:::
