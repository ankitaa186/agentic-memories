# Epic Technical Specification: Cloud Logging Integration

Date: 2026-01-17
Author: Ankit
Epic ID: 11
Status: Draft

---

## Overview

Epic 11 addresses a critical operational gap in Agentic Memories' production deployment: the lack of remote log visibility and proactive alerting. Currently, the architecture uses Docker Compose with logging to stdout, but logs are only accessible via SSH or `docker compose logs`. This epic implements environment-aware cloud logging using Grafana Cloud's free tier with the Loki Docker logging driver, enabling remote debugging and proactive alerting without any application code changes.

This aligns with operational goals of 99%+ uptime by providing the observability infrastructure needed to detect and respond to issues before they impact users.

## Objectives and Scope

### In Scope

- **Production Docker Compose Override**: Create `docker-compose.prod.yml` with Loki logging driver configuration for all three services (api, ui, redis)
- **Environment-Aware Startup**: Modify `scripts/run_docker.sh` to detect `ENV` variable and apply appropriate compose configuration
- **Makefile Integration**: Update Makefile commands (`stop`, `docker-logs`, `docker-rebuild`, `docker-health`, `docker-shell`) to respect `ENV` variable
- **Environment Configuration**: Add `LOKI_URL` to `env.example`
- **Alerting Documentation**: Create `docs/operations/ALERTING.md` with LogQL queries and setup instructions
- **Validation**: End-to-end testing of both development and production modes

### Out of Scope

- Prometheus metrics collection (future consideration)
- Distributed tracing integration with Langfuse (future consideration)
- Multi-environment support (staging) beyond dev/prod
- Custom Grafana dashboards (manual setup in Grafana Cloud UI)
- Log sampling or filtering at source

## System Architecture Alignment

This epic extends Agentic Memories' existing Docker Compose architecture without modifying the core service communication patterns:

**Components Referenced**:
- `docker-compose.yml` - Base configuration (unchanged)
- `docker-compose.prod.yml` - New production override file
- `scripts/run_docker.sh` - Startup script (modified)
- `Makefile` - Build commands (modified)

**Architecture Constraints**:
- Zero application code changes required
- Logging configuration at Docker daemon level via logging driver
- Environment detection via `ENV` shell variable
- Fail-fast behavior in production mode if prerequisites not met

**Service Impact**:
| Service | Change |
|---------|--------|
| api | Logging driver override in prod |
| ui | Logging driver override in prod |
| redis | Logging driver override in prod |

## Detailed Design

### Services and Modules

| Component | Responsibility | Inputs | Outputs | Owner |
|-----------|----------------|--------|---------|-------|
| `docker-compose.prod.yml` | Define Loki logging driver configuration for all services | `LOKI_URL` env var | Logging config applied to containers | DevOps |
| `run_docker.sh` | Environment detection, prerequisite validation, service startup | `ENV` variable, `.env` file | Running containers with correct logging | DevOps |
| `Makefile` | Unified command interface respecting environment | `ENV` variable | Correct compose file selection | DevOps |
| Loki Docker Plugin | Ship container logs to Grafana Cloud | Container stdout/stderr | HTTPS POST to Loki endpoint | External |
| Grafana Cloud | Log aggregation, querying, alerting | Log streams | UI, alerts, API | External |

### Data Models and Contracts

**Log Entry Structure** (existing, unchanged):
```json
{
  "timestamp": "2026-01-17T10:30:00.123Z",
  "level": "INFO",
  "message": "Memory stored successfully",
  "service": "api",
  "request_id": "abc123",
  "extra": {
    "user_id": "user-123",
    "duration_ms": 145
  }
}
```

**Loki Labels** (added by logging driver):
```yaml
labels:
  service: "api"              # From loki-external-labels
  env: "prod"                 # From loki-external-labels
  project: "agentic-memories" # From loki-external-labels
  container_name: "agentic-memories-api-1"  # Auto-added by driver
  compose_service: "api"                     # Auto-added by driver
```

**Environment Variables Contract**:
| Variable | Required | Default | Format |
|----------|----------|---------|--------|
| `ENV` | No | `dev` | `dev` or `prod` |
| `LOKI_URL` | Yes (prod only) | - | `https://<user>:<key>@<host>/loki/api/v1/push` |

### APIs and Interfaces

**No new application APIs** - this epic operates at infrastructure level.

