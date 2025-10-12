#!/bin/bash
# Quick script to force unlock migration lock
# Usage: ./force_unlock.sh <password>

PASS=""
DSN="postgresql://postgres:${PASS}@localhost:5433/agentic_memories"

echo "Forcing migration lock release..."
psql "$DSN" -c "UPDATE migration_lock SET locked = FALSE, locked_by = NULL, locked_at = NULL, process_id = NULL WHERE id = 1;"

if [ $? -eq 0 ]; then
    echo "✅ Lock released successfully!"
    echo ""
    echo "You can now run migrations:"
    echo "  export TIMESCALE_DSN=\"$DSN\""
    echo "  ./migrations/migrate.sh up"
else
    echo "❌ Failed to release lock"
    echo "Check your database connection"
fi

