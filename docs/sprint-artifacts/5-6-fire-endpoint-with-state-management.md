# Story 5.6: Fire Endpoint with State Management

Status: done

## Story

As an **Annie Proactive AI Worker**,
I want **a `/fire` endpoint that reports execution results and manages state transitions**,
so that **intent state is updated correctly after each execution attempt and I receive the next check time**.

## Acceptance Criteria

1. **AC1:** `POST /v1/intents/{id}/fire` accepts execution results
   - Request body: `IntentFireRequest` with status, trigger_data, gate_result, message_id, error_message, timings
   - Returns `IntentFireResponse` with updated next_check, enabled status, execution_count

2. **AC2:** Always updates `last_checked` timestamp
   - Every fire call updates `last_checked = NOW()` regardless of outcome
   - Tracks when intent was last evaluated

3. **AC3:** Updates execution state on success
   - On `status = 'success'`: Updates `last_executed = NOW()`
   - Increments `execution_count`
   - Updates `last_execution_status`, `last_message_id`

4. **AC4:** Calculates `next_check` based on trigger type and result
   - `success (cron)` → croniter.get_next()
   - `success (interval)` → NOW() + interval_minutes
   - `success (once)` → NULL + enabled=false
   - `success (price/silence)` → NOW() + check_interval_minutes
   - `condition_not_met` → NOW() + 5 minutes
   - `gate_blocked` → NOW() + 5 minutes
   - `failed` → NOW() + 15 minutes

5. **AC5:** Auto-disables triggers when limits reached
   - Disables one-time triggers after successful execution
   - Disables if `execution_count >= max_executions`
   - Disables if `expires_at` has passed

6. **AC6:** Logs execution to `intent_executions` table
   - Creates execution record with all timing/status data
   - Links to intent via `intent_id`
   - Stores gate_result, trigger_data as JSONB

7. **AC7:** Returns 404 for non-existent intent
   - Validates intent exists before processing
   - Returns appropriate error response

8. **AC8:** Langfuse tracing
   - Wrap endpoint with `@observe` decorator
   - Log intent_id, status, and next_check calculation

## Tasks / Subtasks

- [x] **Task 1: Create IntentFireRequest/Response models** (AC: 1)
  - [x] 1.1 Add `IntentFireRequest` to `src/schemas.py` if not exists
  - [x] 1.2 Add `IntentFireResponse` to `src/schemas.py` if not exists
  - [x] 1.3 Include fields: status, trigger_data, gate_result, message_id, error_message, evaluation_ms, generation_ms, delivery_ms
  - [x] 1.4 Response includes: next_check, enabled, execution_count, was_disabled_reason

- [x] **Task 2: Add `fire_intent()` method to IntentService** (AC: 2, 3, 4, 5, 6, 7)
  - [x] 2.1 Add method signature accepting intent_id and IntentFireRequest
  - [x] 2.2 Validate intent exists (return not found if missing)
  - [x] 2.3 Always update `last_checked = NOW()`
  - [x] 2.4 If success: update `last_executed`, increment `execution_count`
  - [x] 2.5 Calculate new `next_check` based on trigger_type and status
  - [x] 2.6 Check auto-disable conditions (once/max_executions/expires_at)
  - [x] 2.7 Update intent record in database
  - [x] 2.8 Insert execution record into `intent_executions` table
  - [x] 2.9 Return IntentFireResponse with updated state

- [x] **Task 3: Add `_calculate_next_check_after_fire()` helper** (AC: 4)
  - [x] 3.1 Accept trigger_type, trigger_schedule, and execution status
  - [x] 3.2 Handle cron type with croniter
  - [x] 3.3 Handle interval type (NOW + interval_minutes)
  - [x] 3.4 Handle once type (return None)
  - [x] 3.5 Handle condition types (price/silence) with check_interval
  - [x] 3.6 Handle failure states with backoff intervals

- [x] **Task 4: Add fire endpoint to router** (AC: 1, 7, 8)
  - [x] 4.1 Add `POST /{intent_id}/fire` endpoint to `src/routers/intents.py`
  - [x] 4.2 Add `@observe(name="intents.fire")` decorator
  - [x] 4.3 Validate UUID path parameter
  - [x] 4.4 Call `IntentService.fire_intent()`
  - [x] 4.5 Return 404 if intent not found
  - [x] 4.6 Return IntentFireResponse on success

