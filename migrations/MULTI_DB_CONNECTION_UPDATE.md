# Multi-Database Connection Enhancement

## Summary

Updated the migration script to properly handle separate connection details for PostgreSQL/TimescaleDB, Neo4j, and ChromaDB.

## Changes Made

### 1. Connection Configuration Storage

**File:** `migrations/.dbconfig`

Now stores separate connection details for each database:

```bash
# PostgreSQL/TimescaleDB
PG_HOST="localhost"
PG_PORT="5433"
PG_DATABASE="agentic_memories"
PG_USER="postgres"

# Neo4j
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"

# ChromaDB
CHROMA_HOST="localhost"
CHROMA_PORT="8000"
```

Passwords are never stored for security reasons.

### 2. Interactive Connection Setup

When running `./migrations/migrate.sh`, the script now prompts for:

#### First Time Setup:
- **PostgreSQL/TimescaleDB**: host, port, database, user, password
- **Neo4j**: URI, user, password
- **ChromaDB**: host, port, password (if any)

#### Subsequent Runs (with saved config):
- Only prompts for passwords
- Reuses saved host/port/user information

### 3. Connection Testing

The script now tests all three database connections on startup:

- ✅ PostgreSQL/TimescaleDB - **Required** (script fails if not connected)
- ⚠️  Neo4j - **Optional** (warns and skips Neo4j migrations if not available)
- ⚠️  ChromaDB - **Optional** (warns and skips ChromaDB migrations if not available)

### 4. Environment Variables

All connection details are exported as environment variables for use throughout the script:

```bash
TIMESCALE_DSN="postgresql://user:pass@host:port/database"
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"
CHROMA_HOST="localhost"
CHROMA_PORT="8000"
```

## Default Connection Details

### PostgreSQL/TimescaleDB
- Host: `localhost`
- Port: `5433`
- Database: `agentic_memories`
- User: `postgres`

### Neo4j
- URI: `bolt://localhost:7687`
- User: `neo4j`
- Password: `password`

### ChromaDB
- Host: `localhost`
- Port: `8000`
- No authentication by default

## Usage Example

```bash
# Run interactive mode
./migrations/migrate.sh

# You'll be prompted:
🔧 Database Connection Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══ PostgreSQL/TimescaleDB ═══
Host [localhost]: 
Port [5433]: 
Database Name [agentic_memories]: 
User [postgres]: 
Password: ****

═══ Neo4j ═══
URI [bolt://localhost:7687]: 
User [neo4j]: 
Password: ****

═══ ChromaDB ═══
Host [localhost]: 
Port [8000]: 
Password (if any, or press Enter): 

Save connection config for future use? (Y/n): y

Testing connections...
✅ PostgreSQL/TimescaleDB connected
✅ Neo4j connected
✅ ChromaDB connected
```

## Benefits

1. ✅ **Proper isolation** - Each database can have different hosts, ports, and credentials
2. ✅ **Better defaults** - Port 5433 for PostgreSQL/TimescaleDB (Docker default)
3. ✅ **Graceful degradation** - Script continues if optional databases are unavailable
4. ✅ **Secure** - Passwords are never saved to disk
5. ✅ **Convenient** - Saved config means you only type passwords on subsequent runs
6. ✅ **Complete testing** - Verifies all database connections before proceeding

## Migration Impact

- ✅ Old `.dbconfig` files will be automatically replaced with new format on first run
- ✅ All existing migrations continue to work
- ✅ Database statistics command now uses correct connection details
- ✅ All database operations use appropriate credentials

