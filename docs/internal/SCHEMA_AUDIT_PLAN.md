# Database Schema Audit Plan

## Objective
Compare actual database schemas in PostgreSQL/TimescaleDB with what the code expects when saving and retrieving data. Identify mismatches before completing connection pooling implementation.

## Step 1: Connect to Database and List All Tables

```bash
# Connect to TimescaleDB/PostgreSQL
psql $TIMESCALE_DSN

# List all tables
\dt

# Get detailed info on each table
\d+ episodic_memories
\d+ emotional_memories
\d+ procedural_memories
\d+ semantic_memories
\d+ identity_memories
\d+ portfolio_holdings
\d+ portfolio_transactions
\d+ portfolio_preferences
\d+ portfolio_snapshots
\d+ emotional_patterns
\d+ skill_progressions  # May not exist
```

## Step 2: Extract Schema for Each Table

For each table, get:
- Column names and types
- Constraints (PRIMARY KEY, NOT NULL, CHECK, etc.)
- Indexes
- Foreign keys (if any)

### Query to Get Schema:
```sql
-- Get all columns for a table
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default,
    character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'TABLE_NAME'
ORDER BY ordinal_position;

-- Get constraints
SELECT 
    constraint_name, 
    constraint_type
FROM information_schema.table_constraints 
WHERE table_name = 'TABLE_NAME';

-- Get indexes
SELECT 
    indexname, 
    indexdef
FROM pg_indexes 
WHERE tablename = 'TABLE_NAME';
```

## Step 3: Analyze Code Expectations

### 3.1 Episodic Memory Service
**File**: `src/services/episodic_memory.py`

**INSERT Statement** (lines 84-91):
```sql
INSERT INTO episodic_memories (
    id, user_id, event_timestamp, event_type, content,
    location, participants, emotional_valence, emotional_arousal,
    importance_score, tags, metadata
)
```

**Expected Columns**:
- `id` - UUID
- `user_id` - VARCHAR
- `event_timestamp` - TIMESTAMPTZ
- `event_type` - TEXT/VARCHAR
- `content` - TEXT
- `location` - JSONB (serialized as JSON string)
- `participants` - TEXT[] (array)
- `emotional_valence` - FLOAT
- `emotional_arousal` - FLOAT
- `importance_score` - FLOAT
- `tags` - TEXT[] (array)
- `metadata` - JSONB (serialized as JSON string)

**Retrieval Queries**: Check if any SELECT statements exist

---

### 3.2 Emotional Memory Service
**File**: `src/services/emotional_memory.py`

**INSERT Statement** (lines 142-147):
```sql
INSERT INTO emotional_memories (
    id, user_id, timestamp, emotional_state, valence, arousal,
    dominance, context, trigger_event, intensity, duration_minutes, metadata
)
```

**Expected Columns**:
- `id` - UUID
- `user_id` - VARCHAR
- `timestamp` - TIMESTAMPTZ
- `emotional_state` - VARCHAR
- `valence` - FLOAT (-1.0 to 1.0)
- `arousal` - FLOAT (0.0 to 1.0)
- `dominance` - FLOAT (0.0 to 1.0)
- `context` - TEXT
- `trigger_event` - TEXT
- `intensity` - FLOAT
- `duration_minutes` - INT
- `metadata` - JSONB

**Other Tables**: `emotional_patterns` (check if used)

---

### 3.3 Procedural Memory Service
**File**: `src/services/procedural_memory.py`

**INSERT Statements**: Need to find all SQL operations

**Expected Columns** (from dataclass lines 31-45):
- `id` - UUID/VARCHAR
- `user_id` - VARCHAR
- `skill_name` - VARCHAR
- `proficiency_level` - VARCHAR (beginner/intermediate/advanced/expert/master)
- `steps` - JSONB (list of steps)
- `prerequisites` - JSONB (list of prerequisites)
- `last_practiced` - TIMESTAMPTZ
- `practice_count` - INT
- `success_rate` - FLOAT (0.0 to 1.0)
- `difficulty_rating` - FLOAT (0.0 to 1.0)
- `context` - TEXT
- `tags` - TEXT[]
- `metadata` - JSONB

**Other Tables**: 
- `skill_progressions` (SkillProgression dataclass lines 48-59)
  - Expected but may not exist in DB!

---

### 3.4 Portfolio Service
**File**: `src/services/portfolio_service.py`

**Tables Used**:

#### portfolio_holdings
**INSERT Statement** (lines 193-216):
```sql
INSERT INTO portfolio_holdings (...)
```

**Expected Columns**:
- `id` - UUID
- `user_id` - VARCHAR
- `ticker` - VARCHAR
- `asset_name` - VARCHAR
- `asset_type` - VARCHAR
- `quantity` - FLOAT
- `avg_cost` - FLOAT
- `current_price` - FLOAT
- `market_value` - FLOAT
- `ownership_pct` - FLOAT
- `position` - VARCHAR (long/short)
- `intent` - VARCHAR
- `time_horizon` - VARCHAR
- `target_price` - FLOAT
- `stop_loss` - FLOAT
- `notes` - TEXT
- `memory_id` - VARCHAR

