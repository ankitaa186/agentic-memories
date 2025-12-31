# API Contracts - Backend API (Server)

**Part:** Backend API (server)
**Technology:** Python 3.12+, FastAPI 0.111.0
**Base URL:** `http://localhost:8080`

---

## API Endpoints

### Memory Orchestrator APIs

#### POST /v1/orchestrator/message
**Description:** Stream a single chat message through the adaptive memory orchestrator
**Request:** `OrchestratorMessageRequest`
- `conversation_id`: string
- `message`: Message object with role and content
- `user_id`: string

**Response:** `OrchestratorStreamResponse`
- `injections`: Array of memory injections triggered by this message
- Injections include: memory_id, content, source, channel, score, metadata

**Features:**
- Turn-by-turn stateful retrieval
- Policy-gated memory injections
- Conversation-scoped delivery
- Duplicate suppression via cooldown

#### POST /v1/orchestrator/retrieve
**Description:** Query-only retrieval without ingesting a new turn
**Request:** `OrchestratorRetrieveRequest`
- `conversation_id`: string
- `query`: string
- `limit`: integer (optional)

**Response:** `OrchestratorRetrieveResponse`
- `injections`: Top memory injections for conversation/query

#### POST /v1/orchestrator/transcript
**Description:** Replay batch history through orchestrator
**Request:** `OrchestratorTranscriptResponse`
- `conversation_id`: string
- `history`: Array of messages
- `user_id`: string

**Response:** `OrchestratorTranscriptResponse`
- `injections`: All emitted memory injections from transcript replay

---

### Core Memory APIs

#### POST /v1/store
**Description:** Extract and store memories from conversation history
**Request:** `TranscriptRequest`
- `user_id`: string (required)
- `history`: Array of message objects with role and content

**Response:** `StoreResponse`
- `memories_created`: integer
- `ids`: Array of memory IDs
- `summary`: string
- `memories`: Array of stored memory objects

**Extraction Pipeline:**
1. Worthiness Check - Filters trivial messages
2. Memory Extraction - LLM extracts structured memories
3. Classification - Categorizes by type
4. Enrichment - Adds context from existing memories
5. Parallel Storage - Writes to all databases
6. Vector Embedding - Stores in ChromaDB

**Memory Types Extracted:**
- Episodic: Life events with temporal/spatial/emotional context
- Semantic: Facts, concepts, knowledge
- Procedural: Skills, habits, behaviors with progression
- Emotional: Mood states, patterns, trajectories
- Portfolio: Financial holdings, transactions, goals

#### GET /v1/retrieve
**Description:** Fast semantic search using ChromaDB
**Query Parameters:**
- `user_id`: string (required)
- `query`: string (optional - omit for all memories)
- `layer`: string (optional - short-term, semantic, episodic)
- `type`: string (optional - explicit, implicit)
- `limit`: integer (default: 10)
- `offset`: integer (default: 0)
- `persona`: string (optional - persona filter)

**Response:** `RetrieveResponse`
- `results`: Array of memory items with id, content, score, layer, metadata
- `finance`: Portfolio aggregate data (if applicable)

**Performance:** Sub-second queries (ChromaDB only)

#### POST /v1/retrieve
**Description:** Persona-aware retrieval with dynamic weighting
**Request:** `PersonaRetrieveRequest`
- `user_id`: string
- `query`: string
- `persona`: string (optional - auto-detected if not provided)
- `limit`: integer
- `include_narrative`: boolean
- `include_explainability`: boolean

**Response:** `PersonaRetrieveResponse`
- `persona_selection`: Selected persona with confidence
- `results`: PersonaRetrieveResults with raw/episodic/arc summaries
- `narrative`: Optional narrative construction
- `explainability`: Optional weight explanations and source links

**Features:**
- Automatic persona detection or explicit selection
- Profile-based weight overrides (semantic, temporal, importance, emotional)
- Multi-tier summaries
- Explainability for applied weights

#### POST /v1/retrieve/structured
**Description:** LLM-organized memory categorization
**Request:** `StructuredRetrieveRequest`
- `user_id`: string
- `query`: string
- `limit`: integer (default: 50)

**Response:** `StructuredRetrieveResponse`
Categories: emotions, behaviors, personal, professional, habits, skills_tools, projects, relationships, learning_journal, finance, other

---

### Advanced Memory APIs

#### POST /v1/narrative
**Description:** Generate coherent life stories using hybrid retrieval
**Request:** `NarrativeRequest`
- `user_id`: string
- `query`: string
- `start_time`: datetime (optional)
- `end_time`: datetime (optional)
- `limit`: integer (default: 25)

**Response:** `NarrativeResponse`
- `user_id`: string
- `narrative`: Generated narrative text
- `summary`: Key themes summary
- `sources`: Array of source memories