**External API: Grafana Loki Push API**
- **Endpoint**: `https://logs-prod-us-central1.grafana.net/loki/api/v1/push`
- **Method**: POST
- **Auth**: Basic auth embedded in URL (user-id:api-key)
- **Format**: Protobuf (handled by Loki driver)
- **Rate Limit**: None for free tier (volume-based billing)

**Makefile Interface Changes**:
```makefile
# All commands now accept ENV parameter
make start              # Dev mode (default)
make start ENV=prod     # Prod mode with Loki
make stop ENV=prod      # Stop prod containers
make docker-logs ENV=prod      # View prod container logs
make docker-health ENV=prod    # Check prod health
make check-loki         # Verify Loki plugin installed
```

### Workflows and Sequencing

**Production Startup Sequence**:
```
1. User runs: make start ENV=prod
       ↓
2. Makefile invokes: ENV=prod ./scripts/run_docker.sh
       ↓
3. run_docker.sh detects ENV=prod
       ↓
4. Existing checks (docker, .env, ChromaDB)
       ↓
5. [PROD ONLY] check_loki_plugin() - Verify Loki driver installed
       ↓ FAIL → Exit with install instructions
6. [PROD ONLY] validate_prod_env() - Verify LOKI_URL set
       ↓ FAIL → Exit with configuration instructions
7. Start with -f docker-compose.yml -f docker-compose.prod.yml
       ↓
8. Containers start with Loki logging driver
       ↓
9. Logs flow to Grafana Cloud
```

**Log Flow (Production)**:
```
Container Process
    ↓ stdout/stderr
Docker Daemon
    ↓ Loki logging driver
Batching (400 entries or 2s timeout)
    ↓ HTTPS POST
Grafana Cloud Loki
    ↓ Indexed by labels
LogQL Queries / Alerts
```

## Non-Functional Requirements

### Performance

| Metric | Target | Source |
|--------|--------|--------|
| Log delivery latency | <5s p95 | Epic 11 Success Criteria |
| Container startup overhead | <2s additional | Loki driver initialization |
| Loki driver memory footprint | <50MB per container | Grafana documentation |
| Batch size | 400 entries | Configured in compose |
| Batch timeout | 2s | Configured in compose |

**Impact on Application Performance**:
- Logging driver operates asynchronously; no blocking on application threads
- Batch buffering prevents per-log-line network calls
- Retry mechanism (5 retries) handles transient network issues without log loss

### Security

| Requirement | Implementation | Source |
|-------------|----------------|--------|
| Credential protection | `LOKI_URL` in `.env` (gitignored) | Standard secrets management |
| Transport encryption | HTTPS only (TLS 1.2+) | Grafana Cloud enforced |
| Log data sensitivity | Existing logging patterns apply | Application level |
| Access control | Grafana Cloud account authentication | External service |

**Threat Considerations**:
- **Credential leak**: `LOKI_URL` contains embedded API key. Mitigated by `.gitignore` and environment variable pattern (not hardcoded)
- **Log injection**: N/A - logs are from application, not user-controlled
- **Data exfiltration**: Logs may contain user_id. No PII changes required for V1.

### Reliability/Availability

| Requirement | Implementation |
|-------------|----------------|
| Graceful degradation | If Loki unavailable, logs still written to container stdout (queryable locally) |
| Retry on failure | Loki driver retries 5 times with backoff |
| No single point of failure | Logging failure does not crash application |
| Dev mode fallback | `ENV=dev` bypasses all Loki requirements |

**Failure Scenarios**:
| Scenario | Behavior |
|----------|----------|
| Grafana Cloud outage | Logs buffered locally, may be lost if buffer fills |
| Network timeout | Driver retries 5 times, then drops batch |
| Invalid LOKI_URL | Startup fails fast with clear error message |
| Loki plugin not installed | Startup fails fast with install instructions |

**Recovery**: No manual intervention needed for transient failures. Persistent failures require checking Grafana Cloud status or network connectivity.

### Observability

| Signal | Implementation |
|--------|----------------|
| Log aggregation | Grafana Cloud Loki with LogQL queries |
| Log retention | 14 days (free tier) |
| Alerting | Grafana Cloud Alerting (50 rules, free tier) |
| Dashboards | Manual creation in Grafana Cloud UI |

**Required LogQL Queries** (documented in `docs/operations/ALERTING.md`):
```logql
# Error rate by service
sum by (service) (count_over_time({project="agentic-memories"} |= "ERROR" [5m]))

# API failures
{service="api"} |= "error" |= "failed"

# Memory operations
{service="api"} |= "memory" | json

# ChromaDB issues
{service="api"} |= "chroma" |= "error"
```

