# Story 5.3: Input Validation

Status: done

## Story

As a **developer**,
I want **robust input validation for the Scheduled Intents API**,
so that **bad triggers are rejected at creation time with clear error messages**.

## Acceptance Criteria

1. **AC1:** Rejects creation if user has 25+ active triggers (HTTP 400)
   - Count existing enabled triggers for user_id
   - Return error: "Limit reached: 25 active triggers max"

2. **AC2:** Rejects cron expressions firing more frequently than every 60 seconds
   - Parse cron with croniter to calculate next 2 occurrences
   - If delta < 60 seconds, return error: "Cron too frequent: every Xs. Minimum: 60s"

3. **AC3:** Rejects cron expressions that would fire more than 96 times per day
   - Calculate occurrences over 24h window using croniter
   - If count > 96, return error: "Cron would fire Xx/day. Max: 96"

4. **AC4:** Rejects interval less than 5 minutes
   - Check trigger_schedule.interval_minutes >= 5
   - Return error: "Interval too short: Xm. Minimum: 5m"

5. **AC5:** Rejects one-time triggers with trigger_at in the past
   - Check trigger_schedule.trigger_at > datetime.now(UTC)
   - Return error: "One-time trigger must be in the future"

6. **AC6:** Validates required fields by trigger type
   - `cron`: requires trigger_schedule.cron
   - `interval`: requires trigger_schedule.interval_minutes
   - `once`: requires trigger_schedule.trigger_at
   - `price`: requires trigger_condition.ticker, operator, value
   - `silence`: requires trigger_condition.threshold_hours
   - `event/news`: requires trigger_condition.keywords
   - Return error: "trigger_schedule.cron required for type 'cron'"

7. **AC7:** Returns all validation errors in single response
   - Collect all validation failures before returning
   - Return HTTP 400 with `{"errors": ["error1", "error2", ...]}`
   - Do not short-circuit on first error

## Tasks / Subtasks

- [x] **Task 1: Create IntentValidationService** (AC: 1-7)
  - [x] 1.1 Create `src/services/intent_validation.py` file
  - [x] 1.2 Implement `IntentValidationService` class with dependency injection for DB
  - [x] 1.3 Define `ValidationResult` dataclass with `is_valid: bool` and `errors: List[str]`
  - [x] 1.4 Add docstrings explaining service purpose

- [x] **Task 2: Implement trigger count validation** (AC: 1)
  - [x] 2.1 Add `_validate_trigger_count()` method
  - [x] 2.2 Query: `SELECT COUNT(*) FROM scheduled_intents WHERE user_id = $1 AND enabled = true`
  - [x] 2.3 Return error if count >= 25

- [x] **Task 3: Implement cron validation** (AC: 2, 3)
  - [x] 3.1 Add croniter to requirements.txt if not present
  - [x] 3.2 Add `_validate_cron_frequency()` method
  - [x] 3.3 Parse cron expression with croniter, catch invalid syntax
  - [x] 3.4 Calculate delta between first 2 occurrences for 60s check
  - [x] 3.5 Calculate occurrences over 24h for 96/day check

- [x] **Task 4: Implement interval validation** (AC: 4)
  - [x] 4.1 Add `_validate_interval()` method
  - [x] 4.2 Check interval_minutes >= 5 (Note: Pydantic already has ge=5 on check_interval_minutes, but interval_minutes needs explicit check)

- [x] **Task 5: Implement one-time validation** (AC: 5)
  - [x] 5.1 Add `_validate_once_trigger()` method
  - [x] 5.2 Check trigger_at > datetime.now(timezone.utc)
  - [x] 5.3 Handle timezone-aware comparison correctly

- [x] **Task 6: Implement required fields validation** (AC: 6)
  - [x] 6.1 Add `_validate_required_fields()` method
  - [x] 6.2 Map trigger_type to required field paths
  - [x] 6.3 Check each required field is present and not None
  - [x] 6.4 Generate clear error messages for each missing field

- [x] **Task 7: Implement validate() orchestrator** (AC: 7)
  - [x] 7.1 Add public `validate(intent: ScheduledIntentCreate) -> ValidationResult` method
  - [x] 7.2 Call all private validation methods
  - [x] 7.3 Collect all errors without short-circuiting
  - [x] 7.4 Return ValidationResult with all accumulated errors

