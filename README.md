# Agentic Memories 🧠

<div align="center">

**A living, breathing memory system that transforms AI from stateless responders into sentient companions with human-like consciousness**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
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
│  Episodic | Semantic | Procedural | Emotional | Somatic │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │
┌─────────────────────────────────────────────────────────┐
│              HYBRID STORAGE SYSTEMS                     │
│  TimescaleDB | Neo4j | ChromaDB | PostgreSQL | Redis   │
└─────────────────────────────────────────────────────────┘
```

### 🎯 Key Differentiators

| Traditional Memory Systems | Agentic Memories |
|---------------------------|------------------|
| Static key-value storage | **Dynamic, time-aware consolidation** |
| Facts without context | **Experiences with emotional weight** |
| Simple search | **Reconstructive retrieval** (fills gaps like humans) |
| Infinite retention | **Graceful forgetting** (Ebbinghaus curve) |
| Single database | **Polyglot persistence** (5 specialized databases) |
| Reactive queries | **Predictive intelligence** |
| No narrative capability | **Coherent life story construction** |

### 🔬 Inspired by Neuroscience

- **Episodic Buffer** (Baddeley & Hitch) - Rich contextual event storage
- **Consolidation Theory** (Müller & Pilzecker) - Nightly memory strengthening
- **Forgetting Curves** (Ebbinghaus) - Natural decay with spaced repetition
- **Emotional Memory Enhancement** (McGaugh) - Emotional events remembered better
- **Reconstructive Memory** (Bartlett) - Gap-filling during recall

---

## 🚀 Features

### 🎯 Core Capabilities

- **🧠 Intelligent Memory Extraction** - Unified LangGraph pipeline extracts multiple memory types from conversations using LLMs (GPT-4, Grok)
- **📊 Multi-Modal Memory Types**
  - **Episodic**: Life events with temporal, spatial, and emotional context
  - **Semantic**: Facts, concepts, and declarative knowledge
  - **Procedural**: Skills, habits, and learned behaviors with progression tracking
  - **Emotional**: Mood states, patterns, and emotional trajectories
  - **Portfolio**: Financial holdings, transactions, and investment goals
  - **Identity**: Core values, beliefs, and self-concept (coming soon)
  
- **🔍 Hybrid Retrieval System**
  - Semantic search via vector embeddings (ChromaDB)
  - Temporal queries for time-range narratives (TimescaleDB)
  - Structured queries for skills and holdings (PostgreSQL)
  - Graph traversal for relationships (Neo4j - coming soon)
  - Redis caching for performance
  
- **📖 Narrative Construction** - Weaves memories into coherent stories with temporal awareness and gap-filling

- **💼 Portfolio Intelligence** - Tracks stocks, crypto, assets with intent detection and goal extraction

- **🔐 Privacy-First Design** - Consent management, encryption-ready, sensitivity scoring (coming soon)

- **📈 Observability** - Full Langfuse integration for LLM tracing and debugging

### 🛠️ Technical Features

- **⚡ High Performance**
  - Sub-second simple queries (ChromaDB only)
  - Hybrid multi-database queries for complex narratives
  - Connection pooling and explicit transaction management
  - Redis caching for hot paths
  
- **🔄 Robust Data Management**
  - Versioned migrations for 5 database types
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
  - External database dependencies
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
│ • Neo4j         │                  └─────────────────────┘
│ • Redis         │
└─────────────────┘
```

### Database Strategy: "Write Everywhere, Read Selectively"

| Database | Primary Use | Read Pattern | Data Type |
|----------|-------------|--------------|-----------|
| **ChromaDB** | Vector embeddings | **All retrieval** | Memories with semantic search |
| **TimescaleDB** | Time-series data | Temporal queries | Episodic, emotional, portfolio snapshots |
| **PostgreSQL** | Structured data | Procedural, portfolio | Skills, holdings, transactions |
| **Neo4j** | Graph relationships | (Future) | Skill chains, correlations |
| **Redis** | Hot cache | Short-term layer | Transient memories |

**Why Polyglot Persistence?**
- ✅ Each database optimized for its data type
- ✅ Fast simple queries (ChromaDB only)
- ✅ Complex queries available (multi-database)
- ✅ Data redundancy for resilience
- ✅ Future-proof for analytics and graph queries

---

## 📦 Quick Start

**TL;DR for Docker users**:
```bash
# 1. Start external databases
cd agentic-memories-storage && ./docker-up.sh

# 2. Create database schemas (first time only)
cd ../agentic-memories/migrations && ./migrate.sh
# Select option 10: "Fresh install (drop all tables and rerun)"

# 3. Run Agentic Memories
cd .. && ./run_docker.sh
```

### Prerequisites

