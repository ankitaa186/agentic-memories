# Agentic Memories 🧠

<div align="center">

**Persistent memory for AI agents with semantic retrieval, user profiles, scheduled intents, and equity/options portfolio tracking.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?logo=docker)](https://www.docker.com/)

[Features](#-features) •
[Vision](#-the-vision) •
[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## Recent enhancements (June–September 2026)

- **Relevant recall:** ordinary text queries rank semantic and procedural memories by measured cosine similarity. Unrelated skills, persona tags, recency, and importance no longer displace stronger query matches. SQL-only skills remain searchable, with bounded embedding caching and cross-store deduplication.
- **Equities and options:** portfolio CRUD supports puts/calls, long/short option positions, lifecycle status, and caller-supplied collateral totals. `GET /v1/portfolio` groups equities and options; closed and expired options are opt-in.
- **Connection reliability:** temporal retrieval and episodic storage return pooled PostgreSQL connections on cleanup paths, including rollback failures. `/health/full` exposes pool statistics for observation.
- **API-only updates:** `make service-update ENV=prod` rebuilds and recreates the API without recreating database containers. Apply required schema migrations separately.

See the [review and upgrade notes](docs/recent-enhancements-2026-09.md) for the complete commit inventory, behavior changes, and operational details, and the [portfolio API guide](docs/portfolio-api.md) for working examples.

## 🌟 The Vision

**Imagine an AI that doesn't just respond—it remembers.**

Agentic Memories is not another chatbot memory layer. It's a **Digital Soul** - a sophisticated memory architecture that mirrors human consciousness, enabling AI systems to:

- 🎭 **Remember experiences, not just facts** - Store episodic memories with emotional context, spatial awareness, and causal relationships
- 💭 **Maintain emotional continuity** - Track emotional states over time, recognize patterns, and predict emotional responses
- 🔮 **Predict needs before you ask** - Learn behavioral patterns and anticipate requirements
- 📖 **Construct coherent life narratives** - Weave memories into meaningful stories that evolve over time
- 🌱 **Learn and evolve organically** - Consolidate memories during "digital sleep", forgetting gracefully like humans do
- 💼 **Track structured data intelligently** - Manage portfolios, skills, projects with context-aware storage

This isn't hyperpersonalization—it's **hypersapience**.

---

## ✨ What Makes This Novel?

### 🧬 Biomimetic Memory Architecture

Unlike traditional memory systems that treat data as static records, Agentic Memories implements a **six-layer memory hierarchy** inspired by cognitive neuroscience:

```
┌─────────────────────────────────────────────────────────┐
│              CONSCIOUSNESS LAYER                         │
│    Identity | Values | Narrative | Current State        │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │
┌─────────────────────────────────────────────────────────┐
│              COGNITIVE PROCESSING                        │
│  Pattern Recognition | Prediction | Narrative Builder   │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │
┌─────────────────────────────────────────────────────────┐
│                MEMORY LAYERS                            │
│  Episodic | Semantic | Procedural | Emotional | Portfolio │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │
┌─────────────────────────────────────────────────────────┐
│              HYBRID STORAGE SYSTEMS                     │
│  TimescaleDB | ChromaDB | PostgreSQL | Redis | Neo4j*  │
│  (* Neo4j planned — not yet deployed)                  │
└─────────────────────────────────────────────────────────┘
```

### 🎯 Key Differentiators

| Traditional Memory Systems | Agentic Memories |
|---------------------------|------------------|
| Static key-value storage | **Dynamic, time-aware consolidation** |
| Facts without context | **Experiences with emotional weight** |
| Simple search | **Reconstructive retrieval** (fills gaps like humans) |
| Infinite retention | **Graceful forgetting** (Ebbinghaus curve) |
| Single database | **Polyglot persistence** (4 specialized databases) |
| Reactive queries | **Predictive intelligence** |
| No narrative capability | **Coherent life story construction** |

### 🔬 Inspired by Neuroscience

- **Episodic Buffer** (Baddeley & Hitch) - Rich contextual event storage
- **Consolidation Theory** (Müller & Pilzecker) - Nightly memory strengthening
- **Forgetting Curves** (Ebbinghaus) - Natural decay with spaced repetition
- **Emotional Memory Enhancement** (McGaugh) - Emotional events remembered better
- **Reconstructive Memory** (Bartlett) - Gap-filling during recall

### 🧹 Why Forgetting Matters

> *"We must forget to remember."*

Every AI memory system focuses on storing more. Agentic Memories is designed to also **forget well** — because that's what brains actually do, and for good reason.

Perfect recall is not a superpower — it's a disability. Patients with hyperthymesia (total autobiographical recall) report being overwhelmed by irrelevant detail, unable to generalize or prioritize. The brain's forgetting mechanisms aren't bugs; they're features that enable:

- **Signal over noise** — Pruning low-importance memories surfaces what actually matters. Agentic Memories applies TTL-based decay: episodic memories with importance < 0.3 are pruned after 90 days; low-intensity emotional memories fade after 60 days.
- **Generalization** — Consolidating many similar memories into a single "golden record" mirrors how the hippocampus replays and compresses episodes during sleep. The compaction pipeline clusters semantically similar memories (cosine similarity > 0.75) and merges them via LLM into distilled summaries.
- **Efficient retrieval** — Fewer, higher-quality memories mean faster search and more relevant results. Deduplication across ChromaDB, episodic, and emotional tables keeps the memory store lean.
- **Emotional regulation** — Not every fleeting mood deserves permanent storage. Emotional memories below an intensity threshold are allowed to fade naturally, while high-arousal events are preserved — exactly as McGaugh's research predicts.

This is implemented today via the compaction system (`POST /v1/maintenance/compact`), which runs TTL cleanup, deduplication, and LLM-powered consolidation in a single LangGraph pipeline. The result: a memory system that gets **sharper** over time, not just bigger.

---

## 🚀 Features

### 🎯 Core Capabilities

- **🧠 Intelligent Memory Extraction** - Unified LangGraph pipeline extracts multiple memory types from conversations using LLMs (OpenAI, Grok)
- **📊 Multi-Modal Memory Types**
  - **Episodic**: Life events with temporal, spatial, and emotional context
  - **Semantic**: Facts, concepts, and declarative knowledge
  - **Procedural**: Skills, habits, and learned behaviors with progression tracking
  - **Emotional**: Mood states, patterns, and emotional trajectories
  - **Portfolio**: Financial holdings, transactions, and investment goals
  - **Identity**: Core values, beliefs, and self-concept (coming soon)
  
- **🔍 Hybrid Retrieval System**
  - Semantic search via vector embeddings (ChromaDB), with measured cosine ranking for ordinary text queries
  - Temporal queries for time-range narratives (TimescaleDB)
  - Structured queries for skills and holdings (PostgreSQL)
  - Graph traversal for relationships (Neo4j - coming soon)
  - Redis caching for performance
  
- **📖 Narrative Construction** - Weaves memories into coherent stories with temporal awareness and gap-filling

- **💼 Portfolio Tracking** - Explicit CRUD for equities and option contracts, including lifecycle status and committed collateral for active short options

- **🔐 Privacy-First Design** - Consent management, encryption-ready, sensitivity scoring (coming soon)

- **📈 Observability** - Full Langfuse integration for LLM tracing and debugging

### 🛠️ Technical Features

- **⚡ High Performance**
  - Sub-second simple queries (ChromaDB only)
  - Hybrid multi-database queries for complex narratives
  - Connection pooling and explicit transaction management
  - Redis caching for hot paths
  
- **🔄 Robust Data Management**
  - Versioned migrations for 3 database types (TimescaleDB, PostgreSQL, ChromaDB)
  - Enhanced migration system with rollback support
  - Dry-run mode and validation
  - Migration history tracking and locking
  
- **🎨 Developer Experience**
  - Beautiful web UI for memory browsing
  - GraphQL-style structured retrieval
  - Comprehensive API documentation
  - Health checks for all services
  
- **🐳 Production Ready**
  - Docker Compose deployment
  - All databases included (TimescaleDB, ChromaDB, Redis)
  - Environment-based configuration
  - Graceful error handling

---

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT                                   │
│              (Web UI / API / Chatbot Integration)                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AGENTIC MEMORIES API                          │
│                        (FastAPI)                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │         INGESTION PIPELINE (LangGraph)              │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │       │
│  │  │Worthiness│→ │Extraction│→ │Classification│     │       │
│  │  └──────────┘  └──────────┘  └──────────────┘     │       │
│  │       ↓              ↓              ↓              │       │
│  │  ┌─────────────────────────────────────────┐      │       │
│  │  │     Parallel Storage (All Layers)       │      │       │
│  │  └─────────────────────────────────────────┘      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │      RETRIEVAL PIPELINE (Hybrid)                    │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │       │
│  │  │ Semantic │  │ Temporal │  │  Procedural  │     │       │
│  │  │(ChromaDB)│  │(Timescale│  │ (PostgreSQL) │     │       │
│  │  └──────────┘  └──────────┘  └──────────────┘     │       │
│  │       ↓              ↓              ↓              │       │
│  │  ┌─────────────────────────────────────────┐      │       │
│  │  │     Rank & Merge Results                │      │       │
│  │  └─────────────────────────────────────────┘      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │     COGNITIVE PROCESSING (Future)                   │       │
│  │  • Pattern Recognition  • Prediction Engine         │       │
│  │  • Narrative Construction • Consolidation           │       │
│  └─────────────────────────────────────────────────────┘       │
└──────────────────────────┬───────────────────────────────────────┘
                           │
      ┌────────────────────┴────────────────────┐
      │                                         │
      ▼                                         ▼
┌─────────────────┐                  ┌─────────────────────┐
│  POLYGLOT       │                  │  OBSERVABILITY      │
│  PERSISTENCE    │                  │  LAYER              │
├─────────────────┤                  ├─────────────────────┤
│ • ChromaDB      │                  │ • Langfuse (LLM)    │
│ • TimescaleDB   │                  │ • Structured Logs   │
│ • PostgreSQL    │                  │ • Health Metrics    │
│ • Redis         │                  └─────────────────────┘
│ • Neo4j (soon)  │
└─────────────────┘
```

### Database Strategy: "Write Everywhere, Read Selectively"

| Database | Primary Use | Read Pattern | Data Type |
|----------|-------------|--------------|-----------|
| **ChromaDB** | Vector embeddings | **All retrieval** | Memories with semantic search |
| **TimescaleDB** | Time-series data | Temporal queries | Episodic, emotional, portfolio snapshots |
| **PostgreSQL** | Structured data | Procedural, portfolio | Skills, holdings, transactions |
| **Redis** | Hot cache | Short-term layer | Transient memories |
| **Neo4j** *(planned)* | Graph relationships | (Future) | Skill chains, correlations |

**Why Polyglot Persistence?**
- ✅ Each database optimized for its data type
- ✅ Fast simple queries (ChromaDB only)
- ✅ Complex queries available (multi-database)
- ✅ Data redundancy for resilience
- ✅ Future-proof for analytics and graph queries

---

## 📦 Quick Start

### Prerequisites

- **Docker & Docker Compose** (v2+)
- **An LLM API key** — [OpenAI](https://platform.openai.com/api-keys) or [xAI/Grok](https://console.x.ai/)
- **`psql`** (PostgreSQL client) — for auto-running database migrations
  ```bash
  # macOS
  brew install postgresql

  # Ubuntu/Debian
  sudo apt-get install postgresql-client
  ```

All databases (TimescaleDB, ChromaDB, Redis) run inside Docker Compose. On startup, `migrate.sh` automatically applies any pending migrations.

### Get Running

```bash
# 1. Clone
git clone https://github.com/ankitaa186/agentic-memories.git
cd agentic-memories

# 2. Start (interactive wizard on first run)
make start
```

On first run, an interactive setup wizard walks you through choosing your LLM provider and entering your API key. It then:
- Writes your `.env` file
- Validates all required environment variables
- Starts TimescaleDB, ChromaDB, and Redis
- Runs `migrate.sh up` to apply all database migrations
- Auto-creates the ChromaDB tenant, database, and collection
- Builds and starts the API and Web UI

> **Prefer manual config?** Copy `env.example` to `.env`, edit your API key, then run `make start`.

**Verify:**
```bash
curl -s http://localhost:8080/health/full | python3 -m json.tool
```

### Services

| Service | URL |
|---------|-----|
| API | http://localhost:8080 |
| API Docs (Swagger) | http://localhost:8080/docs |
| Web UI | http://localhost:3000 |
| TimescaleDB | `localhost:5432` |
| ChromaDB | `localhost:8000` |
| Redis | `localhost:6379` |

### Common Commands

```bash
make start              # Start all services
make stop               # Stop all services
make logs               # Tail logs (all services)
make logs SERVICE=api   # Tail API logs only
make test               # Run unit + integration tests
make test-e2e           # Run E2E tests (requires running services)
```

### Troubleshooting

**ChromaDB "default_tenant" not found** — The startup script auto-creates the tenant and database. If it fails, create them manually:
```bash
curl -X POST http://localhost:8000/api/v2/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"agentic-memories"}'

curl -X POST http://localhost:8000/api/v2/tenants/agentic-memories/databases \
  -H "Content-Type: application/json" \
  -d '{"name":"memories"}'
```

**Migration errors on existing data** — `migrate.sh` tracks applied migrations and only runs pending ones. To start completely fresh: `rm -rf data/ && make start`.

**Advanced migrations** — For incremental migrations, rollbacks, or dry-run mode, see the [Migration Guide](migrations/README.md):
```bash
make migrate            # Interactive migration menu
```

For more troubleshooting, see [migrations/README.md](migrations/README.md).

---

### Try Your First Memory!

```bash
curl -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "history": [
      {
        "role": "user",
        "content": "I just learned how to make sourdough bread! It took 3 days but the result was amazing. My family loved it."
      }
    ]
  }' | jq
```

Retrieve it:
```bash
curl "http://localhost:8080/v1/retrieve?user_id=demo_user&query=bread&limit=5" | jq
```

---

## 📖 Integration Guide

Give your AI agent persistent memory in under 5 minutes. Store conversation turns, retrieve relevant context, inject into your LLM. For the full detailed guide with advanced patterns, see [docs/internal/CHATBOT_INTEGRATION_GUIDE.md](docs/internal/CHATBOT_INTEGRATION_GUIDE.md).

### Quickstart: 3 Calls to Persistent Memory

```bash
# 1. Store a conversation turn (orchestrator — recommended)
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "session-1",
    "role": "user",
    "content": "I just got promoted to senior engineer at Stripe!",
    "metadata": {"user_id": "user_123"},
    "flush": true
  }'

# 2. Retrieve relevant memories
curl 'http://localhost:8080/v1/retrieve?user_id=user_123&query=career&limit=5'

# 3. Inject into your LLM prompt
```

```python
import requests

BASE = "http://localhost:8080"

def chat(user_id: str, message: str) -> str:
    # Store
    requests.post(f"{BASE}/v1/orchestrator/message", json={
        "conversation_id": f"session-{user_id}",
        "role": "user",
        "content": message,
        "metadata": {"user_id": user_id},
        "flush": True,
    })

    # Retrieve
    memories = requests.get(f"{BASE}/v1/retrieve", params={
        "user_id": user_id, "query": message, "limit": 5,
    }).json()
    context = "\n".join(f"- {m['content']}" for m in memories.get("results", []))

    # Inject into your LLM
    return call_your_llm(
        system=f"You have these memories about this user:\n{context}",
        user=message,
    )
```

### Storing Memories — 3 Options

| | Orchestrator (recommended) | Direct Memory | Store (legacy) |
|---|---|---|---|
| **Endpoint** | `POST /v1/orchestrator/message` | `POST /v1/memories/direct` | `POST /v1/store` |
| **Latency** | ~10-30s | <3s | 10-60s |
| **LLM extraction** | Yes (full pipeline) | No | Yes (full pipeline) |
| **Batching** | Adaptive throttling | N/A | None |
| **Returns memories** | Yes (injections) | No | No |
| **Best for** | All use cases | Pre-formatted data | One-off backfill |

**Orchestrator** (`POST /v1/orchestrator/message`) — The best default. Runs the full LLM ingestion pipeline (worthiness check, extraction, classification, enrichment) with adaptive throttling that batches messages based on conversation speed. Returns relevant memories in the same call. Set `flush: true` for immediate persistence.

```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "chat-42",
    "role": "user",
    "content": "I just bought 50 shares of NVDA at $130",
    "metadata": {"user_id": "user_123"},
    "flush": true
  }'
```

**Direct Memory** (`POST /v1/memories/direct`) — Fast, deterministic storage for pre-formatted memories. Supports typed storage (episodic, emotional, procedural) via optional fields.

```bash
curl -X POST http://localhost:8080/v1/memories/direct \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "content": "User prefers morning meetings between 9am-12pm",
    "layer": "semantic",
    "type": "explicit",
    "importance": 0.8
  }'
```

**Store Pipeline** (`POST /v1/store`) — Largely superseded by the orchestrator. Runs the same full LLM ingestion pipeline but without throttling or batching — every call triggers immediate processing. Use only for one-off backfill of historical transcripts where adaptive throttling is unnecessary.

```bash
curl -X POST http://localhost:8080/v1/store \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "history": [
      {"role": "user", "content": "I just got back from a 2-week trip to Japan. The ramen in Fukuoka was incredible."}
    ]
  }'