- [x] **Task 8: Write unit tests** (AC: 1-7)
  - [x] 8.1 Create `tests/unit/test_intent_validation.py`
  - [x] 8.2 Test trigger count limit (24 ok, 25 fails)
  - [x] 8.3 Test cron frequency (every minute fails, every 2 minutes ok)
  - [x] 8.4 Test cron daily count (every minute = 1440/day fails, every 15 min = 96/day ok)
  - [x] 8.5 Test interval minimum (4 min fails, 5 min ok)
  - [x] 8.6 Test one-time in past vs future
  - [x] 8.7 Test required fields for each trigger type
  - [x] 8.8 Test multiple errors returned together

## Dev Notes

### Architecture Patterns

- Follow existing service patterns from `src/services/memory_services.py`
- Use dependency injection for database connection (pass `conn` or use existing pool)
- Return structured `ValidationResult` rather than raising exceptions immediately
- All validation runs before any database mutations

### Project Structure Notes

- New file: `src/services/intent_validation.py`
- Import existing models from `src/schemas.py` (ScheduledIntentCreate, TriggerSchedule, TriggerCondition)
- Uses `croniter` library for cron parsing (add to requirements.txt if needed)
- Database queries use existing `get_timescale_conn()` pattern

### Testing Considerations

- Mock database for trigger count tests
- Test cron edge cases: `* * * * *` (every minute), `*/2 * * * *` (every 2 min)
- Test timezone handling for one-time triggers
- Test that all 8 trigger types have their required fields validated
- Test error accumulation (multiple invalid fields return multiple errors)

### Learnings from Previous Stories

**From Story 5-2-pydantic-models (Status: done)**

- **Pydantic Models Available**: `ScheduledIntentCreate`, `TriggerSchedule`, `TriggerCondition` in `src/schemas.py`
- **Field Naming**: `trigger_at` used instead of `datetime` to avoid Python naming conflict
- **Literal Types**: Match DB CHECK constraints exactly - use for error messages
- **Field Constraints**: `check_interval_minutes` already has `ge=5` in Pydantic, but `interval_minutes` does not
- **Import Pattern**: `from src.schemas import ScheduledIntentCreate, TriggerSchedule, TriggerCondition`

