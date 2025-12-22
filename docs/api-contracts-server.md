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

## Scheduled Jobs

**Daily Compaction (Optional):**
- Schedule: 00:00 UTC daily
- Enabled via: `SCHEDULED_MAINTENANCE_ENABLED=true`
- Function: Runs memory compaction for all active users
- Activity Tracking: Uses Redis to track users from last 24h
