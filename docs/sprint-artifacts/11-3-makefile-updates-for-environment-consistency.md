# Story 11.3: Makefile Updates for Environment Consistency

Status: review

## Story

As a **developer**,
I want **Makefile commands to respect the ENV variable and select appropriate compose files**,
so that **`make stop`, `make docker-logs`, and other commands work correctly in both development and production modes**.

## Acceptance Criteria

1. **AC-11.3.1**: `COMPOSE_FILES` variable selects correct files based on `ENV`
2. **AC-11.3.2**: `make stop ENV=prod` stops containers started with prod config
3. **AC-11.3.3**: `make docker-logs ENV=prod` tails logs from prod containers
4. **AC-11.3.4**: `make docker-rebuild ENV=prod` rebuilds with prod config
5. **AC-11.3.5**: `make docker-health ENV=prod` shows prod container status
6. **AC-11.3.6**: `make check-loki` returns success if plugin installed, error if not
7. **AC-11.3.7**: `make help` documents `ENV=prod` usage

## Tasks / Subtasks

- [x] Task 1: Add ENV variable and COMPOSE_FILES logic (AC: 1)
  - [x] Add `ENV ?= dev` variable definition
  - [x] Add `COMPOSE_FILES` variable with conditional logic for prod
  - [x] Place after existing variable definitions (near line 6)
- [x] Task 2: Update stop target (AC: 2)
  - [x] Modify `stop` target to use `$(COMPOSE_FILES)`
  - [x] Ensure it references correct compose files for prod mode
- [x] Task 3: Update docker-logs target (AC: 3)
  - [x] Modify `docker-logs` target to use `$(COMPOSE_FILES)`
  - [x] Support optional `SERVICE` variable for specific service logs
- [x] Task 4: Update docker-rebuild target (AC: 4)
  - [x] Modify `docker-rebuild` target to use `$(COMPOSE_FILES)`
- [x] Task 5: Update docker-health target (AC: 5)
  - [x] Modify `docker-health` target to use `$(COMPOSE_FILES)`
- [x] Task 6: Update docker-shell target (AC: 2, consistency)
  - [x] Modify `docker-shell` target to use `$(COMPOSE_FILES)`
- [x] Task 7: Add check-loki target (AC: 6)
  - [x] Create new target that checks for Loki plugin
  - [x] Return success if installed, error with install instructions if not
- [x] Task 8: Update help target (AC: 7)
  - [x] Add documentation for `ENV=prod` usage
  - [x] Mention in help output header

## Dev Notes

### Architecture Alignment

The Makefile serves as the primary interface for developers. All Docker-related commands should consistently respect the `ENV` variable to ensure operations work correctly regardless of which compose configuration was used to start the containers.

**Pattern:**
```
ENV=prod make start    → Uses docker-compose.yml + docker-compose.prod.yml
ENV=prod make stop     → Must also reference both files to find containers
ENV=prod make logs     → Must reference same config for service names
```

### Project Structure Notes

**File Location:**
- Path: `/Makefile`
- Type: Modified (existing file)

**Integration Points:**
- Calls `scripts/run_docker.sh` for start command
- All other docker commands use `docker compose` directly

### Code Implementation Guidance

**Add after existing variable definitions (near line 6):**
```makefile
# Environment mode (dev or prod)
ENV ?= dev

# Compose file selection based on ENV
COMPOSE_FILES = $(if $(filter prod,$(ENV)),-f docker-compose.yml -f docker-compose.prod.yml,)
```

**Modified targets:**
```makefile
stop: ## Stop Docker containers
	@echo "Stopping Agentic Memories services..."
	@docker compose $(COMPOSE_FILES) down

docker-logs: ## Show Docker container logs (use ENV=prod for production, SERVICE=name for specific)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Viewing logs from all services..."; \
		docker compose $(COMPOSE_FILES) logs -f; \
	else \
		echo "Viewing logs from $(SERVICE)..."; \
		docker compose $(COMPOSE_FILES) logs -f $(SERVICE); \
	fi

docker-rebuild: ## Rebuild Docker containers
	@echo "Rebuilding containers..."
	@docker compose $(COMPOSE_FILES) build --no-cache
	@echo "Containers rebuilt."

docker-health: ## Check service health
	@echo "Checking service health..."
	@docker compose $(COMPOSE_FILES) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

docker-shell: ## Open shell in Docker container (use SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Error: SERVICE variable is required"; \
		echo "Usage: make docker-shell SERVICE=api"; \
		exit 1; \
	fi
	@echo "Accessing $(SERVICE) shell..."
	@docker compose $(COMPOSE_FILES) exec $(SERVICE) /bin/bash || docker compose $(COMPOSE_FILES) exec $(SERVICE) /bin/sh
```

**New target:**
```makefile
check-loki: ## Verify Loki Docker plugin is installed
	@if docker plugin ls 2>/dev/null | grep -q "loki.*true"; then \
		echo "✓ Loki plugin installed and enabled"; \
	else \
		echo "✗ Loki plugin not installed"; \
		echo "Install with: docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions"; \
		exit 1; \
	fi
```

