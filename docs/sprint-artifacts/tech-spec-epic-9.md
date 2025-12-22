# Epic Technical Specification: Neo4j Removal - Architecture Simplification

Date: 2025-12-21
Author: Ankit
Epic ID: 9
Status: Draft

---

## Overview

This epic removes Neo4j from the Agentic Memories architecture based on deep codebase analysis that revealed Neo4j is configured and writes data, but its graph capabilities are not leveraged. The system writes to Neo4j but never reads from it for any meaningful operation - all retrieval uses ChromaDB (semantic search) or TimescaleDB (temporal queries).

**Key Finding:** Neo4j was added with the intent to enable graph-based knowledge reasoning (CORRELATED_WITH, SIMILAR_TO, INFLUENCED relationships), but these features were never implemented. The infrastructure exists but delivers no value.

**Impact:** Simplify architecture from 4 databases to 3 (ChromaDB, TimescaleDB/PostgreSQL), reduce operational overhead, improve ingestion performance by eliminating ~50-100ms Neo4j write latency per memory.

## Objectives and Scope

### In Scope

- Remove all Neo4j write operations from memory services (episodic, procedural, portfolio)
- Remove Neo4j write operations from storage orchestrator
- Remove dead `:RELATED_TO` query from hybrid retrieval (line 614-620)
- Delete `src/dependencies/neo4j_client.py` entirely
- Remove `neo4j==5.23.1` from requirements.txt/pyproject.toml
- Remove Neo4j environment variables from docker-compose and .env.example
- Archive or delete `migrations/neo4j/` directory
- Update `migrations/migrate.sh` to remove Neo4j migration handling
- Remove Neo4j from health check endpoints
- Update all tests that mock Neo4j
- Update architecture documentation to reflect 3-database architecture

### Out of Scope

- Adding new graph database functionality (no replacement)
- Migrating Neo4j data to another graph solution (data already exists in PostgreSQL/TimescaleDB)
- Changing ChromaDB or TimescaleDB usage patterns
- Modifying public API contracts (all endpoints unchanged)
- Adding new features - this is pure subtraction/simplification

## System Architecture Alignment

### Current Architecture (Before)

The current architecture uses 4 databases per PRD line 56 and Architecture doc:

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Ingestion                          │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ TimescaleDB │      │  ChromaDB   │      │   Neo4j     │ ← TO BE REMOVED
│ (Time-series)│     │  (Vectors)  │      │  (Graph)    │
└─────────────┘      └─────────────┘      └─────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
               ┌─────────────────────────┐
               │   Redis (Cache Layer)   │
               └─────────────────────────┘
```

### Target Architecture (After)

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Ingestion                          │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌─────────────┐                 ┌─────────────┐
     │ TimescaleDB │                 │  ChromaDB   │
     │ + PostgreSQL│                 │  (Vectors)  │
     │(Time-series │                 └─────────────┘
     │ + Structured)│
     └─────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
               ┌─────────────────────────┐
               │   Redis (Cache Layer)   │
               └─────────────────────────┘
```

### Architecture Alignment Notes

Per Architecture doc Section "Technology Stack & Versions" (line 74-86):
- Neo4j is listed as `Neo4j: 5.23.1`
- Removal affects no other dependencies

Per PRD line 56:
- Current: "6 memory types across 5 databases (ChromaDB, TimescaleDB, PostgreSQL, Neo4j, Redis)"
- After: "6 memory types across 4 databases (ChromaDB, TimescaleDB, PostgreSQL, Redis)"

**Note:** Redis is cache-only, not primary storage. TimescaleDB and PostgreSQL share the same connection (TimescaleDB is PostgreSQL extension).

## Detailed Design

### Services and Modules

| Service/Module | Current State | Change Required |
|----------------|---------------|-----------------|
| `src/services/episodic_memory.py` | Writes to TimescaleDB + Neo4j + ChromaDB | Remove `_store_in_neo4j()` method |
| `src/services/procedural_memory.py` | Writes to PostgreSQL + Neo4j + ChromaDB | Remove `_store_skill_relationships()` method |
| `src/services/portfolio_service.py` | Writes to PostgreSQL + Neo4j | Remove Neo4j Holding node creation |
| `src/services/emotional_memory.py` | Writes to TimescaleDB + ChromaDB (no Neo4j) | No change needed |
| `src/storage/orchestrator.py` | Creates Episode nodes + LED_TO relationships | Remove Neo4j writes |
| `src/services/hybrid_retrieval.py` | Has dead `:RELATED_TO` query (never executed) | Remove lines 614-620 |
| `src/dependencies/neo4j_client.py` | Neo4j connection pooling + health check | DELETE ENTIRE FILE |
| `src/dependencies/__init__.py` | Exports neo4j_client | Remove neo4j exports |

### Data Models and Contracts

**No changes to data models.** All data written to Neo4j already exists in other databases:

| Neo4j Data | Already Exists In | Verified Location |
|------------|-------------------|-------------------|
| Episode nodes | TimescaleDB `episodic_memories` | Full content + metadata |
| Person nodes + INVOLVES | TimescaleDB `episodic_memories.participants` (array) | Participant list |
| Skill nodes | PostgreSQL `procedural_memories` | Full skill data |
| PREREQUISITE_FOR relationships | PostgreSQL `procedural_memories.prerequisites` (array) | Prerequisites list |
| Context nodes + USED_IN | PostgreSQL `procedural_memories.context` | Context data |
| Holding nodes | PostgreSQL `portfolio_holdings` | Full holding data |
| LED_TO relationships | Not queried | Can be safely removed |

### APIs and Interfaces

**No API changes.** All existing endpoints continue to function identically:

- `POST /v1/store` - Ingestion endpoint (removes Neo4j write internally)
- `GET /v1/retrieve` - Retrieval endpoint (already doesn't use Neo4j)
- `GET /v1/search` - Search endpoint (uses ChromaDB)
- `GET /health/full` - Health check (remove Neo4j check)

### Workflows and Sequencing

**Ingestion Pipeline (LangGraph) Changes:**

```
BEFORE:
init → worthiness → extract → classify → build_memories →
  store_chromadb → store_episodic → store_emotional →
  store_procedural → store_portfolio → store_neo4j → summarize → finalize

AFTER:
init → worthiness → extract → classify → build_memories →
  store_chromadb → store_episodic → store_emotional →
  store_procedural → store_portfolio → summarize → finalize
```

**Removal Sequence (Execution Order):**

1. **Story 9.1:** Remove Neo4j writes from memory services (breaks nothing - writes are fire-and-forget)
2. **Story 9.2:** Remove Neo4j from orchestrator and hybrid retrieval (removes dead code)
3. **Story 9.3:** Remove Neo4j client and dependencies (clean up imports)
4. **Story 9.4:** Remove infrastructure configuration (docker, env, migrations)
5. **Story 9.5:** Update tests and documentation (finalize)

## Non-Functional Requirements

### Performance

| Metric | Current | After Removal | Improvement |
|--------|---------|---------------|-------------|
| Ingestion latency (per memory) | ~350ms | ~250-300ms | -50-100ms |
| Memory footprint (connection pool) | +50MB (Neo4j driver) | -50MB | Reduced |
| Cold start time | Includes Neo4j connection | Faster | Faster startup |

**Rationale:** Neo4j writes add ~50-100ms latency per memory. Removing them directly improves ingestion performance.

### Security

No security changes. Neo4j was not exposed externally:
- Connection was internal (bolt://localhost:7687)
- No external Neo4j endpoints
- No authentication tokens to remove (internal network only)

### Reliability/Availability

**Improved reliability:**
- One fewer database to fail
- Simpler failure mode (3 DBs instead of 4)
- Neo4j already had graceful degradation (exceptions caught)

**No new risks:** Removal is pure subtraction.

### Observability

**Changes:**
- Remove Neo4j health check from `/health/full` endpoint
- Remove Neo4j connection metrics
- Update any dashboards that monitor Neo4j

**No new observability requirements.**

## Dependencies and Integrations

### Dependencies to Remove

| Dependency | Version | Location | Action |
|------------|---------|----------|--------|
| `neo4j` | 5.23.1 | requirements.txt or pyproject.toml | DELETE |

### Files to Remove/Modify

| File | Action | Notes |
|------|--------|-------|
| `src/dependencies/neo4j_client.py` | DELETE | ~50 lines |
| `migrations/neo4j/001_graph_constraints.up.cql` | ARCHIVE or DELETE | |
| `migrations/neo4j/001_graph_constraints.down.cql` | ARCHIVE or DELETE | |

### Environment Variables to Remove

| Variable | Location | Action |
|----------|----------|--------|
| `NEO4J_URI` | docker-compose.yml, .env.example | DELETE |
| `NEO4J_USER` | docker-compose.yml, .env.example | DELETE |
| `NEO4J_PASSWORD` | docker-compose.yml, .env.example | DELETE |

## Acceptance Criteria (Authoritative)

### AC-9.1: Memory Services Neo4j Removal
1. **AC-9.1.1:** `episodic_memory.py` contains no Neo4j imports or session.run() calls
2. **AC-9.1.2:** `procedural_memory.py` contains no Neo4j imports or session.run() calls
3. **AC-9.1.3:** `portfolio_service.py` contains no Neo4j imports or session.run() calls
4. **AC-9.1.4:** All existing unit tests pass without Neo4j mocks
5. **AC-9.1.5:** Integration test for `/v1/store` succeeds without Neo4j running

### AC-9.2: Orchestrator and Retrieval Neo4j Removal
1. **AC-9.2.1:** `storage/orchestrator.py` contains no Neo4j imports or writes
2. **AC-9.2.2:** `hybrid_retrieval.py` contains no `:RELATED_TO` query (lines 614-620 removed)
3. **AC-9.2.3:** Hybrid retrieval tests pass without Neo4j
4. **AC-9.2.4:** `/v1/retrieve` endpoint returns correct results without Neo4j

### AC-9.3: Client and Dependencies Removal
1. **AC-9.3.1:** `src/dependencies/neo4j_client.py` file does not exist
2. **AC-9.3.2:** `src/dependencies/__init__.py` contains no neo4j references
3. **AC-9.3.3:** `grep -r "neo4j" src/` returns no matches (except comments if any)
4. **AC-9.3.4:** `grep -r "from neo4j" src/` returns no matches
5. **AC-9.3.5:** requirements.txt/pyproject.toml contains no neo4j dependency
6. **AC-9.3.6:** `pip install -r requirements.txt` succeeds without neo4j
7. **AC-9.3.7:** Application starts successfully without Neo4j driver

### AC-9.4: Infrastructure Removal
1. **AC-9.4.1:** docker-compose.yml contains no NEO4J_* environment variables
2. **AC-9.4.2:** .env.example contains no NEO4J_* variables
3. **AC-9.4.3:** `migrations/neo4j/` directory is archived or deleted
4. **AC-9.4.4:** `migrations/migrate.sh` contains no Neo4j migration handling
5. **AC-9.4.5:** `/health/full` endpoint does not check Neo4j
6. **AC-9.4.6:** `docker-compose up` succeeds without Neo4j service

### AC-9.5: Tests and Documentation
1. **AC-9.5.1:** All test files containing Neo4j mocks are updated or removed
2. **AC-9.5.2:** `pytest tests/` passes with 100% success rate
3. **AC-9.5.3:** Test coverage remains at or above current baseline
4. **AC-9.5.4:** Architecture documentation updated to show 3 databases
5. **AC-9.5.5:** README or setup docs updated to remove Neo4j setup steps
6. **AC-9.5.6:** `grep -ri "neo4j" docs/` shows updated/removed references

## Traceability Mapping

| AC | Spec Section | Component/File | Test Approach |
|----|--------------|----------------|---------------|
| AC-9.1.1-3 | Detailed Design > Services | episodic_memory.py, procedural_memory.py, portfolio_service.py | Unit tests with storage mocks |
| AC-9.1.4-5 | Workflows | unified_ingestion_graph.py | Integration test: POST /v1/store |
| AC-9.2.1 | Detailed Design > Orchestrator | storage/orchestrator.py | Unit test orchestrator methods |
| AC-9.2.2-4 | Detailed Design > Retrieval | hybrid_retrieval.py | Integration test: GET /v1/retrieve |
| AC-9.3.1-7 | Dependencies | neo4j_client.py, requirements.txt | grep verification + pip install |
| AC-9.4.1-6 | Infrastructure | docker-compose.yml, .env, migrate.sh | docker-compose up, health check |
| AC-9.5.1-6 | Tests/Docs | tests/, docs/ | pytest, grep documentation |

## Risks, Assumptions, Open Questions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Hidden Neo4j dependency** | Low | Medium | grep -r "neo4j" across entire codebase before declaring complete |
| **Test failures due to mock removal** | Medium | Low | Update mocks incrementally per story |
| **Documentation out of sync** | Medium | Low | Final story (9.5) explicitly updates all docs |

### Assumptions

1. **No external systems depend on Neo4j** - Verified: Neo4j is internal only (localhost:7687)
2. **All relationship data exists elsewhere** - Verified: See Data Models section
3. **Graceful degradation already exists** - Verified: Neo4j failures are caught and ignored
4. **No planned graph features in near future** - Confirmed by analysis: no graph queries exist

### Open Questions

1. **Archive vs Delete migrations?**
   - Recommendation: Archive to `migrations/_archived/neo4j/` for audit trail
   - Decision: Per team preference

2. **Should we add a comment explaining why Neo4j was removed?**
   - Recommendation: Add brief comment in architecture.md for future reference
   - Decision: Yes, document the decision

## Test Strategy Summary

### Test Levels

| Level | Approach | Tools |
|-------|----------|-------|
| **Unit Tests** | Remove Neo4j mocks, verify services work without Neo4j | pytest, unittest.mock |
| **Integration Tests** | Full pipeline tests without Neo4j running | pytest, docker-compose (no Neo4j) |
| **Regression Tests** | Verify all existing endpoints return identical responses | pytest, response comparison |

### Test Coverage

- **Target:** Maintain current coverage level (no decrease)
- **Files to update:** tests/services/test_episodic_memory.py, test_procedural_memory.py, test_portfolio_service.py, test_hybrid_retrieval.py

### Edge Cases

1. **Empty Neo4j** - N/A (removing entirely)
2. **Neo4j connection failure** - N/A (removing entirely)
3. **Partial Neo4j write** - N/A (removing entirely)

### Validation Commands

```bash
# Verify no Neo4j imports remain
grep -r "neo4j" src/ --include="*.py"
grep -r "from neo4j" src/ --include="*.py"

# Verify dependencies removed
grep -i "neo4j" requirements.txt
grep -i "neo4j" pyproject.toml

# Verify tests pass
pytest tests/ -v

# Verify application starts
python -c "from src.app import app; print('OK')"

# Verify health check
curl http://localhost:8080/health/full
```

---

**Document Version History:**
- v1.0 (2025-12-21): Initial tech spec based on deep codebase analysis by Party Mode team
