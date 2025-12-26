# Story 5.7: Execution History Endpoint

Status: done

## Story

As an **Annie Dashboard or Admin User**,
I want **a `/history` endpoint that returns execution records for an intent**,
so that **I can view the audit trail of when and how triggers were fired**.

## Acceptance Criteria

1. **AC1:** `GET /v1/intents/{id}/history` returns execution records
   - Returns array of `IntentExecutionResponse` objects
   - Includes all fields from intent_executions table
   - Empty array if no executions exist

2. **AC2:** Paginated with limit parameter
   - Default limit: 50
   - Maximum limit: 100
   - Supports offset for pagination

3. **AC3:** Ordered by `executed_at DESC`
   - Most recent executions first
   - Consistent ordering for pagination

4. **AC4:** Includes all execution details
   - status, trigger_data, gate_result
   - message_id, message_preview
   - evaluation_ms, generation_ms, delivery_ms
   - error_message (if failed)

5. **AC5:** Returns 404 for non-existent intent
   - Validates intent exists before querying history
   - Returns appropriate error response

6. **AC6:** Langfuse tracing
   - Wrap endpoint with `@observe` decorator
   - Log intent_id and result count

## Tasks / Subtasks

- [x] **Task 1: Add `get_intent_history()` to IntentService** (AC: 1, 2, 3, 4, 5)
  - [x] 1.1 Add method signature with intent_id, limit, offset parameters
  - [x] 1.2 Validate intent exists (return not found if missing)
  - [x] 1.3 Query intent_executions table
  - [x] 1.4 Add ORDER BY executed_at DESC
  - [x] 1.5 Add LIMIT and OFFSET clauses
  - [x] 1.6 Map rows to IntentExecutionResponse objects
  - [x] 1.7 Return list in IntentHistoryResult

- [x] **Task 2: Add history endpoint to router** (AC: 1, 5, 6)
  - [x] 2.1 Add `GET /{intent_id}/history` endpoint
  - [x] 2.2 Add optional limit and offset query parameters
  - [x] 2.3 Add `@observe(name="intents.history")` decorator
  - [x] 2.4 Call `IntentService.get_intent_history()`
  - [x] 2.5 Return 404 if intent not found
  - [x] 2.6 Return list of executions on success

- [x] **Task 3: Write integration tests** (AC: 1-6)
  - [x] 3.1 Test history returns execution records
  - [x] 3.2 Test history with pagination (limit/offset)
  - [x] 3.3 Test history returns empty array when no executions
  - [x] 3.4 Test history ordered by executed_at DESC
  - [x] 3.5 Test history includes all execution fields
  - [x] 3.6 Test 404 for non-existent intent
  - [x] 3.7 Test Langfuse trace created (via @observe decorator)

## Dev Notes

### Architecture Patterns

- Follow existing patterns from Story 5.4, 5.5, 5.6
- Add new method to existing `IntentService` class
- Add new endpoint to existing `intents.py` router
- Reuse IntentExecutionResponse from schemas.py

### Project Structure Notes

- Modified files:
  - `src/services/intent_service.py` - Add `get_intent_history()` method
  - `src/routers/intents.py` - Add `GET /{id}/history` endpoint
  - `tests/integration/test_intents_api.py` - Add history tests
- No new files needed - extending existing infrastructure

### Database Query Pattern

```sql
-- History query (AC1, AC2, AC3, AC4)
SELECT * FROM intent_executions
WHERE intent_id = $1
ORDER BY executed_at DESC
LIMIT $2 OFFSET $3;
```

### Learnings from Previous Story

**From Story 5-6-fire-endpoint-with-state-management (Status: done)**

- **IntentFireResult Pattern**: Use dataclass for structured results
- **intent_executions Table**: INSERT works, SELECT should follow same row mapping
- **IntentExecutionResponse**: Already exists in schemas.py (lines 383-402)
- **Route Placement**: Consider placing before /{intent_id} endpoints
- **Langfuse Pattern**: Use `@observe(name="intents.history")` decorator
- **Connection Management**: Use `get_timescale_conn()`/`release_timescale_conn()` pattern

