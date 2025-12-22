# Data Models - Backend API (Server)

**Part:** Backend API (server)
**Database Strategy:** Polyglot Persistence - "Write Everywhere, Read Selectively"

---

## Database Architecture

### Storage Distribution

| Database | Tables | Primary Use | Read Pattern |
|----------|--------|-------------|--------------|
| **TimescaleDB** | 3 tables | Time-series data | Temporal queries |
| **PostgreSQL** | 8 tables | Structured data | Procedural, portfolio, semantic |
| **ChromaDB** | 1 collection | Vector embeddings | All retrieval (semantic search) |
| **Redis** | Key-value cache | Hot cache, short-term layer | Transient memories, session data |

---

## TimescaleDB Tables (Time-Series)

### episodic_memories (Hypertable)
**Purpose:** Life events with temporal, spatial, and emotional context

**Schema:**
```sql
CREATE TABLE episodic_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT,
    content TEXT NOT NULL,
    location JSONB,
    participants TEXT[],
    emotional_valence FLOAT,  -- Range: -1 to 1
    emotional_arousal FLOAT,  -- Range: 0 to 1
    importance_score FLOAT,
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converted to hypertable for time-series optimization
SELECT create_hypertable('episodic_memories', 'event_timestamp');
```

**Key Fields:**
- `event_timestamp`: When the event occurred (hypertable partition key)
- `emotional_valence`: Positive (+1) to negative (-1) emotional tone
- `emotional_arousal`: Low (0) to high (1) emotional intensity
- `location`: JSONB with spatial data (place names, coordinates)
- `participants`: Array of people involved in the event
- `importance_score`: Calculated importance for retention/consolidation

**Indexes:**
- Primary key on `id`
- Time-based partitioning on `event_timestamp`
- Index on `user_id` for user-specific queries

---

### emotional_memories (Hypertable)
**Purpose:** Mood states, emotional patterns, and trajectories over time

**Schema:**
```sql
CREATE TABLE emotional_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    emotional_state VARCHAR(64),
    valence FLOAT,      -- Range: -1 to 1
    arousal FLOAT,      -- Range: 0 to 1
    dominance FLOAT,    -- Range: 0 to 1
    context TEXT,
    trigger_event TEXT,
    intensity FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('emotional_memories', 'timestamp');
```

**Key Fields:**
- `timestamp`: When the emotional state was recorded
- `emotional_state`: Named emotion (happy, sad, anxious, excited, etc.)
- `valence`: Pleasant (+1) to unpleasant (-1)
- `arousal`: Calm (0) to excited (1)
- `dominance`: Submissive (0) to dominant (1)
- `trigger_event`: What caused this emotional state
- `intensity`: Strength of the emotion

**Use Cases:**
- Emotional pattern detection
- Mood tracking over time
- Trigger identification
- Emotional trend analysis

---

### portfolio_snapshots (Hypertable)
**Purpose:** Point-in-time snapshots of portfolio state for historical tracking

**Schema:**
```sql
CREATE TABLE portfolio_snapshots (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    snapshot_timestamp TIMESTAMPTZ NOT NULL,
    total_value NUMERIC,
    holdings_snapshot JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('portfolio_snapshots', 'snapshot_timestamp');
```

**Key Fields:**
- `snapshot_timestamp`: When this snapshot was taken
- `total_value`: Total portfolio value at this point
- `holdings_snapshot`: Complete holdings state as JSONB

---

## PostgreSQL Tables (Structured Data)

### procedural_memories
**Purpose:** Skills, habits, and learned behaviors with progression tracking

**Schema:**
```sql
CREATE TABLE procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    proficiency_level VARCHAR(32),  -- beginner, intermediate, advanced, expert
    steps JSONB,
    prerequisites JSONB,
    last_practiced TIMESTAMPTZ,
    practice_count INT DEFAULT 0,
    success_rate FLOAT,
    context TEXT,
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Proficiency Levels:**
- `beginner`: Just learning
- `intermediate`: Developing competency
- `advanced`: Highly skilled
- `expert`: Mastery level

**Key Fields:**
- `steps`: JSONB array of procedural steps
- `prerequisites`: Required skills/knowledge
- `practice_count`: Number of times practiced
- `success_rate`: 0.0 to 1.0 success ratio

---

### skill_progressions
**Purpose:** Track skill development over time

**Schema:**
```sql
CREATE TABLE skill_progressions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    from_level VARCHAR(32),
    to_level VARCHAR(32),
    progression_date TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    metadata JSONB
);
```

---

### semantic_memories
**Purpose:** Facts, concepts, and declarative knowledge without temporal context

**Schema:**
```sql
CREATE TABLE semantic_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    fact TEXT NOT NULL,
    category VARCHAR(64),
    confidence_score FLOAT,
    source TEXT,
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key Fields:**
- `fact`: The factual statement or knowledge
- `category`: Type of knowledge (preferences, facts, etc.)
- `confidence_score`: How certain we are (0.0 to 1.0)
- `source`: Where this knowledge came from

---

### identity_memories
**Purpose:** Core values, beliefs, and self-concept

