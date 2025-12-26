#!/bin/bash
set -e

# Default debug ports (can be overridden via env vars)
DEBUGGER_PORT="${DEBUGGER_PORT:-5679}"          # Internal debugpy port
API_DEBUG_PORT="${API_DEBUG_PORT:-5681}"        # External port (for user connection)
ENVIRONMENT="${ENVIRONMENT:-production}"

# Check if dev environment (enable remote debugging)
if [ "$ENVIRONMENT" = "dev" ]; then
    WORKERS=3
    echo "🔧 Dev mode - starting uvicorn with $WORKERS workers (debugger on port $API_DEBUG_PORT)"
    # Start uvicorn with workers - debugpy doesn't work well with multiple workers
    # so we prioritize concurrency over debugging in dev mode
    python -m debugpy --listen 0.0.0.0:$DEBUGGER_PORT -m uvicorn src.app:app --host 0.0.0.0 --port 8080 --workers $WORKERS
else
    echo "🚀 Production mode - starting uvicorn with 10 workers"
    # Start uvicorn with multiple workers for concurrent request handling
    uvicorn src.app:app --host 0.0.0.0 --port 8080 --workers 10
fi