**Update help target header:**
```makefile
help: ## Show this help message
	@echo "Available commands:"
	@echo ""
	@echo "  Environment: Use ENV=prod for production mode (e.g., make start ENV=prod)"
	@echo ""
	# ... rest of existing help categories
```

### Testing Checklist

| Command | Expected Behavior |
|---------|-------------------|
| `make stop` | Stops dev containers |
| `make stop ENV=prod` | Stops prod containers (same network/names) |
| `make docker-logs` | Tails dev container logs |
| `make docker-logs ENV=prod` | Tails prod container logs |
| `make docker-logs SERVICE=api` | Tails only api service logs |
| `make docker-rebuild ENV=prod` | Rebuilds with prod config |
| `make docker-health ENV=prod` | Shows prod container status |
| `make check-loki` (with plugin) | Prints success message |
| `make check-loki` (without plugin) | Prints error and exits 1 |
| `make help` | Shows ENV documentation |

### References

- [Source: docs/epic-cloud-logging.md#Story-11.3]
- [Source: docs/sprint-artifacts/tech-spec-epic-11.md#Story-11.3]
- [Source: Makefile - existing file to modify]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/11-3-makefile-updates-for-environment-consistency.context.xml

### Agent Model Used

Claude Opus 4.5

### Debug Log References

- Added ENV and COMPOSE_FILES variables at top of Makefile
- Updated stop, docker-logs, docker-rebuild, docker-health, docker-shell targets
- Added new check-loki target
- Updated help target with ENV documentation

### Completion Notes List

- COMPOSE_FILES variable uses conditional logic: empty for dev, `-f docker-compose.yml -f docker-compose.prod.yml` for prod
- All Docker commands now respect ENV variable
- docker-logs supports SERVICE variable for specific service filtering
- docker-shell requires SERVICE variable (no longer hardcoded container name)
- check-loki target validates plugin installation
- Help output includes ENV usage documentation at top

### File List

- Makefile (MODIFIED)

---

## Senior Developer Review (AI)

### Reviewer
Ankit

### Date
2026-01-17

### Outcome
**APPROVE** ✅

All 7 acceptance criteria are fully implemented. The Makefile correctly reads ENVIRONMENT from .env file and applies COMPOSE_FILES conditional logic to all Docker commands.

### Summary
Story 11.3 updates the Makefile to respect the ENV variable across all Docker-related commands. The implementation uses shell command substitution to read ENVIRONMENT from .env, and a conditional variable for COMPOSE_FILES that applies production compose override when ENV=prod.

### Key Findings
No issues found. Implementation exceeds requirements by also updating docker-test and clean targets.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC-11.3.1 | COMPOSE_FILES selects correct files based on ENV | ✅ IMPLEMENTED | Lines 9-15: shell grep + conditional |
| AC-11.3.2 | make stop ENV=prod stops prod containers | ✅ IMPLEMENTED | Lines 53-55: uses $(COMPOSE_FILES) |
| AC-11.3.3 | make docker-logs ENV=prod tails prod logs | ✅ IMPLEMENTED | Lines 147-154: uses $(COMPOSE_FILES) |
| AC-11.3.4 | make docker-rebuild ENV=prod rebuilds with prod | ✅ IMPLEMENTED | Lines 168-171: uses $(COMPOSE_FILES) |
| AC-11.3.5 | make docker-health ENV=prod shows prod status | ✅ IMPLEMENTED | Lines 173-175: uses $(COMPOSE_FILES) |
| AC-11.3.6 | make check-loki returns success/error | ✅ IMPLEMENTED | Lines 177-184: grep + exit 1 |
| AC-11.3.7 | make help documents ENV=prod usage | ✅ IMPLEMENTED | Lines 18-20: ENV documentation |

**Summary: 7 of 7 acceptance criteria fully implemented**

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: Add ENV and COMPOSE_FILES | [x] | ✅ | Lines 9-15 |
| Task 2: Update stop target | [x] | ✅ | Lines 53-55 |
| Task 3: Update docker-logs target | [x] | ✅ | Lines 147-154 |
| Task 4: Update docker-rebuild target | [x] | ✅ | Lines 168-171 |
| Task 5: Update docker-health target | [x] | ✅ | Lines 173-175 |
| Task 6: Update docker-shell target | [x] | ✅ | Lines 156-163 |
| Task 7: Add check-loki target | [x] | ✅ | Lines 177-184 |
| Task 8: Update help target | [x] | ✅ | Lines 18-20 |

**Summary: 8 of 8 completed tasks verified, 0 questionable, 0 falsely marked**

### Test Coverage and Gaps
- No automated tests (Makefile)
- Manual validation performed in Story 11.6 ✅

### Architectural Alignment
- Consistent ENV handling across all targets ✅
- Shell command reads .env for persistent config ✅

### Security Notes
- No credentials in Makefile ✅

### Best-Practices and References
- [GNU Make Manual](https://www.gnu.org/software/make/manual/)
- [Docker Compose CLI](https://docs.docker.com/compose/reference/)

### Action Items
None required.

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-17 | 1.0 | Story implemented |
| 2026-01-17 | 1.0 | Senior Developer Review notes appended - APPROVED |