- [x] **Task 5: Write integration tests** (AC: 1-8)
  - [x] 5.1 Test fire returns updated state
  - [x] 5.2 Test last_checked always updated
  - [x] 5.3 Test execution_count incremented on success
  - [x] 5.4 Test next_check calculation for each trigger type
  - [x] 5.5 Test one-time trigger disabled after success
  - [x] 5.6 Test max_executions limit disables trigger
  - [x] 5.7 Test expires_at disables trigger
  - [x] 5.8 Test execution logged to intent_executions
  - [x] 5.9 Test 404 for non-existent intent
  - [x] 5.10 Test Langfuse trace created

## Dev Notes

### Architecture Patterns

- Follow existing patterns from Story 5.4 and 5.5
- Add new method to existing `IntentService` class
- Add new endpoint to existing `intents.py` router
- Reuse `_row_to_response()` for consistency
- Create `_calculate_next_check_after_fire()` helper method

### Project Structure Notes

- Modified files:
  - `src/schemas.py` - Add IntentFireRequest/Response if needed
  - `src/services/intent_service.py` - Add `fire_intent()` method
  - `src/routers/intents.py` - Add `POST /{id}/fire` endpoint
  - `tests/integration/test_intents_api.py` - Add fire tests
- No new files needed - extending existing infrastructure

### State Transition Logic

```
fire(status) → updates:
├── ALWAYS: last_checked = NOW()
├── IF success:
│   ├── last_executed = NOW()
│   ├── execution_count += 1
│   ├── last_execution_status = status
│   └── last_message_id = message_id
├── next_check = calculate_next_check_after_fire(...)
└── IF should_disable:
    └── enabled = false
```

### next_check Calculation Table

| Trigger Type | Status | next_check |
|--------------|--------|------------|
| cron | success | croniter.get_next() |
| interval | success | NOW() + interval_minutes |
| once | success | NULL, enabled=false |
| price/silence | success | NOW() + check_interval_minutes |
| any | condition_not_met | NOW() + 5 minutes |
| any | gate_blocked | NOW() + 5 minutes |
| any | failed | NOW() + 15 minutes |

### Learnings from Previous Story

**From Story 5-5-pending-endpoint (Status: done)**

- **IntentService.get_pending_intents()**: Added method following IntentServiceResult pattern
- **Route Placement**: Place new routes BEFORE `/{intent_id}` to avoid conflicts
- **Langfuse Pattern**: Use `@observe(name="intents.fire")` decorator
- **Connection Management**: Use `get_timescale_conn()`/`release_timescale_conn()` pattern
- **Test Pattern**: Mock database cursor, follow existing test structure
- **Query Patterns**: Use parameterized queries with proper NULL handling

