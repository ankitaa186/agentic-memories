# Story 5.8: Next Check Calculation Logic

Status: done

## Story

As an **Agentic Memories API**,
I want **accurate and well-tested `next_check` calculation logic for all trigger types**,
so that **scheduled intents fire at the correct times and Annie's proactive worker can reliably poll pending triggers**.

## Acceptance Criteria

1. **AC1:** `_calculate_initial_next_check()` works for all trigger types
   - `cron`: Uses croniter to get next occurrence
   - `interval`: NOW() + interval_minutes
   - `once`: Returns trigger_at datetime
   - `price/silence/event/calendar/news`: Returns NOW() (immediate check)
   - Invalid/missing schedule: Returns None or sensible default

2. **AC2:** `_calculate_next_check_after_fire()` handles all status outcomes
   - `success (cron)`: croniter.get_next()
   - `success (interval)`: NOW() + interval_minutes
   - `success (once)`: Returns None (trigger disabled)
   - `success (price/silence)`: NOW() + check_interval_minutes
   - `condition_not_met`: NOW() + 5 minutes
   - `gate_blocked`: NOW() + 5 minutes
   - `failed`: NOW() + 15 minutes

3. **AC3:** Unit tests cover all trigger types and status combinations
   - Minimum 15 test cases covering all scenarios
   - Tests for edge cases (invalid cron, missing schedule, etc.)
   - Tests use mocked time for deterministic results

4. **AC4:** Croniter edge cases handled gracefully
   - Invalid cron expression returns sensible default
   - End-of-month handling correct
   - Timezone consistency (UTC)

5. **AC5:** Methods are exposed for testing
   - Can be tested in isolation without database
   - Clear input/output contracts

## Tasks / Subtasks

- [x] **Task 1: Create unit test file for next_check calculations** (AC: 3, 5)
  - [x] 1.1 Create `tests/unit/test_next_check_calculation.py`
  - [x] 1.2 Set up pytest fixtures with mock datetime
  - [x] 1.3 Import IntentService for isolated testing

- [x] **Task 2: Test `_calculate_initial_next_check()` for each trigger type** (AC: 1, 3)
  - [x] 2.1 Test cron type with valid expression
  - [x] 2.2 Test cron type with invalid expression
  - [x] 2.3 Test interval type with various intervals
  - [x] 2.4 Test once type with future datetime
  - [x] 2.5 Test once type with past datetime (edge case)
  - [x] 2.6 Test price type returns immediate check
  - [x] 2.7 Test silence type returns immediate check
  - [x] 2.8 Test missing schedule returns None

- [x] **Task 3: Test `_calculate_next_check_after_fire()` for each status** (AC: 2, 3)
  - [x] 3.1 Test success + cron → croniter.get_next()
  - [x] 3.2 Test success + interval → NOW + interval_minutes
  - [x] 3.3 Test success + once → None
  - [x] 3.4 Test success + price → NOW + check_interval_minutes
  - [x] 3.5 Test condition_not_met → NOW + 5 minutes
  - [x] 3.6 Test gate_blocked → NOW + 5 minutes
  - [x] 3.7 Test failed → NOW + 15 minutes

- [x] **Task 4: Test croniter edge cases** (AC: 4)
  - [x] 4.1 Test end-of-month cron expressions
  - [x] 4.2 Test leap year handling
  - [x] 4.3 Test timezone edge cases
  - [x] 4.4 Verify UTC consistency

- [x] **Task 5: Verify existing integration tests cover calculations** (AC: 1, 2)
  - [x] 5.1 Review test_intents_api.py for calculation coverage
  - [x] 5.2 Add any missing integration test cases
  - [x] 5.3 Document test coverage summary

## Dev Notes

### Architecture Patterns

- Methods already implemented in Story 5.4 and 5.6
- `_calculate_initial_next_check()`: `intent_service.py:774-809`
- `_calculate_next_check_after_fire()`: `intent_service.py:723-772`
- Focus is on comprehensive unit testing and validation

### Project Structure Notes

- New file: `tests/unit/test_next_check_calculation.py`
- May need to refactor methods to be more testable if tightly coupled
- Consider extracting to separate module if complex

### Existing Implementation

**_calculate_initial_next_check()** (intent_service.py:774-809):
```python
# Handles: cron, interval, once, price/silence/event/calendar/news
# Returns: datetime or None
```

**_calculate_next_check_after_fire()** (intent_service.py:723-772):
```python
# Handles: success/failed/gate_blocked/condition_not_met
# Combines trigger_type with status for calculation
```