**Hybrid Retrieval Process:**
1. Semantic Search (ChromaDB) - Find relevant by meaning
2. Temporal Search (TimescaleDB) - Query time-range episodes
3. Procedural Search (PostgreSQL) - Fetch skill progressions
4. Deduplicate & Rank - Merge by relevance/recency/importance
5. LLM Generation - Weave into coherent narrative

**Performance:** 2-5 seconds (multi-database)

#### GET /v1/portfolio/summary
**Description:** Structured portfolio data from PostgreSQL
**Query Parameters:**
- `user_id`: string (required)

**Response:** `PortfolioSummaryResponse`
- `user_id`: string
- `holdings`: Array of portfolio holdings
  - ticker, shares, avg_price, position, intent
- `counts_by_asset_type`: Asset type aggregations
- `goals`: Array of financial goals

---

### Maintenance & Operations

#### POST /v1/forget
**Description:** Run memory compaction for a user
**Request:** `ForgetRequest`
- `user_id`: string

**Response:** Compaction statistics

**Features:**
- Graceful forgetting using Ebbinghaus curve
- Consolidation of memories
- Importance-based retention

#### POST /v1/maintenance
**Description:** Run maintenance tasks
**Request:** `MaintenanceRequest`
- `task`: string

**Response:** `MaintenanceResponse`
- `status`: string
- `details`: object

#### POST /v1/maintenance/compact_all
**Description:** Run compaction for all users
**Response:** `MaintenanceResponse`

---

### Health & Status

#### GET /health
**Description:** Basic health check
**Response:** Simple OK status

#### GET /health/full
**Description:** Comprehensive health check for all services
**Response:**
- `status`: ok/degraded/down
- `time`: Current timestamp
- `checks`: Object with status for each service
  - `env`: Environment variables check
  - `chroma`: ChromaDB connectivity
  - `timescale`: TimescaleDB connectivity
  - `redis`: Redis connectivity
  - `portfolio`: Portfolio service status
  - `langfuse`: Langfuse tracing status

#### GET /v1/me
**Description:** Get current user info/configuration
**Response:** User configuration details

---

## Authentication & Security

**Current Status:** Optional Cloudflare Access integration

**Headers:**
- `Cf-Access-Jwt-Assertion`: Cloudflare Access JWT token (if enabled)
- Standard CORS headers supported

**Middleware:**
- Request/response logging with latency tracking
- CORS middleware for cross-origin requests
- Error handling with structured responses

---

## Database Integration

**Write Strategy:** "Write Everywhere" - All memories written to multiple databases

| Database | Usage | Endpoints |
|----------|-------|-----------|
| **ChromaDB** | Vector embeddings, semantic search | All retrieval endpoints |
| **TimescaleDB** | Time-series episodic/emotional data | /v1/narrative, temporal queries |
| **PostgreSQL** | Structured procedural/portfolio data | /v1/portfolio/summary, skill queries |
| **Redis** | Short-term memory cache, activity tracking | Hot path caching, session data |

---

## LLM Integration

**Providers Supported:**
- OpenAI (GPT-4, GPT-4o)
- xAI (Grok)

**Models Used:**
- **Extraction:** GPT-4o (configurable via `EXTRACTION_MODEL`)
- **Embeddings:** text-embedding-3-large (3072 dimensions)

**Observability:** Full Langfuse integration for LLM tracing

---

## Rate Limits & Performance

**Performance Targets:**
- Simple retrieval (ChromaDB only): Sub-second
- Hybrid retrieval: 2-5 seconds
- Memory extraction: 3-10 seconds (depending on LLM)

**Connection Pooling:**
- PostgreSQL/TimescaleDB: psycopg connection pools
- ChromaDB: Persistent HTTP client
- Redis: Connection pooling

---

## Error Handling

**HTTP Status Codes:**
- `200 OK`: Successful request
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Authentication required (if Cloudflare Access enabled)
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

**Error Response Format:**
```json
{
  "detail": "Error message description"
}
```

---

## Scheduled Intents API (Epic 5 & 6)

API for managing proactive AI triggers. Used by Annie's proactive worker to schedule and execute user-defined alerts and check-ins.

### Intent CRUD

#### POST /v1/intents
**Description:** Create a new scheduled intent/trigger
**Request:** `ScheduledIntentCreate`
- `user_id`: string (required)
- `intent_name`: string (required)
- `trigger_type`: string (cron, interval, once, price, silence, portfolio)
- `trigger_schedule`: TriggerSchedule object (for time-based triggers)
- `trigger_condition`: TriggerCondition object (for condition-based triggers)
- `action_context`: string (briefing document for wake-up LLM)
- `action_priority`: string (low, normal, high, urgent)

**Response:** `ScheduledIntentResponse` with generated id, next_check

