#!/usr/bin/env bash

set -euo pipefail

echo "[agentic-memories] Starting Docker stack..."

# Ensure Docker is available and the daemon is running
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

# Create .env interactively if missing
if [ ! -f .env ]; then
  echo "No .env found. Let's create one. Press Enter to accept defaults."

  # Detect sensible default for CHROMA_HOST (primary IPv4)
  DETECTED_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}') || true
  if [ -z "${DETECTED_IP:-}" ]; then
    DETECTED_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  fi
  DEFAULT_CHROMA_HOST=${DETECTED_IP:-127.0.0.1}
  DEFAULT_CHROMA_PORT=8000
  DEFAULT_REDIS_URL=redis://redis:6379/0

  read -r -p "OPENAI_API_KEY [leave blank to skip]: " INPUT_OPENAI_API_KEY || true
  read -r -p "CHROMA_HOST [${DEFAULT_CHROMA_HOST}]: " INPUT_CHROMA_HOST || true
  read -r -p "CHROMA_PORT [${DEFAULT_CHROMA_PORT}]: " INPUT_CHROMA_PORT || true
  read -r -p "REDIS_URL [${DEFAULT_REDIS_URL}]: " INPUT_REDIS_URL || true

  OPENAI_VAL=${INPUT_OPENAI_API_KEY:-}
  CHROMA_HOST_VAL=${INPUT_CHROMA_HOST:-${DEFAULT_CHROMA_HOST}}
  CHROMA_PORT_VAL=${INPUT_CHROMA_PORT:-${DEFAULT_CHROMA_PORT}}
  REDIS_URL_VAL=${INPUT_REDIS_URL:-${DEFAULT_REDIS_URL}}

  {
    printf "OPENAI_API_KEY=%s\n" "$OPENAI_VAL"
    printf "CHROMA_HOST=%s\n" "$CHROMA_HOST_VAL"
    printf "CHROMA_PORT=%s\n" "$CHROMA_PORT_VAL"
    printf "CHROMA_TENANT=%s\n" "${CHROMA_TENANT:-agentic-memories}"
    printf "CHROMA_DATABASE=%s\n" "${CHROMA_DATABASE:-memories}"
    printf "REDIS_URL=%s\n" "$REDIS_URL_VAL"
  } > .env
  chmod 600 .env 2>/dev/null || true
  echo ".env created."
fi

# Load .env into environment for this run (compose also reads it)
if [ -f .env ]; then
  set +u
  set -a
  . ./.env
  set +a
  set -u
fi

# Hint when OPENAI_API_KEY is not set
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "Warning: OPENAI_API_KEY is not set. The API may fail to call OpenAI until it's configured." >&2
fi

# Load ChromaDB configuration from .env file
export CHROMA_HOST="${CHROMA_HOST:-localhost}"
export CHROMA_PORT="${CHROMA_PORT:-8000}"
export CHROMA_TENANT="${CHROMA_TENANT:-agentic-memories}"
export CHROMA_DATABASE="${CHROMA_DATABASE:-memories}"

echo "Using CHROMA_HOST=${CHROMA_HOST} CHROMA_PORT=${CHROMA_PORT}"

# Function to check ChromaDB health
check_chroma_health() {
  local max_retries=10
  local retry_count=0

  echo "Checking ChromaDB health at ${CHROMA_HOST}:${CHROMA_PORT}..."

  while [ $retry_count -lt $max_retries ]; do
    if curl -f -s "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v2/heartbeat" >/dev/null 2>&1; then
      echo "ChromaDB is healthy"
      return 0
    fi

    retry_count=$((retry_count + 1))
    if [ $retry_count -lt $max_retries ]; then
      echo "ChromaDB not ready (attempt $retry_count/$max_retries), retrying in 2s..."
      sleep 2
    fi
  done

  echo "Error: ChromaDB is not available after $max_retries attempts" >&2
  return 1
}

