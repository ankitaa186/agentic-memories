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
NC='\033[0m' # No Color

echo "[agentic-memories] Starting Docker stack..."

# Ensure Docker is available and the daemon is running
# Check Loki Docker plugin (for production mode)
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

# Validate production environment variables
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

# Create .env from template if missing
if [ ! -f .env ]; then
  echo "No .env found. Creating from env.example..."
  if [ -f env.example ]; then
    cp env.example .env
    chmod 600 .env 2>/dev/null || true
    echo -e "${YELLOW}Please set your OPENAI_API_KEY in .env before using the API.${NC}"
  else
    echo "No .env found. Let's create one. Press Enter to accept defaults."
    read -r -p "OPENAI_API_KEY [leave blank to skip]: " INPUT_OPENAI_API_KEY || true

    {
      printf "OPENAI_API_KEY=%s\n" "${INPUT_OPENAI_API_KEY:-}"
      printf "CHROMA_HOST=chromadb\n"
      printf "CHROMA_PORT=8000\n"
      printf "CHROMA_TENANT=agentic-memories\n"
      printf "CHROMA_DATABASE=memories\n"
      printf "REDIS_URL=redis://redis:6379/0\n"
      printf "TIMESCALE_DSN=postgresql://user:pass@timescaledb:5432/agentic_memories\n"
    } > .env
    chmod 600 .env 2>/dev/null || true
  fi
  echo -e "${GREEN}✓ .env created${NC}"
fi

# Load .env into environment for this run (compose also reads it)
if [ -f .env ]; then
  set +u
  set -a
  . ./.env
  set +a
  set -u
fi

# Environment detection: ENV shell variable > ENVIRONMENT from .env > default "dev"
# This allows ENVIRONMENT=prod in .env for persistent production mode
if [ -z "${ENV:-}" ]; then
    ENV="${ENVIRONMENT:-dev}"
fi
export ENV

# Hint when OPENAI_API_KEY is not set
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "Warning: OPENAI_API_KEY is not set. The API may fail to call OpenAI until it's configured." >&2
fi

# Create persistent data directories
mkdir -p ./data/timescaledb ./data/chromadb
echo -e "${GREEN}✓ Data directories ready (./data/)${NC}"

# ChromaDB configuration
export CHROMA_HOST="${CHROMA_HOST:-localhost}"
export CHROMA_PORT="${CHROMA_PORT:-8000}"
export CHROMA_TENANT="${CHROMA_TENANT:-agentic-memories}"
export CHROMA_DATABASE="${CHROMA_DATABASE:-memories}"

# Function to check ChromaDB health
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

# Function to check and create required database and collection
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

  # If database doesn't exist, prompt to create it
  if [ "$database_exists" = false ]; then
    echo -n "Create the database '${CHROMA_DATABASE}'? (y/N): "
    read -r create_db </dev/tty
    if [[ "$create_db" =~ ^[Yy]$ ]]; then
      echo "Creating database '${CHROMA_DATABASE}'..."
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
    else
      echo "Skipping database creation. Exiting."
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
    echo "Collection '${required_collection}' does not exist in database '${CHROMA_DATABASE}'"

    echo -n "Create the collection '${required_collection}'? (y/N): "
    read -r create_collection </dev/tty
    if [[ "$create_collection" =~ ^[Yy]$ ]]; then
      echo "Creating collection '${required_collection}'..."
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
    else
      echo "Skipping collection creation. Exiting."
      return 1
    fi
  fi
}

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

# ── Step 3: Start application services ──
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


