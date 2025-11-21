#!/bin/bash
set -e

# Default debug ports (can be overridden via env vars)
DEBUGGER_PORT="${DEBUGGER_PORT:-5679}"          # Internal debugpy port
API_DEBUG_PORT="${API_DEBUG_PORT:-5681}"        # External port (for user connection)
ENVIRONMENT="${ENVIRONMENT:-production}"

# Check if dev environment (enable remote debugging)
if [ "$ENVIRONMENT" = "dev" ]; then
    echo "🔧 Dev mode - remote debugger listening on port $API_DEBUG_PORT (internal: $DEBUGGER_PORT)"
    # Start uvicorn with debugpy (non-blocking)
    python -m debugpy --listen 0.0.0.0:$DEBUGGER_PORT -m uvicorn src.app:app --host 0.0.0.0 --port 8080
else
    echo "🚀 Production mode - starting uvicorn normally"
    # Start uvicorn normally
    uvicorn src.app:app --host 0.0.0.0 --port 8080
fi
