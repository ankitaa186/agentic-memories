# Source Tree Analysis

**Project:** agentic-memories
**Type:** Multi-part (Backend API + Web UI)
**Repository Structure:** Monorepo with separate server and client parts

---

## Project Root

```
agentic-memories/
├── src/                          # 🔹 Backend API (Python/FastAPI)
├── ui/                           # 🔹 Web UI (React/TypeScript)
├── migrations/                   # Database migration scripts
├── tests/                        # Python test suites
├── scripts/                      # Utility scripts
├── docs/                         # Generated documentation
├── .github/workflows/            # CI/CD GitHub Actions
├── docker-compose.yml            # Container orchestration
├── Dockerfile                    # API container definition
├── requirements.txt              # Python dependencies
├── run_docker.sh                 # Docker startup script
└── README.md                     # 📖 Main documentation (primary source of truth)
```

---

## Part 1: Backend API (src/)

**Entry Point:** `src/app.py`
**Language:** Python 3.12+
**Framework:** FastAPI 0.111.0

```
src/
├── app.py                        # ⭐ FastAPI application, API endpoints, middleware
├── config.py                     # Environment configuration and settings
├── models.py                     # Pydantic data models
├── schemas.py                    # API request/response schemas
│
├── dependencies/                 # Database client connections
│   ├── chroma.py                # ChromaDB vector database client
│   ├── timescale.py             # TimescaleDB/PostgreSQL client
│   ├── neo4j_client.py          # Neo4j graph database client
│   ├── redis_client.py          # Redis cache client
│   ├── langfuse_client.py       # Langfuse observability client
│   └── cloudflare_access.py     # Cloudflare authentication
│
├── services/                     # Business logic layer
│   ├── unified_ingestion_graph.py  # ⭐ LangGraph extraction pipeline (state machine)
│   ├── extraction.py            # Legacy extraction utilities
│   ├── retrieval.py             # ChromaDB semantic search
│   ├── hybrid_retrieval.py      # Multi-database retrieval
│   ├── reconstruction.py        # Narrative construction service
│   ├── persona_retrieval.py     # Persona-aware retrieval copilot
│   ├── episodic_memory.py       # Episodic memory service
│   ├── emotional_memory.py      # Emotional memory service
│   ├── procedural_memory.py     # Procedural memory (skills) service
│   ├── portfolio_service.py     # Financial portfolio service
│   ├── memory_context.py        # Context management
│   ├── persona_state.py         # Persona state management
│   ├── summary_manager.py       # Summary generation
│   ├── storage.py               # Memory storage orchestration
│   ├── compaction_graph.py      # Memory compaction state machine
│   ├── compaction_ops.py        # Compaction operations
│   ├── forget.py                # Forgetting mechanism
│   ├── graph_extraction.py      # Graph data extraction
│   ├── embedding_utils.py       # Vector embedding utilities
│   ├── extract_utils.py         # LLM call utilities
│   ├── prompts.py               # LLM prompt templates (legacy)
│   ├── prompts_v2.py            # LLM prompt templates (current)
│   ├── tracing.py               # Langfuse tracing integration
│   ├── chat_runtime.py          # Chat runtime bridge
│   └── memory_router.py         # Memory routing logic
│
├── memory_orchestrator/          # Adaptive Memory Orchestrator
│   ├── orchestrator.py          # ⭐ Main orchestrator logic
│   ├── client_api.py            # Orchestrator client API
│   ├── ingestion.py             # Turn-by-turn ingestion
│   ├── retrieval.py             # Orchestrator retrieval
│   ├── message_adapter.py       # Message format adaptation
│   └── policies.py              # Retrieval and injection policies
│
├── storage/                      # Storage layer
│   ├── timescale_client.py      # Direct TimescaleDB operations
│   └── orchestrator.py          # Storage orchestration
│
└── core/                         # Core utilities
    └── maintenance/              # Maintenance tasks
```

### Critical Backend Files

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `app.py` | FastAPI endpoints, middleware, health checks | ~1300 |
| `unified_ingestion_graph.py` | LangGraph extraction state machine | ~800 |
| `orchestrator.py` | Adaptive memory orchestrator | ~600 |
| `reconstruction.py` | Narrative construction | ~400 |
| `retrieval.py` | Semantic search implementation | ~300 |
| `hybrid_retrieval.py` | Multi-database retrieval | ~400 |

### Database Connections (dependencies/)