```

### Retrieving Memories

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/v1/retrieve` | GET | Semantic search — fast, your go-to for most use cases |
| `/v1/retrieve` | POST | Persona-aware retrieval with cosine ranking for text queries |
| `/v1/retrieve/structured` | POST | Memories organized into categories by LLM |
| `/v1/narrative` | POST | Coherent story/timeline from hybrid retrieval |
| `/v1/orchestrator/retrieve` | POST | Retrieve within orchestrator session context |
| `/v1/profile` | GET | Structured user profile (auto-extracted from conversations) |
| `/v1/portfolio` | GET | Equities, options, lifecycle status, and collateral summary |
| `/v1/portfolio/holding` | POST | Create or upsert an equity or option position |
| `/v1/portfolio/holding/{position_key}` | PUT / DELETE | Update or delete a position |
| `/v1/portfolio/summary` | GET | Legacy financial summary |

**Basic retrieval** — semantic search across all stored memories:

```bash
curl 'http://localhost:8080/v1/retrieve?user_id=user_123&query=cooking&limit=10'
```

**User profile** — structured data extracted automatically from conversations:

```bash
curl 'http://localhost:8080/v1/profile?user_id=user_123'
```

**Portfolio** — grouped equity and option positions:

```bash
curl 'http://localhost:8080/v1/portfolio?user_id=user_123'
```