- **Python 3.12+**
- **Docker & Docker Compose** (for databases)
- **External Dependencies**: `agentic-memories-storage` repository
  - Provides: TimescaleDB, Neo4j, ChromaDB, Redis
  - Quick start: `./docker-up.sh` in storage repo
  - See: [agentic-memories-storage](https://github.com/yourusername/agentic-memories-storage) (replace with actual URL)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/agentic-memories.git
cd agentic-memories
```

### 2. Set Up External Databases

This project requires external databases. Deploy the companion storage repository:

```bash
# In a separate directory
git clone https://github.com/yourusername/agentic-memories-storage.git
cd agentic-memories-storage

# Simple one-command startup
./docker-up.sh
```

This provides:
- **TimescaleDB** (PostgreSQL extension): `localhost:5433`
- **Neo4j**: `localhost:7687` (UI: `localhost:7474`)
- **ChromaDB**: `localhost:8000`
- **Redis**: `localhost:6379`

### 3. Configure Environment

```bash
cp env.example .env
```

Edit `.env` with your configuration:

```bash
# LLM Provider (required)
LLM_PROVIDER=openai  # or "xai" for Grok
OPENAI_API_KEY=your_key_here

# Database connections (match agentic-memories-storage ports)
CHROMA_HOST=localhost
CHROMA_PORT=8000
TIMESCALE_DSN=postgresql://postgres:Passw0rd1!@localhost:5433/agentic_memories
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
REDIS_URL=redis://localhost:6379/0

# Observability (optional)
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

### 4. Run Database Migrations

**Fresh Install (first time setup)**:
```bash
cd migrations
./migrate.sh

# Interactive menu will appear:
# Select option 10: "Fresh install (drop all tables and rerun)"
```

**Incremental Updates (existing database)**:
```bash
cd migrations
./migrate.sh

# Interactive menu will appear:
# Select option 1: "Run pending migrations (up)"
```

This will create all necessary tables, hypertables, constraints, and collections across all databases.

### 5. Install Dependencies

**Docker (recommended)**: Skip this step - `run_docker.sh` handles everything!

**Local Development (venv)**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 6. Start the Application

**Docker (recommended)**:
```bash
./run_docker.sh
```

This script will:
- ✅ Check if Docker is running
- ✅ Create `.env` interactively if missing
- ✅ Verify ChromaDB connectivity
- ✅ Create required collections
- ✅ Build and start all services

**Local Development**:
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

### 7. Verify Health

```bash
curl http://localhost:8080/health/full | jq
```

Expected output:
```json
{
  "status": "ok",
  "checks": {
    "chroma": {"ok": true},
    "timescale": {"ok": true},
    "neo4j": {"ok": true},
    "redis": {"ok": true},
    "portfolio": {"ok": true},
    "langfuse": {"ok": true}
  }
}
```

### 8. Try Your First Memory!

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
  "memories_created": 3,
  "ids": ["mem_abc", "mem_def", "mem_ghi"],
  "summary": "Stored: 1 episodic, 1 emotional, 1 portfolio.",
  "memories": [...]
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
- `limit` (default: 10): Results per page
- `offset` (default: 0): Pagination offset

**Response**:
```json
{
  "results": [
    {
      "id": "mem_xyz",
      "content": "User bought 100 shares of AAPL at $175",
      "score": 0.95,
      "layer": "short-term",
      "metadata": {
        "portfolio": "{\"ticker\":\"AAPL\",\"shares\":100,...}"
      }
    }
  ],
  "finance": {
    "portfolio": {
      "holdings": [{"ticker": "AAPL", "shares": 100, ...}],
      "counts_by_asset_type": {"public_equity": 1}
    }
  }
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

**Response**: Memories categorized into:
- `emotions`, `behaviors`, `personal`, `professional`
- `habits`, `skills_tools`, `projects`, `relationships`
- `learning_journal`, `finance`, `other`

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
  "narrative": "In Q1 2025, the user focused on...",
  "summary": "Key themes: career growth, learning Python",
  "sources": [
    {"id": "mem_abc", "content": "...", "type": "episodic"}
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

#### 🔹 Portfolio Summary

```http
GET /v1/portfolio/summary?user_id=user_123
```

Structured portfolio data from PostgreSQL (with ChromaDB fallback).

**Response**:
```json
{
  "user_id": "user_123",
  "holdings": [
    {
      "ticker": "AAPL",
      "shares": 100,
      "avg_price": 175,
      "position": "long",
      "intent": "buy"
    }
  ],
  "counts_by_asset_type": {
    "public_equity": 1
  }
}
```

---

#### 🔹 Health Check

```http
GET /health/full
```

Comprehensive health check for all services.

---

## 🎨 Web UI

Access the beautiful memory browser at: **http://localhost:80**

Features:
- 📊 **Memory Browser**: Visual timeline of all memories
- 🔍 **Semantic Search**: Find memories by meaning
- 📈 **Portfolio Dashboard**: Track financial holdings
- 🏥 **Health Monitor**: Real-time service status
- 🎯 **Debug Console**: Inspect LLM traces with Langfuse

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

```sql
CREATE TABLE portfolio_holdings (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    ticker VARCHAR(16),
    asset_name VARCHAR(256),
    asset_type VARCHAR(64),
    shares FLOAT,
    avg_price FLOAT,
    position VARCHAR(16),  -- long, short
    intent VARCHAR(16),  -- buy, sell, hold, watch
    time_horizon VARCHAR(16),
    source_memory_id VARCHAR(128),
    first_acquired TIMESTAMPTZ,
    last_updated TIMESTAMPTZ
);
```

### Graph Relationships (Neo4j)

```cypher
// Skill dependencies
CREATE CONSTRAINT skill_id_unique FOR (s:Skill) REQUIRE s.id IS UNIQUE;
CREATE INDEX skill_user FOR (s:Skill) ON (s.user_id);

// Relationships
(Skill)-[:REQUIRES]->(Skill)
(Skill)-[:LEADS_TO]->(Skill)
(User)-[:KNOWS]->(Skill)

// Portfolio correlations (future)
(Holding)-[:CORRELATES_WITH]->(Holding)
(Holding)-[:IN_SECTOR]->(Sector)
```

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
│   │   ├── neo4j_client.py
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
│   ├── neo4j/                   # Neo4j migrations
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

**Unit Tests**:
```bash
pytest tests/ -v
```

**End-to-End Tests**:
```bash
cd tests/e2e
./run_e2e_tests.sh
```

**UI Tests (Playwright)**:
  ```bash
  cd ui
npm test
```

### Migration Management

Our enhanced migration system supports:
- ✅ Rollback to previous versions
- ✅ Dry-run mode for safety
- ✅ Migration validation
- ✅ History tracking
- ✅ Concurrency locking

**Common Commands**:
  ```bash
cd migrations

# Run interactively (recommended)
./migrate.sh

# Or use direct commands:
./migrate.sh up              # Apply pending migrations
./migrate.sh up --dry-run    # Preview changes
./migrate.sh down 2          # Rollback 2 migrations
./migrate.sh status          # Check migration status
./migrate.sh history 20      # Show last 20 migrations
./migrate.sh validate        # Check for issues
./migrate.sh fresh           # Fresh install (⚠️ DESTRUCTIVE)

# Generate new migration
./generate.sh postgres add_user_preferences
```

See [migrations/README.md](migrations/README.md) for full documentation.

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | ✅ | `openai` | LLM provider: `openai` or `xai` (Grok) |
| `OPENAI_API_KEY` | ✅ (if openai) | - | OpenAI API key |
| `XAI_API_KEY` | ✅ (if xai) | - | xAI (Grok) API key |
| `EXTRACTION_MODEL` | ❌ | `gpt-4o` | Model for extraction |
| `EMBEDDING_MODEL` | ❌ | `text-embedding-3-large` | Embedding model (3072-dim) |
| `CHROMA_HOST` | ✅ | `localhost` | ChromaDB host |
| `CHROMA_PORT` | ✅ | `8000` | ChromaDB port |
| `TIMESCALE_DSN` | ✅ | - | PostgreSQL/TimescaleDB connection string |
| `NEO4J_URI` | ✅ | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | ✅ | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | ✅ | `password` | Neo4j password |
| `REDIS_URL` | ❌ | `redis://localhost:6379/0` | Redis connection string |
| `LANGFUSE_PUBLIC_KEY` | ❌ | - | Langfuse public key (for tracing) |
| `LANGFUSE_SECRET_KEY` | ❌ | - | Langfuse secret key |
| `LANGFUSE_HOST` | ❌ | `https://us.cloud.langfuse.com` | Langfuse host |

### Docker Deployment

**Important**: When using Docker, unset exported environment variables to avoid overriding `.env`:

```bash
unset CHROMA_HOST TIMESCALE_DSN NEO4J_URI
docker-compose down && docker-compose up -d
```

The containers will use `host.docker.internal` to access external databases.

---

## 📖 Documentation

### Core Documentation

- [**Architecture Deep Dive**](restructure_v2.md) - Complete v2 vision and design
- [**Retrieval Data Flow**](RETRIEVAL_DATA_FLOW.md) - How data is fetched
- [**Comprehensive Data Sources**](COMPREHENSIVE_DATA_SOURCES.md) - Database usage analysis
- [**Deployment Results**](DEPLOYMENT_TEST_RESULTS.md) - Testing and verification
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

## 🚧 Implementation Status

### ✅ Phase 1: Core Infrastructure (COMPLETE)

- [x] FastAPI application with health checks
- [x] Multi-database connectivity (5 databases)
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

### 🚧 Phase 4: Advanced Cognitive Features (PARTIAL)

- [x] Episodic memory service
- [x] Emotional memory service with pattern detection
- [x] Procedural memory with skill progressions
- [x] Portfolio service with intent detection
- [ ] **Semantic memory service** (pending)
- [ ] **Identity memory service** (pending)
- [ ] **Graph retrieval using Neo4j** (pending)
- [ ] **Emotional pattern predictions** (service exists, endpoint pending)
- [ ] **Skill recommendations based on prerequisites** (pending)

### 🚧 Phase 5: Memory Consolidation & Forgetting (PENDING)

- [ ] **Nightly consolidation job** (promote important short-term → semantic)
- [ ] **Forgetting mechanism** with Ebbinghaus curve
- [ ] **Memory compression** (detailed episodes → summaries)
- [ ] **Spaced repetition** for skill retention
- [ ] **Emotional decay** over time

### 🚧 Phase 6: Narrative & Prediction (PARTIAL)

- [x] Basic narrative construction
- [ ] **Gap-filling** with LLM inference
- [ ] **Causal chain tracking** (triggered_by, led_to)
- [ ] **Life story API** (complete narrative timeline)
- [ ] **Predictive engine** (anticipate needs)
- [ ] **Pattern recognition** (behavioral, emotional)

### 🚧 Phase 7: Privacy & Security (PENDING)

- [ ] **Consent management system**
- [ ] **Memory sensitivity scoring**
- [ ] **Encryption for sensitive memories**
- [ ] **User control endpoints** (view, edit, delete memories)
- [ ] **Audit logs** for memory access
- [ ] **GDPR compliance** (right to be forgotten)

### 🚧 Phase 8: Advanced Graph Features (PENDING)

- [ ] **Neo4j read queries** (currently write-only)
- [ ] **Skill dependency traversal**
- [ ] **Portfolio correlation analysis**
- [ ] **Social relationship graphs**
- [ ] **Learning path recommendations**

### ✅ Phase 9: Web UI (COMPLETE)

- [x] Memory browser with timeline
- [x] Store interface for ingestion
- [x] Retrieve interface with search
- [x] Structured retrieval view
- [x] Health monitoring dashboard
- [x] Responsive design with Tailwind CSS
- [x] Playwright E2E tests

### 🚧 Phase 10: Testing & Evaluation (PARTIAL)

- [x] Health check tests
- [x] API integration tests
- [x] E2E tests (Python + Playwright)
- [ ] **LLM evaluation suite** (extraction quality)
- [ ] **Retrieval evaluation** (relevance metrics)
- [ ] **Performance benchmarks** (query latency)
- [ ] **Load testing** (concurrent users)

---

## 🎯 Roadmap

### Q4 2024

- ✅ Core infrastructure and database setup
- ✅ Memory extraction pipeline (LangGraph)
- ✅ Basic retrieval (semantic + hybrid)
- ✅ Narrative construction
- ✅ Portfolio tracking
- ✅ Web UI

### Q1 2025

- [ ] **Consolidation engine** - Nightly memory strengthening
- [ ] **Forgetting mechanism** - Graceful decay with retention policies
- [ ] **Neo4j retrieval** - Graph-based queries
- [ ] **Semantic & Identity services** - Complete all memory layers
- [ ] **Privacy controls** - Consent management and encryption

### Q2 2025

- [ ] **Predictive intelligence** - Anticipate user needs
- [ ] **Pattern recognition** - Behavioral and emotional patterns
- [ ] **Advanced narrative** - Gap-filling and causal chains
- [ ] **Performance optimization** - Sub-100ms simple queries
- [ ] **Multi-tenant support** - Production-ready for SaaS

### Q3 2025

- [ ] **Social memory** - Relationship graphs and shared memories
- [ ] **Learning recommendations** - Skill paths based on graph traversal
- [ ] **Emotional coaching** - Mood tracking and interventions
- [ ] **Mobile app** - iOS/Android native interfaces
- [ ] **Plugin ecosystem** - Integrate with popular chatbot platforms

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

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

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
- [Neo4j](https://neo4j.com/) - Graph database
- [Langfuse](https://langfuse.com/) - LLM observability
- [React](https://react.dev/) + [Tailwind CSS](https://tailwindcss.com/) - Web UI

---

## 📬 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/agentic-memories/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/agentic-memories/discussions)
- **Email**: your.email@example.com
- **Twitter**: [@yourusername](https://twitter.com/yourusername)

---

<div align="center">

**Built with ❤️ by humans who believe AI can remember like we do**

⭐ Star us on GitHub if this project resonates with you!

</div>
