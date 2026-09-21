# Retrieval Data Flow Architecture

> Historical architecture snapshot. For current ordinary-query cosine ranking, procedural embedding caching, and deduplication behavior as of September 2026, see the [retrieval update notes](../recent-enhancements-2026-09.md#retrieval-relevance). Any distance conversion or weighted ordinary-query ranking below predates that update.

## Visual Data Flow Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                                │
│            GET /v1/retrieve?user_id=X&query=Y&limit=10              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RETRIEVAL PIPELINE                              │
│                   (src/services/retrieval.py)                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌───────────────┐             ┌────────────────┐
        │  REDIS CACHE  │             │  EMBEDDING     │
        │   (Optional)  │             │  GENERATION    │
        └───────┬───────┘             └────────┬───────┘
                │                              │
         Cache Hit? ────No───►                 │
                │                              │
                │ Yes                          ▼
                │                    ┌─────────────────────┐
                │                    │   CHROMADB QUERY    │
                │                    │  (Primary Source)   │
                │                    │                     │
                │                    │  Collection:        │
                │                    │  memories_3072      │
                │                    │                     │
                │                    │  Query Type:        │
                │                    │  - Semantic (vector)│
                │                    │  - Metadata filter  │
                │                    └──────────┬──────────┘
                │                              │
                │                              ▼
                │                  ┌────────────────────────┐
                │                  │   CHROMA RETURNS:      │
                │                  │   - IDs                │
                │                  │   - Content (text)     │
                │                  │   - Embeddings         │
                │                  │   - Metadata:          │
                │                  │     • user_id          │
                │                  │     • layer            │
                │                  │     • type             │
                │                  │     • tags             │
                │                  │     • timestamp        │
                │                  │     • confidence       │
                │                  │     • portfolio (JSON) │
                │                  │     • learning_journal │
                │                  └──────────┬─────────────┘
                │                             │
                └─────────────────────────────┤
                                              │
                                              ▼
                                ┌──────────────────────────┐
                                │  HYBRID SCORING          │
                                │  - Semantic: 80%         │
                                │  - Keyword: 20%          │
                                └──────────┬───────────────┘
                                           │
                                           ▼
                                ┌──────────────────────────┐
                                │  SORT & PAGINATE         │
                                │  - Sort by score DESC    │
                                │  - Apply offset/limit    │
                                └──────────┬───────────────┘
                                           │
                                           ▼
                        ┌──────────────────────────────────┐
                        │    PORTFOLIO ENRICHMENT          │
                        │    (src/app.py lines 531-594)    │
                        │                                  │
                        │  For each memory:                │
                        │  1. Parse metadata.portfolio     │
                        │  2. Extract:                     │
                        │     - ticker, shares, avg_price │
                        │     - position, intent           │
                        │     - time_horizon, target_price│
                        │  3. Build holdings array         │
                        │  4. Count by asset_type          │
                        │  5. Extract finance goals        │
                        └──────────┬───────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   BUILD RESPONSE         │
                        │   {                      │
                        │     results: [...],      │
                        │     pagination: {...},   │
                        │     finance: {           │
                        │       portfolio: {...},  │
                        │       goals: [...]       │
                        │     }                    │
                        │   }                      │
                        └──────────┬───────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   CACHE RESULT           │
                        │   (If short-term layer)  │
                        └──────────┬───────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   RETURN TO CLIENT       │
                        └──────────────────────────┘
```

## Data Sources by Type

### Primary Data Source: **ChromaDB** (Vector Store)
- **Collection**: `memories_3072`
- **Contains**:
  - ✅ All memory content (text)
  - ✅ Vector embeddings (3072-dim)
  - ✅ All metadata (as key-value pairs)
  - ✅ Portfolio data (embedded in metadata)
  - ✅ Tags, timestamps, confidence scores

### Secondary Sources: **NOT USED IN CURRENT RETRIEVAL**

❌ **TimescaleDB** (Episodic, Emotional)
- **Status**: Written to, but NOT read during retrieval
- **Contains**: Episodic events, emotional states
- **Usage**: Available for future time-series queries

❌ **PostgreSQL** (Procedural, Portfolio Holdings)
- **Status**: Written to, but NOT read during retrieval
- **Contains**: Skills, portfolio holdings, transactions
- **Usage**: Available for future structured queries

❌ **Neo4j** (Graph Relationships)
- **Status**: Written to, but NOT read during retrieval
- **Contains**: Skill prerequisites, holding correlations
- **Usage**: Available for future graph traversal

### Caching Layer: **Redis** (Optional)
- **When**: Only for `layer=short-term` queries
- **Duration**: Temporary (invalidated on new memories)
- **Benefit**: Faster repeat queries

## Detailed Flow Breakdown

### 1. Query Processing
```
User Request
  ↓
Parse Parameters:
  - user_id (required)
  - query (optional text)
  - layer filter (optional)
  - type filter (optional)
  - limit/offset
```

### 2. Cache Check (Optional)
```
IF filters.layer == "short-term" AND redis_available:
  cache_key = "mem:srch:{user_id}:{query_hash}:v{namespace}"
  ↓
  Check Redis
    ↓
    Hit? → Return cached results
    Miss? → Continue to ChromaDB
```

### 3. ChromaDB Query
```
Collection: memories_3072

Query Types:
┌────────────────────┬─────────────────────────────┐
│  Empty Query       │  Text Query                 │
├────────────────────┼─────────────────────────────┤
│  collection.get()  │  collection.query()         │
│  Metadata-only     │  Semantic vector search     │
│  No embedding      │  + Embedding generation     │
└────────────────────┴─────────────────────────────┘

Filters Applied:
  WHERE user_id = {user_id}
    AND layer = {layer} (if provided)
    AND type = {type} (if provided)

Returns:
  - ids: ["mem_abc123", ...]
  - documents: ["User attended...", ...]
  - metadatas: [{user_id, layer, tags, portfolio, ...}, ...]
  - distances: [0.23, 0.45, ...] (for semantic queries)
```

### 4. Scoring & Ranking
```
For each result:
  semantic_score = 1.0 - distance
  keyword_score = overlap(query_tokens, doc_tokens)
  final_score = 0.8 * semantic + 0.2 * keyword

Sort by final_score DESC
Apply pagination (offset, limit)
```

### 5. Portfolio Enrichment (In-Memory)
```python
# Extract from ChromaDB metadata (NOT from PostgreSQL!)
for memory in results:
    portfolio_data = memory.metadata.get('portfolio')
    if portfolio_data:
        # Parse JSON string to dict
        portfolio = json.loads(portfolio_data)
        
        # Extract holdings
        holdings.append({
            'ticker': portfolio['ticker'],
            'shares': portfolio['shares'],
            'avg_price': portfolio['avg_price'],
            'position': portfolio['position'],
            'intent': portfolio['intent'],
            ...
        })
```

**Key Point**: Portfolio data comes from **metadata stored in ChromaDB**, 
NOT from querying the `portfolio_holdings` table in PostgreSQL!

### 6. Response Assembly
```json
{
  "results": [
    {
      "id": "mem_xyz",
      "content": "User bought 100 shares of AAPL",
      "layer": "short-term",
      "score": 0.95,
      "metadata": {
        "portfolio": "{\"ticker\":\"AAPL\",\"shares\":100,...}"
      }
    }
  ],
  "finance": {
    "portfolio": {
      "user_id": "user123",
      "holdings": [
        {
          "ticker": "AAPL",
          "shares": 100,
          "avg_price": 175,
          ...
        }
      ],
      "counts_by_asset_type": {
        "public_equity": 1
      }
    },
    "goals": [...]
  }
}
```

## Key Insights

### 1. Single Source of Truth for Retrieval
**ChromaDB is the ONLY database queried during retrieval.**

All other databases (TimescaleDB, PostgreSQL, Neo4j) are:
- ✅ Written to during storage
- ❌ NOT read during retrieval
- 📊 Available for future analytics/specialized queries

### 2. Why This Architecture?

**Pros:**
- ⚡ Fast retrieval (single database query)
- 🎯 Semantic search with vector embeddings
- 💾 All necessary data in one place (metadata)
- 🔄 Simple data flow (no joins across databases)

**Cons:**
- 📉 Limited to what's in ChromaDB metadata
- 🚫 No time-series queries (TimescaleDB unused)
- 🚫 No graph traversal (Neo4j unused)
- 📊 Specialized databases underutilized

### 3. Portfolio Data Flow

```
Storage Time:
  Memory → Portfolio Service → PostgreSQL (portfolio_holdings)
                            → ChromaDB (metadata.portfolio)

Retrieval Time:
  ChromaDB (metadata.portfolio) → Parse JSON → Return to client
  
  PostgreSQL is NOT queried!
```

### 4. Future Enhancements

To leverage specialized databases:

```
┌─────────────────────────────────────────────────────┐
│  Enhanced Retrieval (Future)                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. ChromaDB (Semantic Search)                     │
│     ↓                                               │
│  2. TimescaleDB (Time-range filter)                │
│     ↓                                               │
│  3. PostgreSQL (Structured queries)                │
│     ↓                                               │
│  4. Neo4j (Relationship expansion)                 │
│     ↓                                               │
│  5. Merge & Rank                                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Summary

**Current Retrieval**: 100% ChromaDB
- Fast, simple, semantic-aware
- All metadata embedded in ChromaDB
- Other databases are "write-only" for now

**Data Enrichment**: In-memory processing
- Portfolio data from ChromaDB metadata (JSON)
- NOT from PostgreSQL tables
- Lightweight aggregation at response time

**Future**: Hybrid multi-database retrieval
- Leverage specialized databases for their strengths
- Time-series from TimescaleDB
- Structured queries from PostgreSQL
- Graph traversal from Neo4j