# Function to check and create required database and collection
check_required_collections() {
  local required_collection="memories_3072"  # Based on text-embedding-3-large (3072 dims)
  local api_url="http://${CHROMA_HOST}:${CHROMA_PORT}/api/v2"

  echo "Checking ChromaDB database and collections..."

  # First, check if the database exists by listing databases in the tenant
  local databases_response
  databases_response=$(curl -s "${api_url}/tenants/${CHROMA_TENANT}/databases" 2>/dev/null)

  local database_exists=false
  if echo "$databases_response" | grep -q "\"name\":\"${CHROMA_DATABASE}\""; then
    database_exists=true
    echo "Database '${CHROMA_DATABASE}' exists"
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
        echo "Database '${CHROMA_DATABASE}' created successfully"
        database_exists=true
      else
        echo "Error: Failed to create database '${CHROMA_DATABASE}'" >&2
        echo "Response: $create_db_response" >&2
        return 1
      fi
    else
      echo "Skipping database creation. Exiting."
      return 1
    fi
  fi

  # Now check if the required collection exists
  local collections_response
  collections_response=$(curl -s "${api_url}/tenants/${CHROMA_TENANT}/databases/${CHROMA_DATABASE}/collections" 2>/dev/null)

  if echo "$collections_response" | grep -q "\"name\":\"${required_collection}\""; then
    echo "Required collection '${required_collection}' found"
    return 0
  else
    echo "Collection '${required_collection}' does not exist in database '${CHROMA_DATABASE}'"

    # Prompt user to create collection
    echo -n "Create the collection '${required_collection}'? (y/N): "
    read -r create_collection </dev/tty
    if [[ "$create_collection" =~ ^[Yy]$ ]]; then
      echo "Creating collection '${required_collection}'..."
      local create_col_response
      create_col_response=$(curl -s -X POST "${api_url}/tenants/${CHROMA_TENANT}/databases/${CHROMA_DATABASE}/collections" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"${required_collection}\", \"metadata\": {\"created_by\": \"agentic-memories\"}}" 2>/dev/null)

      if [ $? -eq 0 ] && echo "$create_col_response" | grep -q "\"name\":\"${required_collection}\""; then
        echo "Collection '${required_collection}' created successfully"
        return 0
      else
        echo "Error: Failed to create collection '${required_collection}'" >&2
        echo "Response: $create_col_response" >&2
        return 1
      fi
    else
      echo "Skipping collection creation. Exiting."
      return 1
    fi
  fi
}

# Check ChromaDB availability and required collections
# Use localhost for checks since we're running on the host before containers start
ORIGINAL_CHROMA_HOST="$CHROMA_HOST"
export CHROMA_HOST=localhost
if ! check_chroma_health; then
  exit 1
fi

if ! check_required_collections; then
  exit 1
fi

# Unset all env vars so docker-compose reads fresh from .env file
# This ensures the container gets the right values, not inherited shell vars
unset OPENAI_API_KEY
unset XAI_API_KEY
unset LLM_PROVIDER
unset EXTRACTION_MODEL_OPENAI
unset EXTRACTION_MODEL_XAI
unset XAI_BASE_URL
unset CHROMA_HOST
unset CHROMA_PORT
unset CHROMA_TENANT
unset CHROMA_DATABASE
unset REDIS_URL
unset TIMESCALE_DSN
unset NEO4J_URI
unset NEO4J_USER
unset NEO4J_PASSWORD
unset CF_ACCESS_AUD
unset CF_ACCESS_TEAM_DOMAIN
unset SCHEDULED_MAINTENANCE_ENABLED
unset LANGFUSE_PUBLIC_KEY
unset LANGFUSE_SECRET_KEY
unset LANGFUSE_HOST
unset VITE_API_BASE_URL

# Build and start services
${COMPOSE_CMD} up -d --build

echo "\n[agentic-memories] Services started with restart policy 'unless-stopped'."
echo "- API:          http://localhost:8080"
echo "- UI:           http://localhost:80"
echo "- ChromaDB:     http://localhost:8000 (external)"
echo "- Redis:        localhost:6379"

echo "\nLogs (follow) -> ${COMPOSE_CMD} logs -f"
echo "Stop services  -> ${COMPOSE_CMD} down"
echo "\nDone."