- **ChromaDB**: Vector embeddings, semantic search (all queries)
- **TimescaleDB**: Time-series hypertables (episodic, emotional, portfolio snapshots)
- **PostgreSQL**: Structured data (procedural, semantic, portfolio, identity)
- **Neo4j**: Graph relationships (skill dependencies - write-only currently)
- **Redis**: Short-term memory cache, activity tracking

### Services Layer Architecture

```
API Endpoint (app.py)
    ↓
Service Layer (services/)
    ↓
Database Clients (dependencies/)
    ↓
External Databases
```

---

## Part 2: Web UI (ui/)

**Entry Point:** `ui/src/main.tsx`
**Framework:** React 18 + TypeScript
**Build Tool:** Vite 5.4.8

```
ui/
├── src/
│   ├── main.tsx                 # ⭐ Application entry point
│   ├── App.tsx                  # Root component (if exists)
│   │
│   ├── pages/                   # Route-based page components
│   │   ├── AppLayout.tsx        # Main layout wrapper
│   │   ├── Store.tsx            # Memory ingestion page
│   │   ├── Retrieve.tsx         # Memory search page
│   │   ├── Browser.tsx          # Memory timeline browser
│   │   ├── Structured.tsx       # Categorized memory view
│   │   └── Health.tsx           # Service health dashboard
│   │
│   ├── components/              # Reusable components
│   │   └── DevConsole.tsx       # Developer debug console
│   │
│   └── lib/                     # Utility libraries
│       ├── api.ts               # ⭐ API client (calls backend)
│       └── devlog.ts            # Development logging
│
├── tests/                       # Playwright E2E tests
├── package.json                 # Dependencies and scripts
├── vite.config.ts               # Vite build configuration
├── tsconfig.json                # TypeScript configuration
├── tailwind.config.js           # Tailwind CSS configuration
├── postcss.config.js            # PostCSS configuration
└── index.html                   # HTML entry point
```

### UI Routing Structure

```
/ (root)
├─ /store           → Memory ingestion form
├─ /retrieve        → Search and retrieval
├─ /browser         → Timeline view
├─ /structured      → Categorized view
└─ /health          → Service health monitoring
```

---

## Database Migrations (migrations/)

```
migrations/
├── migrate.sh                   # ⭐ Migration CLI tool
├── generate.sh                  # Migration file generator
├── README.md                    # Migration documentation
│
├── postgres/                    # PostgreSQL migrations
│   ├── 001_procedural_memories.up.sql
│   ├── 002_skill_progressions.up.sql
│   ├── 003_semantic_memories.up.sql
│   ├── 004_identity_memories.up.sql
│   ├── 005_portfolio_holdings.up.sql
│   ├── 006_portfolio_transactions.up.sql
│   ├── 007_portfolio_preferences.up.sql
│   └── 008_emotional_patterns.up.sql
│
├── timescaledb/                 # TimescaleDB hypertables
│   ├── 001_episodic_memories.up.sql
│   ├── 002_emotional_memories.up.sql
│   └── 003_portfolio_snapshots.up.sql
│
├── neo4j/                       # Neo4j Cypher migrations
│   ├── 001_skill_nodes.cypher
│   └── 002_skill_relationships.cypher
│
└── chromadb/                    # ChromaDB collection setup
    └── init_collections.py
```

**Migration Features:**
- Up/down migration support
- Rollback capabilities
- Dry-run mode
- Migration locking
- History tracking in `migration_history` table

---

## Testing Infrastructure (tests/)

```
tests/
├── unit/                        # Unit tests
│   └── test_*.py                # pytest unit tests
│
├── e2e/                         # End-to-end integration tests
│   ├── run_e2e_tests.sh         # E2E test runner
│   ├── tests/                   # Python E2E test cases
│   ├── results/                 # Test results and reports
│   ├── logs/                    # Test execution logs
│   └── fixtures/                # Test data fixtures
│
├── evals/                       # LLM evaluation tests
│   ├── test_extraction.py       # Extraction quality tests
│   └── fixtures/                # Eval test data
│
├── memory_orchestrator/         # Orchestrator-specific tests
│   └── test_*.py                # Orchestrator test suite
│
└── fixtures/                    # Shared test fixtures
    └── sample_data.json
```

**Testing Tools:**
- **pytest**: Python unit and integration tests
- **Playwright**: UI end-to-end tests (in `ui/tests/`)
- **Custom evals**: LLM extraction quality tests

---

## Documentation (docs/)