**Schema:**
```sql
CREATE TABLE identity_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    aspect VARCHAR(64),      -- values, beliefs, goals, personality
    content TEXT NOT NULL,
    importance FLOAT,
    stability FLOAT,         -- How unchanging this aspect is
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Identity Aspects:**
- `values`: Core values and principles
- `beliefs`: Worldview and convictions
- `goals`: Long-term aspirations
- `personality`: Personality traits and characteristics

---

### portfolio_holdings
**Purpose:** Current financial holdings and positions

**Schema:**
```sql
CREATE TABLE portfolio_holdings (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    ticker VARCHAR(16),
    asset_name VARCHAR(256),
    asset_type VARCHAR(64),   -- public_equity, crypto, private_equity, etc.
    shares FLOAT,
    avg_price FLOAT,
    position VARCHAR(16),     -- long, short
    intent VARCHAR(16),       -- buy, sell, hold, watch
    time_horizon VARCHAR(16), -- short, medium, long
    source_memory_id VARCHAR(128),
    first_acquired TIMESTAMPTZ,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);
```

**Asset Types:**
- `public_equity`: Stocks
- `crypto`: Cryptocurrencies
- `private_equity`: Private company shares
- `bonds`: Fixed income
- `real_estate`: Property holdings
- `commodities`: Gold, oil, etc.

**Intent Types:**
- `buy`: Planning to acquire more
- `sell`: Planning to sell
- `hold`: Maintaining position
- `watch`: Monitoring but not held

---

### portfolio_transactions
**Purpose:** Historical transactions and trades

**Schema:**
```sql
CREATE TABLE portfolio_transactions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    ticker VARCHAR(16),
    transaction_type VARCHAR(16),  -- buy, sell, dividend, split
    shares FLOAT,
    price FLOAT,
    transaction_date TIMESTAMPTZ NOT NULL,
    source_memory_id VARCHAR(128),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### portfolio_preferences
**Purpose:** Investment goals, risk tolerance, and preferences

**Schema:**
```sql
CREATE TABLE portfolio_preferences (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    preference_type VARCHAR(64),  -- risk_tolerance, investment_goal, etc.
    value TEXT,
    priority INT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### emotional_patterns
**Purpose:** Detected emotional patterns and trends

**Schema:**
```sql
CREATE TABLE emotional_patterns (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    pattern_type VARCHAR(64),  -- recurring, trigger-based, seasonal
    description TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    confidence FLOAT,
    supporting_memories JSONB,
    metadata JSONB
);
```

---

## ChromaDB Collections

### memories_3072
**Purpose:** Vector embeddings for semantic search

**Configuration:**
- **Embedding Model:** text-embedding-3-large (OpenAI)
- **Dimensions:** 3072
- **Distance Metric:** Cosine similarity
- **Tenant:** agentic-memories
- **Database:** memories

**Document Structure:**
```json
{
  "id": "mem_uuid",
  "embedding": [3072-dimensional vector],
  "document": "Memory content text",
  "metadata": {
    "user_id": "user_123",
    "layer": "short-term|semantic|episodic",
    "type": "explicit|implicit",
    "timestamp": "ISO datetime",
    "emotional_valence": -1 to 1,
    "importance": 0 to 1,
    "episodic": "{json_data}",  // If episodic memory
    "portfolio": "{json_data}"  // If portfolio memory
  }
}
```

**Search Capabilities:**
- Semantic similarity search
- Metadata filtering (user_id, layer, type)
- Hybrid queries combining vector + metadata filters

---

## Redis Key Patterns

### Short-Term Memory
```
memory:short-term:{user_id}:{memory_id}
TTL: 3600 seconds (1 hour)
Value: JSON memory object
```

### User Activity Tracking
```
recent_users:{YYYYMMDD}
Type: SET
Members: user_ids who were active that day
Used for: Daily compaction job targeting
```

### Session Data
```
session:{user_id}
TTL: Variable
Value: JSON session state
```

---

## Data Relationships

### Memory Type Flow

```
User Message
    ↓
Extraction Pipeline (LangGraph)
    ↓
├─→ Episodic Memory → TimescaleDB + ChromaDB
├─→ Semantic Memory → PostgreSQL + ChromaDB
├─→ Procedural Memory → PostgreSQL + ChromaDB
├─→ Emotional Memory → TimescaleDB + ChromaDB
├─→ Portfolio Memory → PostgreSQL (holdings/transactions) + TimescaleDB (snapshots) + ChromaDB
└─→ Short-term Memory → Redis + ChromaDB
```

### Retrieval Strategy

**Simple Retrieval:**
- ChromaDB only
- Fast (<1 second)
- Semantic search via embeddings

**Hybrid Retrieval:**
- ChromaDB (semantic) + TimescaleDB (temporal) + PostgreSQL (structured)
- Comprehensive (2-5 seconds)
- Multi-database queries merged and ranked

---

## Migration System

**Migration Files Located:** `/migrations/`

**Database Types:**
- `postgres/` - PostgreSQL schema migrations
- `timescaledb/` - TimescaleDB hypertable migrations
- `chromadb/` - Collection creation (Python-based)

**Migration Tool:** `migrations/migrate.sh`

**Features:**
- Up/down migrations with rollback support
- Dry-run mode
- Migration locking
- History tracking
- Validation

---

## Data Validation

**Pydantic Models (src/models.py, src/schemas.py):**
- Strict type validation
- Request/response schemas
- Automatic OpenAPI documentation
- Field constraints and defaults

---

## Observability

**Langfuse Integration:**
- LLM call tracing
- Extraction pipeline monitoring
- Token usage tracking
- Error logging

**Database Monitoring:**
- Connection pool metrics
- Query performance logging
- Health checks for all databases
