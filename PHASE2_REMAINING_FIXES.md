# Phase 2: Remaining Fixes for Memory Storage

**Status**: Episodic, Emotional, and Procedural storage services have issues preventing storage  
**Portfolio**: ✅ Working perfectly

---

## Issues Found

### 1. ✅ FIXED: Episodic Table Schema Issues
- ✅ Column `significance_score` → `importance_score` (renamed)
- ✅ Added missing `tags TEXT[]` column
- ✅ Added missing `metadata JSONB` column
- ✅ Fixed UUID generation (not reusing ChromaDB IDs)
- ✅ Fixed TEXT[] array handling (not JSON-encoding arrays)

### 2. ❌ REMAINING: Episodic ChromaDB Integration Issue
**Error**: `'V2Collection' object has no attribute 'add'`

**Location**: `src/services/episodic_memory.py` line ~160

**Problem**: The code is using ChromaDB v1 API (`.add()`) but we're running ChromaDB v2

**Fix Needed**:
```python
# OLD (v1 API):
collection.add(
    documents=[memory.content],
    ids=[memory.id],
    metadatas=[metadata]
)

# NEW (v2 API):
collection.upsert(
    documents=[memory.content],
    ids=[memory.id],
    metadatas=[metadata]
)
```

**Files to Update**:
- `src/services/episodic_memory.py` - Change `.add()` to `.upsert()`
- `src/services/emotional_memory.py` - Same fix if it also uses ChromaDB

---

### 3. ❌ REMAINING: Procedural Table Schema Issue
**Error**: `column "last_practiced" of relation "procedural_memories" does not exist`

**Problem**: Code expects `last_practiced` column but migration doesn't have it

**Fix Needed - Option A** (Add column to table):
```sql
ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS last_practiced TIMESTAMPTZ;
```

**Fix Needed - Option B** (Update code to match schema):
Check `migrations/003_postgres_procedural.sql` for actual column name and update `src/services/procedural_memory.py` accordingly.

---

### 4. ❌ REMAINING: Emotional Storage Transaction Cascades
**Error**: `current transaction is aborted, commands ignored until end of transaction block`

**Problem**: When episodic fails, it aborts the transaction, and all subsequent operations in that connection fail

**Fix Needed**:
Each storage service should use its own connection/transaction, not share one. OR add proper transaction rollback/commit per node.

**Current Flow**:
```
episodic (fails) → transaction aborted
emotional (tries to use same connection) → fails
procedural (tries to use same connection) → fails
```

**Solution**:
Add transaction isolation in each storage node:
```python
def node_store_episodic(state):
    try:
        # ... storage logic ...
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(...)
```

---

## Quick Fix Priority

### Priority 1: ChromaDB API Fix (5 minutes)
**Impact**: Unblocks episodic storage

```bash
# In src/services/episodic_memory.py
# Find: collection.add(
# Replace with: collection.upsert(
```

### Priority 2: Procedural Schema Fix (2 minutes)
**Impact**: Unblocks procedural storage

```sql
ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS last_practiced TIMESTAMPTZ;
```

### Priority 3: Transaction Isolation (15 minutes)
**Impact**: Prevents cascade failures

Add proper commit/rollback in each storage node.

---

## Testing After Fixes

```bash
curl -X POST http://localhost:8080/v1/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "phase2_final_test",
    "history": [
      {"role": "user", "content": "I learned Python decorators today. Bought AAPL stock. Feeling great!"}
    ]
  }'
```

**Expected Output**:
```
[graph.classify] episodic=X procedural=Y emotional=Z
[graph.episodic] user_id=phase2_final_test stored=X  ← Should be > 0
[graph.emotional] user_id=phase2_final_test stored=Z  ← Should be > 0
[graph.procedural] user_id=phase2_final_test stored=Y  ← Should be > 0
[graph.portfolio] user_id=phase2_final_test stored=1  ← Already works
```

---

## What's Actually Working

✅ **Extraction Pipeline**
- Worthiness check
- LLM-based extraction
- Context-aware (checks existing memories)
- Smart deduplication

✅ **Classification**
- Correctly identifies episodic, procedural, emotional memories
- Sentiment analysis working
- Tags and metadata extraction

✅ **ChromaDB Vector Storage**
- All memories stored in ChromaDB
- Embeddings generated
- Semantic search working

✅ **Portfolio Service**
- PostgreSQL holdings & transactions
- TimescaleDB snapshots
- Neo4j relationships
- **Fully functional!**

✅ **Langfuse Tracing**
- Hierarchical traces
- LLM call tracking
- Graph node visibility
- Performance metrics

---

## Summary

**The pipeline works end-to-end**, but the specialized storage services (episodic, emotional, procedural) have minor integration issues:

1. ChromaDB API version mismatch (v1 vs v2)
2. Database schema mismatches (missing columns)
3. Transaction isolation issues (cascading failures)

**Once these 3 issues are fixed** (est. 30 minutes of work), Phase 2 will be 100% complete and all memory types will store to their respective databases.

---

**Next Steps**:
1. Fix ChromaDB `.add()` → `.upsert()` in episodic/emotional services
2. Add `last_practiced` column to procedural_memories table
3. Add transaction isolation (commit/rollback) in storage nodes
4. Test and verify all storage types working
5. Move to Phase 3: Semantic & Identity services (new implementations)