```
docs/
├── bmm-index.md                 # Generated BMM documentation index (this file)
├── api-contracts-server.md      # Backend API documentation
├── data-models-server.md        # Database schema documentation
├── component-inventory-client.md # UI component documentation
├── source-tree-analysis.md      # This file
├── project-overview.md          # (To be generated)
├── architecture-server.md       # (To be generated)
├── architecture-client.md       # (To be generated)
├── development-guide-server.md  # (To be generated)
├── development-guide-client.md  # (To be generated)
├── deployment-guide.md          # (To be generated)
├── integration-architecture.md  # (To be generated)
│
├── sprint-artifacts/            # Sprint planning and stories
│
└── project-scan-report.json     # Workflow state (resume support)
```

---

## Deployment & DevOps

```
.github/workflows/               # GitHub Actions CI/CD
├── test.yml                     # Test pipeline
├── build.yml                    # Build pipeline
└── deploy.yml                   # Deployment pipeline

docker-compose.yml               # Multi-container orchestration
Dockerfile                       # API container definition
ui/Dockerfile                    # (If exists) UI container
run_docker.sh                    # Docker startup automation
```

---

## Scripts & Utilities

```
scripts/
├── setup.sh                     # Project setup script
├── db_reset.sh                  # Database reset utility
└── (other utility scripts)
```

---

## Configuration Files

```
Project Root:
├── .env                         # Environment variables (not in git)
├── env.example                  # Environment template
├── .gitignore                   # Git exclusions
├── .dockerignore                # Docker exclusions
├── requirements.txt             # Python dependencies
└── pyproject.toml               # (If exists) Python project config

UI Root (ui/):
├── package.json                 # Node.js dependencies
├── tsconfig.json                # TypeScript configuration
├── vite.config.ts               # Vite build config
├── tailwind.config.js           # Tailwind CSS config
└── postcss.config.js            # PostCSS config
```

---

## Integration Points

### Backend → Databases

```
src/app.py (FastAPI)
    ↓
src/services/* (Business Logic)
    ↓
src/dependencies/* (DB Clients)
    ↓
[ChromaDB, TimescaleDB, PostgreSQL, Neo4j, Redis]
```

### Frontend → Backend

```
ui/src/lib/api.ts (API Client)
    ↓
HTTP/JSON REST API
    ↓
src/app.py (FastAPI Endpoints)
```

### LLM Integration

```
src/services/unified_ingestion_graph.py (LangGraph)
    ↓
src/services/extract_utils.py (LLM Caller)
    ↓
[OpenAI GPT-4 | xAI Grok]
    ↓
src/services/tracing.py (Langfuse)
```

---

## Data Flow Example: Memory Storage

```
1. User → UI (Store.tsx)
    ↓
2. HTTP POST → /v1/store
    ↓
3. app.py → unified_ingestion_graph.py
    ↓
4. LangGraph Pipeline:
   - Worthiness Check
   - Memory Extraction (LLM)
   - Classification
    ↓
5. storage.py → Parallel writes:
   - ChromaDB (vector embedding)
   - TimescaleDB (if episodic/emotional)
   - PostgreSQL (if procedural/portfolio/semantic)
   - Neo4j (if skill relationships)
   - Redis (short-term cache)
    ↓
6. Response → UI (display created memories)
```

---

## Key Directories by Purpose

| Directory | Purpose | Primary Language |
|-----------|---------|------------------|
| `src/` | Backend API server | Python |
| `ui/src/` | Web UI client | TypeScript/React |
| `migrations/` | Database schemas | SQL/Cypher/Python |
| `tests/` | Test suites | Python/Playwright |
| `docs/` | Generated documentation | Markdown |
| `.github/workflows/` | CI/CD pipelines | YAML |

---

## File Count Summary

**Backend:**
- Python files: ~45
- Services: ~25
- Dependencies: ~8

**Frontend:**
- TypeScript/TSX files: ~10
- Pages: 6
- Components: ~2

**Migrations:**
- PostgreSQL: 8 migrations
- TimescaleDB: 3 migrations
- Neo4j: 2 migrations
- ChromaDB: 1 initialization script

**Total Source Files:** ~70 (excluding tests)

---

## Critical Entry Points

1. **Backend API:** `src/app.py` (FastAPI application)
2. **Frontend UI:** `ui/src/main.tsx` (React entry)
3. **Migrations:** `migrations/migrate.sh` (DB setup)
4. **Docker:** `docker-compose.yml` (Full stack deployment)
5. **Tests:** `pytest tests/` or `cd ui && npm run test:e2e`