[Source: docs/sprint-artifacts/5-2-pydantic-models.md#Dev-Agent-Record]

**From Story 5-1-database-schema-migration (Status: done)**

- **Trigger Types**: 'cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news'
- **Existing Index**: `idx_intents_user_enabled` for efficient user trigger count query

[Source: docs/sprint-artifacts/5-1-database-schema-migration.md#Dev-Agent-Record]

### Validation Rules Reference

| Trigger Type | Required Schedule Fields | Required Condition Fields |
|--------------|-------------------------|---------------------------|
| cron | cron | - |
| interval | interval_minutes | - |
| once | trigger_at | - |
| price | - | ticker, operator, value |
| silence | - | threshold_hours |
| event | - | keywords |
| calendar | - | (TBD - may need date field) |
| news | - | keywords |

### Error Response Format

```json
{
  "errors": [
    "Limit reached: 25 active triggers max",
    "Cron too frequent: every 30s. Minimum: 60s",
    "trigger_condition.ticker required for type 'price'"
  ]
}
```

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-5.md#Story-5.3]
- [Source: docs/epic-5-scheduled-intents.md#Story-5.3]
- [Source: src/schemas.py] - Pydantic models for ScheduledIntentCreate

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/5-3-input-validation.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first implementation run (after test expectation fixes)

### Completion Notes List

1. Created `IntentValidationService` class with dependency injection pattern
2. Implemented `ValidationResult` dataclass for structured return values
3. All validation methods follow non-short-circuit pattern (AC7)
4. Cron validation uses croniter library for accurate interval/daily count calculation
5. Test expectations were corrected for cron edge cases:
   - `* * * * *` fires every 60s (at limit, not below) so only fails daily count
   - `*/2 * * * *` fires 720x/day, exceeds 96 limit
6. All 8 trigger types have required field validation
7. Timezone-naive datetime handling implemented for one-time triggers
8. 43 unit tests covering all ACs with 100% pass rate

### File List

| File | Action |
|------|--------|
| `src/services/intent_validation.py` | Created (333 lines) |
| `tests/unit/test_intent_validation.py` | Created (683 lines, 43 tests) |
| `requirements.txt` | Modified (added croniter==2.0.1) |

## Change Log

| Date | Change |
|------|--------|
| 2025-12-22 | Story drafted from Epic 5 tech spec |
| 2025-12-22 | Context file generated, status: ready-for-dev |
| 2025-12-22 | Implementation complete, 43/43 tests passing, status: review |
| 2025-12-22 | Senior Developer Review notes appended, status: done |

---

## Senior Developer Review (AI)

### Reviewer
Ankit

### Date
2025-12-22

### Outcome: **APPROVE** ✅

All acceptance criteria implemented with evidence. All 24 subtasks verified complete. No falsely marked complete tasks found. Code quality is excellent with comprehensive test coverage.

### Summary

Story 5.3 (Input Validation) implements a robust validation service for the Scheduled Intents API. The implementation is complete, well-tested, and follows established patterns. All 7 acceptance criteria are fully implemented with comprehensive test coverage (43 tests, 100% pass rate).

### Key Findings

**No High/Medium severity issues found.**

**Low severity (informational):**
- Story context interface suggested `validate(intent, user_id)` but implementation correctly extracts `user_id` from `intent.user_id` - this is cleaner design

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Rejects creation if user has 25+ active triggers | IMPLEMENTED | `intent_validation.py:142-179` |
| AC2 | Rejects cron expressions firing < 60 seconds | IMPLEMENTED | `intent_validation.py:199-207` |
| AC3 | Rejects cron expressions > 96 fires/day | IMPLEMENTED | `intent_validation.py:209-227` |
| AC4 | Rejects interval < 5 minutes | IMPLEMENTED | `intent_validation.py:253-257` |
| AC5 | Rejects one-time triggers in past | IMPLEMENTED | `intent_validation.py:278-286` |
| AC6 | Validates required fields by trigger type | IMPLEMENTED | `intent_validation.py:37-46,290-332` |
| AC7 | Returns all errors in single response | IMPLEMENTED | `intent_validation.py:101-127` |

**Summary: 7 of 7 acceptance criteria fully implemented**

### Task Completion Validation

| Task | Subtasks | Verified |
|------|----------|----------|
| Task 1: Create IntentValidationService | 4/4 | ✓ All verified |
| Task 2: Trigger count validation | 3/3 | ✓ All verified |
| Task 3: Cron validation | 5/5 | ✓ All verified |
| Task 4: Interval validation | 2/2 | ✓ All verified |
| Task 5: One-time validation | 3/3 | ✓ All verified |
| Task 6: Required fields validation | 4/4 | ✓ All verified |
| Task 7: validate() orchestrator | 4/4 | ✓ All verified |
| Task 8: Unit tests | 8/8 | ✓ All verified |

**Summary: 24 of 24 completed tasks verified, 0 questionable, 0 falsely marked complete**

### Test Coverage and Gaps

- 43 unit tests covering all 7 ACs
- Test classes organized by validation type
- Edge cases covered: invalid cron, timezone handling, DB errors
- **All tests passing**

### Architectural Alignment

- ✅ Follows existing service pattern (ProfileStorageService)
- ✅ Uses dependency injection for DB connection
- ✅ Returns structured ValidationResult (AD-014 compliant)
- ✅ Graceful degradation on DB errors
- ✅ All 8 trigger types from Story 5-1 covered

### Security Notes

- ✅ Parameterized SQL queries (no injection risk)
- ✅ No sensitive data logged
- ✅ Proper type validation via Pydantic

### Best-Practices and References

- [croniter 2.0.1](https://pypi.org/project/croniter/) - Python cron parser
- AD-014: Graceful degradation error handling pattern

### Action Items

**Code Changes Required:**
(None - all criteria met)

**Advisory Notes:**
- Note: Consider adding integration test with actual DB in future stories (not required for this story)
