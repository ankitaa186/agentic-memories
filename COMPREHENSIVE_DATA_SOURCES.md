# Comprehensive Data Sources Analysis
**All API Endpoints - Complete Data Flow Map**

## Executive Summary

The system uses a **hybrid architecture** with different data sources for different endpoints:
- **Simple retrieval**: ChromaDB only (fast, semantic)
- **Complex retrieval**: Multi-database (ChromaDB + TimescaleDB + PostgreSQL)
- **Portfolio queries**: PostgreSQL primary, ChromaDB fallback
- **Narrative**: Depends on hybrid retrieval (can use all databases)

---

## Complete Endpoint Analysis

### 1. `/v1/retrieve` (GET) - Simple Memory Retrieval ⚡

**Purpose**: Fast semantic memory search

**Data Sources**:
```
PRIMARY: ChromaDB (100%)
  └─ Collection: memories_3072
     ├─ All memory content
     ├─ All metadata
     └─ Portfolio data (in metadata)

OPTIONAL: Redis Cache
  └─ For short-term layer queries
```

**Database Usage**:
| Database | Read | Write | Status |
|----------|------|-------|--------|
| ChromaDB | ✅ Yes | ❌ No | PRIMARY |
| Redis | ✅ Cache | ❌ No | OPTIONAL |
| TimescaleDB | ❌ No | ❌ No | UNUSED |
| PostgreSQL | ❌ No | ❌ No | UNUSED |
| Neo4j | ❌ No | ❌ No | UNUSED |

**Flow**:
```
Request → Redis Cache Check → ChromaDB Query → Score & Rank → Return
                ↓ miss
            (semantic search)
```

---

### 2. `/v1/retrieve/structured` (POST) - LLM-Organized Retrieval 🧠

**Purpose**: AI-categorized memory organization

**Data Sources**:
```
PRIMARY: ChromaDB (100%)
  └─ Fetches ALL user memories
  └─ LLM categorizes into buckets:
     - emotions, behaviors, personal
     - professional, habits, skills
     - projects, relationships, finance
```

**Database Usage**: Same as `/v1/retrieve`

**Flow**:
```
Request → ChromaDB (fetch all) → LLM Categorization → Structured Response
```

---

### 3. `/v1/narrative` (POST) - Story Generation 📖

**Purpose**: Generate coherent narrative from memories

**Data Sources**: **MULTI-DATABASE** (via Hybrid Retrieval)

```
HYBRID RETRIEVAL STRATEGY:
  ├─ ChromaDB (Semantic Search)
  │  └─ Query: collection.query(embeddings, n_results=20)
  │
  ├─ TimescaleDB (Temporal Search) ⭐ USED!
  │  ├─ episodic_memories (time range query)
  │  └─ emotional_memories (time range query)
  │
  └─ PostgreSQL (Procedural Search) ⭐ USED!
     └─ procedural_memories (skill queries)
```

**Database Usage**:
| Database | Read | Write | Status |
|----------|------|-------|--------|
| ChromaDB | ✅ Yes | ❌ No | PRIMARY (semantic) |
| TimescaleDB | ✅ Yes | ❌ No | **TIME-RANGE** |
| PostgreSQL | ✅ Yes | ❌ No | **PROCEDURAL** |
| Redis | ❌ No | ❌ No | UNUSED |
| Neo4j | ❌ No | ❌ No | UNUSED |

**Detailed Flow**:

```
┌────────────────────────────────────────────────────────────────┐
│  /v1/narrative Request                                         │
│  { user_id, query, time_range?, limit }                       │
└───────────────────┬────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────┐
│  HybridRetrievalService.retrieve_memories()                    │
└────────────────────┬───────────────────────────────────────────┘
                     │
    ┌────────────────┴────────────────────────┐
    │                                         │
    ▼                                         ▼
┌─────────────────────┐              ┌──────────────────────────┐
│ IF query_text:      │              │ IF time_range:           │
│  _semantic_         │              │  _temporal_retrieval()   │
│   retrieval()       │              │                          │
│                     │              │  TimescaleDB:            │
│  ChromaDB:          │              │  ├─ episodic_memories    │
│  └─ memories_3072   │              │  │  WHERE timestamp      │
│     (vector search) │              │  │  BETWEEN start & end  │
│                     │              │  │                       │
│  Returns:           │              │  └─ emotional_memories   │
│  - RetrievalResult[]│              │     WHERE timestamp      │
│    with semantic    │              │     BETWEEN start & end  │
│    similarity       │              │                          │
└─────────────────────┘              │  Returns:                │
                                     │  - RetrievalResult[]     │
                                     │    with temporal         │
                                     │    relevance scores      │
                                     └──────────────────────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        │
                        ▼
              ┌──────────────────────────┐
              │ IF procedural requested: │
              │  _procedural_retrieval() │
              │                          │
              │  PostgreSQL:             │
              │  └─ procedural_memories  │
              │     (skill queries)      │
              │                          │
              │  Returns:                │
              │  - RetrievalResult[]     │
              │    with skill matches    │
              └──────────┬───────────────┘
                         │
                         ▼
              ┌─────────────────────────┐
              │  Deduplicate & Rank     │
              │  - Merge all results    │
              │  - Remove duplicates    │
              │  - Rank by:             │
              │    • Relevance          │
              │    • Recency            │
              │    • Importance         │
              └──────────┬──────────────┘
                         │
                         ▼
              ┌─────────────────────────┐
              │  LLM Narrative          │
              │  Generation             │
              │  - Weave into story     │
              │  - Maintain timeline    │
              │  - Preserve facts       │
              └──────────┬──────────────┘
                         │
                         ▼
              ┌─────────────────────────┐
              │  Return Narrative       │
              │  + Source Citations     │
              └─────────────────────────┘
```

**Key Insight**: Narrative is the **ONLY endpoint** that actually queries TimescaleDB and PostgreSQL during retrieval!

---

### 4. `/v1/portfolio/summary` (GET) - Portfolio Dashboard 💼

**Purpose**: Fetch user's complete portfolio holdings

**Data Sources**: **POSTGRESQL PRIMARY** with ChromaDB fallback

```
PRIMARY: PostgreSQL
  └─ portfolio_holdings table
     ├─ ticker, shares, avg_price
     ├─ position, intent, time_horizon
     └─ All financial metadata

FALLBACK: ChromaDB
  └─ metadata.portfolio (if PostgreSQL fails)
```

**Database Usage**:
| Database | Read | Write | Status |
|----------|------|-------|--------|
| PostgreSQL | ✅ Yes | ❌ No | **PRIMARY** ⭐ |
| ChromaDB | ✅ Fallback | ❌ No | BACKUP |
| TimescaleDB | ❌ No | ❌ No | UNUSED |
| Redis | ❌ No | ❌ No | UNUSED |
| Neo4j | ❌ No | ❌ No | UNUSED |

**Flow**:
```
Request
  ↓
Try: PostgreSQL Query
  SELECT * FROM portfolio_holdings WHERE user_id = ?
  ↓
Success? → Format & Return
  ↓
Failed? → FALLBACK to ChromaDB
  ↓
Parse metadata.portfolio from all memories → Aggregate → Return
```

**SQL Query**:
```sql
SELECT * FROM portfolio_holdings
WHERE user_id = %s
ORDER BY last_updated DESC
```

---

### 5. `/health/full` (GET) - System Health Check 🏥

**Purpose**: Verify all database connections

**Data Sources**: **ALL DATABASES** (ping only, no data fetch)

```
Checks:
  ├─ ChromaDB → heartbeat
  ├─ TimescaleDB → SELECT 1
  ├─ Neo4j → session.run("RETURN 1")
  ├─ Redis → ping
  ├─ PostgreSQL (portfolio) → SELECT COUNT(*) FROM portfolio_holdings
  └─ Langfuse → API connectivity
```

**Database Usage**:
| Database | Read | Write | Status |
|----------|------|-------|--------|
| ChromaDB | ✅ Ping | ❌ No | HEALTH CHECK |
| TimescaleDB | ✅ Ping | ❌ No | HEALTH CHECK |
| PostgreSQL | ✅ Count | ❌ No | HEALTH CHECK |
| Redis | ✅ Ping | ❌ No | HEALTH CHECK |
| Neo4j | ✅ Ping | ❌ No | HEALTH CHECK |
| Langfuse | ✅ Ping | ❌ No | HEALTH CHECK |

---

## Data Source Summary by Endpoint

### Quick Reference Table

