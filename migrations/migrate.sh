#!/bin/bash
# Migration Manager - Handles fresh deployments and incremental upgrades
# Tracks applied migrations and only runs new ones

# Don't exit on error - we handle errors gracefully
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_TABLE="schema_migrations"
DRY_RUN=false
AUTO_ROLLBACK_ON_ERROR=false
MIGRATION_IN_PROGRESS=false

# Colors for output (define early)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Signal handler for graceful shutdown
cleanup_on_exit() {
    local exit_code=$?
    
    if [ "$MIGRATION_IN_PROGRESS" = true ]; then
        echo ""
        log_warning "Migration interrupted!"
        
        # Release lock if held
        if [ "$DRY_RUN" = false ] && [ -n "$TIMESCALE_DSN" ]; then
            release_lock 2>/dev/null || true
        fi
        
        log_info "Cleanup completed"
        
        # Ask user if they want to continue or abort
        if [ -t 0 ]; then  # Check if stdin is a terminal
            echo ""
            read -p "Migration was interrupted. View status? (y/n): " view_status
            if [ "$view_status" = "y" ] || [ "$view_status" = "Y" ]; then
                show_status 2>/dev/null || true
            fi
        fi
    fi
    
    exit $exit_code
}

# Set up signal handlers
trap cleanup_on_exit EXIT
trap 'MIGRATION_IN_PROGRESS=true; log_warning "Received interrupt signal (Ctrl+C). Finishing current operation..."; sleep 1' INT
trap 'MIGRATION_IN_PROGRESS=true; log_warning "Received termination signal. Cleaning up..."; sleep 1' TERM