**Recommended Alerts**:
| Alert | Condition | Severity |
|-------|-----------|----------|
| Service Error Spike | >10 errors in 5 min | Critical |
| ChromaDB Connection Failed | Any occurrence | Critical |
| Redis Connection Lost | Any occurrence | Critical |
| LLM Latency High | >5 occurrences/hour | Warning |

## Dependencies and Integrations

### External Service Dependencies

| Service | Version/Tier | Purpose | Required |
|---------|--------------|---------|----------|
| Grafana Cloud | Free tier | Log aggregation, alerting | Yes (prod) |
| Loki Docker Plugin | `grafana/loki-docker-driver:latest` | Log shipping | Yes (prod) |

### Infrastructure Dependencies

| Component | Version | Constraint | Notes |
|-----------|---------|------------|-------|
| Docker | 20.10+ | Minimum for Loki plugin | Validated in `run_docker.sh` |
| Docker Compose | v2 (preferred) or v1 | Compose file override support | Auto-detected |
| Linux/macOS | Any | Docker plugin support | Windows requires WSL2 |

### File Dependencies

| File | Type | Dependency |
|------|------|------------|
| `docker-compose.yml` | Existing | Base configuration (not modified) |
| `docker-compose.prod.yml` | New | Requires `docker-compose.yml` as base |
| `.env` | Existing | Must contain `LOKI_URL` for prod mode |
| `scripts/run_docker.sh` | Modified | No new file dependencies |
| `Makefile` | Modified | No new file dependencies |

### Grafana Cloud Setup Requirements

1. **Account Creation**: https://grafana.com/products/cloud/ (free tier)
2. **Loki Data Source**: Auto-provisioned with account
3. **Push URL**: Connections → Hosted Logs → Loki → Details
4. **API Key**: Embedded in push URL (no separate key management)

## Acceptance Criteria (Authoritative)

### Story 11.1: Production Docker Compose Override
| ID | Criterion |
|----|-----------|
| AC-11.1.1 | `docker-compose.prod.yml` exists and configures Loki logging driver for all 3 services (api, ui, redis) |
| AC-11.1.2 | YAML anchor (`x-loki-logging`) used to avoid configuration duplication |
| AC-11.1.3 | Each service has labels: `service`, `env=prod`, `project=agentic-memories` |
| AC-11.1.4 | File includes usage documentation in header comments |
| AC-11.1.5 | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates without errors |

### Story 11.2: Environment-Aware Startup Script
| ID | Criterion |
|----|-----------|
| AC-11.2.1 | `ENV` variable defaults to `dev` when not set |
| AC-11.2.2 | `ENV=prod` triggers Loki plugin check before startup |
| AC-11.2.3 | `ENV=prod` validates `LOKI_URL` is set and not `REPLACE_ME` |
| AC-11.2.4 | Missing Loki plugin displays install command and exits non-zero |
| AC-11.2.5 | Missing `LOKI_URL` displays configuration example and exits non-zero |
| AC-11.2.6 | Prod mode uses `-f docker-compose.yml -f docker-compose.prod.yml` |
| AC-11.2.7 | Dev mode (`ENV=dev` or unset) works identically to current behavior |
| AC-11.2.8 | Console output clearly indicates which mode (dev/prod) is active |

### Story 11.3: Makefile Updates
| ID | Criterion |
|----|-----------|
| AC-11.3.1 | `COMPOSE_FILES` variable selects correct files based on `ENV` |
| AC-11.3.2 | `make stop ENV=prod` stops containers started with prod config |
| AC-11.3.3 | `make docker-logs ENV=prod` tails logs from prod containers |
| AC-11.3.4 | `make docker-rebuild ENV=prod` rebuilds with prod config |
| AC-11.3.5 | `make docker-health ENV=prod` shows prod container status |
| AC-11.3.6 | `make check-loki` returns success if plugin installed, error if not |
| AC-11.3.7 | `make help` documents `ENV=prod` usage |

### Story 11.4: Environment Configuration
| ID | Criterion |
|----|-----------|
| AC-11.4.1 | `LOKI_URL` added to `env.example` with format documentation |
| AC-11.4.2 | Loki plugin installation command documented in `env.example` |