**Structured retrieval** — memories categorized into emotions, professional, skills, habits, etc.:

```bash
curl -X POST http://localhost:8080/v1/retrieve/structured \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "query": "career and skills", "limit": 50}'
```

**Narrative** — generate a coherent story from memories over a time range:

```bash
curl -X POST http://localhost:8080/v1/narrative \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "query": "What happened this quarter?", "start_time": "2025-01-01T00:00:00Z", "end_time": "2025-03-31T23:59:59Z"}'
```

### Compaction Runs Behind the Scenes

Memory compaction runs automatically. The system consolidates similar memories, applies decay factors, promotes important short-term memories to long-term, and archives stale data. You don't need to manage this — retrieval stays fast and relevant over time. If needed, trigger it manually:

```bash
curl -X POST 'http://localhost:8080/v1/maintenance/compact?user_id=user_123'
```

See the [full Integration Guide](docs/internal/CHATBOT_INTEGRATION_GUIDE.md) for detailed examples, the complete Python client, typed storage patterns, persona-aware retrieval, and the endpoint reference cheat sheet.

---

## 📚 API Documentation

### Core Endpoints

#### 🔹 Store Memories

```http
POST /v1/store
```

Extracts and stores memories from conversation history. Automatically detects memory types.

**Request**:
```json
{
  "user_id": "user_123",
  "history": [
    {
      "role": "user",
      "content": "I bought 100 shares of AAPL at $175"
    }
  ]
}
```

**Response**:
```json
{
  "memories_created": 2,
  "ids": ["mem_abc123", "mem_def456"],
  "summary": "Stored: 1 episodic, 1 emotional.",
  "memories": [
    {
      "content": "User bought 100 shares of AAPL at $175",
      "layer": "semantic",
      "type": "explicit",
      "confidence": 0.95,
      "metadata": {
        "tags": ["investment", "stocks", "AAPL"],
        "portfolio": "{\"ticker\":\"AAPL\",\"shares\":100,\"avg_price\":175.0,\"intent\":\"buy\"}"
      }
    }
  ],
  "duplicates_avoided": 0,
  "updates_made": 0,
  "existing_memories_checked": 12
}
```

**Extraction Pipeline**:
1. **Worthiness Check**: Filters out trivial messages
2. **Memory Extraction**: LLM extracts structured memories
3. **Classification**: Categorizes by type (episodic, procedural, portfolio, etc.)
4. **Enrichment**: Adds context from existing memories
5. **Parallel Storage**: Writes to all appropriate databases
6. **Vector Embedding**: Stores in ChromaDB for semantic search

---

#### 🔹 Retrieve Memories

```http
GET /v1/retrieve?user_id=user_123&query=stocks&limit=10
```

Fast semantic search using ChromaDB.

**Parameters**:
- `user_id` (required): User identifier
- `query` (optional): Search query (omit for all memories)
- `layer` (optional): Filter by layer (`short-term`, `semantic`, `episodic`)
- `type` (optional): Filter by type (`explicit`, `implicit`)
- `persona` (optional): Force a specific persona for retrieval
- `sort` (optional): Sort order — `newest` or `oldest`
- `limit` (default: 50, max: 1000): Results per page
- `offset` (default: 0): Pagination offset

**Response**:
```json
{
  "results": [
    {
      "id": "mem_d477499c0106",
      "content": "User likes spicy food.",
      "layer": "semantic",
      "type": "explicit",
      "score": 0.87,
      "metadata": {
        "user_id": "user_123",
        "layer": "semantic",
        "type": "explicit",
        "timestamp": "2025-12-22T22:44:07.249153+00:00",
        "importance": 0.5,
        "tags": ["preferences", "food"],
        "confidence": 1.0,
        "relevance_score": 0.0,
        "usage_count": 0,
        "persona_tags": []
      },
      "importance": 0.5,
      "persona_tags": [],
      "emotional_signature": null
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "total": 1
  },
  "finance": null
}
```

---

#### 🔹 Structured Retrieval

```http
POST /v1/retrieve/structured
```

LLM-organized memory categorization.

**Request**:
```json
{
  "user_id": "user_123",
  "query": "career and skills",
  "limit": 50
}
```

**Response**:
```json
{
  "emotions": [
    {
      "id": "mem_e001",
      "content": "User felt excited and proud after shipping their first API endpoint.",
      "layer": "semantic",
      "type": "explicit",
      "score": 0.91,
      "metadata": {"importance": 0.8, "tags": ["excitement", "achievement"]},
      "importance": 0.8,
      "persona_tags": ["career", "emotions"],
      "emotional_signature": null
    }
  ],
  "behaviors": [],
  "personal": [],
  "professional": [
    {
      "id": "mem_p001",
      "content": "User is a Senior Software Engineer at Acme Corp, focusing on backend systems.",
      "layer": "semantic",
      "type": "explicit",
      "score": 0.88,
      "metadata": {"importance": 0.9, "tags": ["career", "engineering"]},
      "importance": 0.9,
      "persona_tags": ["career"],
      "emotional_signature": null
    }
  ],
  "habits": [],
  "skills_tools": [
    {
      "id": "mem_s001",
      "content": "Python:  (Context: Learning Python through FastAPI projects, intermediate level)",
      "layer": "semantic",
      "type": "explicit",
      "score": 0.85,
      "metadata": {"skill_name": "Python", "proficiency_level": "intermediate", "practice_count": 12},
      "importance": null,
      "persona_tags": null,
      "emotional_signature": null
    }
  ],
  "projects": [],
  "relationships": [],
  "learning_journal": [],
  "other": [],
  "finance": null
}
```

