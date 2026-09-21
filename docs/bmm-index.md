# Agentic Memories - Project Documentation Index

## Start here: MCP (preferred)

- [MCP connection guide](MCP.md) — same-process, same-port Streamable HTTP at `http://localhost:8080/mcp`; 43 tools, client examples and access controls.
- [Agent integration guide](internal/CHATBOT_INTEGRATION_GUIDE.md) — MCP first, REST patterns as an alternative.
- [Tool/route inventory](mcp-route-mapping.json) — all 39 application operations plus four documentation endpoints.
- [Current architecture and historical design](architecture.md) — distinguishes implemented MCP from older deferred plans.

MCP support is implemented in the source revision; a deployed instance must be rebuilt with that revision. The generated 2025 index below retains historical context.


**Generated:** 2025-11-15
**Project Type:** Multi-part (Backend API + Web UI)
**Primary Language:** Python (Backend) + TypeScript (Frontend)
**Architecture:** Service-oriented with polyglot persistence

---

## Quick Reference

**Backend API (server)**
- **Type:** Backend (Python/FastAPI)
- **Tech Stack:** Python 3.12+, FastAPI 0.111.0, LangGraph 0.2.25
- **Databases:** ChromaDB, TimescaleDB, PostgreSQL, Redis
- **Root:** `/src/`
- **Entry Point:** `src/app.py`

**Web UI (client)**
- **Type:** Web (React/TypeScript)
- **Tech Stack:** React 18.3.1, TypeScript 5.6.2, Vite 5.4.8
- **Root:** `/ui/`
- **Entry Point:** `ui/src/main.tsx`

---

## 📚 Generated BMM Documentation

### Architecture & Design
- [Source Tree Analysis](./source-tree-analysis.md) - Complete directory structure with annotations
- **[Architecture - Backend](./architecture-server.md)** _(To be generated)_
- **[Architecture - Frontend](./architecture-client.md)** _(To be generated)_
- **[Integration Architecture](./integration-architecture.md)** _(To be generated)_ - How backend and frontend communicate

### API & Data
- [API Contracts - Backend](./api-contracts-server.md) - MCP entry point and supported REST endpoint reference
- [Data Models - Backend](./data-models-server.md) - Complete database schema (11 tables across 3 databases)

### Components & UI
- [Component Inventory - Frontend](./component-inventory-client.md) - All React components and pages

### Development & Operations
- **[Development Guide - Backend](./development-guide-server.md)** _(To be generated)_
- **[Development Guide - Frontend](./development-guide-client.md)** _(To be generated)_
- **[Deployment Guide](./deployment-guide.md)** _(To be generated)_

---

## 📖 Existing Project Documentation

**⭐ Primary Source of Truth:**
- [README.md](../README.md) - **Main documentation** (Last updated: Nov 2, 2025)

**Architecture Deep Dives:**
- [restructure_v2.md](../restructure_v2.md) - Complete v2 architecture vision (70KB, Oct 19, 2025)
- [RETRIEVAL_DATA_FLOW.md](../RETRIEVAL_DATA_FLOW.md) - How retrieval works
- [COMPREHENSIVE_DATA_SOURCES.md](../COMPREHENSIVE_DATA_SOURCES.md) - Database usage analysis

**Latest Features:**
- [CHATBOT_INTEGRATION_GUIDE.md](../CHATBOT_INTEGRATION_GUIDE.md) - Orchestrator API (Oct 21, 2025)
- [RETRIEVAL_OVERHAUL_PLAN.md](../RETRIEVAL_OVERHAUL_PLAN.md) - Persona-aware retrieval (Oct 20, 2025)

**Implementation Status:**
- [V2_IMPLEMENTATION_STATUS.md](../V2_IMPLEMENTATION_STATUS.md) - Current implementation status
- [DEPLOYMENT_TEST_RESULTS.md](../DEPLOYMENT_TEST_RESULTS.md) - Testing and verification