# Function to prompt for database connection details
prompt_for_db_connection() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🔧 Database Connection Setup${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Try to load previous config
    local has_saved_config=false
    if load_connection_config; then
        has_saved_config=true
        echo -e "${BLUE}Found saved connection config${NC}"
        echo ""
        read -p "Use saved config? (Y/n): " use_saved
        use_saved=${use_saved:-Y}
        
        if [ "$use_saved" = "Y" ] || [ "$use_saved" = "y" ]; then
            # Only prompt for passwords
            echo ""
            echo -e "${GREEN}Enter passwords for databases:${NC}"
            read -sp "PostgreSQL/TimescaleDB Password: " PG_PASSWORD
            echo ""
            read -sp "Neo4j Password [password]: " NEO4J_PASSWORD
            NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
            echo ""
            echo -e "${YELLOW}ChromaDB Password (if any, or press Enter):${NC}"
            read -sp "" CHROMA_PASSWORD
            echo ""
        else
            has_saved_config=false
        fi
    fi
    
    # Prompt for new details if no saved config or user declined
    if [ "$has_saved_config" = false ]; then
        echo -e "${BLUE}═══ PostgreSQL/TimescaleDB ═══${NC}"
        read -p "Host [localhost]: " PG_HOST
        PG_HOST=${PG_HOST:-localhost}
        
        read -p "Port [5433]: " PG_PORT
        PG_PORT=${PG_PORT:-5433}
        
        read -p "Database Name [agentic_memories]: " PG_DATABASE
        PG_DATABASE=${PG_DATABASE:-agentic_memories}
        
        read -p "User [postgres]: " PG_USER
        PG_USER=${PG_USER:-postgres}
        
        read -sp "Password: " PG_PASSWORD
        echo ""
        echo ""
        
        echo -e "${BLUE}═══ Neo4j ═══${NC}"
        read -p "URI [bolt://localhost:7687]: " NEO4J_URI
        NEO4J_URI=${NEO4J_URI:-bolt://localhost:7687}
        
        read -p "User [neo4j]: " NEO4J_USER
        NEO4J_USER=${NEO4J_USER:-neo4j}
        
        read -sp "Password [password]: " NEO4J_PASSWORD
        NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
        echo ""
        echo ""
        
        echo -e "${BLUE}═══ ChromaDB ═══${NC}"
        read -p "Host [localhost]: " CHROMA_HOST
        CHROMA_HOST=${CHROMA_HOST:-localhost}
        
        read -p "Port [8000]: " CHROMA_PORT
        CHROMA_PORT=${CHROMA_PORT:-8000}
        
        echo -e "${YELLOW}Password (if any, or press Enter):${NC}"
        read -sp "" CHROMA_PASSWORD
        echo ""
        
        # Ask if user wants to save config
        echo ""
        read -p "Save connection config for future use? (Y/n): " save_config
        save_config=${save_config:-Y}
        
        if [ "$save_config" = "Y" ] || [ "$save_config" = "y" ]; then
            save_connection_config
        fi
    fi
    
    # Construct DSNs
    export TIMESCALE_DSN="postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"
    
	# Export for Neo4j and ChromaDB usage
	export NEO4J_URI NEO4J_USER NEO4J_PASSWORD
	export CHROMA_HOST CHROMA_PORT
	# Ensure defaults for Chroma (v2 servers expect tenant/database)
	export CHROMA_TENANT=${CHROMA_TENANT:-agentic-memories}
	export CHROMA_DATABASE=${CHROMA_DATABASE:-memories}
    
    echo ""
    log_info "Testing connections..."
    
    # Test PostgreSQL
    if psql "$TIMESCALE_DSN" -c "SELECT 1;" > /dev/null 2>&1; then
        log_success "✅ PostgreSQL/TimescaleDB connected"
    else
        log_error "❌ PostgreSQL/TimescaleDB connection failed"
        return 1
    fi
    
    # Test Neo4j (if cypher-shell is available)
    if command -v cypher-shell &> /dev/null; then
        if cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1" > /dev/null 2>&1; then
            log_success "✅ Neo4j connected"
        else
            log_warning "⚠️  Neo4j connection failed (will skip Neo4j migrations)"
        fi
    else
        log_warning "⚠️  cypher-shell not found (will skip Neo4j migrations)"
    fi
    
    # Test ChromaDB (if python3 is available)
    if command -v python3 &> /dev/null; then
        if python3 -c "from chromadb import HttpClient; HttpClient(host='$CHROMA_HOST', port=$CHROMA_PORT).heartbeat()" > /dev/null 2>&1; then
            log_success "✅ ChromaDB connected"
        else
            log_warning "⚠️  ChromaDB connection failed (will skip ChromaDB migrations)"
        fi
    else
        log_warning "⚠️  python3 not found (will skip ChromaDB migrations)"
    fi
    
    echo ""
}

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check required environment variables
check_env() {
    if [ -z "$TIMESCALE_DSN" ]; then
        log_info "Database connection not configured"
        echo ""
        prompt_for_db_connection
        
        # Verify connection works
        if ! psql "$TIMESCALE_DSN" -c "SELECT 1" > /dev/null 2>&1; then
            log_error "Failed to connect to database"
            log_info "Please check your connection details and try again"
            return 1
        fi
	fi
	# Always ensure CHROMA_TENANT/DATABASE have defaults for subsequent steps
	export CHROMA_TENANT=${CHROMA_TENANT:-agentic-memories}
	export CHROMA_DATABASE=${CHROMA_DATABASE:-memories}
	log_success "Database connection verified"
    return 0
}

# Save connection details to a config file for reuse
save_connection_config() {
    local config_file="$SCRIPT_DIR/.dbconfig"
    
    cat > "$config_file" << EOF
# Database configuration (auto-generated)
# Stores connection details for all databases
# Passwords are not stored for security reasons

# PostgreSQL/TimescaleDB
PG_HOST="$PG_HOST"
PG_PORT="$PG_PORT"
PG_DATABASE="$PG_DATABASE"
PG_USER="$PG_USER"

# Neo4j
NEO4J_URI="$NEO4J_URI"
NEO4J_USER="$NEO4J_USER"

# ChromaDB
CHROMA_HOST="$CHROMA_HOST"
CHROMA_PORT="$CHROMA_PORT"
EOF
    
    chmod 600 "$config_file"
    log_info "Connection config saved to .dbconfig"
}

# Load connection config if exists
load_connection_config() {
    local config_file="$SCRIPT_DIR/.dbconfig"
    
    if [ -f "$config_file" ]; then
        source "$config_file"
        return 0
    fi
    return 1
}

# Create migrations tracking table if it doesn't exist
init_migrations_table() {
    log_info "Initializing migrations tracking table..."
    
    psql "$TIMESCALE_DSN" << EOF
-- Main tracking table for applied migrations
CREATE TABLE IF NOT EXISTS $MIGRATIONS_TABLE (
    id SERIAL PRIMARY KEY,
    database_type VARCHAR(32) NOT NULL,
    migration_file VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum VARCHAR(64),
    UNIQUE(database_type, migration_file)
);

-- History table for all migration actions (up and down)
CREATE TABLE IF NOT EXISTS migration_history (
    id SERIAL PRIMARY KEY,
    database_type VARCHAR(32) NOT NULL,
    migration_file VARCHAR(255) NOT NULL,
    action VARCHAR(16) NOT NULL,  -- 'up' or 'down'
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execution_time_ms INT,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_migration_history_applied 
    ON migration_history (applied_at DESC);

CREATE INDEX IF NOT EXISTS idx_migration_history_file 
    ON migration_history (database_type, migration_file);

-- Lock table to prevent concurrent migrations
CREATE TABLE IF NOT EXISTS migration_lock (
    id INT PRIMARY KEY DEFAULT 1,
    locked BOOLEAN DEFAULT FALSE,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(255),
    process_id INT,
    CONSTRAINT single_lock CHECK (id = 1)
);

-- Insert single lock row if it doesn't exist
INSERT INTO migration_lock (id, locked, locked_by) 
VALUES (1, FALSE, NULL) 
ON CONFLICT (id) DO NOTHING;
EOF
    
    log_success "Migration tracking tables ready"
}

# Calculate checksum of a migration file
get_checksum() {
    local file="$1"
    if command -v sha256sum &> /dev/null; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$file" | awk '{print $1}'
    else
        echo "NO_CHECKSUM"
    fi
}

# Check if a migration has been applied
is_applied() {
    local db_type="$1"
    local filename="$2"
    
    local count=$(psql "$TIMESCALE_DSN" -t -c \
        "SELECT COUNT(*) FROM $MIGRATIONS_TABLE WHERE database_type='$db_type' AND migration_file='$filename'" | tr -d ' ')
    
    [ "$count" -gt 0 ]
}

# Mark migration as applied
mark_applied() {
    local db_type="$1"
    local filename="$2"
    local checksum="$3"
    
    psql "$TIMESCALE_DSN" -c \
        "INSERT INTO $MIGRATIONS_TABLE (database_type, migration_file, checksum) VALUES ('$db_type', '$filename', '$checksum')" \
        > /dev/null
}

# Record migration action in history
record_history() {
    local db_type="$1"
    local filename="$2"
    local action="$3"
    local execution_time="${4:-0}"
    local success="${5:-true}"
    local error_msg="${6:-}"
    
    if [ "$DRY_RUN" = true ]; then
        return 0
    fi
    
    psql "$TIMESCALE_DSN" -c \
        "INSERT INTO migration_history (database_type, migration_file, action, execution_time_ms, success, error_message) 
         VALUES ('$db_type', '$filename', '$action', $execution_time, $success, $([ -z "$error_msg" ] && echo "NULL" || echo "'$error_msg'"))" \
        > /dev/null 2>&1 || true  # Don't fail if history logging fails
}

# Acquire migration lock
acquire_lock() {
    local lock_id="migrate_$$_$(date +%s)"
    local max_wait=30  # seconds
    local waited=0
    
    log_info "Acquiring migration lock..."
    
    while [ $waited -lt $max_wait ]; do
        # Try to acquire lock - returns number of rows updated
        local updated=$(psql "$TIMESCALE_DSN" -t -A -c \
            "UPDATE migration_lock 
             SET locked = TRUE, locked_at = NOW(), locked_by = '$lock_id', process_id = $$ 
             WHERE id = 1 AND (locked = FALSE OR locked_at < NOW() - INTERVAL '5 minutes');" \
            2>&1 | grep -o '^UPDATE [0-9]*' | awk '{print $2}')
        
        # If we updated a row, we got the lock
        if [ "$updated" = "1" ]; then
            log_success "Lock acquired: $lock_id"
            return 0
        fi
        
        # Check who has the lock (only on first attempt)
        if [ $waited -eq 0 ]; then
            local lock_info=$(psql "$TIMESCALE_DSN" -t -c \
                "SELECT locked_by, locked_at, process_id FROM migration_lock WHERE id = 1;" 2>/dev/null)
            log_warning "Migration lock held by another process"
            echo "  Lock info: $lock_info"
            log_info "Waiting for lock (timeout: ${max_wait}s)..."
        fi
        
        sleep 1
        ((waited++))
    done
    
    log_error "Failed to acquire lock after ${max_wait}s"
    return 1
}

# Release migration lock
release_lock() {
    psql "$TIMESCALE_DSN" -c \
        "UPDATE migration_lock SET locked = FALSE, locked_by = NULL, locked_at = NULL, process_id = NULL WHERE id = 1" \
        > /dev/null 2>&1 || true
    
    log_info "Lock released"
}

# Force unlock (admin command)
force_unlock() {
    log_warning "Force unlocking migration lock..."
    echo ""
    
    # Get lock info with formatted output
    local lock_info=$(psql "$TIMESCALE_DSN" -t -A -F'|' -c \
        "SELECT 
            CASE WHEN locked THEN 'LOCKED' ELSE 'UNLOCKED' END as status,
            COALESCE(locked_by, 'N/A') as locked_by,
            COALESCE(to_char(locked_at, 'YYYY-MM-DD HH24:MI:SS'), 'N/A') as locked_at,
            COALESCE(process_id::text, 'N/A') as process_id
         FROM migration_lock 
         WHERE id = 1;")
    
    if [ -z "$lock_info" ]; then
        log_error "Could not retrieve lock information"
        return 1
    fi
    
    # Parse the lock info (pipe-separated)
    IFS='|' read -r status locked_by locked_at process_id <<< "$lock_info"
    
    echo -e "${BLUE}Current Lock Status:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    echo -e "  Status:     ${status}"
    echo -e "  Locked By:  ${locked_by}"
    echo -e "  Locked At:  ${locked_at}"
    echo -e "  Process ID: ${process_id}"
    echo "─────────────────────────────────────────────────────────────"
    echo ""
    
    if [ "$status" = "UNLOCKED" ]; then
        log_info "Lock is already released. No action needed."
        return 0
    fi
    
    log_warning "⚠️  This will forcefully release the lock!"
    read -p "Are you sure you want to force unlock? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        release_lock
        log_success "✅ Lock forcefully released"
    else
        log_info "Unlock cancelled"
    fi
}

# Run PostgreSQL/TimescaleDB migrations
run_sql_migrations() {
    local db_type="$1"
    local migrations_dir="$SCRIPT_DIR/$db_type"
    
    if [ ! -d "$migrations_dir" ]; then
        log_warning "No $db_type migrations directory found"
        return 0
    fi
    
    log_info "Processing $db_type migrations..."
    
    local applied=0
    local skipped=0
    
    # Sort files numerically, look for .up.sql files
    for migration_file in $(ls "$migrations_dir"/*.up.sql 2>/dev/null | sort -V); do
        local filename=$(basename "$migration_file")
        
        if is_applied "$db_type" "$filename"; then
            log_info "  ⏭️  $filename (already applied)"
            ((skipped++))
            continue
        fi
        
        if [ "$DRY_RUN" = true ]; then
            log_info "  [DRY-RUN] Would apply $filename"
            ((applied++))
            continue
        fi
        
        log_info "  🔄 Applying $filename..."
        
        # Run the migration with timing
        local start_time=$(date +%s)
        if psql "$TIMESCALE_DSN" < "$migration_file"; then
            local end_time=$(date +%s)
            local execution_time=$(( (end_time - start_time) * 1000 ))
            
            local checksum=$(get_checksum "$migration_file")
            mark_applied "$db_type" "$filename" "$checksum"
            record_history "$db_type" "$filename" "up" "$execution_time" "true"
            log_success "  ✅ Applied $filename (${execution_time}ms)"
            ((applied++))
        else
            local end_time=$(date +%s)
            local execution_time=$(( (end_time - start_time) * 1000 ))
            record_history "$db_type" "$filename" "up" "$execution_time" "false" "Migration failed"
            log_error "  ❌ Failed to apply $filename"
            exit 1
        fi
    done
    
    if [ $applied -eq 0 ] && [ $skipped -eq 0 ]; then
        log_info "  No migrations found"
    else
        log_success "$db_type: Applied $applied, Skipped $skipped"
    fi
}

# Run Neo4j migrations
run_neo4j_migrations() {
    local migrations_dir="$SCRIPT_DIR/neo4j"
    
    if [ ! -d "$migrations_dir" ]; then
        log_warning "No neo4j migrations directory found"
        return 0
    fi
    
    log_info "Processing Neo4j migrations..."
    
    # Check if Neo4j is accessible
    if ! command -v cypher-shell &> /dev/null; then
        log_warning "cypher-shell not found, skipping Neo4j migrations"
        log_info "Run manually: docker exec <neo4j-container> cypher-shell < migrations/neo4j/001_graph_constraints.cql"
        return 0
    fi
    
    local applied=0
    local skipped=0
    
    for migration_file in $(ls "$migrations_dir"/*.up.cql 2>/dev/null | sort -V); do
        local filename=$(basename "$migration_file")
        
        if is_applied "neo4j" "$filename"; then
            log_info "  ⏭️  $filename (already applied)"
            ((skipped++))
            continue
        fi
        
        if [ "$DRY_RUN" = true ]; then
            log_info "  [DRY-RUN] Would apply $filename"
            ((applied++))
            continue
        fi
        
        log_info "  🔄 Applying $filename..."
        
        # Run the migration (requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars)
        if cat "$migration_file" | cypher-shell -a "${NEO4J_URI:-bolt://localhost:7687}" \
                                                  -u "${NEO4J_USER:-neo4j}" \
                                                  -p "${NEO4J_PASSWORD:-password}"; then
            local checksum=$(get_checksum "$migration_file")
            mark_applied "neo4j" "$filename" "$checksum"
            log_success "  ✅ Applied $filename"
            ((applied++))
        else
            log_warning "  ⚠️  Failed to apply $filename (may need manual intervention)"
        fi
    done
    
    log_success "Neo4j: Applied $applied, Skipped $skipped"
}

# Run ChromaDB migrations
run_chromadb_migrations() {
    local migrations_dir="$SCRIPT_DIR/chromadb"
    
    if [ ! -d "$migrations_dir" ]; then
        log_warning "No chromadb migrations directory found"
        return 0
    fi
    
    log_info "Processing ChromaDB migrations..."
    
    local applied=0
    local skipped=0
    
    for migration_file in $(ls "$migrations_dir"/*.up.py 2>/dev/null | sort -V); do
        local filename=$(basename "$migration_file")
        
        if is_applied "chromadb" "$filename"; then
            log_info "  ⏭️  $filename (already applied)"
            ((skipped++))
            continue
        fi
        
        if [ "$DRY_RUN" = true ]; then
            log_info "  [DRY-RUN] Would apply $filename"
            ((applied++))
            continue
        fi
        
        log_info "  🔄 Applying $filename..."
        
        # Run the Python migration
        if python3 "$migration_file"; then
            local checksum=$(get_checksum "$migration_file")
            mark_applied "chromadb" "$filename" "$checksum"
            log_success "  ✅ Applied $filename"
            ((applied++))
        else
            log_warning "  ⚠️  Failed to apply $filename"
        fi
    done
    
    log_success "ChromaDB: Applied $applied, Skipped $skipped"
}

# Remove migration from tracking table
unmark_applied() {
    local db_type="$1"
    local filename="$2"
    
    psql "$TIMESCALE_DSN" -c \
        "DELETE FROM $MIGRATIONS_TABLE WHERE database_type='$db_type' AND migration_file='$filename'" \
        > /dev/null
}

# Rollback SQL migration
rollback_sql_migration() {
    local db_type="$1"
    local up_filename="$2"
    local down_filename="${up_filename/.up./.down.}"
    local down_file="$SCRIPT_DIR/$db_type/$down_filename"
    
    if [ ! -f "$down_file" ]; then
        log_error "Down migration not found: $down_file"
        return 1
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log_info "  [DRY-RUN] Would rollback $up_filename using $down_filename"
        return 0
    fi
    
    log_info "  🔄 Rolling back $up_filename..."
    
    local start_time=$(date +%s)
    if psql "$TIMESCALE_DSN" < "$down_file"; then
        local end_time=$(date +%s)
        local execution_time=$(( (end_time - start_time) * 1000 ))
        
        unmark_applied "$db_type" "$up_filename"
        record_history "$db_type" "$up_filename" "down" "$execution_time" "true"
        log_success "  ✅ Rolled back $up_filename (${execution_time}ms)"
        return 0
    else
        local end_time=$(date +%s)
        local execution_time=$(( (end_time - start_time) * 1000 ))
        record_history "$db_type" "$up_filename" "down" "$execution_time" "false" "Rollback failed"
        log_error "  ❌ Failed to rollback $up_filename"
        return 1
    fi
}

# Rollback Neo4j migration
rollback_neo4j_migration() {
    local up_filename="$1"
    local down_filename="${up_filename/.up./.down.}"
    local down_file="$SCRIPT_DIR/neo4j/$down_filename"
    
    if [ ! -f "$down_file" ]; then
        log_error "Down migration not found: $down_file"
        return 1
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log_info "  [DRY-RUN] Would rollback $up_filename using $down_filename"
        return 0
    fi
    
    log_info "  🔄 Rolling back $up_filename..."
    
    if cat "$down_file" | cypher-shell -a "${NEO4J_URI:-bolt://localhost:7687}" \
                                       -u "${NEO4J_USER:-neo4j}" \
                                       -p "${NEO4J_PASSWORD:-password}"; then
        unmark_applied "neo4j" "$up_filename"
        log_success "  ✅ Rolled back $up_filename"
        return 0
    else
        log_warning "  ⚠️  Failed to rollback $up_filename"
        return 1
    fi
}

# Rollback ChromaDB migration
rollback_chromadb_migration() {
    local up_filename="$1"
    local down_filename="${up_filename/.up./.down.}"
    local down_file="$SCRIPT_DIR/chromadb/$down_filename"
    
    if [ ! -f "$down_file" ]; then
        log_error "Down migration not found: $down_file"
        return 1
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log_info "  [DRY-RUN] Would rollback $up_filename using $down_filename"
        return 0
    fi
    
    log_info "  🔄 Rolling back $up_filename..."
    
    if python3 "$down_file"; then
        unmark_applied "chromadb" "$up_filename"
        log_success "  ✅ Rolled back $up_filename"
        return 0
    else
        log_warning "  ⚠️  Failed to rollback $up_filename"
        return 1
    fi
}

# Rollback last N migrations
rollback_last() {
    local count=${1:-1}
    
    log_info "═══════════════════════════════════════════════════════════════"
    log_info "Rolling Back Last $count Migration(s)"
    log_info "═══════════════════════════════════════════════════════════════"
    echo ""
    
    MIGRATION_IN_PROGRESS=true
    
    # Acquire lock if not in dry-run mode
    if [ "$DRY_RUN" = false ]; then
        if ! acquire_lock; then
            log_error "Failed to acquire migration lock"
            MIGRATION_IN_PROGRESS=false
            return 1
        fi
    fi
    
    # Get last N migrations in reverse order
    local migrations=$(psql "$TIMESCALE_DSN" -t -c \
        "SELECT database_type, migration_file FROM $MIGRATIONS_TABLE ORDER BY applied_at DESC LIMIT $count" 2>/dev/null)
    
    if [ -z "$migrations" ]; then
        log_warning "No migrations to rollback"
        if [ "$DRY_RUN" = false ]; then
            release_lock
        fi
        MIGRATION_IN_PROGRESS=false
        return 0
    fi
    
    local rollback_failed=false
    
    echo "$migrations" | while IFS='|' read -r db_type filename; do
        # Trim whitespace
        db_type=$(echo "$db_type" | xargs)
        filename=$(echo "$filename" | xargs)
        
        if [ -z "$db_type" ] || [ -z "$filename" ]; then
            continue
        fi
        
        case "$db_type" in
            timescaledb|postgres)
                rollback_sql_migration "$db_type" "$filename" || rollback_failed=true
                ;;
            neo4j)
                rollback_neo4j_migration "$filename" || rollback_failed=true
                ;;
            chromadb)
                rollback_chromadb_migration "$filename" || rollback_failed=true
                ;;
            *)
                log_warning "Unknown database type: $db_type"
                ;;
        esac
    done
    
    # Release lock
    if [ "$DRY_RUN" = false ]; then
        release_lock
    fi
    
    MIGRATION_IN_PROGRESS=false
    
    echo ""
    if [ "$rollback_failed" = false ]; then
        log_success "Rollback complete"
        return 0
    else
        log_error "Rollback completed with some failures"
        log_info "Check the output above for details"
        return 1
    fi
}

# Validate migrations
validate_migrations() {
    log_info "Validating migrations..."
    local errors=0
    
    # Check for matching up/down pairs
    for db_type in timescaledb postgres; do
        local dir="$SCRIPT_DIR/$db_type"
        if [ -d "$dir" ]; then
            for up_file in "$dir"/*.up.sql; do
                if [ -f "$up_file" ]; then
                    local down_file="${up_file/.up./.down.}"
                    if [ ! -f "$down_file" ]; then
                        log_warning "Missing down migration: $(basename "$down_file")"
                        ((errors++))
                    fi
                fi
            done
        fi
    done
    
    # Check Neo4j
    for up_file in "$SCRIPT_DIR/neo4j"/*.up.cql; do
        if [ -f "$up_file" ]; then
            local down_file="${up_file/.up./.down.}"
            if [ ! -f "$down_file" ]; then
                log_warning "Missing down migration: $(basename "$down_file")"
                ((errors++))
            fi
        fi
    done
    
    # Check ChromaDB
    for up_file in "$SCRIPT_DIR/chromadb"/*.up.py; do
        if [ -f "$up_file" ]; then
            local down_file="${up_file/.up./.down.}"
            if [ ! -f "$down_file" ]; then
                log_warning "Missing down migration: $(basename "$down_file")"
                ((errors++))
            fi
        fi
    done
    
    if [ $errors -eq 0 ]; then
        log_success "All migrations validated successfully"
    else
        log_warning "Found $errors validation issue(s)"
    fi
}

# Show migration status
# Show database statistics
show_database_stats() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Database Statistics${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # PostgreSQL/TimescaleDB Statistics
    echo -e "${GREEN}PostgreSQL / TimescaleDB:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    local pg_stats=$(psql "$TIMESCALE_DSN" -t -c "
        SELECT 
            COUNT(*) as table_count,
            COALESCE(SUM(n_live_tup), 0) as total_rows
        FROM pg_stat_user_tables
        WHERE schemaname = 'public';
    ")
    
    if [ $? -eq 0 ] && [ -n "$pg_stats" ]; then
        read -r table_count total_rows <<< "$pg_stats"
        echo -e "  Tables:      ${table_count}"
        echo -e "  Total Rows:  ${total_rows}"
        echo ""
        
        echo "  Table Details:"
        psql "$TIMESCALE_DSN" -c "
            SELECT 
                schemaname as schema,
                relname as table_name,
                n_live_tup as rows,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as size
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC;
        "
    else
        echo -e "  ${RED}Could not retrieve PostgreSQL stats${NC}"
    fi
    
    echo ""
    
    # Neo4j Statistics
    echo -e "${GREEN}Neo4j:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    local neo4j_uri="${NEO4J_URI:-bolt://localhost:7687}"
    local neo4j_user="${NEO4J_USER:-neo4j}"
    local neo4j_pass="${NEO4J_PASSWORD:-password}"
    
    if command -v cypher-shell &> /dev/null; then
        local node_count=$(cypher-shell -a "$neo4j_uri" -u "$neo4j_user" -p "$neo4j_pass" \
            "MATCH (n) RETURN count(n) as count" --format plain 2>/dev/null | tail -n 1)
        local rel_count=$(cypher-shell -a "$neo4j_uri" -u "$neo4j_user" -p "$neo4j_pass" \
            "MATCH ()-[r]->() RETURN count(r) as count" --format plain 2>/dev/null | tail -n 1)
        
        if [ -n "$node_count" ] && [ -n "$rel_count" ]; then
            echo -e "  Nodes:         ${node_count}"
            echo -e "  Relationships: ${rel_count}"
            echo ""
            
            echo "  Node Labels:"
            cypher-shell -a "$neo4j_uri" -u "$neo4j_user" -p "$neo4j_pass" \
                "CALL db.labels() YIELD label RETURN label ORDER BY label" 2>/dev/null || echo "    (unable to retrieve)"
        else
            echo -e "  ${YELLOW}Could not retrieve Neo4j stats (check connection)${NC}"
        fi
    else
        echo -e "  ${YELLOW}cypher-shell not installed - skipping Neo4j stats${NC}"
        echo -e "  ${YELLOW}Install with: brew install cypher-shell (macOS)${NC}"
    fi
    
    echo ""
    
    # ChromaDB Statistics
    echo -e "${GREEN}ChromaDB:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    local chroma_host="${CHROMA_HOST:-localhost}"
    local chroma_port="${CHROMA_PORT:-8000}"
    
    if command -v python3 &> /dev/null; then
        python3 << EOF 2>/dev/null
import os
import sys
try:
    from chromadb import HttpClient
    
    host = os.getenv("CHROMA_HOST", "$chroma_host")
    port = int(os.getenv("CHROMA_PORT", "$chroma_port"))
    
    client = HttpClient(host=host, port=port)
    collections = client.list_collections()
    
    print(f"  Collections: {len(collections)}")
    print()
    
    if collections:
        print("  Collection Details:")
        print("  ┌─────────────────────────────────┬───────────┐")
        print("  │ Collection Name                  │ Documents │")
        print("  ├─────────────────────────────────┼───────────┤")
        for col in collections:
            count = col.count()
            name = col.name[:30].ljust(30)
            print(f"  │ {name} │ {str(count).rjust(9)} │")
        print("  └─────────────────────────────────┴───────────┘")
    else:
        print("  No collections found")
        
except Exception as e:
    print(f"  Could not retrieve ChromaDB stats: {e}", file=sys.stderr)
    sys.exit(1)
EOF
        if [ $? -ne 0 ]; then
            echo -e "  ${YELLOW}Could not retrieve ChromaDB stats (check connection)${NC}"
        fi
    else
        echo -e "  ${YELLOW}python3 not available - skipping ChromaDB stats${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

show_status() {
    log_info "Migration Status"
    echo ""
    
    echo "Applied Migrations:"
    psql "$TIMESCALE_DSN" -c \
        "SELECT database_type, migration_file, applied_at FROM $MIGRATIONS_TABLE ORDER BY applied_at DESC LIMIT 20;"
    
    echo ""
    echo "Pending Migrations:"
    
    # Check each database type
    for db_type in timescaledb postgres neo4j chromadb; do
        local dir="$SCRIPT_DIR/$db_type"
        if [ -d "$dir" ]; then
            local ext="up.sql"
            [ "$db_type" = "neo4j" ] && ext="up.cql"
            [ "$db_type" = "chromadb" ] && ext="up.py"
            
            for file in $(ls "$dir"/*.$ext 2>/dev/null | sort -V); do
                local filename=$(basename "$file")
                if ! is_applied "$db_type" "$filename"; then
                    echo "  - $db_type/$filename"
                fi
            done
        fi
    done
}

# Show full migration history
show_history() {
    local limit="${1:-50}"
    
    log_info "Migration History (last $limit actions)"
    echo ""
    
    psql "$TIMESCALE_DSN" -c \
        "SELECT 
            database_type,
            migration_file,
            action,
            applied_at,
            execution_time_ms || 'ms' as duration,
            CASE WHEN success THEN '✓' ELSE '✗' END as status,
            error_message
         FROM migration_history 
         ORDER BY applied_at DESC 
         LIMIT $limit;"
    
    echo ""
    log_info "Statistics:"
    
    psql "$TIMESCALE_DSN" -c \
        "SELECT 
            action,
            COUNT(*) as total,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed,
            ROUND(AVG(execution_time_ms)) || 'ms' as avg_time
         FROM migration_history 
         GROUP BY action
         ORDER BY action;"
}

# Fresh install (drop all tables and rerun)
fresh_install() {
    log_warning "═══════════════════════════════════════════════════════════════"
    log_warning "FRESH INSTALL MODE - ALL DATA & MIGRATION HISTORY WILL BE DELETED"
    log_warning "═══════════════════════════════════════════════════════════════"
    echo ""
    read -p "Are you absolutely sure? Type 'DELETE ALL DATA' to confirm: " confirm
    
    if [ "$confirm" != "DELETE ALL DATA" ]; then
        log_info "Aborted."
        exit 0
    fi
    
    log_info "Dropping all tables (including migration tracking)..."
    
    # Dynamically get all tables in the public schema
    local tables=$(psql "$TIMESCALE_DSN" -t -c \
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")
    
    if [ -n "$tables" ]; then
        local table_count=$(echo "$tables" | wc -w | xargs)
        log_info "Found $table_count tables to drop..."
        
        # Drop tables one by one (handles TimescaleDB hypertables correctly)
        for table in $tables; do
            psql "$TIMESCALE_DSN" -c "DROP TABLE IF EXISTS $table CASCADE;" > /dev/null 2>&1
        done
        
        log_success "All $table_count tables dropped"
    else
        log_info "No tables found to drop"
    fi
    
    # Verify all tables are gone
    local remaining=$(psql "$TIMESCALE_DSN" -t -c \
        "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';")
    remaining=$(echo "$remaining" | xargs)
    
    if [ "$remaining" != "0" ]; then
        log_warning "Warning: $remaining tables still remain"
    fi
    
    # Initialize migration tracking tables
    log_info "Creating migration tracking tables..."
    init_migrations_table
    
    # Run all migrations
    log_info "Running all migrations..."
    migrate_up
}

# Run pending migrations
migrate_up() {
    log_info "═══════════════════════════════════════════════════════════════"
    log_info "Running Migrations"
    log_info "═══════════════════════════════════════════════════════════════"
    echo ""
    
    MIGRATION_IN_PROGRESS=true
    
    # Acquire lock if not in dry-run mode
    if [ "$DRY_RUN" = false ]; then
        if ! acquire_lock; then
            log_error "Failed to acquire migration lock"
            MIGRATION_IN_PROGRESS=false
            return 1
        fi
    fi
    
    # Run in dependency order
    local migration_failed=false
    
    run_sql_migrations "timescaledb" || migration_failed=true
    echo ""
    
    if [ "$migration_failed" = false ]; then
        run_sql_migrations "postgres" || migration_failed=true
        echo ""
    fi
    
    if [ "$migration_failed" = false ]; then
        run_neo4j_migrations || migration_failed=true
        echo ""
    fi
    
    if [ "$migration_failed" = false ]; then
        run_chromadb_migrations || migration_failed=true
    fi
    
    # Release lock
    if [ "$DRY_RUN" = false ]; then
        release_lock
    fi
    
    MIGRATION_IN_PROGRESS=false
    
    echo ""
    if [ "$migration_failed" = false ]; then
        log_success "═══════════════════════════════════════════════════════════════"
        log_success "Migration Complete!"
        log_success "═══════════════════════════════════════════════════════════════"
        return 0
    else
        log_error "═══════════════════════════════════════════════════════════════"
        log_error "Migration Failed - Some migrations did not complete"
        log_error "═══════════════════════════════════════════════════════════════"
        log_info "Run './migrate.sh status' to see what was applied"
        return 1
    fi
}


# Interactive menu
show_menu() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Migration Manager - Main Menu${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "1) Run pending migrations (up)"
    echo "2) Preview pending migrations (up --dry-run)"
    echo "3) Rollback last migration (down)"
    echo "4) Rollback multiple migrations (down N)"
    echo "5) Show migration status"
    echo "6) Show migration history"
    echo "7) Show database statistics"
    echo "8) Validate migration files"
    echo "9) Force unlock migration lock"
    echo "10) Fresh install (DESTRUCTIVE)"
    echo "0) Exit"
    echo ""
    read -p "Select an option [0-10]: " choice
    echo ""
    
    case "$choice" in
        1)
            migrate_up
            ;;
        2)
            DRY_RUN=true
            migrate_up
            DRY_RUN=false
            ;;
        3)
            rollback_last 1
            ;;
        4)
            read -p "How many migrations to rollback? " count
            rollback_last "$count"
            ;;
        5)
            show_status
            ;;
        6)
            read -p "How many history entries to show? [50]: " limit
            limit=${limit:-50}
            show_history "$limit"
            ;;
        7)
            show_database_stats
            ;;
        8)
            validate_migrations
            ;;
        9)
            force_unlock
            ;;
        10)
            fresh_install
            ;;
        0)
            log_info "Exiting..."
            exit 0
            ;;
        *)
            log_error "Invalid option: $choice"
            ;;
    esac
    
    # Always return to menu (unless option 0 was selected to exit)
    echo ""
    echo -e "${BLUE}Press Enter to continue...${NC}"
    read -r
    show_menu
}

# Interactive mode
interactive_mode() {
    log_info "═══════════════════════════════════════════════════════════════"
    log_info "Migration Manager - Interactive Mode"
    log_info "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Initialize connection and tables
    if ! check_env; then
        log_error "Failed to connect to database"
        exit 1
    fi
    
    init_migrations_table
    echo ""
    
    # Show current status
    log_info "Current Migration Status:"
    echo ""
    show_status
    
    # Show menu
    show_menu
}

# Main command dispatcher
if [ $# -eq 0 ]; then
    # No arguments - run interactive mode
    interactive_mode
else
    # Command-line mode
    case "${1}" in
        up)
            [ "${2}" = "--dry-run" ] && DRY_RUN=true
            check_env
            init_migrations_table
            migrate_up
            ;;
        
        down)
            [ "${3}" = "--dry-run" ] && DRY_RUN=true
            check_env
            init_migrations_table
            rollback_last "${2:-1}"
            ;;
        
        fresh|reset)
            check_env
            fresh_install
            ;;
        
        status)
            check_env
            init_migrations_table
            show_status
            ;;
        
        stats|statistics)
            check_env
            show_database_stats
            ;;
        
        history)
            check_env
            init_migrations_table
            show_history "${2:-50}"
            ;;
        
        validate)
            validate_migrations
            ;;
        
        unlock)
            check_env
            force_unlock
            ;;
        
        init)
            check_env
            init_migrations_table
            log_success "Migration tracking initialized"
            ;;
        
        menu|interactive)
            interactive_mode
            ;;
        
        help|--help|-h)
            echo "Migration Manager - Database schema migration tool"
            echo ""
            echo "Usage: $0 [command] [options]"
            echo ""
            echo "Commands:"
            echo "  (no command)             Interactive mode with menu (default)"
            echo "  up [--dry-run]           Run pending migrations"
            echo "  down [N] [--dry-run]     Rollback last N migrations (default: 1)"
            echo "  fresh                    Drop data tables, clear history, rerun migrations (DESTRUCTIVE)"
            echo "  status                   Show migration status"
            echo "  stats                    Show database statistics (tables, rows, sizes)"
            echo "  history [N]              Show migration history (default: last 50)"
            echo "  validate                 Validate migration files"
            echo "  unlock                   Force release migration lock"
            echo "  init                     Initialize migration tracking only"
            echo "  menu                     Launch interactive menu"
            echo "  help                     Show this help message"
            echo ""
            echo "Options:"
            echo "  --dry-run                Show what would be executed without running"
            echo ""
            echo "Environment Variables:"
            echo "  TIMESCALE_DSN            PostgreSQL/TimescaleDB connection string (optional)"
            echo "  NEO4J_URI                Neo4j connection URI (optional, default: bolt://localhost:7687)"
            echo "  NEO4J_USER               Neo4j username (optional, default: neo4j)"
            echo "  NEO4J_PASSWORD           Neo4j password (optional, default: password)"
            echo "  CHROMA_HOST              ChromaDB host (optional, default: localhost)"
            echo "  CHROMA_PORT              ChromaDB port (optional, default: 8000)"
            echo ""
            echo "Examples:"
            echo "  $0                       # Interactive mode"
            echo "  $0 up                    # Run pending migrations"
            echo "  $0 up --dry-run          # Preview pending migrations"
            echo "  $0 down                  # Rollback last migration"
            echo "  $0 down 3                # Rollback last 3 migrations"
            echo "  $0 down --dry-run        # Preview rollback"
            echo "  $0 status                # Check what's applied"
            echo "  $0 stats                 # Show database statistics"
            echo "  $0 history               # Show last 50 migration actions"
            echo "  $0 history 100           # Show last 100 migration actions"
            echo "  $0 validate              # Validate migration files"
            echo "  $0 unlock                # Force release stale lock"
            echo "  $0 fresh                 # Fresh install (DESTRUCTIVE)"
            echo ""
            ;;
        
        *)
            log_error "Unknown command: $1"
            echo "Run '$0 help' for usage information"
            echo "Or run '$0' without arguments for interactive mode"
            exit 1
            ;;
    esac
fi