Each category contains full `RetrieveItem` objects with scores, metadata, and persona tags. The LLM classifies each memory into the most appropriate category. Categories: `emotions`, `behaviors`, `personal`, `professional`, `habits`, `skills_tools`, `projects`, `relationships`, `learning_journal`, `other`, plus a `finance` aggregate from portfolio metadata.

---

#### 🔹 Narrative Construction

```http
POST /v1/narrative
```

Generates coherent life stories using **hybrid retrieval** (ChromaDB + TimescaleDB + PostgreSQL).

**Request**:
```json
{
  "user_id": "user_123",
  "query": "What happened in Q1 2025?",
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2025-03-31T23:59:59Z",
  "limit": 25
}
```

**Response**:
```json
{
  "user_id": "user_123",
  "narrative": "In early January you dove into Python, starting with a FastAPI tutorial that quickly turned into a full project. By mid-month you had your first working endpoint, and the excitement carried over into a weekend hackathon where you built a simple portfolio tracker. The learning curve was steep but rewarding — your journal entries from that period show a mix of frustration with async patterns and genuine delight when things clicked. By February you were refactoring confidently and exploring deployment options.",
  "summary": "Key themes: rapid Python learning via FastAPI project, portfolio tracker hackathon, growing confidence with async patterns and deployment.",
  "sources": [
    {
      "id": "mem_abc123",
      "type": "semantic",
      "content": "User started learning Python through a FastAPI tutorial project.",
      "meta": {
        "layer": "episodic",
        "confidence": 0.9,
        "relevance_score": 0.85,
        "source": "direct_api",
        "importance": 0.85,
        "conversation_id": "conv_1abf23040f40",
        "mood": "curious",
        "persona_tags": ["conversation_summary", "learning", "python"],
        "type": "explicit",
        "typed_table_id": "e4257758-b09f-4890-93b0-e5e2f31a4b3f",
        "category": "learning",
        "stored_in_episodic": true,
        "stored_in_emotional": true,
        "stored_in_procedural": false,
        "timestamp": "2025-01-10T08:30:00.000000+00:00",
        "user_id": "user_123",
        "topics": ["python", "fastapi", "learning"],
        "message_count": 24,
        "has_unresolved": false
      }
    },
    {
      "id": "mem_def456",
      "type": "semantic",
      "content": "User built a portfolio tracker during a weekend hackathon, expressing excitement about the project.",
      "meta": {
        "layer": "episodic",
        "confidence": 0.9,
        "relevance_score": 0.8,
        "source": "direct_api",
        "importance": 0.9,
        "mood": "excited",
        "persona_tags": ["conversation_summary", "project", "hackathon"],
        "type": "explicit",
        "category": "project",
        "stored_in_episodic": true,
        "stored_in_emotional": true,
        "timestamp": "2025-01-18T14:00:00.000000+00:00",
        "user_id": "user_123",
        "topics": ["hackathon", "portfolio", "python"]
      }
    }
  ]
}
```

**Hybrid Retrieval Process**:
1. **Semantic Search** (ChromaDB): Find relevant memories by meaning
2. **Temporal Search** (TimescaleDB): Query episodic/emotional memories in time range
3. **Procedural Search** (PostgreSQL): Fetch skill progressions
4. **Deduplicate & Rank**: Merge results by relevance, recency, importance
5. **LLM Generation**: Weave into coherent narrative

---

#### 🔹 Portfolio CRUD

Use `GET /v1/portfolio?user_id=user_123` for the flat `holdings` list, grouped `equities` and `options`, counts, and `summary.total_committed_options_collateral`. The default view includes equities and active options; add `include_inactive=true` to include closed and expired options.

Create or upsert positions with `POST /v1/portfolio/holding`; update or delete with `/v1/portfolio/holding/{position_key}`. Option keys can be a position UUID, generated OCC-style symbol, or the underlying plus contract fields. See the [portfolio API guide](docs/portfolio-api.md) for request bodies, lifecycle semantics, validation, and migration 025.

#### 🔹 Legacy Portfolio Summary

This endpoint keeps its older response shape; use the CRUD GET endpoint above for option lifecycle and collateral aggregates.

```http
GET /v1/portfolio/summary?user_id=user_123
```

Structured portfolio data from PostgreSQL (with ChromaDB fallback).

**Response**:
```json
{
  "user_id": "user_123",
  "total_holdings": 1,
  "holdings": [
    {
      "ticker": "AAPL",
      "asset_name": "Apple Inc.",
      "shares": 100,
      "avg_price": 175.0,
      "first_acquired": "2025-01-15T10:30:00Z",
      "last_updated": "2025-01-15T10:30:00Z"
    }
  ]
}
```

> **Note**: Portfolio holdings are managed via explicit CRUD calls (`POST /v1/portfolio/holding`), not auto-extracted from the ingestion pipeline.

---

#### 🔹 Profile Management

Profile CRUD APIs provide read and write access to user profile data extracted from conversations. Profiles are automatically populated during ingestion and can be manually edited via these endpoints.

**Profile Categories** (27 baseline fields, extensible — the system auto-discovers new fields from conversations):
- `basics`: name, birthday, location, occupation, family_status, spouse, children, ...
- `preferences`: communication_style, food_preferences, dietary_restrictions, sleep_schedule, investing_style, risk_tolerance, ...
- `goals`: short_term, long_term, current_focus, financial_goals, aspirations, ...
- `interests`: hobbies, learning_areas, favorite_topics, music_taste, passions, ...
- `background`: skills, education_history, work_history, current_employer, cultural_background, achievements, ...
- `health`: allergies, dietary_needs, clothing_sizes, vision_correction, ...
- `personality`: strengths, conflict_style, personality_type, stress_response, ...
- `values`: life_values, spiritual_alignment, philanthropy, ...

##### GET /v1/profile - Get Complete Profile

```http
GET /v1/profile?user_id=user_123
```

Returns complete user profile with all categories and confidence scores.

**Parameters**:
- `user_id` (required): User identifier