### Story 11.5: Grafana Alerting Configuration
| ID | Criterion |
|----|-----------|
| AC-11.5.1 | `docs/operations/ALERTING.md` created with recommended alert rules |
| AC-11.5.2 | LogQL queries provided for: error spike, ChromaDB failure, redis disconnect, LLM latency |
| AC-11.5.3 | Step-by-step Grafana Cloud alert setup instructions included |
| AC-11.5.4 | YAML export example provided for alert rule automation |

### Story 11.6: Integration Testing & Validation
| ID | Criterion |
|----|-----------|
| AC-11.6.1 | Dev mode: `make start` works without `ENV` set |
| AC-11.6.2 | Dev mode: No Loki-related errors in startup |
| AC-11.6.3 | Prod mode: `make start ENV=prod` starts with Loki logging |
| AC-11.6.4 | Prod mode: Logs appear in Grafana Cloud within 10 seconds |
| AC-11.6.5 | Prod mode: Labels (service, env, project) visible in Grafana |
| AC-11.6.6 | Error handling: Graceful failure with instructions when prerequisites missing |

## Traceability Mapping

| AC ID | Spec Section | Component/File | Test Approach |
|-------|--------------|----------------|---------------|
| AC-11.1.1 | Detailed Design - Services | `docker-compose.prod.yml` | File inspection, `docker compose config` |
| AC-11.1.2 | Detailed Design - Services | `docker-compose.prod.yml` | YAML lint, anchor presence |
| AC-11.1.3 | Data Models - Loki Labels | `docker-compose.prod.yml` | Config validation |
| AC-11.1.4 | N/A | `docker-compose.prod.yml` | Code review |
| AC-11.1.5 | N/A | `docker-compose.prod.yml` | `docker compose config` command |
| AC-11.2.1 | Workflows - Startup | `scripts/run_docker.sh` | Manual test: unset ENV |
| AC-11.2.2 | Workflows - Startup | `scripts/run_docker.sh` | Manual test: ENV=prod without plugin |
| AC-11.2.3 | Workflows - Startup | `scripts/run_docker.sh` | Manual test: ENV=prod without LOKI_URL |
| AC-11.2.4 | NFR - Reliability | `scripts/run_docker.sh` | Manual test: verify exit code |
| AC-11.2.5 | NFR - Reliability | `scripts/run_docker.sh` | Manual test: verify exit code |
| AC-11.2.6 | Workflows - Startup | `scripts/run_docker.sh` | Manual test: verify compose command |
| AC-11.2.7 | Objectives - Scope | `scripts/run_docker.sh` | Regression test: existing workflow |
| AC-11.2.8 | N/A | `scripts/run_docker.sh` | Visual inspection of output |
| AC-11.3.1 | APIs - Makefile Interface | `Makefile` | Code review |
| AC-11.3.2 | APIs - Makefile Interface | `Makefile` | Manual test: stop prod containers |
| AC-11.3.3 | APIs - Makefile Interface | `Makefile` | Manual test: view logs |
| AC-11.3.4 | APIs - Makefile Interface | `Makefile` | Manual test: rebuild |
| AC-11.3.5 | APIs - Makefile Interface | `Makefile` | Manual test: health check |
| AC-11.3.6 | Dependencies | `Makefile` | Manual test: with/without plugin |
| AC-11.3.7 | N/A | `Makefile` | Visual inspection |
| AC-11.4.1 | Dependencies - Setup | `env.example` | File inspection |
| AC-11.4.2 | Dependencies - Setup | `env.example` | File inspection |
| AC-11.5.1 | NFR - Observability | `docs/operations/ALERTING.md` | File exists |
| AC-11.5.2 | NFR - Observability | `docs/operations/ALERTING.md` | LogQL syntax validation |
| AC-11.5.3 | N/A | `docs/operations/ALERTING.md` | Code review |
| AC-11.5.4 | N/A | `docs/operations/ALERTING.md` | YAML syntax validation |
| AC-11.6.1 | Objectives - Scope | Manual checklist | `make start` without ENV |
| AC-11.6.2 | Objectives - Scope | Manual checklist | Inspect startup output |
| AC-11.6.3 | NFR - Performance | Manual checklist | `make start ENV=prod` |
| AC-11.6.4 | NFR - Performance | Manual checklist | Query Grafana Cloud UI |
| AC-11.6.5 | Data Models - Labels | Manual checklist | Inspect labels in Grafana |
| AC-11.6.6 | NFR - Reliability | Manual checklist | Test without plugin/LOKI_URL |