**Database & Migrations:**
- [migrations/README.md](../migrations/README.md) - Migration system guide
- [MIGRATION_ENHANCEMENT_COMPLETE.md](../MIGRATION_ENHANCEMENT_COMPLETE.md)
- [SCHEMA_AUDIT_FINAL.md](../SCHEMA_AUDIT_FINAL.md)

**Historical/Planning Docs:**
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- [PHASE2_COMPLETION_SUMMARY.md](../PHASE2_COMPLETION_SUMMARY.md)
- [PHASE4_COMPLETE.md](../PHASE4_COMPLETE.md)
- [LANGFUSE_IMPLEMENTATION.md](../LANGFUSE_IMPLEMENTATION.md)
- [ENHANCED_EXTRACTION_SUMMARY.md](../ENHANCED_EXTRACTION_SUMMARY.md)

---

## 🚀 Getting Started

### For New Developers

1. **Read First:**
   - [README.md](../README.md) - Start here for project overview
   - [Source Tree Analysis](./source-tree-analysis.md) - Understand the codebase structure
   - [API Contracts - Backend](./api-contracts-server.md) - Learn the API endpoints

2. **Setup Environment:**
   - Follow [README.md Quick Start](../README.md#get-started)
   - Run `make start` to launch all services (API, UI, databases)
   - Run migrations: `cd migrations && bash migrate.sh up`

3. **Development:**
   - Backend: `uvicorn src.app:app --reload`
   - Frontend: `cd ui && npm run dev`
   - Docker: `./scripts/run_docker.sh`

### For Planning New Features (Brownfield PRD)

When creating a brownfield PRD, reference these key documents:

**For Full-Stack Features:**
- [Data Models - Backend](./data-models-server.md) - Understand existing schema
- [API Contracts - Backend](./api-contracts-server.md) - Existing endpoints
- [Component Inventory - Frontend](./component-inventory-client.md) - Reusable UI components
- Integration Architecture _(to be generated)_ - How parts communicate

**For Backend-Only Features:**
- [Architecture - Backend](./architecture-server.md) _(to be generated)_
- [Data Models - Backend](./data-models-server.md)
- [restructure_v2.md](../restructure_v2.md) - Deep architecture details

**For Frontend-Only Features:**
- [Architecture - Frontend](./architecture-client.md) _(to be generated)_
- [Component Inventory - Frontend](./component-inventory-client.md)
- [API Contracts - Backend](./api-contracts-server.md) - Available backend APIs

---

## 🏗️ Architecture Overview

### System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    WEB UI (React/TypeScript)                     │
│                        Port: 80                                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST API (HTTP/JSON)
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│              BACKEND API (Python/FastAPI)                        │
│                        Port: 8080                                 │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │  Adaptive Memory Orchestrator                       │         │
│  │  (Turn-by-turn stateful retrieval)                 │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │  LangGraph Extraction Pipeline                      │         │
│  │  (Worthiness → Extraction → Classification)        │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │  Hybrid Retrieval System                            │         │
│  │  (ChromaDB + TimescaleDB + PostgreSQL)             │         │
│  └────────────────────────────────────────────────────┘         │
└───────────────────────────┬──────────────────────────────────────┘
                            │
      ┌─────────────────────┴───────────────────────┐
      │                                             │
      ▼                                             ▼
┌─────────────────────┐                  ┌─────────────────────┐
│  POLYGLOT           │                  │  OBSERVABILITY      │
│  PERSISTENCE        │                  │  & LLM              │
├─────────────────────┤                  ├─────────────────────┤
│ • ChromaDB :8000    │                  │ • Langfuse          │
│ • TimescaleDB :5433 │                  │ • OpenAI GPT-4      │
│ • PostgreSQL        │                  │ • xAI Grok          │
│ • Redis :6379       │                  └─────────────────────┘
└─────────────────────┘
```

### Memory Types & Database Mapping

| Memory Type | ChromaDB | TimescaleDB | PostgreSQL | Redis |
|-------------|----------|-------------|------------|-------|
| **Episodic** | ✅ Vector | ✅ Time-series | - | Short-term |
| **Semantic** | ✅ Vector | - | ✅ Structured | Short-term |
| **Procedural** | ✅ Vector | - | ✅ Structured | Short-term |
| **Emotional** | ✅ Vector | ✅ Time-series | Patterns | Short-term |
| **Portfolio** | ✅ Vector | ✅ Snapshots | ✅ Holdings | Short-term |

---

## 🔑 Key Features

**Memory Orchestrator (Latest - Oct 2025):**
- Turn-by-turn stateful retrieval
- Policy-gated memory injections
- Conversation-scoped delivery
- Duplicate suppression

**Extraction Pipeline:**
- LangGraph state machine
- Multi-type memory extraction (6 types)
- LLM-powered (GPT-4 or Grok)
- Parallel database storage

**Retrieval Systems:**
- Simple retrieval: Sub-second (ChromaDB only)
- Hybrid retrieval: 2-5 seconds (Multi-database)
- Persona-aware retrieval: Dynamic weighting by persona
- Structured retrieval: LLM-categorized

**Advanced Features:**
- Narrative construction with gap-filling
- Emotional pattern detection
- Skill progression tracking
- Portfolio intelligence
- Memory compaction (graceful forgetting)

---

## 📊 Project Statistics

**Codebase Size:**
- Backend Python files: ~45
- Frontend TypeScript files: ~10
- Database migrations: 12 (across 2 databases)
- Total documentation: 24+ markdown files

**Database Tables:**
- TimescaleDB hypertables: 3
- PostgreSQL tables: 8
- ChromaDB collections: 1 (memories_3072)

**API Endpoints:** 15
- Orchestrator APIs: 3
- Core memory APIs: 5
- Advanced APIs: 3
- Maintenance: 3
- Health: 2

---

## 🧪 Testing

**Backend Tests:**
- Unit tests: `pytest tests/unit/`
- E2E tests: `tests/e2e/run_e2e_tests.sh`
- LLM evals: `pytest tests/evals/`
- Orchestrator tests: `pytest tests/memory_orchestrator/`

**Frontend Tests:**
- E2E tests: `cd ui && npm run test:e2e` (Playwright)

---

## 🚢 Deployment

**Development:**
```bash
# Start all services (API, UI, databases)
make start

# Run migrations
cd migrations && bash migrate.sh up

# Start UI
cd ui && npm run dev
```

**Production (Docker):**
```bash
./scripts/run_docker.sh
```

**Services:**
- Backend API: http://localhost:8080
- API Docs: http://localhost:8080/docs
- Web UI: http://localhost:80
- Health Check: http://localhost:8080/health/full

---

## 🤝 For AI-Assisted Development

This index and linked documentation provide complete context for AI agents to:

1. **Understand the Architecture** - Multi-part system with polyglot persistence
2. **Locate Code** - Source tree with entry points and critical files
3. **Extend APIs** - Existing endpoint patterns and data models
4. **Add Features** - Component inventory and integration points
5. **Modify Data Models** - Complete schema documentation
6. **Navigate Codebase** - Clear directory structure and file purposes

**Recommendation:** Start with README.md for high-level understanding, then dive into specific documents as needed for your feature planning.

---

## 📝 Documentation Trust Hierarchy

When encountering conflicting information:

1. **README.md** (Nov 2, 2025) - Primary source of truth
2. **CHATBOT_INTEGRATION_GUIDE.md** (Oct 21, 2025) - Latest features
3. **RETRIEVAL_OVERHAUL_PLAN.md** (Oct 20, 2025) - Recent planning
4. **Oct 19 merged docs** (restructure_v2.md, etc.) - Secondary sources
5. **Phase completion docs** - Historical context only

---

## 🔄 Keeping Documentation Current

**When to Update:**
- After major feature additions
- When API contracts change
- When database schema evolves
- After architecture refactors

**How to Update:**
- Re-run document-project workflow: `/bmad:bmm:workflows:document-project`
- Update specific documents as needed
- Regenerate this index

---

**For Questions or Issues:**
- Check existing documentation first (trust hierarchy above)
- Review source code in critical files (see Source Tree Analysis)
- Consult README.md for architectural decisions

**Happy Building! 🚀**