#### GET /v1/intents
**Description:** List intents for a user
**Query Parameters:**
- `user_id`: string (required)
- `trigger_type`: string (optional filter)
- `enabled`: boolean (optional filter)
- `limit`: integer (default: 50)
- `offset`: integer (default: 0)

**Response:** Array of `ScheduledIntentResponse`

#### GET /v1/intents/{id}
**Description:** Get a single intent by ID
**Response:** `ScheduledIntentResponse`

#### PUT /v1/intents/{id}
**Description:** Update an existing intent
**Request:** `ScheduledIntentUpdate` (partial update)
**Response:** `ScheduledIntentResponse`

#### DELETE /v1/intents/{id}
**Description:** Delete an intent
**Response:** 204 No Content

### Worker Endpoints

#### GET /v1/intents/pending
**Description:** Get intents due for execution (read-only query)
**Query Parameters:**
- `user_id`: string (optional - filter by user)
- `limit`: integer (optional - for batch processing)

**Response:** Array of `ScheduledIntentResponse` where `enabled=true` AND `next_check <= NOW()`

**Notes:**
- Excludes recently claimed intents (claimed_at > NOW() - 5 minutes)
- Excludes intents in cooldown (for condition triggers)
- Returns `in_cooldown` flag for transparency
- Read-only - does not modify any state

#### POST /v1/intents/{id}/claim
**Description:** Claim an intent for processing (prevents duplicate execution)
**Response:** `IntentClaimResponse`
- `intent`: Full intent data
- `claimed_at`: Timestamp when claimed

**Error Responses:**
- `404 Not Found`: Intent does not exist
- `409 Conflict`: Intent already claimed by another worker (within 5 min timeout)

**Multi-Worker Safety:**
- Uses `FOR UPDATE SKIP LOCKED` to prevent race conditions
- Claims expire after 5 minutes (for crashed worker recovery)
- Worker flow: `get_pending` → `claim` → process → `fire`

#### POST /v1/intents/{id}/fire
**Description:** Report execution result and update intent state
**Request:** `IntentFireRequest`
- `status`: string (success, failed, gate_blocked, condition_not_met, skipped)
- `message_id`: string (optional - Telegram message ID)
- `message_preview`: string (optional - first 100 chars)
- `trigger_data`: object (optional - price at fire time, etc.)
- `gate_result`: object (optional - subconscious gate details)
- `evaluation_ms`: integer (optional - condition eval time)
- `generation_ms`: integer (optional - LLM generation time)
- `delivery_ms`: integer (optional - message delivery time)
- `error_message`: string (optional - for failed status)

**Response:** `IntentFireResponse`
- `intent_id`: UUID
- `status`: string
- `next_check`: datetime (next scheduled check)
- `enabled`: boolean
- `execution_count`: integer
- `was_disabled_reason`: string (if auto-disabled)
- `cooldown_active`: boolean (if blocked by cooldown)
- `cooldown_remaining_hours`: float (if in cooldown)
- `last_condition_fire`: datetime (for condition triggers)

**Side Effects:**
- Clears `claimed_at` (releases claim)
- Updates `last_checked`, `last_executed`, `execution_count`
- Calculates and sets `next_check`
- Auto-disables if: once-trigger success, max_executions reached, expires_at passed
- Logs to `intent_executions` table for audit trail

#### GET /v1/intents/{id}/history
**Description:** Get execution history for an intent
**Query Parameters:**
- `limit`: integer (default: 50, max: 100)
- `offset`: integer (default: 0)

**Response:** Array of `IntentExecutionResponse` ordered by `executed_at DESC`

---

## Direct Memory API (Epic 10)

API for direct memory storage and deletion, bypassing the LLM extraction pipeline. Enables explicit memory management for AI assistants like Annie.

### POST /v1/memories/direct

**Description:** Store a pre-formatted memory directly into the memory system, bypassing LLM extraction.

**Performance Target:** < 3 seconds p95

**Request Body:** `DirectMemoryRequest`

**Required Fields:**
- `user_id`: string - User identifier for memory ownership
- `content`: string - Memory content text (max 5000 characters)

**Optional General Fields:**
- `layer`: string - Memory layer: `short-term`, `semantic` (default), `long-term`
- `type`: string - Memory type: `explicit` (default), `implicit`
- `importance`: float - Importance score 0.0-1.0 (default: 0.8)
- `confidence`: float - Confidence score 0.0-1.0 (default: 0.9)
- `persona_tags`: array[string] - Tags for memory categorization (max 10)
- `metadata`: object - Additional key-value metadata

**Optional Episodic Fields** (triggers episodic_memories table storage):
- `event_timestamp`: datetime - When the event occurred (ISO8601)
- `location`: string - Where the event occurred
- `participants`: array[string] - People involved
- `event_type`: string - Type of event (meeting, conversation, milestone)

