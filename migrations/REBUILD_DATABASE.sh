#!/bin/bash
# Clean database rebuild script - ORGANIZED BY DATABASE TYPE
# WARNING: This will DELETE ALL DATA in dev environment

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "🧹 CLEAN DATABASE REBUILD"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  WARNING: This will DROP and RECREATE all tables"
echo "⚠️  ALL DATA WILL BE LOST"
echo ""
read -p "Are you sure you want to continue? (type 'yes'): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Dropping all existing tables..."
psql $TIMESCALE_DSN < migrations/DROP_ALL.sql

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Step 2: Creating TimescaleDB tables (time-series data)"
echo "════════════════════════════════════════════════════════════════"

echo "  001 → episodic_memories (12 columns)"
psql $TIMESCALE_DSN < migrations/timescaledb/001_episodic_memories.sql

echo "  002 → emotional_memories (12 columns)"
psql $TIMESCALE_DSN < migrations/timescaledb/002_emotional_memories.sql

echo "  003 → portfolio_snapshots"
psql $TIMESCALE_DSN < migrations/timescaledb/003_portfolio_snapshots.sql

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Step 3: Creating PostgreSQL tables (relational data)"
echo "════════════════════════════════════════════════════════════════"

echo "  001 → procedural_memories (13 columns)"
psql $TIMESCALE_DSN < migrations/postgres/001_procedural_memories.sql

echo "  002 → skill_progressions (9 columns) **NEW**"
psql $TIMESCALE_DSN < migrations/postgres/002_skill_progressions.sql

echo "  003 → semantic_memories (Phase 3)"
psql $TIMESCALE_DSN < migrations/postgres/003_semantic_memories.sql

echo "  004 → identity_memories (Phase 3)"
psql $TIMESCALE_DSN < migrations/postgres/004_identity_memories.sql

echo "  005 → portfolio_holdings"
psql $TIMESCALE_DSN < migrations/postgres/005_portfolio_holdings.sql

echo "  006 → portfolio_transactions"
psql $TIMESCALE_DSN < migrations/postgres/006_portfolio_transactions.sql

echo "  007 → portfolio_preferences"
psql $TIMESCALE_DSN < migrations/postgres/007_portfolio_preferences.sql

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Step 4: Verifying tables created..."
echo "════════════════════════════════════════════════════════════════"
psql $TIMESCALE_DSN -c "\dt" | grep -E "(episodic|emotional|procedural|skill|semantic|identity|portfolio)" || echo "✅ Tables created"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ DATABASE REBUILD COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Summary:"
echo ""
echo "📊 TimescaleDB (3 tables):"
echo "  ✅ episodic_memories (12 columns)"
echo "  ✅ emotional_memories (12 columns)"
echo "  ✅ portfolio_snapshots"
echo ""
echo "📊 PostgreSQL (7 tables):"
echo "  ✅ procedural_memories (13 columns)"
echo "  ✅ skill_progressions (9 columns) **NEW**"
echo "  ✅ semantic_memories (Phase 3)"
echo "  ✅ identity_memories (Phase 3)"
echo "  ✅ portfolio_holdings"
echo "  ✅ portfolio_transactions"
echo "  ✅ portfolio_preferences"
echo ""
echo "Next steps:"
echo "  1. Neo4j: Run migrations/neo4j/001_graph_constraints.cql manually"
echo "  2. ChromaDB: Run migrations/chromadb/001_collections.py manually"
echo "  3. Restart API: docker-compose restart api"
echo "  4. Test storage: curl -X POST http://localhost:8080/v1/store ..."
echo ""
