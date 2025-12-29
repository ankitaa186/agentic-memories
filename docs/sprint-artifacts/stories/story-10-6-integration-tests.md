# Story 10.6: Integration Tests

**Epic:** 10 - Direct Memory API
**Story ID:** 10-6
**Status:** ready-for-dev
**Dependencies:** Story 10.5 (Unit Tests)
**Blocked By:** 10-5-unit-tests

---

## Goal

End-to-end testing of store/retrieve/delete lifecycle with real storage backends.

## Acceptance Criteria

### AC 10.6.1: Lifecycle Test

**Given** the Direct Memory API endpoints are implemented
**When** a memory is stored via `POST /v1/memories/direct`
**Then** the memory is retrievable via `/v1/retrieve`

**Given** a stored memory exists
**When** the memory is deleted via `DELETE /v1/memories/{memory_id}`
**Then** the memory is no longer retrievable via `/v1/retrieve`

- [ ] Store memory via direct API
- [ ] Retrieve via `/v1/retrieve` (verify found)
- [ ] Delete via delete endpoint
- [ ] Retrieve again (verify not found)

### AC 10.6.2: Typed Memory Tests

**Given** the Direct Memory API supports typed memory storage
**When** an episodic memory is stored with `event_timestamp`
**Then** the memory appears in time-based hybrid retrieval

**Given** the Direct Memory API supports typed memory storage
**When** an emotional memory is stored with `emotional_state`
**Then** the memory appears in emotional retrieval

**Given** the Direct Memory API supports typed memory storage
**When** a procedural memory is stored with `skill_name`
**Then** the memory appears in procedural queries

- [ ] Store episodic memory -> verify in time-based retrieval
- [ ] Store emotional memory -> verify in emotional retrieval
- [ ] Store procedural memory -> verify in procedural queries

### AC 10.6.3: Performance Test

**Given** the performance requirements for Direct Memory API
**When** a memory is stored via direct store endpoint
**Then** the operation completes in < 3 seconds

**Given** the performance requirements for Direct Memory API
**When** a memory is deleted via delete endpoint
**Then** the operation completes in < 1 second

- [ ] Verify direct store completes in < 3s
- [ ] Verify delete completes in < 1s

## Technical Notes

### Test File Location

`tests/integration/test_direct_memory_api.py`

### Test Approach

- Use FastAPI `TestClient` for HTTP endpoint testing
- Test full lifecycle: store -> retrieve -> delete -> verify not found
- Use real ChromaDB and TimescaleDB connections (integration environment)
- Verify retrieval via existing `/v1/retrieve` endpoint to confirm memories are stored correctly
- Performance assertions with timing measurements

### Test Categories

```python
# Lifecycle tests
# - test_store_and_retrieve_lifecycle
# - test_store_and_delete_lifecycle
# - test_full_lifecycle_store_retrieve_delete

# Typed memory tests
# - test_episodic_memory_in_hybrid_retrieval
# - test_emotional_memory_in_hybrid_retrieval
# - test_procedural_memory_in_hybrid_retrieval

# Performance tests
# - test_direct_store_performance_under_3_seconds
# - test_delete_performance_under_1_second
```

### Test Fixtures

```python
@pytest.fixture
def sample_direct_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User prefers morning meetings before 10am",
        "layer": "semantic",
        "type": "explicit",
        "importance": 0.85,
        "persona_tags": ["preferences", "scheduling"]
    }

@pytest.fixture
def sample_episodic_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User attended team offsite in Lake Tahoe",
        "event_timestamp": "2025-06-15T09:00:00Z",
        "location": "Lake Tahoe, CA",
        "participants": ["team", "manager"],
        "event_type": "work_event"
    }

@pytest.fixture
def sample_emotional_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User expressed frustration about job search",
        "emotional_state": "frustrated",
        "valence": -0.6,
        "arousal": 0.7,
        "trigger_event": "Another job rejection email"
    }

@pytest.fixture
def sample_procedural_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User demonstrated Python expertise",
        "skill_name": "python_programming",
        "proficiency_level": "advanced"
    }
```

### Performance Testing Strategy

- Use `time.time()` or `pytest-benchmark` for timing
- Assert p95 latency thresholds:
  - Store: < 3 seconds
  - Delete: < 1 second
- Run multiple iterations to get reliable measurements

### Dependencies

- Requires Stories 10.1-10.5 to be complete
- Requires running ChromaDB and TimescaleDB instances
- Requires `/v1/retrieve` endpoint to be functional

## Tasks

- [ ] Task 1: Set up integration test infrastructure
  - [ ] 1.1 Create `tests/integration/test_direct_memory_api.py`
  - [ ] 1.2 Configure TestClient with FastAPI app
  - [ ] 1.3 Set up test database connections (ChromaDB, TimescaleDB)
  - [ ] 1.4 Create test cleanup fixtures (delete test data after tests)

- [ ] Task 2: Implement lifecycle tests (AC 10.6.1)
  - [ ] 2.1 Write `test_store_and_retrieve_lifecycle` - store memory, retrieve via `/v1/retrieve`, verify found
  - [ ] 2.2 Write `test_store_and_delete_lifecycle` - store memory, delete, verify deleted
  - [ ] 2.3 Write `test_full_lifecycle_store_retrieve_delete` - complete cycle with verification

- [ ] Task 3: Implement typed memory tests (AC 10.6.2)
  - [ ] 3.1 Write `test_episodic_memory_in_hybrid_retrieval` - store with event_timestamp, verify time-based retrieval
  - [ ] 3.2 Write `test_emotional_memory_in_hybrid_retrieval` - store with emotional_state, verify emotional retrieval
  - [ ] 3.3 Write `test_procedural_memory_in_hybrid_retrieval` - store with skill_name, verify procedural queries

- [ ] Task 4: Implement performance tests (AC 10.6.3)
  - [ ] 4.1 Write `test_direct_store_performance_under_3_seconds` - verify store completes in < 3s
  - [ ] 4.2 Write `test_delete_performance_under_1_second` - verify delete completes in < 1s
  - [ ] 4.3 Add timing assertions with clear error messages

- [ ] Task 5: Test cleanup and verification
  - [ ] 5.1 Ensure all test data is cleaned up after tests
  - [ ] 5.2 Run integration tests against local environment
  - [ ] 5.3 Verify all tests pass consistently
  - [ ] 5.4 Document any environment setup requirements

## Definition of Done

- [ ] All acceptance criteria met (AC 10.6.1, AC 10.6.2, AC 10.6.3)
- [ ] Full store/retrieve/delete lifecycle tested end-to-end
- [ ] Typed memory retrieval verified (episodic, emotional, procedural)
- [ ] Performance verified: store < 3s, delete < 1s
- [ ] All integration tests pass consistently
- [ ] Test cleanup properly removes test data
- [ ] PR ready for review

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-29 | Claude Code | Story drafted from Epic 10 and tech spec |
