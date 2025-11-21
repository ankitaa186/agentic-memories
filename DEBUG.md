# Remote Debugging Guide

This project supports remote debugging with `debugpy` when running in Docker containers.
Debug setup follows the same pattern as the Annie project for consistency.

## Prerequisites

- VS Code with Python extension installed
- Docker and Docker Compose
- The project environment configured (`.env` file)

## How to Enable Debug Mode

### Option 1: Environment Variable (Recommended)

Add to your `.env` file:
```bash
ENVIRONMENT=dev
```

Then start the services:
```bash
bash run_docker.sh
```

### Option 2: Command Line

```bash
ENVIRONMENT=dev docker compose up --build
```

### Option 3: Export Environment Variable

```bash
export ENVIRONMENT=dev
docker compose up --build
```

## How Debugging Works

When `ENVIRONMENT=dev`:
1. The container starts `debugpy` on port 5679 (inside container)
2. The application **starts immediately** (non-blocking)
3. You can attach VS Code debugger at any time via external port 5681
4. Set breakpoints and they will hit on the next request

When `ENVIRONMENT=production` (default):
- Application starts normally without debugpy
- No performance overhead
- Production-ready mode

**Key Difference from Annie**: We use an entrypoint script instead of application code for simplicity.

## Port Configuration

| Service | Debug Port (Internal) | External Port (Default) | Configurable Via |
|---------|----------------------|-------------------------|------------------|
| API | 5679 | 5681 | `API_DEBUG_PORT` |

**Note**: External port 5681 is used by default to avoid conflicts with:
- Annie backend (5678)
- Annie MCP server (5679)
- Annie telegram bot (5680)

If you need a different port:
```bash
# In .env for agentic-memories
API_DEBUG_PORT=5682  # Use a different port
```

## Attaching the Debugger (VS Code)

1. **Start the container in dev mode**:
   ```bash
   ENVIRONMENT=dev bash run_docker.sh
   ```

2. **Wait for the message**:
   ```
   🔧 Dev mode - remote debugger listening on port 5681 (internal: 5679)
   ```

3. **In VS Code**:
   - Press `F5` or go to Run & Debug panel
   - Select "Python: Remote Attach (API)"
   - Click the green play button

4. **Set breakpoints**:
   - Open any Python file (e.g., `src/app.py`, `src/routers/profile.py`)
   - Click in the gutter to set breakpoints
   - Make API requests to trigger your breakpoints

## Debug Configuration

The VS Code launch configuration (`.vscode/launch.json`) is already set up:

```json
{
  "name": "Python: Remote Attach (API)",
  "type": "debugpy",
  "request": "attach",
  "connect": {
    "host": "localhost",
    "port": 5681
  },
  "pathMappings": [
    {
      "localRoot": "${workspaceFolder}",
      "remoteRoot": "/app"
    }
  ],
  "justMyCode": false,
  "redirectOutput": true,
  "showReturnValue": true
}
```

**Key Settings** (matching Annie project):
- `port: 5681` - external port to connect to debugpy
- `pathMappings` - maps local files to container paths
- `justMyCode: false` - allows stepping into library code
- `redirectOutput: true` - redirects stdout/stderr to debug console
- `showReturnValue: true` - shows function return values in debugger

## Example Debugging Session

```bash
# 1. Enable dev mode
ENVIRONMENT=dev bash run_docker.sh

# 2. Wait for "Dev mode - remote debugger listening on port 5681" message

# 3. In VS Code, press F5 and select "Python: Remote Attach (API)" (connects to port 5681)

# 4. Set a breakpoint in src/routers/profile.py - get_profile function

# 5. Test the API
curl "http://localhost:8080/v1/profile?user_id=test-user"

# 6. Your breakpoint should hit! 🎉
```

## Debugging Features

- ✅ Set breakpoints in any Python file
- ✅ Step through code (F10 = step over, F11 = step into)
- ✅ Inspect variables in the debug panel
- ✅ Evaluate expressions in the debug console
- ✅ View call stack
- ✅ See function return values (thanks to `showReturnValue: true`)
- ✅ Redirected output in debug console (thanks to `redirectOutput: true`)

