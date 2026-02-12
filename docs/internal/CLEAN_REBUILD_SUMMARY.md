# 🧹 Clean Rebuild - Execution Summary

## What Will Happen

### 1. Backup & Cleanup
- Move old migrations to `migrations/old_v1/` folder
- Delete all `FIX_*.sql` files (no longer needed)

### 2. New Clean Migration Files

#### Will CREATE these NEW files:
- `migrations/DROP_ALL.sql` - Drop script for clean rebuild
- `migrations/003b_postgres_skill_progressions.sql` - NEW table (was missing!)
- `migrations/004b_postgres_emotional_patterns.sql` - Split out from 004

#### Will REPLACE these existing files:
- `migrations/001_timescale_episodic.sql` - Remove 5 extra columns
- `migrations/002_postgres_semantic.sql` - Keep simple for Phase 3
- `migrations/003_postgres_procedural.sql` - Already clean, minor updates
- `migrations/004_timescale_emotional.sql` - Remove 6 extra columns
- `migrations/005_postgres_identity.sql` - Keep simple for Phase 3

#### Will KEEP unchanged:
- `migrations/006_neo4j_graph.cql` - Already clean
- `migrations/007_chroma_collections.py` - Already clean
- `migrations/008_postgres_portfolio.sql` - Already clean
- `migrations/009_timescale_portfolio_snapshots.sql` - Already clean
- `migrations/010_neo4j_portfolio_graph.cql` - Already clean

### 3. Column Reductions

**episodic_memories**: 17 → 12 columns  
Removing: sensory_context, causal_chain, replay_count, last_recalled, decay_factor

**emotional_memories**: 18 → 12 columns  
Removing: emotion_vector, triggers, duration, coping_strategies, resolution, linked_episodes

**procedural_memories**: 13 columns (already perfect!)

**skill_progressions**: NEW TABLE with 9 columns

### 4. Execution Steps (When You're Ready)

```bash
# Backup old migrations
mkdir -p migrations/old_v1
mv migrations/001_timescale_episodic.sql migrations/old_v1/
mv migrations/002_postgres_semantic.sql migrations/old_v1/
mv migrations/003_postgres_procedural.sql migrations/old_v1/
mv migrations/004_timescale_emotional.sql migrations/old_v1/
mv migrations/005_postgres_identity.sql migrations/old_v1/

# Remove FIX files
rm migrations/FIX_*.sql

# Drop all tables
psql $TIMESCALE_DSN < migrations/DROP_ALL.sql

# Run new clean migrations
psql $TIMESCALE_DSN < migrations/001_timescale_episodic.sql
psql $TIMESCALE_DSN < migrations/002_postgres_semantic.sql
psql $TIMESCALE_DSN < migrations/003_postgres_procedural.sql
psql $TIMESCALE_DSN < migrations/003b_postgres_skill_progressions.sql
psql $TIMESCALE_DSN < migrations/004_timescale_emotional.sql
psql $TIMESCALE_DSN < migrations/004b_postgres_emotional_patterns.sql
psql $TIMESCALE_DSN < migrations/005_postgres_identity.sql
psql $TIMESCALE_DSN < migrations/008_postgres_portfolio.sql
psql $TIMESCALE_DSN < migrations/009_timescale_portfolio_snapshots.sql

# Verify
psql $TIMESCALE_DSN -c "\dt"
```

## Expected Results

✅ 11 tables with clean schemas  
✅ Only columns code actually uses  
✅ skill_progressions table now exists  
✅ No FIX files needed  
✅ Perfect match with code expectations  

## Ready to Proceed?

Answer "yes" and I'll:
1. Create all new migration files
2. Show you a preview
3. Wait for your approval before executing