[Source: docs/sprint-artifacts/5-5-pending-endpoint.md#Dev-Agent-Record]

### Testing Considerations

- Mock database cursor for unit tests
- Test each trigger type's next_check calculation
- Test auto-disable conditions
- Test execution logging
- Test error handling for missing intent

### References

- [Source: docs/epic-5-scheduled-intents.md#Story-5.6]
- [Source: src/services/intent_service.py] - IntentService to extend
- [Source: src/routers/intents.py] - Router to extend
- [Source: tests/integration/test_intents_api.py] - Test patterns

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/5-6-fire-endpoint-with-state-management.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- No errors during implementation
- All 38 integration tests pass
- All 43 validation tests pass (no regression)

### Completion Notes List

1. **IntentFireRequest/Response models** (already existed in schemas.py)
   - Added `was_disabled_reason: Optional[str]` field to IntentFireResponse
   - All required fields already present from Story 5.2

2. **IntentFireResult dataclass** (~15 lines)
   - Added to intent_service.py for fire operation results
   - Pattern consistent with IntentServiceResult

3. **IntentService.fire_intent()** (~160 lines)
   - Updates last_checked on every call (AC2)
   - Increments execution_count on success (AC3)
   - Calculates next_check via _calculate_next_check_after_fire() (AC4)
   - Handles auto-disable for once/max_executions/expires_at (AC5)
   - Logs to intent_executions table (AC6)
   - Returns IntentFireResult with was_disabled_reason

4. **IntentService._calculate_next_check_after_fire()** (~50 lines)
   - Handles failure backoff: 15 min for failed, 5 min for gate_blocked/condition_not_met
   - Success cases: cron→croniter, interval→+minutes, once→None, condition→check_interval

5. **POST /{intent_id}/fire endpoint** (~55 lines)
   - @observe(name="intents.fire") decorator for Langfuse (AC8)
   - Returns 404 for non-existent intent (AC7)
   - Returns IntentFireResponse on success

6. **Integration tests** (12 new tests in TestFireIntent class)
   - Tests cover all 8 ACs
   - Includes fixtures for interval, once, and max_executions intents

### File List

| File | Action | Lines Changed |
|------|--------|---------------|
| `src/schemas.py` | Modified | +1 (was_disabled_reason field) |
| `src/services/intent_service.py` | Modified | +225 (IntentFireResult, fire_intent, _calculate_next_check_after_fire) |
| `src/routers/intents.py` | Modified | +55 (POST /{id}/fire endpoint) |
| `tests/integration/test_intents_api.py` | Modified | +315 (TestFireIntent class with 12 tests) |

## Change Log

| Date | Change |
|------|--------|
| 2025-12-23 | Story drafted from Epic 5 with learnings from Story 5.5 |
| 2025-12-23 | Story context generated, marked ready-for-dev |
| 2025-12-23 | Implementation complete - all 5 tasks done, 12 new tests passing |
| 2025-12-23 | SM Review: APPROVED - moved to done |

## SM Review Notes

### Review Date: 2025-12-23

### Reviewer: Claude Opus 4.5 (SM Agent)

### Review Outcome: APPROVED

### AC Validation Summary

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC1 | POST /fire accepts results | ✅ PASS | `intents.py:204-251` - endpoint with IntentFireRequest/Response |
| AC2 | Always updates last_checked | ✅ PASS | `intent_service.py:511-512` - `new_last_checked = now` |
| AC3 | Updates execution state on success | ✅ PASS | `intent_service.py:521-524` - increments count, updates last_executed |
| AC4 | Calculates next_check by type | ✅ PASS | `intent_service.py:646-695` - _calculate_next_check_after_fire() |
| AC5 | Auto-disables at limits | ✅ PASS | `intent_service.py:545-559` - once/max_executions/expires_at |
| AC6 | Logs to intent_executions | ✅ PASS | `intent_service.py:589-620` - INSERT INTO intent_executions |
| AC7 | Returns 404 for missing | ✅ PASS | `intent_service.py:504-506` - returns IntentFireResult with error |
| AC8 | Langfuse tracing | ✅ PASS | `intents.py:205` - @observe(name="intents.fire") |

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: IntentFireRequest/Response | [x] | ✅ | `schemas.py:353-380` - models exist with was_disabled_reason |
| Task 2: fire_intent() method | [x] | ✅ | `intent_service.py:478-644` - 160 lines |
| Task 3: _calculate_next_check_after_fire() | [x] | ✅ | `intent_service.py:646-695` - 50 lines |
| Task 4: Fire endpoint in router | [x] | ✅ | `intents.py:200-251` - POST /{id}/fire |
| Task 5: Integration tests | [x] | ✅ | `test_intents_api.py:579-886` - 12 tests in TestFireIntent |

**Summary:** 5/5 tasks verified complete, 0 questionable, 0 false completions

### Test Coverage

- 12 new tests in TestFireIntent class covering all 8 ACs
- All 38 integration tests pass
- All 43 validation tests pass (no regression)

### Architectural Alignment

- Follows IntentServiceResult pattern established in Story 5.4
- Uses IntentFireResult dataclass for fire operation results
- Route placement follows convention (before /{intent_id})
- Connection management with try/finally pattern

### DoD Checklist

- [x] All acceptance criteria implemented with evidence
- [x] All tasks verified complete
- [x] Integration tests passing
- [x] No regression in existing tests
- [x] Code follows project patterns
- [x] Langfuse tracing enabled
