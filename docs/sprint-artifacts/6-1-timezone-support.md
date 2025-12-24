# Story 6.1: Timezone Support

Status: ready-for-dev

## Story

As an **Annie Proactive Worker**,
I want **scheduled triggers to support IANA timezone configuration**,
so that **users receive proactive messages at appropriate local times regardless of their geographic location**.

## Acceptance Criteria

1. **AC1.1:** `trigger_timezone` column added to `scheduled_intents` table with default 'UTC'
   - Migration 019 adds VARCHAR(64) column
   - Default value is 'UTC' for backward compatibility
   - Existing triggers remain unaffected

2. **AC1.2:** TriggerSchedule model accepts `timezone` field
   - New field: `timezone: str = Field(default="UTC", description="IANA timezone")`
   - Field serialized to/from `trigger_schedule` JSONB column
   - Backward compatible with existing triggers (missing field = 'UTC')

3. **AC1.3:** Invalid timezones return validation error with IANA format example
   - Uses Python `zoneinfo.ZoneInfo` for validation
   - Error message: "Invalid timezone: {tz}. Use IANA format (e.g., 'America/Los_Angeles')"
   - Validation occurs in `IntentValidationService`

4. **AC1.4:** Cron next_check calculated using user timezone, stored as UTC
   - croniter receives timezone parameter
   - Next occurrence computed in user's local time
   - Result converted to UTC before storage
   - Handles DST transitions correctly

5. **AC1.5:** API response includes timezone in trigger_schedule
   - `ScheduledIntentResponse.trigger_schedule` includes timezone field
   - GET endpoints return timezone for all triggers
   - Default 'UTC' shown if not explicitly set

## Tasks / Subtasks

- [ ] **Task 1: Database Migration** (AC: 1.1)
  - [ ] 1.1 Create `migrations/postgres/019_intents_alignment.up.sql`
  - [ ] 1.2 Add `trigger_timezone VARCHAR(64) DEFAULT 'UTC'` column
  - [ ] 1.3 Create `migrations/postgres/019_intents_alignment.down.sql`
  - [ ] 1.4 Run migration and verify column exists

- [ ] **Task 2: Extend TriggerSchedule Pydantic Model** (AC: 1.2)
  - [ ] 2.1 Add `timezone: str = Field(default="UTC")` to TriggerSchedule in `src/schemas.py`
  - [ ] 2.2 Add field description for OpenAPI documentation
  - [ ] 2.3 Verify serialization to/from JSONB works correctly

- [ ] **Task 3: Implement Timezone Validation** (AC: 1.3)
  - [ ] 3.1 Add `validate_timezone()` method to `IntentValidationService`
  - [ ] 3.2 Use `zoneinfo.ZoneInfo` for validation
  - [ ] 3.3 Return descriptive error with IANA format example
  - [ ] 3.4 Call validation from `validate()` when trigger_schedule.timezone is present

- [ ] **Task 4: Update Next Check Calculation for Timezone** (AC: 1.4)
  - [ ] 4.1 Modify `_calculate_initial_next_check()` to accept timezone parameter
  - [ ] 4.2 Pass timezone to croniter for cron triggers
  - [ ] 4.3 Convert result to UTC before returning
  - [ ] 4.4 Handle 'once' trigger_at interpretation in user timezone
  - [ ] 4.5 Update `_calculate_next_check_after_fire()` similarly

- [ ] **Task 5: Update IntentService for Timezone Handling** (AC: 1.2, 1.5)
  - [ ] 5.1 Extract timezone from trigger_schedule JSONB in `_row_to_response()`
  - [ ] 5.2 Include timezone when building trigger_schedule for storage
  - [ ] 5.3 Pass timezone to next_check calculation methods

- [ ] **Task 6: Unit Tests for Timezone** (AC: 1.1-1.5)
  - [ ] 6.1 Test valid IANA timezone validation (America/Los_Angeles, Europe/London, Asia/Tokyo)
  - [ ] 6.2 Test invalid timezone rejection (Invalid/Zone, empty string, numeric)
  - [ ] 6.3 Test cron next_check with non-UTC timezone
  - [ ] 6.4 Test timezone included in API response
  - [ ] 6.5 Test backward compatibility (missing timezone defaults to UTC)

- [ ] **Task 7: Integration Tests** (AC: 1.4, 1.5)
  - [ ] 7.1 Create intent with America/Los_Angeles timezone, verify next_check is UTC
  - [ ] 7.2 Get intent, verify timezone in response
  - [ ] 7.3 Fire intent, verify next_check recalculated with timezone
  - [ ] 7.4 Test DST transition scenario (optional but recommended)

## Dev Notes

### Architecture Patterns

- **Database Column:** Add to existing `scheduled_intents` table as new column (not in JSONB)
- **Pydantic Model:** Extend existing `TriggerSchedule` model in `src/schemas.py`
- **Validation:** Add to `IntentValidationService.validate()` in `src/services/intent_validation.py`
- **Next Check:** Modify methods in `src/services/intent_service.py:723-809`

### Project Structure Notes

- Migration file: `migrations/postgres/019_intents_alignment.up.sql`
- Schema changes: `src/schemas.py::TriggerSchedule`
- Validation changes: `src/services/intent_validation.py::IntentValidationService`
- Service changes: `src/services/intent_service.py::IntentService`
- Unit tests: `tests/unit/test_timezone_validation.py` (new)
- Integration tests: `tests/integration/test_intents_api.py` (extend existing)

### Timezone Handling Best Practices

```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def validate_timezone(tz: str) -> bool:
    """Validate IANA timezone string."""
    try:
        ZoneInfo(tz)
        return True
    except ZoneInfoNotFoundError:
        return False
```

### Croniter with Timezone

```python
from croniter import croniter
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

def calculate_cron_next(cron_expr: str, tz_str: str = "UTC") -> datetime:
    """Calculate next cron occurrence in user timezone, return as UTC."""
    tz = ZoneInfo(tz_str)
    now_local = datetime.now(tz)
    cron = croniter(cron_expr, now_local)
    next_local = cron.get_next(datetime)
    return next_local.astimezone(timezone.utc)
```

### Learnings from Previous Story

**From Story 5-8-next-check-calculation-logic (Status: done)**

- **Next Check Methods Location**: `_calculate_initial_next_check()` at `intent_service.py:774-809`, `_calculate_next_check_after_fire()` at `intent_service.py:723-772`
- **Croniter Usage**: Already imported and used for cron triggers
- **Test Patterns**: 31 unit tests in `tests/unit/test_next_check_calculation.py` - follow same patterns
- **Mock Time**: Use `fixed_now` fixture pattern for deterministic tests
- **Edge Cases**: Croniter has try/except fallback for invalid expressions (lines 751-755, 794-796)

[Source: docs/sprint-artifacts/5-8-next-check-calculation-logic.md#Dev-Agent-Record]

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-6.md#Story-6.1-Timezone-Support]
- [Source: docs/epic-6-intents-api-alignment.md#Story-6.1]
- [Source: src/services/intent_service.py:723-809] - Next check calculation methods
- [Source: src/services/intent_validation.py] - Validation service
- [Source: tests/unit/test_next_check_calculation.py] - Existing test patterns

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/6-1-timezone-support.context.xml`

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|------|--------|
| 2025-12-24 | Story drafted from Epic 6 tech spec with learnings from Story 5.8 |
