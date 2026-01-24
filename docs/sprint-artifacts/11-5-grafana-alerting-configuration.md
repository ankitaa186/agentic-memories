# Story 11.5: Grafana Alerting Configuration

Status: review

## Story

As a **DevOps engineer**,
I want **documented alerting rules and LogQL queries for Grafana Cloud**,
so that **I can set up proactive monitoring and receive notifications for critical issues**.

## Acceptance Criteria

1. **AC-11.5.1**: `docs/operations/ALERTING.md` created with recommended alert rules
2. **AC-11.5.2**: LogQL queries provided for: error spike, ChromaDB failure, redis disconnect, LLM latency
3. **AC-11.5.3**: Step-by-step Grafana Cloud alert setup instructions included
4. **AC-11.5.4**: YAML export example provided for alert rule automation

## Tasks / Subtasks

- [x] Task 1: Create docs/operations directory structure (AC: 1)
  - [x] Create `docs/operations/` directory if it doesn't exist
  - [x] Create `docs/operations/ALERTING.md` file
- [x] Task 2: Document critical alerts with LogQL queries (AC: 1, 2)
  - [x] Service Error Spike alert
  - [x] API Health Check Failed alert
  - [x] Redis Connection Lost alert
  - [x] Container Restart alert
  - [x] ChromaDB Connection Failed alert
- [x] Task 3: Document warning alerts with LogQL queries (AC: 1, 2)
  - [x] LLM Latency High alert
  - [x] Memory Store Failures alert
  - [x] Extraction Errors alert
  - [x] Rate Limit Warnings alert
- [x] Task 4: Document cost monitoring alerts (AC: 1)
  - [x] OpenAI API Calls High alert
  - [x] High Log Volume alert
- [x] Task 5: Write step-by-step setup instructions (AC: 3)
  - [x] Navigate to Alerting -> Alert Rules
  - [x] Create new alert rule
  - [x] Configure LogQL query
  - [x] Set condition threshold
  - [x] Configure notification channel
- [x] Task 6: Provide YAML export example (AC: 4)
  - [x] Include complete apiVersion 1 alert rule YAML
  - [x] Show datasource configuration
  - [x] Include labels and annotations
- [x] Task 7: Add useful LogQL query reference (AC: 2)
  - [x] View all errors query
  - [x] API requests by endpoint query
  - [x] Memory operations query
  - [x] Profile extraction events query
  - [x] ChromaDB operations query
  - [x] Redis operations query

## Dev Notes

### Architecture Alignment

This story creates operational documentation that enables proactive monitoring. The alerts are designed to catch issues before they impact users and provide actionable information for debugging.

**Alert Categories:**
| Category | Purpose | Notification |
|----------|---------|--------------|
| Critical | Service failures, connection errors | Immediate email |
| Warning | Performance degradation, elevated errors | Email |
| Cost | Usage threshold monitoring | Daily digest |

### Project Structure Notes

**File Location:**
- Path: `/docs/operations/ALERTING.md`
- Type: New file

**Directory Structure:**
```
docs/
├── operations/          # NEW directory
│   └── ALERTING.md     # NEW file
├── epic-cloud-logging.md
├── sprint-artifacts/
│   └── tech-spec-epic-11.md
└── ...
```

### Document Content Outline

The document should include:

1. **Introduction** - Overview of Grafana Cloud alerting capabilities
2. **Critical Alerts Table** - Name, LogQL, Condition, Notification
3. **Warning Alerts Table** - Name, LogQL, Condition, Notification
4. **Cost Monitoring Table** - Name, LogQL, Condition, Notification
5. **Setup Instructions** - Step-by-step with screenshots placeholders
6. **YAML Export Example** - For automation/version control
7. **Useful LogQL Queries** - Reference section for ad-hoc debugging

### LogQL Query Reference

**Critical Alerts:**
```logql
# Service Error Spike
sum(count_over_time({project="agentic-memories"} |= "ERROR" [5m]))

# API Health Check Failed
{service="api"} |= "health" |= "failed"

# Redis Connection Lost
{project="agentic-memories"} |= "redis" |= "connection" |= "error"

# ChromaDB Connection Failed
{service="api"} |= "ChromaDB" |= "error"
```

**Warning Alerts:**
```logql
# LLM Latency High
{service="api"} | json | duration_ms > 5000

# Memory Store Failures
{service="api"} |= "store" |= "failed"

# Extraction Errors
{service="api"} |= "extraction" |= "error"
```