**Response**:
```json
{
  "user_id": "user_123",
  "completeness_pct": 74.07,
  "populated_fields": 20,
  "total_fields": 27,
  "last_updated": "2025-12-22T22:44:07.249153+00:00",
  "created_at": "2025-11-17T10:25:12.654321+00:00",
  "profile": {
    "basics": {
      "name": {"value": "Sarah Martinez", "last_updated": "2025-11-17T10:30:45+00:00"},
      "birthday": {"value": "March 15", "last_updated": "2025-12-01T09:00:00+00:00"},
      "location": {"value": "San Francisco, CA", "last_updated": "2025-12-10T14:22:00+00:00"},
      "occupation": {"value": "Senior Software Engineer at Acme Corp", "last_updated": "2025-12-15T08:00:00+00:00"},
      "family_status": {"value": "married", "last_updated": "2025-11-20T12:00:00+00:00"},
      "spouse": {"value": {"name": "Alex", "nickname": null}, "last_updated": "2025-11-20T12:00:00+00:00"}
    },
    "preferences": {
      "communication_style": {"value": "Prefers analytical, concise explanations", "last_updated": "2025-12-05T16:30:00+00:00"},
      "food_preferences": {"value": ["Italian", "Japanese"], "last_updated": "2025-12-08T19:00:00+00:00"},
      "dietary_restrictions": {"value": "vegetarian", "last_updated": "2025-12-08T19:00:00+00:00"},
      "sleep_schedule": {"value": "night owl (often active around 1-2am)", "last_updated": "2025-12-20T02:00:00+00:00"}
    },
    "goals": {
      "short_term": {"value": "Complete ML certification within 6 months", "last_updated": "2025-11-17T10:30:45+00:00"},
      "long_term": {"value": "Transition into AI research", "last_updated": "2025-12-01T09:00:00+00:00"},
      "current_focus": {"value": "Building a personal AI assistant project", "last_updated": "2025-12-15T08:00:00+00:00"}
    },
    "interests": {
      "hobbies": {"value": ["rock climbing", "journaling"], "last_updated": "2025-12-10T14:22:00+00:00"},
      "favorite_topics": {"value": ["AI", "cognitive science"], "last_updated": "2025-12-18T11:00:00+00:00"},
      "learning_areas": {"value": ["Python", "LangChain"], "last_updated": "2025-12-15T08:00:00+00:00"}
    },
    "background": {
      "skills": {"value": ["Backend Engineering", "Python", "Docker"], "last_updated": "2025-12-15T08:00:00+00:00"},
      "current_employer": {"value": "Acme Corp", "last_updated": "2025-12-15T08:00:00+00:00"},
      "education_history": {"value": "MS Computer Science, Stanford", "last_updated": "2025-11-25T10:00:00+00:00"}
    },
    "health": {
      "dietary_needs": {"value": "Vegetarian (eats eggs). Favorites: pasta, sushi.", "last_updated": "2025-12-08T19:00:00+00:00"},
      "allergies": {"value": [], "last_updated": "2025-12-08T19:00:00+00:00"}
    },
    "personality": {
      "strengths": {"value": ["Builder mindset", "detail-oriented"], "last_updated": "2025-12-12T09:00:00+00:00"},
      "conflict_style": {"value": "Seeks rapid resolution; prefers direct conversation", "last_updated": "2025-12-14T20:00:00+00:00"}
    },
    "values": {
      "life_values": {"value": "Emphasizes learning by doing over theoretical study", "last_updated": "2025-12-18T11:00:00+00:00"},
      "spiritual_alignment": {"value": "Secular humanist", "last_updated": "2025-12-01T09:00:00+00:00"}
    }
  }
}
```

**HTTP Status Codes**:
- `200`: Success
- `404`: Profile not found for user_id

---

##### GET /v1/profile/{category} - Get Category Data

```http
GET /v1/profile/basics?user_id=user_123
```

Returns only the specified category's fields.

**Parameters**:
- `category` (path, required): One of: `basics`, `preferences`, `goals`, `interests`, `background`
- `user_id` (query, required): User identifier

**Response**:
```json
{
  "user_id": "user_123",
  "category": "basics",
  "fields": {
    "name": {"value": "Sarah Martinez", "last_updated": "2025-11-17T10:30:45+00:00"},
    "age": {"value": 28, "last_updated": "2025-11-17T10:30:45+00:00"},
    "occupation": {"value": "software engineer", "last_updated": "2025-11-17T10:30:45+00:00"}
  }
}
```

**HTTP Status Codes**:
- `200`: Success
- `400`: Invalid category
- `404`: Profile not found for user_id

---

##### PUT /v1/profile/{category}/{field_name} - Update Field

```http
PUT /v1/profile/basics/location
```

Updates a single profile field. Manual edits always set confidence to 100% (authoritative).

**Request Body**:
```json
{
  "user_id": "user_123",
  "value": "San Francisco, CA",
  "source": "manual"
}
```

**Response**:
```json
{
  "user_id": "user_123",
  "category": "basics",
  "field_name": "location",
  "value": "San Francisco, CA",
  "confidence": 100.0,
  "last_updated": "2025-11-17T10:35:22.789012+00:00"
}
```

**Notes**:
- Manual edits are recorded as `source_type="explicit"` in `profile_sources` table
- Confidence scores are set to 100 across all components (frequency, recency, explicitness, source diversity)
- Automatically updates profile completeness percentage

**HTTP Status Codes**:
- `200`: Success
- `400`: Invalid category
- `500`: Database error

---

##### DELETE /v1/profile - Delete Profile

```http
DELETE /v1/profile?user_id=user_123&confirmation=DELETE
```

Deletes all profile data for a user. Requires confirmation to prevent accidental deletion.

**Parameters**:
- `user_id` (required): User identifier
- `confirmation` (required): Must be exactly `DELETE` (case-sensitive)

**Response**:
```json
{
  "deleted": true,
  "user_id": "user_123"
}
```

**Notes**:
- Cascade deletes from all related tables: `profile_fields`, `profile_confidence_scores`, `profile_sources`, `user_profiles`
- This operation is irreversible

**HTTP Status Codes**:
- `200`: Success
- `400`: Confirmation mismatch
- `404`: Profile not found for user_id
- `500`: Database error

---

##### GET /v1/profile/completeness - Get Completeness Metrics

```http
GET /v1/profile/completeness?user_id=user_123
```

Returns profile completeness statistics.

**Parameters**:
- `user_id` (required): User identifier

**Response**:
```json
{
  "user_id": "user_123",
  "overall_completeness_pct": 33.33,
  "populated_fields": 9,
  "total_fields": 27
}
```

**Notes**:
- Completeness = (populated_fields / 27 total expected fields) × 100
- Expected fields: basics(5) + preferences(4) + goals(3) + interests(3) + background(4) + health(2) + personality(3) + values(3) = 27 total

**HTTP Status Codes**:
- `200`: Success
- `404`: Profile not found for user_id

---

**Example Workflow**:
```bash
# 1. Ingest conversation (automatic profile extraction)
curl -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sarah_123",
    "history": [
      {"role": "user", "content": "Hi! My name is Sarah Martinez and I am 28 years old."}
    ]
  }'

# 2. Retrieve complete profile
curl "http://localhost:8080/v1/profile?user_id=sarah_123" | jq

# 3. Update a field manually
curl -X PUT http://localhost:8080/v1/profile/basics/location \
  -H "Content-Type: application/json" \
  -d '{"user_id": "sarah_123", "value": "San Francisco, CA"}'

# 4. Check completeness
curl "http://localhost:8080/v1/profile/completeness?user_id=sarah_123" | jq
```

---

#### 🔹 Health Check

```http
GET /health/full
```

Comprehensive health check for all services. `checks.timescale_pool` contains `psycopg_pool.get_stats()` when a pool exists, `null` when absent, or an error object if statistics cannot be read. These statistics are informational and do not change the overall health status.

---

## 🎨 Web UI

Access the beautiful memory browser at: **http://localhost:3000**

Features:
- 📊 **Memory Browser**: Visual timeline of all memories
- 🔍 **Semantic Search**: Find memories by meaning
- 📈 **Portfolio Dashboard**: Track financial holdings
- 👤 **Profile Viewer**: Structured user profile data
- 🏥 **Health Monitor**: Real-time service status

---

## 🗄️ Database Schemas

### Episodic Memories (TimescaleDB)

```sql
CREATE TABLE episodic_memories (
    id UUID,
    user_id VARCHAR(64),
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT,
    content TEXT,
    location JSONB,
    participants TEXT[],
    emotional_valence FLOAT,  -- -1 to 1
    emotional_arousal FLOAT,  -- 0 to 1
    importance_score FLOAT,
    tags TEXT[],
    metadata JSONB
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('episodic_memories', 'event_timestamp');
```

### Emotional Memories (TimescaleDB)

```sql
CREATE TABLE emotional_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    timestamp TIMESTAMPTZ NOT NULL,
    emotional_state VARCHAR(64),
    valence FLOAT,  -- -1 to 1
    arousal FLOAT,  -- 0 to 1
    dominance FLOAT,  -- 0 to 1
    context TEXT,
    trigger_event TEXT,
    intensity FLOAT,
    metadata JSONB
);
```

### Procedural Memories (PostgreSQL)

```sql
CREATE TABLE procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    skill_name VARCHAR(128),
    proficiency_level VARCHAR(32),  -- beginner, intermediate, advanced
    steps JSONB,
    prerequisites JSONB,
    last_practiced TIMESTAMPTZ,
    practice_count INT,
    success_rate FLOAT,
    context TEXT,
    tags TEXT[],
    metadata JSONB
);
```