| Endpoint | ChromaDB | TimescaleDB | PostgreSQL | Neo4j | Redis |
|----------|----------|-------------|------------|-------|-------|
| `/v1/retrieve` | ✅ PRIMARY | ❌ | ❌ | ❌ | 🔶 Cache |
| `/v1/retrieve/structured` | ✅ PRIMARY | ❌ | ❌ | ❌ | ❌ |
| `/v1/narrative` | ✅ Semantic | ✅ Temporal | ✅ Procedural | ❌ | ❌ |
| `/v1/portfolio/summary` | 🔶 Fallback | ❌ | ✅ PRIMARY | ❌ | ❌ |
| `/health/full` | ✅ Ping | ✅ Ping | ✅ Ping | ✅ Ping | ✅ Ping |
| `/v1/store` | ✅ Write | ✅ Write | ✅ Write | ✅ Write | ❌ |

**Legend**:
- ✅ **Active Use** - Database is queried/written
- 🔶 **Conditional** - Used in specific scenarios
- ❌ **Unused** - Database not accessed

---

## Hybrid Retrieval Deep Dive

### When TimescaleDB is Actually Used

**Endpoint**: `/v1/narrative` (only!)

**Conditions**:
```python
if time_range:  # User provides start_time and end_time
    # Query TimescaleDB for temporal data
    
    # Episodic memories within time range
    SELECT id, content, event_timestamp, importance_score
    FROM episodic_memories
    WHERE user_id = ? AND event_timestamp BETWEEN ? AND ?
    
    # Emotional states within time range
    SELECT id, context, timestamp, valence, arousal
    FROM emotional_memories
    WHERE user_id = ? AND timestamp BETWEEN ? AND ?
```

**Example Request**:
```json
POST /v1/narrative
{
  "user_id": "user_123",
  "query": "What happened in Q1?",
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2025-03-31T23:59:59Z"
}
```
**Result**: Queries TimescaleDB for time-series data ✅

---

### When PostgreSQL is Actually Used

**Endpoint 1**: `/v1/narrative` (conditional)

**Conditions**:
```python
# Always runs (unless filtered out)
# Retrieves procedural memories (skills)
SELECT id, skill_name, proficiency_level, context
FROM procedural_memories
WHERE user_id = ?
```

**Endpoint 2**: `/v1/portfolio/summary` (always)

**Conditions**:
```python
# Always runs (primary data source)
SELECT * FROM portfolio_holdings
WHERE user_id = ?
ORDER BY last_updated DESC
```

---

## Architecture Insights

### 1. Storage vs Retrieval Pattern

```
┌─────────────────────────────────────────────────────────┐
│  STORAGE PHASE (/v1/store)                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Memory → Unified Graph → WRITE to ALL databases:      │
│                                                         │
│    ✅ ChromaDB (for retrieval)                         │
│    ✅ TimescaleDB (for time-series analytics)          │
│    ✅ PostgreSQL (for structured queries)              │
│    ✅ Neo4j (for graph relationships)                  │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  RETRIEVAL PHASE (various endpoints)                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Simple Queries (/v1/retrieve):                        │
│    └─ READ from ChromaDB only                          │
│                                                         │
│  Complex Queries (/v1/narrative):                      │
│    ├─ READ from ChromaDB (semantic)                    │
│    ├─ READ from TimescaleDB (temporal)                 │
│    └─ READ from PostgreSQL (procedural)                │
│                                                         │
│  Portfolio Queries (/v1/portfolio/summary):            │
│    ├─ READ from PostgreSQL (primary)                   │
│    └─ FALLBACK to ChromaDB                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2. Why This Architecture?

**Design Philosophy**: Write Everywhere, Read Selectively

**Benefits**:
- ✅ **Performance**: Fast simple queries (ChromaDB only)
- ✅ **Flexibility**: Complex queries available when needed
- ✅ **Resilience**: Multiple copies of data
- ✅ **Future-proof**: Data ready for analytics/graph queries

**Trade-offs**:
- ⚠️ **Storage overhead**: Data duplicated across databases
- ⚠️ **Consistency**: Must keep all databases in sync
- ⚠️ **Complexity**: More databases to manage

### 3. Database Utilization

```
Write Utilization (Storage):
  ChromaDB:     ████████████ 100%
  TimescaleDB:  ████████████ 100%
  PostgreSQL:   ████████████ 100%
  Neo4j:        ████████████ 100%