#### portfolio_snapshots
**INSERT Statement** (lines 310-317):
```sql
INSERT INTO portfolio_snapshots (
    user_id, snapshot_timestamp, total_value,
    cash_value, equity_value, holdings_snapshot
)
```

**Expected Columns**:
- `user_id` - VARCHAR
- `snapshot_timestamp` - TIMESTAMPTZ (auto NOW())
- `total_value` - FLOAT
- `cash_value` - FLOAT
- `equity_value` - FLOAT
- `holdings_snapshot` - JSONB

#### portfolio_transactions (check if used)
#### portfolio_preferences (check if used)

---

### 3.5 Semantic Memory Service
**Status**: Not implemented yet (Phase 2 TODO)

**Migration**: `migrations/002_postgres_semantic.sql`

**Expected Table**: `semantic_memories`

---

### 3.6 Identity Memory Service
**Status**: Not implemented yet (Phase 2 TODO)

**Migration**: `migrations/005_postgres_identity.sql`

**Expected Table**: `identity_memories`

---

## Step 4: Comparison Matrix

Create a table for each service:

### Template:
```
| Column Name        | Expected Type | Actual Type | Match? | Notes |
|--------------------|---------------|-------------|--------|-------|
| id                 | UUID          | uuid        | ✅     |       |
| user_id            | VARCHAR       | varchar     | ✅     |       |
| some_field         | JSONB         | ARRAY       | ❌     | TYPE MISMATCH |
| missing_field      | TEXT          | -           | ❌     | MISSING IN DB |
| extra_db_field     | -             | jsonb       | ⚠️     | NOT USED BY CODE |
```

## Step 5: Issues to Document

### Schema Mismatches
- Type mismatches (e.g., ARRAY vs JSONB)
- Missing columns
- Extra columns (not used by code)
- Wrong column names

### Missing Tables
- Tables code expects but don't exist
- Tables in migrations but not created

### Index & Constraint Issues
- Missing indexes that code might need for performance
- Missing constraints that could cause data issues

### JSON Serialization Issues
- Fields where code does `json.dumps()` but DB expects TEXT
- Fields where code expects JSONB but DB has ARRAY

## Step 6: Create Fix Recommendations

For each issue found:
1. **Severity**: Critical / High / Medium / Low
2. **Impact**: What breaks if not fixed
3. **Fix**: Exact SQL to apply
4. **Migration File**: Which migration needs updating

## Expected Findings (Based on Previous Errors)

### Already Known Issues:
1. ✅ **FIXED**: `episodic_memories.importance_score` (was `significance_score`)
2. ✅ **FIXED**: `episodic_memories.tags` and `metadata` (were missing)
3. ✅ **FIXED**: `emotional_memories.*` (complete schema mismatch - fixed)
4. ⚠️ **PARTIALLY FIXED**: `procedural_memories.last_practiced` (was `last_performed`)
5. ⚠️ **PARTIALLY FIXED**: `procedural_memories.proficiency_level` (FLOAT vs VARCHAR)
6. ⚠️ **PARTIALLY FIXED**: `procedural_memories.steps` (ARRAY vs JSONB)
7. ❌ **UNKNOWN**: `skill_progressions` table (may not exist)

### Potential Issues to Investigate:
- Portfolio tables: Check if all columns exist
- ChromaDB collections: Verify expected collections exist
- Neo4j constraints: Check if graph schema is correct

## Step 7: Output Format

Create a comprehensive audit report:

```markdown
# Database Schema Audit Report

## Executive Summary
- Total Tables Expected: X
- Total Tables Found: Y
- Tables with Issues: Z
- Critical Issues: N

## Detailed Findings

### 1. episodic_memories
- **Status**: ✅ GOOD / ⚠️ WARNINGS / ❌ ISSUES
- **Issues Found**: [list]
- **Recommendations**: [list]

### 2. emotional_memories
...

## Priority Fixes
1. [Critical] Fix X before proceeding
2. [High] Fix Y for reliability
3. [Medium] Optimize Z for performance

## Migration Updates Needed
- Update `migrations/003_postgres_procedural.sql`
- Create `migrations/FIX_XXX.sql` for existing DBs
```

## Commands to Run

```bash
# 1. Export database schema to file
pg_dump $TIMESCALE_DSN --schema-only --no-owner --no-privileges > /tmp/db_schema.sql

# 2. Connect and run queries
psql $TIMESCALE_DSN

# 3. For each table, run detailed schema query
# 4. Save output to file for analysis
# 5. Compare with code expectations
# 6. Generate audit report
```

## Tools We'll Use
- `psql` - interactive queries
- `pg_dump` - export full schema
- `grep` - search code for SQL statements
- Manual comparison - code vs DB

## Next Steps After Audit
1. Review audit report with user
2. Prioritize fixes
3. Create/update migration files
4. Apply fixes to database
5. Test with connection pooling
6. Complete Phase 2