**Useful Queries:**
```logql
# View all errors
{project="agentic-memories"} |= "ERROR"

# API requests by endpoint
{service="api"} | json | line_format "{{.method}} {{.path}} - {{.status}}"

# Memory operations
{service="api"} |= "memory" | json

# ChromaDB operations
{service="api"} |= "chroma" | json
```

### Grafana Cloud Free Tier Limits

| Resource | Limit |
|----------|-------|
| Alert rules | 50 |
| Notification channels | Unlimited (email free) |
| Evaluation interval | 1 minute minimum |

### References

- [Source: docs/epic-cloud-logging.md#Story-11.5]
- [Source: docs/sprint-artifacts/tech-spec-epic-11.md#Story-11.5]
- [Grafana Alerting Documentation](https://grafana.com/docs/grafana/latest/alerting/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/logql/)

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/11-5-grafana-alerting-configuration.context.xml

### Agent Model Used

Claude Opus 4.5

### Debug Log References

- Created docs/operations directory
- Created ALERTING.md with comprehensive alerting documentation

### Completion Notes List

- Created docs/operations/ALERTING.md with full alerting guide
- Documented 5 critical alerts (error spike, health check, redis, container restart, ChromaDB)
- Documented 4 warning alerts (LLM latency, store failures, extraction errors, rate limits)
- Documented 2 cost monitoring alerts
- Step-by-step Grafana Cloud setup instructions (7 steps)
- YAML export example with apiVersion 1 format
- 10 useful LogQL queries for debugging
- Troubleshooting section for common issues

### File List

- docs/operations/ALERTING.md (NEW)

---

## Senior Developer Review (AI)

### Reviewer
Ankit

### Date
2026-01-17

### Outcome
**APPROVE** ✅

All 4 acceptance criteria are fully implemented. The ALERTING.md document provides comprehensive alerting guidance including all required LogQL queries, step-by-step setup instructions, and YAML export example.

### Summary
Story 11.5 creates `docs/operations/ALERTING.md` with recommended alert rules for Agentic Memories. The document includes 5 critical alerts, 4 warning alerts, 2 cost monitoring alerts, 7-step setup instructions, YAML export example, 10 useful LogQL queries, and troubleshooting section.

### Key Findings
No issues found. Documentation is thorough and exceeds requirements.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC-11.5.1 | ALERTING.md created with alert rules | ✅ IMPLEMENTED | File exists with tables at lines 11-46 |
| AC-11.5.2 | LogQL for error spike, ChromaDB, redis, LLM latency | ✅ IMPLEMENTED | Lines 17, 21, 19, 31 |
| AC-11.5.3 | Step-by-step Grafana setup instructions | ✅ IMPLEMENTED | Lines 49-98: 7 detailed steps |
| AC-11.5.4 | YAML export example provided | ✅ IMPLEMENTED | Lines 101-140: apiVersion 1 YAML |

**Summary: 4 of 4 acceptance criteria fully implemented**

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: Create directory structure | [x] | ✅ | docs/operations/ exists |
| Task 2: Document critical alerts | [x] | ✅ | Lines 11-22: 5 alerts |
| Task 3: Document warning alerts | [x] | ✅ | Lines 25-35: 4 alerts |
| Task 4: Document cost alerts | [x] | ✅ | Lines 38-46: 2 alerts |
| Task 5: Write setup instructions | [x] | ✅ | Lines 49-98: 7 steps |
| Task 6: Provide YAML example | [x] | ✅ | Lines 101-140 |
| Task 7: Add LogQL reference | [x] | ✅ | Lines 144-199: 10 queries |

**Summary: 7 of 7 completed tasks verified, 0 questionable, 0 falsely marked**

### Test Coverage and Gaps
- Documentation file; no tests required ✅
- LogQL syntax appears valid ✅

### Architectural Alignment
- Follows Grafana Cloud alerting patterns ✅
- Labels match docker-compose.prod.yml ✅

### Security Notes
- No credentials in documentation ✅
- Troubleshooting refers to .env appropriately ✅

### Best-Practices and References
- [Grafana Loki LogQL](https://grafana.com/docs/loki/latest/logql/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)

### Action Items
None required.

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-17 | 1.0 | Story implemented |
| 2026-01-17 | 1.0 | Senior Developer Review notes appended - APPROVED |