## Risks, Assumptions, Open Questions

### Risks

| ID | Risk | Impact | Probability | Mitigation |
|----|------|--------|-------------|------------|
| R1 | Grafana Cloud free tier discontinued | High | Low | Volume estimates show minimal usage; paid tier is affordable ($0.50/GB) |
| R2 | Loki Docker plugin incompatible with future Docker versions | Medium | Low | Plugin maintained by Grafana; fallback to Promtail sidecar if needed |
| R3 | LOKI_URL credential accidentally committed | High | Low | `.env` already in `.gitignore`; pre-commit hooks could add extra protection |
| R4 | Log buffer overflow during Grafana outage | Low | Low | Acceptable risk for personal project; logs still in container during runtime |

### Assumptions

| ID | Assumption | Validation |
|----|------------|------------|
| A1 | Docker 20.10+ is available on production host | Validated in `run_docker.sh` |
| A2 | Production host has outbound HTTPS (443) access | Standard for cloud deployments |
| A3 | Grafana Cloud free tier limits (50GB/month) are sufficient | Volume estimate: ~300MB/month (0.6% of limit) |
| A4 | Single user (Ankit) is sole Grafana Cloud admin | Personal project scope |
| A5 | Existing logging format is compatible with Loki | Loki accepts any text; JSON enables structured queries |

### Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| Q1 | Should we add Prometheus metrics in a future epic? | Ankit | Deferred to future consideration |
| Q2 | Do we need log retention beyond 14 days? | Ankit | No - 14 days sufficient for debugging |
| Q3 | Should alerts go to Slack/Discord instead of email? | Ankit | Email for V1; webhook is future enhancement |

## Test Strategy Summary

### Test Approach

This epic is **infrastructure-only** with no application code changes. Testing is entirely **manual validation** using a checklist approach.

### Test Levels

| Level | Applicable | Rationale |
|-------|------------|-----------|
| Unit Tests | No | No application code changes |
| Integration Tests | No | Infrastructure configuration only |
| E2E Tests | No | Manual validation sufficient |
| Manual Validation | Yes | Primary test method |

### Manual Validation Checklist

**Development Mode (Regression)**:
- [ ] `make start` works without `ENV` set
- [ ] `make docker-logs` shows container output
- [ ] `make stop` stops all containers
- [ ] No Loki-related errors in startup output

**Production Mode Prerequisites**:
- [ ] `make check-loki` passes (plugin installed)
- [ ] `LOKI_URL` set in `.env`
- [ ] Grafana Cloud account accessible

**Production Mode Functional**:
- [ ] `make start ENV=prod` starts with Loki logging
- [ ] Console shows "production mode" indication
- [ ] Logs appear in Grafana Cloud within 10 seconds
- [ ] Labels visible in Grafana: `service`, `env`, `project`
- [ ] `make stop ENV=prod` stops containers
- [ ] `make docker-logs ENV=prod` shows container logs during runtime

**Error Handling**:
- [ ] `make start ENV=prod` fails gracefully if Loki plugin missing
- [ ] Error message includes install command
- [ ] `make start ENV=prod` fails gracefully if `LOKI_URL` not set
- [ ] Error message includes configuration example
- [ ] Exit codes are non-zero on failure

**Documentation**:
- [ ] `env.example` contains `LOKI_URL` with instructions
- [ ] `docs/operations/ALERTING.md` exists with LogQL queries

### Coverage Summary

| Story | Test Method | Coverage Target |
|-------|-------------|-----------------|
| 11.1 | Config validation, code review | 100% of ACs |
| 11.2 | Manual testing of all paths | 100% of ACs |
| 11.3 | Manual testing of all commands | 100% of ACs |
| 11.4 | File inspection | 100% of ACs |
| 11.5 | File inspection, LogQL syntax check | 100% of ACs |
| 11.6 | Manual checklist execution | 100% of ACs |

### Edge Cases

| Scenario | Expected Behavior | Test Method |
|----------|-------------------|-------------|
| ENV=prod without Loki plugin | Fail fast with install instructions | Manual |
| ENV=prod with LOKI_URL=REPLACE_ME | Fail fast with config instructions | Manual |
| ENV=staging (invalid) | Treated as dev mode | Manual |
| Grafana Cloud unreachable | Containers start, logs buffered locally | Manual (disconnect network) |
| Very long log lines (>64KB) | Truncated by Loki driver | Optional manual test |