Read Utilization (Retrieval):
  ChromaDB:     ████████████ 100% (all endpoints)
  TimescaleDB:  ██░░░░░░░░░░  20% (only /v1/narrative with time_range)
  PostgreSQL:   ████░░░░░░░░  40% (/v1/narrative + /v1/portfolio/summary)
  Neo4j:        ░░░░░░░░░░░░   0% (not yet used in retrieval)
  Redis:        █░░░░░░░░░░░  10% (cache for short-term layer)
```

**Underutilized Databases**:
- ❌ **Neo4j**: Written to, never read (0% utilization)
- 🟡 **TimescaleDB**: Rarely read (20% utilization)

---

## Query Patterns by Use Case

### Use Case 1: "Show me my recent memories"
```
Endpoint: GET /v1/retrieve?user_id=X&limit=10
Data Source: ChromaDB only
Query Type: Metadata-only fetch
Performance: ⚡ Very Fast
```

### Use Case 2: "What did I do last quarter?"
```
Endpoint: POST /v1/narrative
  { "user_id": "X", "start_time": "...", "end_time": "..." }
Data Sources: 
  - ChromaDB (semantic context)
  - TimescaleDB (episodic + emotional in time range)
  - PostgreSQL (procedural/skills)
Query Type: Multi-database hybrid
Performance: 🐢 Slower (3 databases)
```

### Use Case 3: "Show my portfolio"
```
Endpoint: GET /v1/portfolio/summary?user_id=X
Data Source: PostgreSQL primary (ChromaDB fallback)
Query Type: Structured SQL
Performance: ⚡ Fast
```

### Use Case 4: "What stocks do I own based on memories?"
```
Endpoint: GET /v1/retrieve?user_id=X&query=stocks
Data Source: ChromaDB (metadata.portfolio)
Query Type: Semantic + metadata parsing
Performance: ⚡ Fast (but limited)
```

---

## Future Enhancements

### 1. Enable Neo4j Retrieval
```python
# Add to HybridRetrievalService
def _graph_retrieval(self, query: RetrievalQuery):
    """Traverse skill prerequisites and portfolio correlations"""
    # Query Neo4j for:
    # - Skill dependency chains
    # - Asset correlation networks
    # - Learning path recommendations
```

### 2. Optimize Database Selection
```python
# Smart routing based on query type
def choose_retrieval_strategy(query):
    if has_time_range(query):
        return "timescale"  # Time-series optimized
    elif has_semantic_query(query):
        return "chromadb"   # Vector search
    elif has_structured_filters(query):
        return "postgres"   # SQL optimized
    elif has_relationship_query(query):
        return "neo4j"      # Graph traversal
```

### 3. Consolidate Duplicate Data
```python
# Reduce storage overhead
# Option: Store only references in ChromaDB
{
  "id": "mem_123",
  "content": "...",
  "metadata": {
    "portfolio_id": "holding_456",  # Reference, not full data
    "episodic_id": "episode_789"    # Reference, not full data
  }
}
```

---

## Summary: Complete Data Flow Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴────────────────┐
            │                                │
            ▼                                ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Simple Queries  │          │  Complex Queries │
    │  (/v1/retrieve)  │          │  (/v1/narrative) │
    └────────┬─────────┘          └────────┬─────────┘
             │                              │
             │                    ┌─────────┴─────────┐
             │                    │                   │
             ▼                    ▼                   ▼
    ┌─────────────┐     ┌──────────────┐   ┌──────────────┐
    │  ChromaDB   │     │  ChromaDB    │   │ TimescaleDB  │
    │  (vector)   │     │  (semantic)  │   │ (temporal)   │
    └─────────────┘     └──────────────┘   └──────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ PostgreSQL   │
                        │ (procedural) │
                        └──────────────┘

    ┌──────────────────┐
    │ Portfolio Query  │
    │ (/v1/portfolio)  │
    └────────┬─────────┘
             │
             ├─ Try: PostgreSQL (primary)
             │
             └─ Fallback: ChromaDB
```

---

## Key Takeaways

1. **ChromaDB is universal**: Used by ALL retrieval endpoints
2. **TimescaleDB is specialized**: Only used for time-range queries in narratives
3. **PostgreSQL has dual use**: Procedural queries + portfolio primary storage
4. **Neo4j is dormant**: Written to but never read (yet)
5. **Redis is minimal**: Only caches short-term layer queries

**Architecture Grade**: 🎯 **Good for MVP, needs optimization for scale**
- Simple queries are fast ✅
- Complex queries available ✅
- Some databases underutilized ⚠️
- Data redundancy high ⚠️

