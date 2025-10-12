#!/bin/bash
# Migration Generator - Creates up/down migration pairs with auto-numbering
#
# Usage: ./generate.sh <db_type> <migration_name>
# Example: ./generate.sh postgres add_user_preferences

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Validate arguments
if [ "$#" -lt 2 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo ""
    echo "Usage: $0 <db_type> <migration_name>"
    echo ""
    echo "Database Types:"
    echo "  timescaledb   - TimescaleDB/PostgreSQL time-series tables"
    echo "  postgres      - PostgreSQL relational tables"
    echo "  neo4j         - Neo4j graph constraints/indexes"
    echo "  chromadb      - ChromaDB collections"
    echo ""
    echo "Examples:"
    echo "  $0 postgres add_user_preferences"
    echo "  $0 timescaledb add_metrics_table"
    echo "  $0 neo4j add_relationship_constraints"
    echo ""
    exit 1
fi

DB_TYPE="$1"
MIGRATION_NAME="$2"

# Validate database type
case "$DB_TYPE" in
    timescaledb|postgres|neo4j|chromadb)
        ;;
    *)
        echo -e "${RED}Error: Invalid database type '$DB_TYPE'${NC}"
        echo "Valid types: timescaledb, postgres, neo4j, chromadb"
        exit 1
        ;;
esac

# Determine file extension
EXT="sql"
[ "$DB_TYPE" = "neo4j" ] && EXT="cql"
[ "$DB_TYPE" = "chromadb" ] && EXT="py"

# Find next migration number
MIGRATIONS_DIR="$SCRIPT_DIR/$DB_TYPE"
mkdir -p "$MIGRATIONS_DIR"

NEXT_NUM="001"
if ls "$MIGRATIONS_DIR"/*.up.${EXT} 1> /dev/null 2>&1; then
    LAST_FILE=$(ls "$MIGRATIONS_DIR"/*.up.${EXT} | sort -V | tail -n 1)
    LAST_NUM=$(basename "$LAST_FILE" | grep -o '^[0-9]\+')
    NEXT_NUM=$(printf "%03d" $((10#$LAST_NUM + 1)))
fi

# Generate filenames
UP_FILE="$MIGRATIONS_DIR/${NEXT_NUM}_${MIGRATION_NAME}.up.${EXT}"
DOWN_FILE="$MIGRATIONS_DIR/${NEXT_NUM}_${MIGRATION_NAME}.down.${EXT}"

# Generate content based on database type
case "$DB_TYPE" in
    timescaledb)
        cat > "$UP_FILE" << 'EOF'
-- TimescaleDB Migration: MIGRATION_NAME
-- Description: [Add description here]

CREATE TABLE IF NOT EXISTS table_name (
    id UUID NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    -- Add your columns here
    metadata JSONB
);

-- Convert to hypertable
SELECT create_hypertable('table_name', 'timestamp', if_not_exists => TRUE);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_table_name_user_time 
    ON table_name (user_id, timestamp DESC);

-- TimescaleDB optimizations
SELECT set_chunk_time_interval('table_name', INTERVAL '7 days');

ALTER TABLE table_name
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('table_name', INTERVAL '30 days');
EOF
        cat > "$DOWN_FILE" << 'EOF'
-- Rollback TimescaleDB Migration: MIGRATION_NAME

-- Drop compression policy
SELECT remove_compression_policy('table_name', if_exists => TRUE);

-- Drop indexes
DROP INDEX IF EXISTS idx_table_name_user_time;

-- Drop table (hypertable dropped automatically)
DROP TABLE IF EXISTS table_name CASCADE;
EOF
        ;;
    
    postgres)
        cat > "$UP_FILE" << 'EOF'
-- PostgreSQL Migration: MIGRATION_NAME
-- Description: [Add description here]

CREATE TABLE IF NOT EXISTS table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Add your columns here
    metadata JSONB
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_table_name_user 
    ON table_name (user_id);

-- Add constraints
-- ALTER TABLE table_name
--   ADD CONSTRAINT chk_constraint_name CHECK (column_name IS NOT NULL);
EOF
        cat > "$DOWN_FILE" << 'EOF'
-- Rollback PostgreSQL Migration: MIGRATION_NAME

-- Drop indexes
DROP INDEX IF EXISTS idx_table_name_user;

-- Drop table
DROP TABLE IF EXISTS table_name CASCADE;
EOF
        ;;
    
    neo4j)
        cat > "$UP_FILE" << 'EOF'
// Neo4j Migration: MIGRATION_NAME
// Description: [Add description here]

// Create constraints
CREATE CONSTRAINT node_id_unique IF NOT EXISTS
FOR (n:NodeLabel) REQUIRE n.id IS UNIQUE;

// Create indexes
CREATE INDEX node_property_idx IF NOT EXISTS 
FOR (n:NodeLabel) ON (n.property_name);

// Example relationship patterns (created by application):
// (n1:NodeLabel {id: '123'})-[:RELATIONSHIP_TYPE {property: 'value'}]->(n2:NodeLabel {id: '456'})
EOF
        cat > "$DOWN_FILE" << 'EOF'
// Rollback Neo4j Migration: MIGRATION_NAME

// Drop indexes
DROP INDEX node_property_idx IF EXISTS;

// Drop constraints
DROP CONSTRAINT node_id_unique IF EXISTS;

// Note: To delete all nodes of a type:
// MATCH (n:NodeLabel) DETACH DELETE n;
EOF
        ;;
    
    chromadb)
        cat > "$UP_FILE" << 'EOF'
#!/usr/bin/env python3
"""
ChromaDB Migration: MIGRATION_NAME
Description: [Add description here]
"""
import os
from chromadb import HttpClient


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    client = HttpClient(host=host, port=port)
    
    collection_name = "your_collection_name"
    
    # Create collection if it doesn't exist
    existing = [c.name for c in client.list_collections()]
    if collection_name not in existing:
        client.create_collection(
            name=collection_name,
            metadata={
                "distance": "cosine",
                "dimension": 3072,
                "description": "Collection description"
            },
        )
        print(f"Created collection: {collection_name}")
    else:
        print(f"Collection already exists: {collection_name}")


if __name__ == "__main__":
    main()
EOF
        cat > "$DOWN_FILE" << 'EOF'
#!/usr/bin/env python3
"""
Rollback ChromaDB Migration: MIGRATION_NAME
WARNING: This will delete the collection and all its data!
"""
import os
from chromadb import HttpClient


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    client = HttpClient(host=host, port=port)
    
    collection_name = "your_collection_name"
    
    try:
        client.delete_collection(name=collection_name)
        print(f"Deleted collection: {collection_name}")
    except Exception as e:
        print(f"Collection may not exist: {e}")


if __name__ == "__main__":
    main()
EOF
        chmod +x "$UP_FILE" "$DOWN_FILE"
        ;;
esac

# Replace placeholder text
sed -i.bak "s/MIGRATION_NAME/${MIGRATION_NAME}/g" "$UP_FILE" "$DOWN_FILE"
rm "${UP_FILE}.bak" "${DOWN_FILE}.bak" 2>/dev/null || true

# Success message
echo -e "${GREEN}✅ Migration files created:${NC}"
echo -e "${BLUE}  UP:   $(basename "$UP_FILE")${NC}"
echo -e "${BLUE}  DOWN: $(basename "$DOWN_FILE")${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Edit the migration files to add your changes"
echo "  2. Test with: ./migrate.sh up --dry-run"
echo "  3. Apply with: ./migrate.sh up"
echo ""