**Optional Emotional Fields** (triggers emotional_memories table storage):
- `emotional_state`: string - Primary emotion (happy, anxious, excited)
- `valence`: float - Emotional valence -1.0 (negative) to 1.0 (positive)
- `arousal`: float - Emotional intensity 0.0 (calm) to 1.0 (intense)
- `trigger_event`: string - What triggered the emotional state

**Optional Procedural Fields** (triggers procedural_memories table storage):
- `skill_name`: string - Name of the skill or procedure
- `proficiency_level`: string - Level (beginner, intermediate, expert)

**Response:** `DirectMemoryResponse`
- `status`: string - `success` or `error`
- `memory_id`: string - UUID of stored memory (on success)
- `message`: string - Human-readable status message
- `storage`: object - Per-backend storage status
- `error_code`: string - Error code on failure (see Error Codes below)

**Example Request:**
```json
{
  "user_id": "user_12345",
  "content": "User mentioned they prefer morning meetings and work best between 9am-12pm.",
  "layer": "semantic",
  "type": "explicit",
  "importance": 0.8,
  "confidence": 0.9,
  "persona_tags": ["work", "preferences"],
  "metadata": {"source": "chat", "session_id": "abc123"}
}
```

**Example Response (Success):**
```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "stored_in_episodic": false,
    "stored_in_emotional": false,
    "stored_in_procedural": false
  }
}
```

**Example Request with Episodic Data:**
```json
{
  "user_id": "user_12345",
  "content": "Had a productive meeting with the engineering team about the Q1 roadmap.",
  "event_timestamp": "2025-01-15T10:30:00Z",
  "location": "Office conference room",
  "participants": ["Alice", "Bob"],
  "event_type": "meeting"
}
```

---

### DELETE /v1/memories/{memory_id}

**Description:** Delete a memory from all storage backends where it exists.

**Performance Target:** < 1 second p95

**Path Parameters:**
- `memory_id`: string - UUID of the memory to delete

**Query Parameters:**
- `user_id`: string (required) - User ID for authorization

**Response:** `DeleteMemoryResponse`
- `status`: string - `success` or `error`
- `deleted`: boolean - True if memory was deleted from at least one backend
- `memory_id`: string - The requested memory ID
- `storage`: object - Per-backend deletion status
- `message`: string - Status or error message

**Example Request:**
```http
DELETE /v1/memories/mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890?user_id=user_12345
```

**Example Response:**
```json
{
  "status": "success",
  "deleted": true,
  "memory_id": "mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "storage": {
    "chromadb": true,
    "episodic_memories": true,
    "emotional_memories": false,
    "procedural_memories": false
  },
  "message": "Memory deleted successfully from all backends"
}
```

---

### Direct Memory API Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed (invalid fields, missing required data, constraint violations) |
| `EMBEDDING_ERROR` | 500 | Failed to generate embedding vector for the content (OpenAI API issue) |
| `STORAGE_ERROR` | 500 | Database storage operation failed (ChromaDB or TimescaleDB write error) |
| `INTERNAL_ERROR` | 500 | Unexpected server error during processing |

**Error Response Format:**
```json
{
  "status": "error",
  "memory_id": null,
  "message": "Failed to generate embedding: OpenAI API rate limit exceeded",
  "storage": null,
  "error_code": "EMBEDDING_ERROR"
}
```

---

### Storage Routing Logic

The Direct Memory API routes memories to multiple backends based on the request fields:

1. **ChromaDB** (always): Every memory is stored in ChromaDB with its embedding vector for semantic search.

2. **episodic_memories** (conditional): Stored when `event_timestamp` is provided. Enables temporal queries and life event reconstruction.

3. **emotional_memories** (conditional): Stored when `emotional_state` is provided. Enables emotional pattern analysis and mood tracking.

4. **procedural_memories** (conditional): Stored when `skill_name` is provided. Enables skill progression tracking.

**Routing Diagram:**
```
DirectMemoryRequest
       │
       ▼
Always → ChromaDB (via upsert_memories)
       │
       ├── If event_timestamp → episodic_memories table
       ├── If emotional_state → emotional_memories table
       └── If skill_name → procedural_memories table
```

**Metadata Flags:**
The response `storage` object contains boolean flags indicating where the memory was stored:
- `chromadb`: Always true on success
- `stored_in_episodic`: True if stored in episodic_memories
- `stored_in_emotional`: True if stored in emotional_memories
- `stored_in_procedural`: True if stored in procedural_memories

---

## Scheduled Jobs

**Daily Compaction (Optional):**
- Schedule: 00:00 UTC daily
- Enabled via: `SCHEDULED_MAINTENANCE_ENABLED=true`
- Function: Runs memory compaction for all active users
- Activity Tracking: Uses Redis to track users from last 24h
