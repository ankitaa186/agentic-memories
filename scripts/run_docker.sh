#!/usr/bin/env bash
#
# Run Docker stack for Agentic Memories
#
# Usage:
#   ./scripts/run_docker.sh           # Uses ENVIRONMENT from .env (or dev if unset)
#   ENV=prod ./scripts/run_docker.sh  # Force production mode
#   ENV=dev ./scripts/run_docker.sh   # Force development mode

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# ════════════════════════════════════════════════════════════════════════════════
# Helper functions
# ════════════════════════════════════════════════════════════════════════════════

# Check if a value looks like an unedited placeholder
is_placeholder() {
    local val="$1"
    case "$val" in
        ""|sk-REPLACE_ME|xai-REPLACE_ME|xaikey-REPLACE_ME|REPLACE_ME|sk-your_*|xai-your_*|changeme_*)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# ════════════════════════════════════════════════════════════════════════════════
# First-time interactive setup wizard
# ════════════════════════════════════════════════════════════════════════════════

run_first_time_setup() {
    echo ""
    echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}   Welcome to Agentic Memories!${NC}"
    echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Looks like this is your first time running the project."
    echo -e "  Let's get you set up. This will only take a moment."
    echo ""

    # ── Step 1: Check prerequisites ──────────────────────────────────────────
    echo -e "${BOLD}Checking prerequisites...${NC}"
    echo ""

    local prereqs_ok=true

    # Docker
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Docker is installed and running"
    else
        echo -e "  ${RED}✗${NC} Docker is not installed or not running"
        echo -e "    ${DIM}Install from https://docs.docker.com/get-docker/${NC}"
        prereqs_ok=false
    fi

    # Docker Compose
    if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Docker Compose is available"
    else
        echo -e "  ${RED}✗${NC} Docker Compose is not available"
        echo -e "    ${DIM}Install Docker Desktop (includes Compose) or install separately${NC}"
        prereqs_ok=false
    fi

    # psql
    if command -v psql >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} psql (PostgreSQL client) is installed"
    else
        echo -e "  ${YELLOW}!${NC} psql not found — database migrations will be skipped on startup"
        echo -e "    ${DIM}Install: brew install postgresql (macOS) or apt install postgresql-client (Linux)${NC}"
    fi

    # curl
    if command -v curl >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} curl is installed"
    else
        echo -e "  ${RED}✗${NC} curl is not installed"
        prereqs_ok=false
    fi

    echo ""

    if [ "$prereqs_ok" = false ]; then
        echo -e "${RED}Some required prerequisites are missing. Please install them and try again.${NC}"
        exit 1
    fi

    # ── Step 2: OpenAI API key (always required — used for embeddings) ─────
    echo -e "${BOLD}Step 1/2: Enter your OpenAI API key${NC}"
    echo -e "  ${DIM}Required for embeddings (text-embedding-3-large) and extraction.${NC}"
    echo -e "  ${DIM}Get one at: https://platform.openai.com/api-keys${NC}"
    echo ""

    local OPENAI_KEY=""
    while true; do
        read -r -p "  OPENAI_API_KEY: " OPENAI_KEY </dev/tty
        if [ -z "$OPENAI_KEY" ]; then
            echo -e "  ${RED}API key cannot be empty.${NC}"
        elif is_placeholder "$OPENAI_KEY"; then
            echo -e "  ${RED}That looks like a placeholder. Please enter your real API key.${NC}"
        else
            break
        fi
    done
    echo -e "  ${GREEN}✓${NC} OpenAI API key set (${OPENAI_KEY:0:8}...)"
    echo ""

    # ── Optional: xAI/Grok for extraction ─────────────────────────────────
    local LLM_PROVIDER="openai"
    local XAI_KEY=""

    echo -e "  ${DIM}Want to use xAI/Grok instead of GPT-4o for memory extraction?${NC}"
    echo -e "  ${DIM}(OpenAI is still used for embeddings either way.)${NC}"
    read -r -p "  Use xAI for extraction? (y/N): " use_xai </dev/tty
    if [[ "${use_xai:-}" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "  ${DIM}Get a key at: https://console.x.ai/${NC}"
        while true; do
            read -r -p "  XAI_API_KEY: " XAI_KEY </dev/tty
            if [ -z "$XAI_KEY" ]; then
                echo -e "  ${RED}API key cannot be empty.${NC}"
            elif is_placeholder "$XAI_KEY"; then
                echo -e "  ${RED}That looks like a placeholder. Please enter your real API key.${NC}"
            else
                break
            fi
        done
        LLM_PROVIDER="xai"
        echo -e "  ${GREEN}✓${NC} xAI API key set (${XAI_KEY:0:8}...)"
    else
        echo -e "  ${GREEN}✓${NC} Using OpenAI for extraction"
    fi
    echo ""

    # ── Optional: Langfuse observability ──────────────────────────────────
    local LANGFUSE_PK=""
    local LANGFUSE_SK=""
    local LANGFUSE_HOST_VAL=""

    echo -e "  ${DIM}Langfuse provides LLM tracing and observability.${NC}"
    echo -e "  ${DIM}(Free tier available at https://cloud.langfuse.com)${NC}"
    read -r -p "  Enable Langfuse tracing? (y/N): " use_langfuse </dev/tty
    if [[ "${use_langfuse:-}" =~ ^[Yy]$ ]]; then
        echo ""
        while true; do
            read -r -p "  LANGFUSE_PUBLIC_KEY: " LANGFUSE_PK </dev/tty
            if [ -z "$LANGFUSE_PK" ]; then
                echo -e "  ${RED}Public key cannot be empty.${NC}"
            else
                break
            fi
        done
        while true; do
            read -r -p "  LANGFUSE_SECRET_KEY: " LANGFUSE_SK </dev/tty
            if [ -z "$LANGFUSE_SK" ]; then
                echo -e "  ${RED}Secret key cannot be empty.${NC}"
            else
                break
            fi
        done
        read -r -p "  LANGFUSE_HOST [https://us.cloud.langfuse.com]: " LANGFUSE_HOST_VAL </dev/tty
        LANGFUSE_HOST_VAL="${LANGFUSE_HOST_VAL:-https://us.cloud.langfuse.com}"
        echo -e "  ${GREEN}✓${NC} Langfuse enabled"
    else
        echo -e "  ${GREEN}✓${NC} Skipping Langfuse (can add later in .env)"
    fi
    echo ""

    # ── Step 3: Database password ────────────────────────────────────────────
    echo -e "${BOLD}Step 2/2: Set a database password${NC}"
    echo -e "  ${DIM}This password is used for the local TimescaleDB instance.${NC}"
    echo -e "  ${DIM}Press Enter to use the default (changeme).${NC}"
    echo ""

    local DB_PASSWORD=""
    read -r -p "  POSTGRES_PASSWORD [changeme]: " DB_PASSWORD </dev/tty
    DB_PASSWORD="${DB_PASSWORD:-changeme}"
    echo -e "  ${GREEN}✓${NC} Database password set"
    echo ""

    # ── Write .env file ──────────────────────────────────────────────────────
    echo -e "${BOLD}Writing .env file...${NC}"

    {
        echo "# Generated by first-time setup — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        echo "# Edit this file to change settings, then run: make start"
        echo ""
        echo "LLM_PROVIDER=${LLM_PROVIDER}"
        echo "OPENAI_API_KEY=${OPENAI_KEY}"
        if [ -n "$XAI_KEY" ]; then
            echo "XAI_API_KEY=${XAI_KEY}"
            echo "XAI_BASE_URL=https://api.x.ai/v1"
        fi
        echo ""
        echo "POSTGRES_PASSWORD=${DB_PASSWORD}"
        if [ -n "$LANGFUSE_PK" ]; then
            echo ""
            echo "LANGFUSE_PUBLIC_KEY=${LANGFUSE_PK}"
            echo "LANGFUSE_SECRET_KEY=${LANGFUSE_SK}"
            echo "LANGFUSE_HOST=${LANGFUSE_HOST_VAL}"
        fi
    } > .env
    chmod 600 .env 2>/dev/null || true

    echo -e "  ${GREEN}✓${NC} .env created"
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "  Setup complete! Starting services..."
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ════════════════════════════════════════════════════════════════════════════════
# Validate required environment variables (runs on every start)
# ════════════════════════════════════════════════════════════════════════════════

validate_env() {
    local errors=0

    echo -e "${BOLD}Validating environment...${NC}"

    # LLM_PROVIDER
    local provider="${LLM_PROVIDER:-}"
    if [ -z "$provider" ]; then
        echo -e "  ${RED}✗${NC} LLM_PROVIDER is not set (must be 'openai' or 'xai')"
        errors=$((errors + 1))
    elif [ "$provider" != "openai" ] && [ "$provider" != "xai" ] && [ "$provider" != "grok" ]; then
        echo -e "  ${RED}✗${NC} LLM_PROVIDER='${provider}' is not valid (must be 'openai' or 'xai')"
        errors=$((errors + 1))
    else
        echo -e "  ${GREEN}✓${NC} LLM_PROVIDER=${provider}"
    fi

    # OPENAI_API_KEY is always required (embeddings use OpenAI)
    local oai_key="${OPENAI_API_KEY:-}"
    if [ -z "$oai_key" ]; then
        echo -e "  ${RED}✗${NC} OPENAI_API_KEY is not set (required for embeddings)"
        errors=$((errors + 1))
    elif is_placeholder "$oai_key"; then
        echo -e "  ${RED}✗${NC} OPENAI_API_KEY is still a placeholder — edit .env with your real key"
        errors=$((errors + 1))
    else
        echo -e "  ${GREEN}✓${NC} OPENAI_API_KEY is set (${oai_key:0:8}...)"
    fi

    # XAI_API_KEY is required only when using xAI for extraction
    if [ "$provider" = "xai" ] || [ "$provider" = "grok" ]; then
        local xai_key="${XAI_API_KEY:-}"
        if [ -z "$xai_key" ]; then
            echo -e "  ${RED}✗${NC} XAI_API_KEY is not set (required when LLM_PROVIDER=xai)"
            errors=$((errors + 1))
        elif is_placeholder "$xai_key"; then
            echo -e "  ${RED}✗${NC} XAI_API_KEY is still a placeholder — edit .env with your real key"
            errors=$((errors + 1))
        else
            echo -e "  ${GREEN}✓${NC} XAI_API_KEY is set (${xai_key:0:8}...)"
        fi
    fi

    # POSTGRES_PASSWORD (warn if default, don't block)
    local pg_pw="${POSTGRES_PASSWORD:-changeme}"
    if [ "$pg_pw" = "changeme" ]; then
        echo -e "  ${YELLOW}!${NC} POSTGRES_PASSWORD is using the default ('changeme')"
    else
        echo -e "  ${GREEN}✓${NC} POSTGRES_PASSWORD is set"
    fi

    echo ""

    if [ "$errors" -gt 0 ]; then
        echo -e "${RED}Found ${errors} configuration error(s). Please fix your .env file and try again.${NC}"
        echo -e "${DIM}  Edit directly:  \$EDITOR .env${NC}"
        echo -e "${DIM}  Or delete it to re-run setup:  rm .env && make start${NC}"
        exit 1
    fi

    echo -e "${GREEN}Environment OK${NC}"
}

# ════════════════════════════════════════════════════════════════════════════════
# Loki / production helpers (unchanged)
# ════════════════════════════════════════════════════════════════════════════════

check_loki_plugin() {
    if ! docker plugin ls 2>/dev/null | grep -q "loki.*true"; then
        echo -e "${RED}Error: Loki Docker plugin not installed or not enabled${NC}"
        echo ""
        echo "Install with:"
        echo "  docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions"
        echo ""
        echo "Or run in dev mode: ENV=dev make start"
        exit 1
    fi
    echo -e "${GREEN}✓ Loki Docker plugin installed${NC}"
}

validate_prod_env() {
    if [ -z "${LOKI_URL:-}" ] || [ "${LOKI_URL:-}" = "REPLACE_ME" ]; then
        echo -e "${RED}Error: LOKI_URL required for production mode${NC}"
        echo ""
        echo "Set in .env:"
        echo "  LOKI_URL=https://<user-id>:<api-key>@logs-prod-us-central1.grafana.net/loki/api/v1/push"
        echo ""
        echo "Or run in dev mode: ENV=dev make start"
        exit 1
    fi
    echo -e "${GREEN}✓ LOKI_URL configured${NC}"
}

# ════════════════════════════════════════════════════════════════════════════════
# ChromaDB pre-flight helpers
# ════════════════════════════════════════════════════════════════════════════════

check_chroma_health() {
    local max_retries=10
    local retry_count=0

    echo "Checking ChromaDB health at localhost:${CHROMA_PORT}..."

    while [ $retry_count -lt $max_retries ]; do
        if curl -f -s "http://localhost:${CHROMA_PORT}/api/v2/heartbeat" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ ChromaDB is healthy${NC}"
            return 0
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "ChromaDB not ready (attempt $retry_count/$max_retries), retrying in 3s..."
            sleep 3
        fi
    done

    echo -e "${RED}Error: ChromaDB is not available after $max_retries attempts${NC}" >&2
    return 1
}

check_required_collections() {
    local required_collection="memories_3072"  # Based on text-embedding-3-large (3072 dims)
    local api_url="http://localhost:${CHROMA_PORT}/api/v2"

    echo "Checking ChromaDB database and collections..."

    # Check if the database exists
    local databases_response
    databases_response=$(curl -s "${api_url}/tenants/${CHROMA_TENANT}/databases" 2>/dev/null)

    local database_exists=false
    if echo "$databases_response" | grep -q "\"name\"[[:space:]]*:[[:space:]]*\"${CHROMA_DATABASE}\""; then
        database_exists=true
        echo -e "${GREEN}✓ Database '${CHROMA_DATABASE}' exists${NC}"
    else
        echo "Database '${CHROMA_DATABASE}' does not exist in tenant '${CHROMA_TENANT}'"
    fi

    # Auto-create database if it doesn't exist
    if [ "$database_exists" = false ]; then
        echo "Auto-creating database '${CHROMA_DATABASE}'..."
        local create_db_response
        create_db_response=$(curl -s -X POST "${api_url}/tenants/${CHROMA_TENANT}/databases" \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"${CHROMA_DATABASE}\"}" 2>/dev/null)

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Database '${CHROMA_DATABASE}' created${NC}"
            database_exists=true
        else
            echo -e "${RED}Error: Failed to create database '${CHROMA_DATABASE}'${NC}" >&2
            echo "Response: $create_db_response" >&2
            return 1
        fi
    fi

    # Check if the required collection exists
    local collections_response
    collections_response=$(curl -s "${api_url}/tenants/${CHROMA_TENANT}/databases/${CHROMA_DATABASE}/collections" 2>/dev/null)

    if echo "$collections_response" | grep -q "\"name\"[[:space:]]*:[[:space:]]*\"${required_collection}\""; then
        echo -e "${GREEN}✓ Collection '${required_collection}' found${NC}"
        return 0
    else
        echo "Auto-creating collection '${required_collection}'..."
        local create_col_response
        create_col_response=$(curl -s -X POST "${api_url}/tenants/${CHROMA_TENANT}/databases/${CHROMA_DATABASE}/collections" \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"${required_collection}\", \"metadata\": {\"created_by\": \"agentic-memories\"}}" 2>/dev/null)

        if [ $? -eq 0 ] && echo "$create_col_response" | grep -q "\"name\"[[:space:]]*:[[:space:]]*\"${required_collection}\""; then
            echo -e "${GREEN}✓ Collection '${required_collection}' created${NC}"
            return 0
        else
            echo -e "${RED}Error: Failed to create collection '${required_collection}'${NC}" >&2
            echo "Response: $create_col_response" >&2
            return 1
        fi
    fi
}

# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

echo "[agentic-memories] Starting Docker stack..."

# ── Pre-flight: Docker checks ────────────────────────────────────────────────

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not in PATH." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: docker daemon not running. Start Docker and retry." >&2
    exit 1
fi

# Determine docker compose command
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "Error: docker compose not found (neither 'docker compose' nor 'docker-compose')." >&2
    exit 1
fi

# ── First-time setup: interactive wizard when .env is missing ────────────────

if [ ! -f .env ]; then
    run_first_time_setup
fi

# ── Load .env ────────────────────────────────────────────────────────────────

if [ -f .env ]; then
    set +u
    set -a
    . ./.env
    set +a
    set -u
fi

# ── Validate required environment variables ──────────────────────────────────

validate_env

# ── Environment / mode detection ─────────────────────────────────────────────

if [ -z "${ENV:-}" ]; then
    ENV="${ENVIRONMENT:-dev}"
fi
export ENV

# ── Create persistent data directories ───────────────────────────────────────

mkdir -p ./data/timescaledb ./data/chromadb
echo -e "${GREEN}✓ Data directories ready (./data/)${NC}"

# ChromaDB configuration — local vars for host-side health checks only.
# .env was sourced with `set -a`, so CHROMA_HOST may be exported as "chromadb".
# Unexport it so "localhost" (needed for host-side curl checks) does not leak
# into docker compose and override the container-internal service name.
unset CHROMA_HOST
CHROMA_HOST="localhost"
CHROMA_PORT="${CHROMA_PORT:-8000}"
CHROMA_TENANT="${CHROMA_TENANT:-agentic-memories}"
CHROMA_DATABASE="${CHROMA_DATABASE:-memories}"

# ── Step 1: Start infrastructure services (databases) ──
echo ""
echo -e "${GREEN}Starting infrastructure services (TimescaleDB, ChromaDB, Redis)...${NC}"
if [ "$ENV" = "prod" ]; then
    check_loki_plugin
    validate_prod_env
    ${COMPOSE_CMD} -f docker-compose.yml -f docker-compose.prod.yml up -d --build timescaledb chromadb redis
else
    ${COMPOSE_CMD} up -d --build timescaledb chromadb redis
fi

# ── Step 2: Pre-flight checks on ChromaDB ──
if ! check_chroma_health; then
    exit 1
fi

if ! check_required_collections; then
    exit 1
fi

# ── Step 3: Run database migrations ──
echo ""
echo -e "${GREEN}Running database migrations...${NC}"
MIGRATE_DSN="postgresql://postgres:${POSTGRES_PASSWORD:-changeme}@localhost:5432/agentic_memories"
if command -v psql >/dev/null 2>&1; then
    set +e
    TIMESCALE_DSN="$MIGRATE_DSN" \
    CHROMA_HOST=localhost \
    CHROMA_PORT="${CHROMA_PORT:-8000}" \
    CHROMA_TENANT="${CHROMA_TENANT:-agentic-memories}" \
    CHROMA_DATABASE="${CHROMA_DATABASE:-memories}" \
        bash "$(dirname "$0")/../migrations/migrate.sh" up
    migrate_exit=$?
    set -e

    if [ $migrate_exit -ne 0 ]; then
        # Check if failure was due to a stale migration lock
        lock_status=$(docker exec agentic-memories-timescaledb-1 \
            psql -U postgres -d agentic_memories -t -A -c \
            "SELECT locked FROM migration_lock WHERE id = 1;" 2>/dev/null || echo "unknown")

        if [ "$lock_status" = "t" ]; then
            echo -e "${YELLOW}Migration lock is stuck — force-releasing and retrying...${NC}"
            docker exec agentic-memories-timescaledb-1 \
                psql -U postgres -d agentic_memories -c \
                "UPDATE migration_lock SET locked = FALSE, locked_by = NULL, locked_at = NULL, process_id = NULL WHERE id = 1;" \
                >/dev/null 2>&1
            echo -e "${GREEN}Lock released. Retrying migrations...${NC}"

            TIMESCALE_DSN="$MIGRATE_DSN" \
            CHROMA_HOST=localhost \
            CHROMA_PORT="${CHROMA_PORT:-8000}" \
            CHROMA_TENANT="${CHROMA_TENANT:-agentic-memories}" \
            CHROMA_DATABASE="${CHROMA_DATABASE:-memories}" \
                bash "$(dirname "$0")/../migrations/migrate.sh" up
        else
            echo -e "${RED}Migration failed (not a lock issue). See errors above.${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}Warning: psql not found — skipping auto-migrations.${NC}"
    echo -e "${YELLOW}Install psql to enable, or run manually: make migrate${NC}"
fi

# ── Step 4: Start application services ──
echo ""
if [ "$ENV" = "prod" ]; then
    echo -e "${GREEN}Starting application services (${YELLOW}production${GREEN} mode)...${NC}"
    ${COMPOSE_CMD} -f docker-compose.yml -f docker-compose.prod.yml up -d --build api ui
    echo ""
    echo -e "${GREEN}✓ Services started with Loki logging enabled${NC}"
    echo "View logs at: https://grafana.com (your Grafana Cloud stack)"
else
    echo -e "${GREEN}Starting application services (${YELLOW}development${GREEN} mode)...${NC}"
    ${COMPOSE_CMD} up -d --build api ui
fi

echo ""
echo "[agentic-memories] Services started with restart policy 'unless-stopped'."
echo "- API:          http://localhost:8080"
echo "- UI:           http://localhost:3000"
echo "- TimescaleDB:  localhost:5432"
echo "- ChromaDB:     http://localhost:8000"
echo "- Redis:        localhost:6379"
echo "- Data:         ./data/"

echo ""
echo "Logs (follow) -> ${COMPOSE_CMD} logs -f"
echo "Stop services  -> ${COMPOSE_CMD} down"
echo ""
echo "Done."
