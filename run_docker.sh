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

# Ensure CHROMA defaults for external instance if not provided
if [ -z "${CHROMA_HOST:-}" ]; then
  HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}') || true
  if [ -z "${HOST_IP:-}" ]; then
    HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  fi
  export CHROMA_HOST="${HOST_IP:-127.0.0.1}"
else
  export CHROMA_HOST
fi
export CHROMA_PORT="${CHROMA_PORT:-8000}"

echo "Using CHROMA_HOST=${CHROMA_HOST} CHROMA_PORT=${CHROMA_PORT}"

# Build and start services
${COMPOSE_CMD} up -d --build

echo "\n[agentic-memories] Services started with restart policy 'unless-stopped'."
echo "- API:          http://localhost:8080"
echo "- ChromaDB:     http://${CHROMA_HOST}:${CHROMA_PORT} (external)"
echo "- Redis:        localhost:6379"

echo "\nLogs (follow) -> ${COMPOSE_CMD} logs -f"
echo "Stop services  -> ${COMPOSE_CMD} down"
echo "\nDone."