### Portfolio Holdings (PostgreSQL)

`portfolio_holdings` stores equities and options keyed by `(user_id, ticker)`. Migration 025 adds contract fields and widens `ticker` to 32 characters for generated OCC-style option symbols. Options use `contracts`; equities use `shares` and `avg_price`. The API computes option status from the action and expiration date.

See the [current field reference](docs/data-models-server.md#portfolio_holdings) and [portfolio API guide](docs/portfolio-api.md). SQL migrations are the authoritative schema, including constraints.

### Graph Relationships (Neo4j — planned)

> Neo4j integration is planned for a future release. It will enable graph-based queries for skill dependencies, portfolio correlations, and social relationship graphs.

---

## 🛠️ Development

### Project Structure

```
agentic-memories/
├── src/
│   ├── app.py                    # FastAPI application & endpoints
│   ├── config.py                 # Configuration management
│   ├── models.py                 # Pydantic models
│   ├── schemas.py                # API schemas
│   ├── dependencies/             # Database clients
│   │   ├── chroma.py
│   │   ├── timescale.py
│   │   └── redis_client.py
│   └── services/                 # Business logic
│       ├── unified_ingestion_graph.py   # LangGraph extraction pipeline
│       ├── retrieval.py                 # ChromaDB retrieval
│       ├── hybrid_retrieval.py          # Multi-database retrieval
│       ├── reconstruction.py            # Narrative construction
│       ├── episodic_memory.py           # Episodic service
│       ├── emotional_memory.py          # Emotional service
│       ├── procedural_memory.py         # Procedural service
│       ├── portfolio_service.py         # Portfolio service
│       ├── embedding_utils.py           # Vector embeddings
│       ├── extract_utils.py             # LLM utilities
│       └── tracing.py                   # Langfuse integration
├── migrations/                   # Database migrations
│   ├── migrate.sh               # Migration manager
│   ├── generate.sh              # Migration generator
│   ├── timescaledb/             # TimescaleDB migrations
│   ├── postgres/                # PostgreSQL migrations
│   └── chromadb/                # ChromaDB migrations
├── ui/                          # React web interface
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Store.tsx       # Memory ingestion
│   │   │   ├── Browser.tsx     # Memory browser
│   │   │   ├── Retrieve.tsx    # Search interface
│   │   │   ├── Structured.tsx  # Categorized view
│   │   │   └── Health.tsx      # Service health
│   │   └── components/
│   └── tests/                   # Playwright E2E tests
├── tests/                       # Python tests
│   ├── e2e/                    # End-to-end tests
│   └── evals/                  # LLM evaluation tests
├── docker-compose.yml           # Container orchestration
├── Dockerfile                   # API container
└── requirements.txt             # Python dependencies
```

### Running Tests

```bash
make test               # Unit + integration tests
make test-fast          # Unit tests only (fastest)
make test-e2e           # E2E tests (requires running services)
make test-all           # All tests including E2E
make test-coverage      # Tests with coverage report
```

**UI Tests (Playwright)**:
```bash
cd ui && npm test
```

### Migration Management

Migrations run automatically on `make start`. For manual control:

```bash
make migrate                        # Interactive migration menu

# Or use direct commands:
./migrations/migrate.sh up          # Apply pending migrations
./migrations/migrate.sh up --dry-run # Preview changes
./migrations/migrate.sh down 2      # Rollback 2 migrations
./migrations/migrate.sh status      # Check migration status
./migrations/migrate.sh fresh       # Fresh install (DESTRUCTIVE)
```

See [migrations/README.md](migrations/README.md) for full documentation.

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | ✅ | `openai` | Extraction model provider: `openai` or `xai` (Grok) |
| `OPENAI_API_KEY` | ✅ | - | OpenAI API key (always required — used for embeddings) |
| `XAI_API_KEY` | ✅ (if xai) | - | xAI API key (only if using Grok for extraction) |
| `EXTRACTION_MODEL_OPENAI` | ❌ | `gpt-5` | OpenAI model for extraction |
| `EXTRACTION_MODEL_XAI` | ❌ | `grok-4-fast-reasoning` | xAI model for extraction |
| `POSTGRES_PASSWORD` | ❌ | `changeme` | Password for TimescaleDB (used by docker-compose) |
| `LANGFUSE_PUBLIC_KEY` | ❌ | - | Langfuse public key (for tracing) |
| `LANGFUSE_SECRET_KEY` | ❌ | - | Langfuse secret key |
| `LANGFUSE_HOST` | ❌ | `https://us.cloud.langfuse.com` | Langfuse host |

> Database connection strings (`TIMESCALE_DSN`, `CHROMA_HOST`, `REDIS_URL`, etc.) are pre-configured in `docker-compose.yml` and don't need to be set manually.

### Docker Deployment

All services (API, UI, databases) are defined in `docker-compose.yml`. Use `make start` / `make stop` for normal operation. For direct control:

```bash
docker compose up -d        # Start all services
docker compose down          # Stop all services
docker compose logs -f api   # Follow API logs
```

---

## 📖 Documentation

### Core Documentation

- [**Architecture Deep Dive**](docs/internal/restructure_v2.md) - Complete v2 vision and design
- [**Retrieval Data Flow**](docs/internal/RETRIEVAL_DATA_FLOW.md) - How data is fetched
- [**Comprehensive Data Sources**](docs/internal/COMPREHENSIVE_DATA_SOURCES.md) - Database usage analysis
- [**Deployment Results**](docs/internal/DEPLOYMENT_TEST_RESULTS.md) - Testing and verification
- [**Migration Guide**](migrations/README.md) - Database migration system

### API Reference

- **OpenAPI Docs**: http://localhost:8080/docs (Swagger UI)
- **ReDoc**: http://localhost:8080/redoc

### Key Concepts

#### Memory Layers

1. **Short-Term** (TTL: 1 hour)
   - Transient context for current conversation
   - Cached in Redis
   - Example: "User just asked about Python"

2. **Semantic** (Permanent)
   - Facts and concepts
   - No expiration
   - Example: "User's favorite color is blue"

3. **Episodic** (Time-series)
   - Life events with context
   - Stored in TimescaleDB
   - Example: "User attended team meeting on 2025-10-12"

4. **Procedural** (Skill-based)
   - Skills and learning progressions
   - Tracked in PostgreSQL
   - Example: "User learning Python, intermediate level"

5. **Emotional** (Time-series)
   - Mood states and patterns
   - Stored in TimescaleDB
   - Example: "User felt excited about Q4 strategy"

6. **Portfolio** (Structured)
   - Financial holdings and goals
   - Tracked in PostgreSQL + TimescaleDB snapshots
   - Example: "User holds 100 shares of AAPL"

#### Retrieval Strategies

**Simple Retrieval** (`/v1/retrieve`):
- Uses ChromaDB only
- ⚡ Very fast (sub-second)
- Semantic vector search
- Best for: Quick queries, recent memories

**Hybrid Retrieval** (`/v1/narrative`):
- Uses ChromaDB + TimescaleDB + PostgreSQL
- 🐢 Slower (2-5 seconds)
- Multi-database queries
- Best for: Complex narratives, time-range queries, skill tracking

**Structured Retrieval** (`/v1/retrieve/structured`):
- Uses ChromaDB + LLM categorization
- 🧠 LLM-powered organization
- Best for: Organized memory views, category browsing

---

## Streaming Orchestrator Retrieval (vs traditional APIs)

### New retrieval mechanism (high-level)

- **Two access paths**
  - Traditional API: `GET /v1/retrieve` and `POST /v1/retrieve` (persona-aware).
  - Orchestrator API: `POST /v1/orchestrator/message | /retrieve | /transcript`.

### Orchestrator retrieval flow

- **Event in → possible retrieval out**
  - `stream_message` ingests an event, optionally batches/persists it, then immediately calls retrieval to surface relevant memories for that turn.
  - `fetch_memories` runs on-demand retrieval without ingesting a new turn.

- **Search**
  - Uses the same core search as the classic pipeline.
  - Core search now returns measured cosine similarity. However, the orchestrator injection adapter still applies the legacy `1 - score` transformation in `src/memory_orchestrator/retrieval.py`. Its injection scores and threshold behavior therefore differ from ordinary retrieval; the September ranking fix did not update this adapter.

- **Policy gating**
  - `RetrievalPolicy` controls surfacing:
    - `min_similarity` (default 0.15) filters out weak matches.
    - `max_injections_per_message` caps how many memories are injected per turn.
    - `reinjection_cooldown_turns` suppresses repeat injections across nearby turns.

- **Injections**
  - Each result is formatted into a `MemoryInjection` with:
    - `source` derived from metadata layer: short-term → SHORT_TERM; semantic/long-term → LONG_TERM.
    - `channel` default INLINE.
    - `metadata` includes `conversation_id` to support scoped subscriptions.
  - Orchestrator publishes injections only to listeners subscribed for the same `conversation_id`.

- **HTTP endpoints**
  - `POST /v1/orchestrator/message`: stream one turn, returns any immediate injections.
  - `POST /v1/orchestrator/retrieve`: query-only; returns top injections for a conversation/query.
  - `POST /v1/orchestrator/transcript`: replay a batch history through the orchestrator, returning all emitted injections.

### Traditional and persona-aware retrieval

- **GET /v1/retrieve**
  - Standard retrieval with optional `persona` and metadata filters.
  - Falls back to baseline search if persona-specific path yields nothing.

- **POST /v1/retrieve (persona)**
  - `PersonaCoPilot` picks or honors a persona. Ordinary text queries use measured cosine relevance; specialized temporal/emotional queries and browse paths retain their separate scoring behavior. It can return:
    - selected persona + confidence,
    - multi-tier summaries (raw/episodic/arc),
    - optional narrative,
    - optional explainability (applied weights, source links).

### Advantages over traditional APIs

- **Stateful, turn-by-turn retrieval**: policy-gated injections per message instead of static result lists.
- **Duplicate suppression**: `reinjection_cooldown_turns` prevents repeating the same memory across nearby turns.
- **Conversation-scoped delivery**: subscribers receive injections only for their `conversation_id`, avoiding cross-chat leakage.
- **Core-search relevance**: ordinary retrieval uses measured cosine similarity. Orchestrator injection scores retain the legacy inversion described above.
- **Cost-aware ingestion**: batching/flush policies reduce vector upsert churn during bursts.
- **Persona-ready**: seamlessly pairs with persona-aware POST `/v1/retrieve` for dynamic weighting, summaries, and explainability.

### How to tune

- `min_similarity` gates the orchestrator adapter's transformed score; because the legacy inversion remains, increasing it is not equivalent to demanding stronger cosine relevance.
- Lower `max_injections_per_message` to reduce context bloat.
- Raise `reinjection_cooldown_turns` to avoid repeats across multiple turns.
- Persona weight profiles apply to specialized scoring paths; they do not boost ordinary text-query matches above more relevant memories.

> Key impact: more relevant, timely, and non-redundant context injections; persona-aware retrieval for richer personalization.


## 🚧 Implementation Status

### ✅ Phase 1: Core Infrastructure (COMPLETE)

- [x] FastAPI application with health checks
- [x] Multi-database connectivity (4 databases)
- [x] Environment configuration
- [x] Docker deployment
- [x] Migration system (enhanced with rollback)
- [x] Web UI scaffolding

### ✅ Phase 2: Memory Extraction & Storage (COMPLETE)

- [x] Unified LangGraph extraction pipeline
- [x] Memory worthiness filtering
- [x] Multi-type extraction (episodic, semantic, procedural, emotional, portfolio)
- [x] Parallel storage to all databases
- [x] ChromaDB vector embeddings
- [x] Transaction commit fixes
- [x] Connection pooling
- [x] Langfuse tracing integration

### ✅ Phase 3: Retrieval & Reconstruction (COMPLETE)

- [x] Simple semantic retrieval (ChromaDB)
- [x] Structured retrieval with LLM categorization
- [x] Hybrid retrieval (multi-database)
- [x] Temporal queries (TimescaleDB)
- [x] Procedural queries (PostgreSQL)
- [x] Narrative construction
- [x] Portfolio summary endpoint
- [x] Redis caching for short-term layer

### ✅ Phase 4: Advanced Cognitive Features (COMPLETE)

- [x] Episodic memory service
- [x] Emotional memory service with pattern detection
- [x] Procedural memory with skill progressions
- [x] Portfolio service with intent detection
- [x] Emotional pattern predictions (service method implemented)
- [x] Skill recommendations based on prerequisites (service method implemented)

### ✅ Phase 5: Memory Consolidation & Forgetting (COMPLETE)

- [x] **Consolidation job** — LLM-powered clustering + merging related memories into golden records (`POST /v1/maintenance/compact`)
- [x] **TTL-based forgetting** — Expired short-term cleanup (ChromaDB + TimescaleDB), low-importance episodic pruning (< 0.3, > 90 days), low-intensity emotional pruning (< 0.2, > 60 days)
- [x] **Memory compression** — Clusters of 3-10 similar memories consolidated into single summaries
- [x] **Deduplication** — Cosine-similarity dedup across ChromaDB, episodic, and emotional tables
- [x] **Scheduled consolidation** — APScheduler daily cron at 00:00 UTC + on-demand via `POST /v1/maintenance/compact`

### ✅ Phase 6: Narrative & Reconstruction (COMPLETE)

- [x] Narrative construction with hybrid retrieval (`POST /v1/narrative`)
- [x] Gap-filling with LLM inference (ReconstructionService fills gaps during narrative generation)
- [x] Emotional pattern recognition (service method in EmotionalMemoryService)
- [x] Causal chain schema (`triggered_by`, `led_to` fields in episodic memories)

### ✅ Phase 7: Data Lifecycle & Deletion (COMPLETE)

- [x] **Memory deletion** — Cross-storage delete via `DELETE /v1/memories/{memory_id}` (ChromaDB + episodic + emotional + procedural)
- [x] **Profile deletion** — `DELETE /v1/profile` with cascade across all profile tables
- [x] **Portfolio deletion** — `DELETE /v1/portfolio` and `DELETE /v1/portfolio/holding/{ticker}`

### ✅ Phase 8: Profile & Persona Intelligence (COMPLETE)

- [x] **Profile extraction** — Auto-populated from conversations during ingestion (27 fields, 8 categories)
- [x] **Profile CRUD** — `GET /v1/profile`, `PUT /v1/profile/{category}/{field}`, `DELETE /v1/profile`
- [x] **Profile completeness** — `GET /v1/profile/completeness` with populated/total field tracking
- [x] **Persona-aware retrieval** — PersonaCoPilot with 8 personas (identity, relationships, health, finance, creativity, partner, guide, strategist)
- [x] **Weighted retrieval** — Custom weight profiles per persona (semantic, temporal, importance, emotional)
- [x] **Explainability** — Source links and applied weight profiles in persona retrieval responses

### ✅ Phase 9: Orchestrator & Proactive Intelligence (COMPLETE)

- [x] **Orchestrator message streaming** — `POST /v1/orchestrator/message` with adaptive throttling
- [x] **Orchestrator retrieval** — `POST /v1/orchestrator/retrieve` for query-only retrieval
- [x] **Transcript ingestion** — `POST /v1/orchestrator/transcript` for batch history replay
- [x] **Memory injection** — Policy-gated injections per turn with similarity thresholds and cooldowns
- [x] **Direct memory storage** — `POST /v1/memories/direct` for sub-3s typed storage (bypasses LLM pipeline)
- [x] **Intents & scheduling** — Full CRUD for scheduled intents with cron, interval, and event-based triggers
- [x] **Intent execution** — Claim, fire, cooldown logic, and execution history tracking

### ✅ Phase 10: Web UI (COMPLETE)

- [x] Memory browser with timeline
- [x] Store interface for ingestion
- [x] Retrieve interface with search
- [x] Structured retrieval view
- [x] Health monitoring dashboard
- [x] Responsive design with Tailwind CSS
- [x] Playwright E2E tests

### ✅ Phase 11: CI/CD & DevOps (COMPLETE)

- [x] **GitHub Actions CI** — Linting (ruff), unit + integration tests, Docker build + push
- [x] **Secret scanning** — Gitleaks integration with allowlist configuration
- [x] **Container registry** — Docker images pushed to GitHub Container Registry
- [x] **Deployment pipeline** — `.github/workflows/deploy.yml`
- [x] **Test reporting** — JUnit XML result reporting

### ✅ Phase 12: Testing & Evaluation (COMPLETE)

- [x] Health check tests
- [x] API integration tests
- [x] E2E tests (Python + Playwright)
- [x] **LLM evaluation suite** — Extraction quality metrics (precision, recall, F1, calibration) in `tests/evals/`

---

### Upcoming Phases

### 🔮 Phase 13: Advanced Forgetting & Retention

- [ ] **Ebbinghaus forgetting curves** — Exponential decay based on review intervals (current: threshold-based)
- [ ] **Spaced repetition** for skill retention
- [ ] **Continuous emotional decay** over time

### 🔮 Phase 14: Prediction & Behavioral Intelligence

- [ ] **Predictive engine** — Anticipate user needs based on patterns
- [ ] **Behavioral pattern recognition** — Complement existing emotional patterns
- [ ] **Causal relationship queries** — Traverse `triggered_by`/`led_to` chains via API
- [ ] **Life story API** — Complete narrative timeline from all memories

### 🔮 Phase 15: Dedicated Memory Services

- [ ] **Semantic memory service** — Dedicated service (currently stored via generic pipeline)
- [ ] **Identity memory service** — Dedicated service (currently lives in profile system)
- [ ] **Emotional prediction API endpoint** — Expose existing `predict_emotional_response()` service method
- [ ] **Skill recommendation API endpoint** — Expose existing `recommend_next_skills()` service method
- [ ] **Memory edit endpoint** — Edit existing memories (view and delete already exist)

### 🔮 Phase 16: Graph Intelligence (Neo4j)

- [ ] **Neo4j integration** — Deploy and connect graph database
- [ ] **Skill dependency traversal** — Graph-based skill chain queries
- [ ] **Portfolio correlation analysis** — Cross-holding relationship graphs
- [ ] **Social relationship graphs** — People and interaction mapping
- [ ] **Learning path recommendations** — Graph-powered skill progression suggestions

### 🔮 Phase 17: Privacy & Compliance

- [ ] **Consent management system** — Opt-in/out controls per memory type
- [ ] **Memory sensitivity scoring** — Auto-classify sensitive content
- [ ] **Encryption for sensitive memories** — At-rest encryption for high-sensitivity data
- [ ] **Audit logs** — Track all memory access and modifications
- [ ] **GDPR compliance** — Right to be forgotten, data export, retention policies

### 🔮 Phase 18: Performance & Scale

- [ ] **Retrieval evaluation** — Relevance metrics, ranking quality benchmarks
- [ ] **Performance benchmarks** — Query latency profiling
- [ ] **Load testing** — Concurrent user benchmarks
- [ ] **Sub-100ms simple queries** — Performance optimization target

---

## 🎯 Roadmap

### Completed

- ✅ Core infrastructure and database setup
- ✅ Memory extraction pipeline (LangGraph)
- ✅ Retrieval: semantic, hybrid, structured, persona-aware
- ✅ Narrative construction with gap-filling
- ✅ Portfolio tracking with full CRUD
- ✅ Web UI
- ✅ Profile extraction and management (27 fields, 8 categories)
- ✅ Orchestrator with adaptive throttling and memory injection
- ✅ Persona-aware retrieval (PersonaCoPilot with 8 personas)
- ✅ Direct memory storage (sub-3s typed storage)
- ✅ Intents & scheduled actions (cron, interval, event-based triggers)
- ✅ Consolidation engine (LLM-powered clustering, TTL forgetting, deduplication)
- ✅ Scheduled nightly compaction (APScheduler daily cron)
- ✅ Emotional pattern detection
- ✅ Skill recommendations based on prerequisites
- ✅ LLM evaluation suite (extraction quality metrics)
- ✅ Cross-storage memory deletion
- ✅ CI/CD pipeline with secret scanning

### Planned

- [ ] **Phase 13: Advanced Forgetting** - Ebbinghaus curves, spaced repetition, emotional decay
- [ ] **Phase 14: Prediction & Behavior** - Predictive engine, behavioral patterns, causal queries, life story API
- [ ] **Phase 15: Dedicated Services** - Semantic/identity memory services, expose prediction & recommendation APIs
- [ ] **Phase 16: Graph Intelligence** - Neo4j deployment, skill traversal, portfolio correlation, relationship graphs
- [ ] **Phase 17: Privacy & Compliance** - Consent management, encryption, sensitivity scoring, audit logs, GDPR
- [ ] **Phase 18: Performance & Scale** - Retrieval benchmarks, load testing, sub-100ms query target

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas We Need Help

- 🧪 **Testing**: LLM evaluation, performance benchmarks
- 📖 **Documentation**: Tutorials, examples, translations
- 🎨 **UI/UX**: Web interface improvements
- 🧠 **Cognitive Features**: Consolidation, forgetting, prediction algorithms
- 🔐 **Security**: Encryption, consent management, auditing
- 🌍 **Internationalization**: Multi-language support

---

## Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED. USE AT YOUR OWN RISK.

**The authors and contributors of Agentic Memories shall not be held liable
for any damages, losses, or consequences arising from the use, misuse, or
inability to use this software**, including but not limited to:

- **Data loss or corruption** — This software manages databases and persistent
  storage. Always maintain independent backups of any critical data.
- **AI-generated content** — Memory extraction, consolidation, and retrieval
  rely on large language models (LLMs) which may produce inaccurate, incomplete,
  misleading, or biased outputs. Do not rely on this software for medical,
  legal, financial, or safety-critical decisions.
- **Security vulnerabilities** — While we make reasonable efforts to follow
  security best practices, no software is guaranteed to be free of
  vulnerabilities. You are responsible for securing your own deployment,
  credentials, and infrastructure.
- **Third-party services** — This software integrates with external APIs and
  services (OpenAI, Grok, etc.) which have their own terms of service, pricing,
  and limitations. You are solely responsible for compliance with those terms
  and any costs incurred.
- **Privacy and personal data** — This software stores and processes user
  conversations and personal information. You are solely responsible for
  compliance with all applicable data protection laws and regulations (GDPR,
  CCPA, etc.) in your jurisdiction.

**By using this software, you acknowledge that you have read this disclaimer
and agree to assume all risks associated with its use.**

This project is experimental and under active development. APIs, data formats,
and behavior may change without notice between versions.

---

## 📝 License

Licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

### Inspiration

- **Cognitive Science**: Baddeley & Hitch (Working Memory), Ebbinghaus (Forgetting Curve), Bartlett (Reconstructive Memory)
- **Neuroscience**: McGaugh (Emotional Memory), Müller & Pilzecker (Consolidation)
- **AI Research**: LangChain, LangGraph, Mem0, Zep, MemGPT

### Technologies

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [LangChain/LangGraph](https://www.langchain.com/) - LLM orchestration
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [TimescaleDB](https://www.timescale.com/) - Time-series PostgreSQL
- [Langfuse](https://langfuse.com/) - LLM observability
- [React](https://react.dev/) + [Tailwind CSS](https://tailwindcss.com/) - Web UI

---

## 📬 Contact

- **Issues**: [GitHub Issues](https://github.com/ankitaa186/agentic-memories/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ankitaa186/agentic-memories/discussions)

---

<div align="center">

**Built with ❤️ by humans who believe AI can remember like we do**

⭐ Star us on GitHub if this project resonates with you!

</div>
 