## Common Issues

### Issue: "Connection refused" or "Connection timed out"

**Solution**: Ensure the container is running and debugpy started:
```bash
docker logs agentic-memories-api-1 | grep "Dev mode"
```

You should see: `🔧 Dev mode - remote debugger listening on port 5681 (internal: 5679)`

### Issue: Port conflict with other services

If port 5681 is already in use:

**Solution**: Choose a different external port
```bash
# In .env file
API_DEBUG_PORT=5682  # or any available port

# Then rebuild
docker compose down && docker compose up --build
```

**Update VS Code launch.json**:
```json
"connect": {
  "host": "localhost",
  "port": 5682  // Match your API_DEBUG_PORT
}
```

### Issue: Breakpoints not hitting

**Possible causes**:
1. **Debugger not attached**: Press F5 in VS Code
2. **Wrong file**: Ensure you're editing the file in your local workspace
3. **Code mismatch**: Rebuild the container if you changed code before attaching

**Solution**:
```bash
# Rebuild and restart
docker compose down
ENVIRONMENT=dev docker compose up --build
```

### Issue: Want to check current environment

```bash
# Check current ENVIRONMENT value
docker exec $(docker ps -q -f name=api) env | grep ENVIRONMENT
```

### Issue: Performance is slow

**Debugging adds overhead!** Only use `ENVIRONMENT=dev` during development.

For production: `ENVIRONMENT=production` (or omit the variable entirely)

## Debugging Specific Scenarios

### Profile Extraction Pipeline

Set breakpoints in:
- `src/services/unified_ingestion_graph.py` - Main pipeline
- `src/services/profile_extraction.py` - Profile extraction logic
- `src/services/profile_storage.py` - Database storage

### API Endpoints

Set breakpoints in:
- `src/routers/profile.py` - Profile CRUD endpoints
- `src/app.py` - Main application and middleware

### Memory Retrieval

Set breakpoints in:
- `src/services/retrieval.py` - ChromaDB retrieval
- `src/services/storage.py` - Memory storage

## Tips & Best Practices

1. **Use conditional breakpoints**: Right-click breakpoint → Edit Breakpoint → Condition
   ```python
   user_id == "test-user"
   ```

2. **Log points instead of print**: Right-click breakpoint → Log Message
   ```
   User ID: {user_id}, Count: {len(memories)}
   ```

3. **Watch expressions**: Add variables to Watch panel for continuous monitoring

4. **Debug console**: Evaluate expressions while paused
   ```python
   >>> memory.id
   'mem_abc123'
   >>> len(state["memories"])
   10
   ```

5. **Restart quickly**: Use Docker Compose restart (faster than rebuild)
   ```bash
   docker compose restart api
   ```

6. **View return values**: Thanks to `showReturnValue: true`, function returns appear in Variables panel

7. **Check redirected output**: stdout/stderr appears in debug console thanks to `redirectOutput: true`

## Disabling Debug Mode

Remove `ENVIRONMENT=dev` from `.env` or:
```bash
unset ENVIRONMENT
docker compose restart api
```

Or explicitly set:
```bash
ENVIRONMENT=production docker compose restart api
```

## Comparison with Annie Project

| Aspect | Annie | Agentic Memories |
|--------|-------|------------------|
| **Trigger** | `ENVIRONMENT=dev` | `ENVIRONMENT=dev` ✓ |
| **Debug ports** | 5678, 5679, 5680 | 5681 (internal: 5679) |
| **Blocking** | Non-blocking | Non-blocking ✓ |
| **Location** | Application code (`main.py`) | Entrypoint script |
| **Extra options** | `redirectOutput`, `showReturnValue` | Same ✓ |

**Why use entrypoint script instead of application code?**
- Keeps application code clean
- No need to modify `src/app.py`
- Easier to maintain and understand
- Same behavior as Annie, simpler implementation

---

**Happy Debugging!** 🐛🔍
