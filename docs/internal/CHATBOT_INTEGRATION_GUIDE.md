# Integration Guide

Give your AI agent persistent memory in under 5 minutes.

Agentic Memories is a REST API. You store memories by sending conversations in, and retrieve them by querying. Everything below assumes the service is running at `http://localhost:8080` (see [Quick Start](../../README.md#-quick-start) to get there).

---

## Table of Contents

1. [Quickstart: 3 Calls to Persistent Memory](#1-quickstart-3-calls-to-persistent-memory)
2. [Storing Memories](#2-storing-memories)
   - [Option A: Orchestrator (recommended)](#option-a-orchestrator-endpoint-recommended)
   - [Option B: Direct Memory Storage](#option-b-direct-memory-storage)
   - [Option C: Transcript Ingestion](#option-c-transcript-ingestion-v1store)
3. [Retrieving Memories](#3-retrieving-memories)
   - [Basic Retrieval](#basic-retrieval)
   - [User Profile](#user-profile)
   - [Portfolio](#portfolio)
   - [Structured Retrieval](#structured-retrieval)
   - [Narrative Construction](#narrative-construction)
   - [Persona-Aware Retrieval](#persona-aware-retrieval)
4. [Compaction & Maintenance](#4-compaction--maintenance)
5. [Full Integration Example](#5-full-integration-example)
6. [Endpoint Reference Cheat Sheet](#6-endpoint-reference-cheat-sheet)

---

## 1. Quickstart: 3 Calls to Persistent Memory

This is the absolute minimum to give your agent memory. One call to store, one to retrieve, done.

**Store a conversation turn:**

```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "session-1",
    "role": "user",
    "content": "I just got promoted to senior engineer at Stripe!",
    "metadata": {"user_id": "user_123"},
    "flush": true
  }'
```

**Retrieve relevant memories:**

```bash
curl 'http://localhost:8080/v1/retrieve?user_id=user_123&query=career&limit=5'
```

**Inject into your LLM prompt:**

```python
import requests

BASE = "http://localhost:8080"

def chat(user_id: str, message: str) -> str:
    # 1. Store the message
    requests.post(f"{BASE}/v1/orchestrator/message", json={
        "conversation_id": f"session-{user_id}",
        "role": "user",
        "content": message,
        "metadata": {"user_id": user_id},
        "flush": True,
    })

    # 2. Retrieve relevant memories
    memories = requests.get(f"{BASE}/v1/retrieve", params={
        "user_id": user_id,
        "query": message,
        "limit": 5,
    }).json()

    # 3. Build context and call your LLM
    context = "\n".join(f"- {m['content']}" for m in memories.get("results", []))

    return call_your_llm(
        system=f"You have the following memories about this user:\n{context}",
        user=message,
    )
```

That's it. Your agent now remembers across sessions. Everything below is about doing it better.

---

## 2. Storing Memories

Three ways to get data in, ordered from most to least recommended.

### Option A: Orchestrator Endpoint (recommended)

**`POST /v1/orchestrator/message`**

The orchestrator is the best way to store memories for most integrations. You stream conversation turns in real-time and the orchestrator handles everything: batching messages during high-volume bursts, deduplicating, embedding, and persisting across all storage backends.

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

**Request fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `conversation_id` | string | yes | Groups messages by session |
| `role` | string | yes | `"user"`, `"assistant"`, `"system"`, or `"tool"` |
| `content` | string | yes | The message text |
| `metadata` | object | no | Must include `user_id` for retrieval |
| `flush` | bool | no | `true` = persist immediately. `false` = let the orchestrator batch. Default `false` |

**Response:** Returns any memories surfaced by this turn.

```json
{
  "injections": [
    {
      "memory_id": "mem-abc123",
      "content": "User previously mentioned watching NVDA closely.",
      "source": "long_term",
      "channel": "inline",
      "score": 0.91,
      "metadata": {"layer": "semantic", "conversation_id": "chat-42"}
    }
  ]
}
```

**Why this is the best option:**
- Cost-aware: batches messages during bursts so you don't overload vector upserts
- Stateful: tracks recent turns and suppresses duplicate memory injections
- Two-in-one: stores *and* retrieves in a single call
- Conversation-scoped: memories are isolated per `conversation_id`

**Set `flush: true`** when you want guaranteed persistence (end of conversation, important messages). Leave it `false` during rapid exchanges and the orchestrator will batch optimally.

**Batch replay** an existing transcript:

```bash
curl -X POST http://localhost:8080/v1/orchestrator/transcript \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "history": [
      {"role": "user", "content": "I started learning Rust last week"},
      {"role": "assistant", "content": "That is exciting! What are you building?"},
      {"role": "user", "content": "A CLI tool for my team at work"}
    ]
  }'
```

**Retrieve without storing** a new turn:

```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "chat-42",
    "query": "investments",
    "metadata": {"user_id": "user_123"},
    "limit": 5
  }'
```

---

### Option B: Direct Memory Storage

**`POST /v1/memories/direct`**

Use this when you already know exactly what memory to store and don't need LLM extraction. Sub-3-second latency. Great for explicit user statements, structured data, or when your own application logic has already parsed the information.

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

**Response:**

```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {"chromadb": true}
}
```

**Typed storage** is triggered by setting optional fields. The memory is always stored in ChromaDB and additionally routed to specialized tables:

```bash
# Episodic memory (stored in episodic_memories table)
curl -X POST http://localhost:8080/v1/memories/direct \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "content": "Had a great 1:1 with manager about promotion path",
    "layer": "episodic",
    "event_timestamp": "2025-01-15T10:30:00Z",
    "event_type": "meeting",
    "location": "Office",
    "participants": ["Alice", "Manager"],
    "importance": 0.9
  }'

# Emotional memory (stored in emotional_memories table)
curl -X POST http://localhost:8080/v1/memories/direct \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "content": "Feeling excited about the new role",
    "layer": "emotional",
    "emotional_state": "excited",
    "valence": 0.8,
    "arousal": 0.7,
    "trigger_event": "Got promoted"
  }'

# Procedural memory (stored in procedural_memories table)
curl -X POST http://localhost:8080/v1/memories/direct \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "content": "Learning Kubernetes for container orchestration",
    "layer": "procedural",
    "skill_name": "Kubernetes",
    "proficiency_level": "beginner"
  }'
```

**When to use direct storage over the orchestrator:**
- You've already extracted the memory content yourself
- You need to store typed memories (episodic events, emotions, skills)
- You want deterministic, low-latency writes without LLM processing

---

### Option C: Transcript Ingestion (`/v1/store`)

**`POST /v1/store`**

The full LLM-powered ingestion pipeline. Sends a conversation through a LangGraph pipeline that evaluates worthiness, extracts multiple memory types, classifies, enriches, and stores across all backends. This is the most thorough but slowest path.

```bash
curl -X POST http://localhost:8080/v1/store \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "history": [
      {"role": "user", "content": "I just got back from a 2-week trip to Japan. Visited Tokyo, Kyoto, and Osaka. The ramen in Fukuoka was incredible. I am thinking of moving there."}
    ]
  }'
```

**Response:**

```json
{
  "memories_created": 4,
  "ids": ["mem_001", "mem_002", "mem_003", "mem_004"],
  "summary": "Stored: 2 episodic, 1 emotional, 1 semantic.",
  "memories": [
    {"id": "mem_001", "content": "User traveled to Japan for 2 weeks", "layer": "episodic", "type": "explicit", "confidence": 0.95},
    {"id": "mem_002", "content": "User visited Tokyo, Kyoto, Osaka, and Fukuoka", "layer": "episodic", "type": "explicit", "confidence": 0.92},
    {"id": "mem_003", "content": "User enjoyed ramen in Fukuoka", "layer": "emotional", "type": "implicit", "confidence": 0.85},
    {"id": "mem_004", "content": "User is considering relocating to Japan", "layer": "semantic", "type": "explicit", "confidence": 0.88}
  ]
}
```

**What the pipeline does:**
1. **Worthiness check** -- filters trivial messages ("ok", "thanks", etc.)
2. **Memory extraction** -- LLM extracts episodic, semantic, procedural, and emotional memories in parallel
3. **Classification** -- assigns layers, types, and confidence scores
4. **Enrichment** -- adds sentiment analysis, persona tags, metadata
5. **Parallel storage** -- writes to ChromaDB, TimescaleDB, PostgreSQL simultaneously

**When to use `/v1/store`:**
- Backfilling historical conversations
- When you want the LLM to figure out what's worth remembering
- Batch processing where latency doesn't matter

### Storage comparison

| | Orchestrator (recommended) | Direct | Store (legacy) |
|---|---|---|---|
| **Endpoint** | `POST /v1/orchestrator/message` | `POST /v1/memories/direct` | `POST /v1/store` |
| **Latency** | ~1-3s | <3s | 10-60s |
| **LLM extraction** | Yes (full pipeline) | No | Yes (full pipeline) |
| **Batching** | Adaptive throttling | N/A | None |
| **Also retrieves** | Yes (returns injections) | No | No |
| **Best for** | All use cases | Pre-formatted data | One-off backfill |

---

## 3. Retrieving Memories

Multiple retrieval endpoints serve different use cases. Start with basic retrieval and use the others when you need specialized data.

### Basic Retrieval

**`GET /v1/retrieve`**

Fast semantic search across all stored memories. This is your go-to for most use cases.

```bash
curl 'http://localhost:8080/v1/retrieve?user_id=user_123&query=cooking&limit=10'
```

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `user_id` | string | required | User identifier |
| `query` | string | optional | Search query (omit for all memories) |
| `layer` | string | optional | Filter: `short-term`, `semantic`, `episodic`, `long-term` |
| `type` | string | optional | Filter: `explicit` or `implicit` |
| `persona` | string | optional | Force persona: `finance`, `health`, `work`, etc. |
| `sort` | string | optional | `newest` or `oldest` (by timestamp) |
| `limit` | int | 50 | Results per page (max 1000) |
| `offset` | int | 0 | Pagination offset |

**Response:**

```json
{
  "results": [
    {
      "id": "mem_abc",
      "content": "User learned to make sourdough bread over 3 days",
      "layer": "episodic",
      "type": "explicit",
      "score": 0.94,
      "importance": 0.8,
      "persona_tags": ["cooking", "hobbies"],
      "metadata": {}
    }
  ],
  "pagination": {"limit": 10, "offset": 0, "total": 1},
  "finance": null
}
```

Queries with financial content automatically include portfolio data in the `finance` field.

---

### User Profile

**`GET /v1/profile`**

Returns a structured profile automatically extracted from conversations. Fields are organized into categories: `basics`, `preferences`, `goals`, `interests`, `background`.

```bash
# Full profile
curl 'http://localhost:8080/v1/profile?user_id=user_123'

# Single category
curl 'http://localhost:8080/v1/profile/basics?user_id=user_123'

# Completeness metrics
curl 'http://localhost:8080/v1/profile/completeness?user_id=user_123'
```

**Response (full profile):**

```json
{
  "user_id": "user_123",
  "completeness_pct": 42.86,
  "populated_fields": 9,
  "total_fields": 21,
  "profile": {
    "basics": {
      "name": {"value": "Sarah Martinez", "last_updated": "2025-11-17T10:30:45+00:00"},
      "age": {"value": 28, "last_updated": "2025-11-17T10:30:45+00:00"},
      "occupation": {"value": "software engineer", "last_updated": "2025-11-17T10:30:45+00:00"}
    },
    "preferences": {
      "communication_style": {"value": "direct", "last_updated": "2025-11-17T10:30:45+00:00"}
    },
    "goals": {},
    "interests": {},
    "background": {}
  }
}
```

Profiles are populated automatically during ingestion. You can also write fields manually:

```bash
curl -X PUT http://localhost:8080/v1/profile/basics/location \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "value": "San Francisco, CA"}'
```

---

### Portfolio

**`GET /v1/portfolio/summary`**

Structured financial holdings extracted from conversations.

```bash
curl 'http://localhost:8080/v1/portfolio/summary?user_id=user_123'
```

**Response:**

```json
{
  "user_id": "user_123",
  "holdings": [
    {"ticker": "NVDA", "shares": 50.0, "avg_price": 130.00, "asset_name": null, "first_acquired": null, "last_updated": null},
    {"ticker": "AAPL", "shares": 100.0, "avg_price": 175.00, "asset_name": null, "first_acquired": null, "last_updated": null}
  ],
  "total_holdings": 2
}
```

CRUD operations for holdings:

```bash
# Add holding
curl -X POST http://localhost:8080/v1/portfolio/holding \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "ticker": "TSLA", "shares": 25, "avg_price": 250.00}'

# Update holding
curl -X PUT http://localhost:8080/v1/portfolio/holding/TSLA \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "shares": 50}'

# Delete holding
curl -X DELETE 'http://localhost:8080/v1/portfolio/holding/TSLA?user_id=user_123'
```

---

### Structured Retrieval

**`POST /v1/retrieve/structured`**

Returns memories organized into categories by an LLM: `emotions`, `behaviors`, `personal`, `professional`, `habits`, `skills_tools`, `projects`, `relationships`, `learning_journal`, `finance`, `other`.

```bash
curl -X POST http://localhost:8080/v1/retrieve/structured \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_123", "query": "career and skills", "limit": 50}'
```

**Response (abbreviated):**

```json
{
  "professional": [
    {"id": "mem_001", "content": "User is a senior engineer at Stripe", "score": 0.95}
  ],
  "skills_tools": [
    {"id": "mem_002", "content": "User is learning Kubernetes", "score": 0.88}
  ],
  "learning_journal": [
    {"id": "mem_003", "content": "Started Rust last week, building a CLI tool", "score": 0.82}
  ],
  "emotions": [],
  "behaviors": [],
  "personal": [],
  "habits": [],
  "projects": [],
  "relationships": [],
  "other": [],
  "finance": null
}
```

---

### Narrative Construction

**`POST /v1/narrative`**

Generates a coherent story from memories using hybrid retrieval (ChromaDB + TimescaleDB + PostgreSQL). Useful for generating summaries, life timelines, or onboarding context.

```bash
curl -X POST http://localhost:8080/v1/narrative \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "query": "What happened this quarter?",
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-03-31T23:59:59Z",
    "limit": 25
  }'
```

**Response:**

```json
{
  "user_id": "user_123",
  "narrative": "In Q1 2025, the user transitioned into a senior role at Stripe, began learning Rust for a team CLI project, and traveled to Japan for two weeks...",
  "summary": "Key themes: career growth, travel, skill development",
  "sources": [
    {"id": "mem_001", "content": "Got promoted to senior engineer", "type": "episodic"},
    {"id": "mem_003", "content": "Started learning Rust", "type": "procedural"}
  ]
}
```

---

### Persona-Aware Retrieval

**`POST /v1/retrieve`** (POST variant)

Retrieves memories weighted by persona context. The system auto-detects or accepts a forced persona (e.g., `finance`, `health`, `work`) and adjusts scoring weights accordingly.

```bash
curl -X POST http://localhost:8080/v1/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "query": "How is my portfolio performing?",
    "persona_context": {"forced_persona": "finance"},
    "granularity": "episodic",
    "include_narrative": true,
    "explain": true,
    "limit": 10
  }'
```

**Response:**

```json
{
  "persona": {"selected": "finance", "confidence": 0.95},
  "results": {
    "granularity": "episodic",
    "memories": [
      {"id": "mem_005", "content": "Bought 50 shares of NVDA at $130", "score": 0.92}
    ],
    "narrative": "The user has been actively building a tech-focused portfolio..."
  },
  "explainability": {
    "weights": {"semantic": 0.4, "temporal": 0.2, "importance": 0.3, "emotional": 0.1},
    "source_links": [{"id": "mem_005", "score": 0.92}]
  }
}
```

---

## 4. Compaction & Maintenance

Memory compaction runs behind the scenes. The system automatically consolidates, decays, and archives memories to keep retrieval fast and relevant. You don't need to manage this, but you can trigger maintenance manually if needed:

```bash
# Trigger compaction for a specific user
curl -X POST 'http://localhost:8080/v1/maintenance/compact?user_id=user_123'

# Trigger compaction for all users
curl -X POST http://localhost:8080/v1/maintenance/compact_all \
  -H 'Content-Type: application/json' \
  -d '{}'

# Run specific maintenance jobs
curl -X POST http://localhost:8080/v1/maintenance \
  -H 'Content-Type: application/json' \
  -d '{
    "jobs": ["ttl_cleanup", "promotion", "compaction"],
    "since_hours": 24
  }'
```

**What compaction does:**
- Consolidates similar memories into summaries
- Applies decay factors to reduce stale memory relevance
- Promotes important short-term memories to long-term storage
- Archives old memories to keep the active set lean

To delete individual memories, use the direct deletion endpoint:

```bash
curl -X DELETE 'http://localhost:8080/v1/memories/mem_abc123?user_id=user_123'
```

> **Note:** The `POST /v1/forget` endpoint exists but is currently a stub (not yet implemented). It accepts `scopes` and `dry_run` but does not perform any actual deletion.

---

## 5. Full Integration Example

A complete Python integration showing the recommended pattern: orchestrator for storage, basic retrieval for context injection.

```python
import requests
from typing import Optional

class AgenticMemoryClient:
    """Minimal client for integrating Agentic Memories into any AI agent."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base = base_url
        self.session = requests.Session()

    # -- Storage (Orchestrator) --

    def store_message(self, user_id: str, conversation_id: str,
                      role: str, content: str, flush: bool = False):
        """Stream a conversation turn into memory."""
        return self.session.post(f"{self.base}/v1/orchestrator/message", json={
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "metadata": {"user_id": user_id},
            "flush": flush,
        }).json()

    def store_direct(self, user_id: str, content: str,
                     layer: str = "semantic", **kwargs):
        """Store a pre-formatted memory directly (no LLM extraction)."""
        return self.session.post(f"{self.base}/v1/memories/direct", json={
            "user_id": user_id,
            "content": content,
            "layer": layer,
            **kwargs,
        }).json()

    # -- Retrieval --

    def recall(self, user_id: str, query: str, limit: int = 5):
        """Retrieve relevant memories for a query."""
        return self.session.get(f"{self.base}/v1/retrieve", params={
            "user_id": user_id,
            "query": query,
            "limit": limit,
        }).json()

    def get_profile(self, user_id: str):
        """Get the user's extracted profile."""
        resp = self.session.get(f"{self.base}/v1/profile", params={"user_id": user_id})
        return resp.json() if resp.status_code == 200 else None

    def get_portfolio(self, user_id: str):
        """Get the user's portfolio holdings."""
        resp = self.session.get(f"{self.base}/v1/portfolio/summary", params={"user_id": user_id})
        return resp.json() if resp.status_code == 200 else None

    def get_structured(self, user_id: str, query: Optional[str] = None, limit: int = 50):
        """Get memories organized by category."""
        return self.session.post(f"{self.base}/v1/retrieve/structured", json={
            "user_id": user_id,
            "query": query,
            "limit": limit,
        }).json()

    # -- Deletion --

    def delete_memory(self, memory_id: str, user_id: str):
        """Delete a specific memory across all storage backends."""
        return self.session.delete(
            f"{self.base}/v1/memories/{memory_id}",
            params={"user_id": user_id},
        ).json()


# ---- Usage ----

memory = AgenticMemoryClient()
USER = "user_123"
CONV = "session-abc"

# Store both sides of the conversation
memory.store_message(USER, CONV, "user", "I just landed a new job at Google!")
memory.store_message(USER, CONV, "assistant", "Congratulations! What role?", flush=True)

# Later, retrieve context for a new conversation
results = memory.recall(USER, "career updates")
context = "\n".join(f"- {r['content']}" for r in results.get("results", []))

# Feed into your LLM
prompt = f"""You have these memories about the user:
{context}

User: How's everything going?
"""
```

---

## 6. Endpoint Reference Cheat Sheet

### Storage

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/v1/orchestrator/message` | POST | Stream chat turns (recommended) |
| `/v1/orchestrator/transcript` | POST | Replay a full transcript |
| `/v1/memories/direct` | POST | Store pre-formatted memories |
| `/v1/store` | POST | Legacy unthrottled ingestion (use orchestrator instead) |

### Retrieval

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/v1/retrieve` | GET | Semantic search (fast, primary) |
| `/v1/retrieve` | POST | Persona-aware retrieval |
| `/v1/retrieve/structured` | POST | Categorized memory view |
| `/v1/narrative` | POST | Story/timeline generation |
| `/v1/orchestrator/retrieve` | POST | Retrieve within orchestrator context |
| `/v1/profile` | GET | User profile data |
| `/v1/profile/{category}` | GET | Single profile category |
| `/v1/portfolio/summary` | GET | Financial holdings |

### Management

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/v1/memories/{id}` | DELETE | Delete a memory |
| `/v1/forget` | POST | Bulk forget by scope (stub — not yet implemented) |
| `/v1/maintenance` | POST | Trigger maintenance jobs |
| `/v1/maintenance/compact` | POST | Compact a user's memories |
| `/v1/profile/{cat}/{field}` | PUT | Update profile field |
| `/v1/portfolio/holding` | POST/PUT/DELETE | Manage holdings |

### System

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/health` | GET | Quick health check |
| `/health/full` | GET | All backend health |
| `/v1/me` | GET | Current user info |
| `/docs` | GET | Swagger UI |