[Source: docs/sprint-artifacts/5-6-fire-endpoint-with-state-management.md#Dev-Agent-Record]

### Testing Considerations

- Mock database cursor for unit tests
- Test pagination with multiple execution records
- Test empty result set behavior
- Test field mapping from DB to Pydantic model

### References

- [Source: docs/epic-5-scheduled-intents.md#Story-5.7]
- [Source: src/services/intent_service.py] - IntentService to extend
- [Source: src/routers/intents.py] - Router to extend
- [Source: tests/integration/test_intents_api.py] - Test patterns

## Dev Agent Record

### Context Reference

<!-- Context derived from Story 5.6 patterns and existing codebase -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- No errors during implementation
- All 46 integration tests pass (38 existing + 8 new)

### Completion Notes List

1. **IntentHistoryResult dataclass** (~12 lines)
   - Added to intent_service.py for history operation results
   - Pattern consistent with IntentFireResult

2. **IntentService.get_intent_history()** (~60 lines)
   - Validates intent exists first (AC5)
   - Queries intent_executions with ORDER BY executed_at DESC (AC3)
   - Enforces max limit of 100 (AC2)
   - Returns IntentHistoryResult with executions list

3. **IntentService._execution_row_to_response()** (~45 lines)
   - Maps database rows to IntentExecutionResponse
   - Handles both dict and tuple cursor results
   - Includes all execution fields (AC4)

4. **GET /{intent_id}/history endpoint** (~50 lines)
   - @observe(name="intents.history") decorator for Langfuse (AC6)
   - Query parameters: limit (1-100, default 50), offset (default 0)
   - Returns 404 for non-existent intent (AC5)
   - Returns list of IntentExecutionResponse on success (AC1)

5. **Integration tests** (8 new tests in TestHistoryIntent class)
   - Tests cover all 6 ACs
   - Fixtures for execution_row and execution_rows (for pagination)

### File List

| File | Action | Lines Changed |
|------|--------|---------------|
| `src/services/intent_service.py` | Modified | +117 (IntentHistoryResult, get_intent_history, _execution_row_to_response) |
| `src/routers/intents.py` | Modified | +52 (GET /{id}/history endpoint) |
| `tests/integration/test_intents_api.py` | Modified | +178 (TestHistoryIntent class with 8 tests) |

## Change Log

| Date | Change |
|------|--------|
| 2025-12-23 | Story drafted from Epic 5 with learnings from Story 5.6 |
| 2025-12-23 | Implementation complete - all 3 tasks done, 8 new tests passing |
| 2025-12-23 | SM Review: APPROVED - moved to done |

## SM Review Notes

### Review Date: 2025-12-23

### Reviewer: Claude Opus 4.5 (SM Agent)

### Review Outcome: APPROVED

All acceptance criteria implemented with evidence. All tasks verified complete. No issues found.

### AC Validation Summary

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC1 | GET /history returns execution records | ✅ PASS | `intents.py:259`, `intent_service.py:661-721` |
| AC2 | Paginated with limit/offset | ✅ PASS | `intents.py:263-264` (ge=1, le=100, default 50), `intent_service.py:680-681` |
| AC3 | Ordered by executed_at DESC | ✅ PASS | `intent_service.py:703` - ORDER BY clause |
| AC4 | Includes all execution fields | ✅ PASS | `intent_service.py:697-700` SELECT, `intent_service.py:883-931` mapper |
| AC5 | Returns 404 for missing intent | ✅ PASS | `intent_service.py:686-692` validation, `intents.py:288-290` |
| AC6 | Langfuse tracing | ✅ PASS | `intents.py:260` - @observe(name="intents.history") |

**Summary:** 6 of 6 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: get_intent_history() | [x] | ✅ | `intent_service.py:661-721` - complete method |
| 1.1 Method signature | [x] | ✅ | `intent_service.py:661-666` |
| 1.2 Validate intent exists | [x] | ✅ | `intent_service.py:686-692` |
| 1.3 Query intent_executions | [x] | ✅ | `intent_service.py:695-707` |
| 1.4 ORDER BY executed_at DESC | [x] | ✅ | `intent_service.py:703` |
| 1.5 LIMIT and OFFSET | [x] | ✅ | `intent_service.py:704` |
| 1.6 Map to IntentExecutionResponse | [x] | ✅ | `intent_service.py:710` |
| 1.7 Return IntentHistoryResult | [x] | ✅ | `intent_service.py:717` |
| Task 2: Router endpoint | [x] | ✅ | `intents.py:259-304` |
| 2.1 GET /{id}/history | [x] | ✅ | `intents.py:259` |
| 2.2 limit/offset params | [x] | ✅ | `intents.py:263-264` |
| 2.3 @observe decorator | [x] | ✅ | `intents.py:260` |
| 2.4 Call service method | [x] | ✅ | `intents.py:285` |
| 2.5 Return 404 | [x] | ✅ | `intents.py:288-290` |
| 2.6 Return list | [x] | ✅ | `intents.py:295` |
| Task 3: Integration tests | [x] | ✅ | `test_intents_api.py:893-1065` - 8 tests |
| 3.1-3.7 All subtasks | [x] | ✅ | Individual tests verified in TestHistoryIntent class |

**Summary:** 20 of 20 completed tasks verified, 0 questionable, 0 falsely marked complete

### Test Coverage

- 8 new tests in TestHistoryIntent class covering all 6 ACs
- All 46 integration tests pass (38 existing + 8 new)
- Tests cover: happy path, pagination, empty results, ordering, field presence, 404, database error, decorator

### Architectural Alignment

- Follows IntentServiceResult/IntentFireResult pattern with IntentHistoryResult dataclass
- Uses get_timescale_conn()/release_timescale_conn() connection management
- Endpoint placed before /{intent_id} to avoid FastAPI route conflicts
- Reuses existing IntentExecutionResponse schema

### Security Notes

- No security concerns identified
- UUID validation prevents injection
- Parameterized SQL queries used

### DoD Checklist

- [x] All acceptance criteria implemented with evidence
- [x] All tasks verified complete
- [x] Integration tests passing
- [x] No regression in existing tests
- [x] Code follows project patterns
- [x] Langfuse tracing enabled