### Testing Considerations

- Use `freezegun` or `unittest.mock.patch` for deterministic time
- Test with TriggerSchedule Pydantic models
- Verify edge cases don't cause exceptions
- Check croniter is properly installed and imported

### Learnings from Previous Story

**From Story 5-7-execution-history-endpoint (Status: done)**

- **IntentHistoryResult Pattern**: Dataclass pattern for structured results
- **_execution_row_to_response()**: Row mapping helper at `intent_service.py:883-931`
- **Test Patterns**: Use mock_db_connection fixture, patch get_timescale_conn
- **File Structure**: Tests in `tests/integration/test_intents_api.py`

[Source: docs/sprint-artifacts/5-7-execution-history-endpoint.md#Dev-Agent-Record]

### References

- [Source: docs/epic-5-scheduled-intents.md#Story-5.8]
- [Source: src/services/intent_service.py:723-809] - Existing calculation methods
- [Source: tests/integration/test_intents_api.py] - Integration test patterns

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/5-8-next-check-calculation-logic.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed datetime mocking issue with croniter (croniter uses internal type checking that conflicts with mock)

### Completion Notes List

1. **Unit Test File Created** (Task 1)
   - Created `tests/unit/test_next_check_calculation.py` with 31 test cases
   - Fixtures: mock_conn, intent_service, fixed_now for isolated testing

2. **Initial Calculation Tests** (Task 2) - 12 tests
   - TestCalculateInitialNextCheck class covers all trigger types
   - Cron valid/invalid, interval, once (future/past), price, silence, event, missing schedule

3. **After-Fire Calculation Tests** (Task 3) - 11 tests
   - TestCalculateNextCheckAfterFire class covers all status outcomes
   - Success variants by trigger type, condition_not_met (+5min), gate_blocked (+5min), failed (+15min)

4. **Croniter Edge Case Tests** (Task 4) - 6 tests
   - TestCroniterEdgeCases class covers end-of-month, leap year, UTC consistency
   - Invalid expression fallback verified

5. **Integration Test Review** (Task 5)
   - Existing coverage in test_intents_api.py:
     - test_create_interval_intent_with_next_check (creation)
     - test_update_schedule_recalculates_next_check (update)
     - test_fire_calculates_next_check_for_interval (interval fire)
     - test_fire_backoff_on_failure (15-min backoff)
     - test_fire_disables_one_time_trigger (once → None)
   - No additional integration tests needed - unit tests provide comprehensive isolated coverage

### File List

| File | Action | Lines Changed |
|------|--------|---------------|
| `tests/unit/test_next_check_calculation.py` | Created | +425 (31 test cases in 4 test classes) |

### Test Coverage Summary

| Test Category | Test Count | Coverage |
|---------------|------------|----------|
| Initial calculation (AC1) | 12 | All trigger types |
| After-fire calculation (AC2) | 11 | All status outcomes |
| Croniter edge cases (AC4) | 6 | End-of-month, leap year, UTC |
| Additional edge cases | 2 | None schedule handling |
| **Total Unit Tests** | **31** | **Exceeds AC3 minimum of 15** |

## Change Log

| Date | Change |
|------|--------|
| 2025-12-23 | Story drafted from Epic 5 with learnings from Story 5.7 |
| 2025-12-23 | Implementation complete - 31 unit tests created and passing |
| 2025-12-23 | SM Review: APPROVED - moved to done |

## SM Review Notes

### Review Date: 2025-12-23

### Reviewer: Claude Opus 4.5 (SM Agent)

### Review Outcome: APPROVED

All acceptance criteria implemented with evidence. All tasks verified complete. 31 unit tests created exceeding the AC3 minimum of 15.

### AC Validation Summary

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC1 | _calculate_initial_next_check() works for all trigger types | ✅ PASS | `intent_service.py:774-809` - handles cron, interval, once, price/silence/event |
| AC2 | _calculate_next_check_after_fire() handles all status outcomes | ✅ PASS | `intent_service.py:723-772` - success variants, condition_not_met (+5), gate_blocked (+5), failed (+15) |
| AC3 | Unit tests cover all trigger types (min 15) | ✅ PASS | `test_next_check_calculation.py` - 31 test cases (exceeds minimum) |
| AC4 | Croniter edge cases handled gracefully | ✅ PASS | `intent_service.py:751-755,794-796` - try/except with fallback |
| AC5 | Methods exposed for testing | ✅ PASS | `test_next_check_calculation.py:32-34` - IntentService tested with mock_conn |

**Summary:** 5 of 5 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: Create unit test file | [x] | ✅ | `tests/unit/test_next_check_calculation.py` - 425 lines |
| 1.1 Create file | [x] | ✅ | File exists at path |
| 1.2 Set up pytest fixtures | [x] | ✅ | Lines 25-40: mock_conn, intent_service, fixed_now |
| 1.3 Import IntentService | [x] | ✅ | Line 18: `from src.services.intent_service import IntentService` |
| Task 2: Test _calculate_initial_next_check() | [x] | ✅ | `TestCalculateInitialNextCheck` class lines 47-177 |
| 2.1 Test cron valid | [x] | ✅ | Lines 50-62: test_cron_valid_expression |
| 2.2 Test cron invalid | [x] | ✅ | Lines 64-77: test_cron_invalid_expression |
| 2.3 Test interval | [x] | ✅ | Lines 79-104: test_interval_30_minutes, test_interval_various_values |
| 2.4 Test once future | [x] | ✅ | Lines 106-113: test_once_future_datetime |
| 2.5 Test once past | [x] | ✅ | Lines 115-124: test_once_past_datetime |
| 2.6 Test price | [x] | ✅ | Lines 126-137: test_price_immediate_check |
| 2.7 Test silence | [x] | ✅ | Lines 139-149: test_silence_immediate_check |
| 2.8 Test missing schedule | [x] | ✅ | Lines 161-165: test_missing_schedule_returns_none |
| Task 3: Test _calculate_next_check_after_fire() | [x] | ✅ | `TestCalculateNextCheckAfterFire` class lines 184-295 |
| 3.1 Test success + cron | [x] | ✅ | Lines 187-197: test_success_cron_next_occurrence |
| 3.2 Test success + interval | [x] | ✅ | Lines 199-208: test_success_interval_now_plus_minutes |
| 3.3 Test success + once | [x] | ✅ | Lines 210-218: test_success_once_returns_none |
| 3.4 Test success + price | [x] | ✅ | Lines 220-229: test_success_price_check_interval |
| 3.5 Test condition_not_met | [x] | ✅ | Lines 253-262: test_condition_not_met_5_minutes |
| 3.6 Test gate_blocked | [x] | ✅ | Lines 264-273: test_gate_blocked_5_minutes |
| 3.7 Test failed | [x] | ✅ | Lines 275-284: test_failed_15_minutes |
| Task 4: Test croniter edge cases | [x] | ✅ | `TestCroniterEdgeCases` class lines 302-386 |
| 4.1 Test end-of-month | [x] | ✅ | Lines 305-317: test_end_of_month_cron |
| 4.2 Test leap year | [x] | ✅ | Lines 331-343: test_leap_year_february_29 |
| 4.3 Test timezone | [x] | ✅ | Lines 345-359: test_timezone_utc_consistency |
| 4.4 Verify UTC | [x] | ✅ | Verified in test_timezone_utc_consistency |
| Task 5: Verify integration tests | [x] | ✅ | Documented in Completion Notes |
| 5.1 Review test_intents_api.py | [x] | ✅ | Completion Notes lists 5 relevant tests |
| 5.2 Add missing tests | [x] | ✅ | No additions needed - unit tests comprehensive |
| 5.3 Document coverage | [x] | ✅ | Test Coverage Summary table in story |

**Summary:** 28 of 28 completed tasks verified, 0 questionable, 0 falsely marked complete

### Test Coverage

- 31 unit tests in 4 test classes (TestCalculateInitialNextCheck, TestCalculateNextCheckAfterFire, TestCroniterEdgeCases, TestEdgeCases)
- All 31 tests pass
- Test count exceeds AC3 minimum of 15 by 16 tests (107% over requirement)
- Tests use mocked time via fixed_now fixture for determinism

### Architectural Alignment

- Methods implemented in Story 5.4/5.6 at correct locations (intent_service.py:723-809)
- Unit tests follow existing patterns in tests/unit/
- Tests use mock_conn to avoid database dependency (AC5)
- croniter edge cases properly handled with try/except fallback

### Security Notes

- No security concerns - this story adds only test files
- No new endpoints or data handling

### DoD Checklist

- [x] All acceptance criteria implemented with evidence
- [x] All tasks verified complete (28/28)
- [x] Unit tests passing (31 tests)
- [x] Test count exceeds minimum requirement
- [x] Code follows project patterns
- [x] Methods testable in isolation (AC5 verified)
