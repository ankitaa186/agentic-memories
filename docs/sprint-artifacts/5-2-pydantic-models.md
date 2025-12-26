# Story 5.2: Pydantic Models

Status: done

## Story

As a **developer**,
I want **Pydantic request and response models for the Scheduled Intents API**,
so that **API inputs are validated consistently and responses are properly serialized**.

## Acceptance Criteria

1. **AC1:** `TriggerSchedule` model validates schedule configuration:
   - `cron`: Optional[str] - cron expression
   - `interval_minutes`: Optional[int] - repeat interval
   - `datetime`: Optional[datetime] - one-time trigger time
   - `check_interval_minutes`: Optional[int] = Field(default=5, ge=5) - for condition checks

2. **AC2:** `TriggerCondition` model validates condition configuration:
   - `ticker`: Optional[str] - stock ticker for price triggers
   - `operator`: Optional[str] - comparison operator ('<', '>', '<=', '>=', '==')
   - `value`: Optional[float] - threshold value
   - `keywords`: Optional[List[str]] - for news/event triggers
   - `threshold_hours`: Optional[int] - for silence detection

3. **AC3:** `ScheduledIntentCreate` model enforces required fields and valid enums:
   - `user_id`: str (required)
   - `intent_name`: str (required)
   - `description`: Optional[str]
   - `trigger_type`: Literal['cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news']
   - `trigger_schedule`: Optional[TriggerSchedule]
   - `trigger_condition`: Optional[TriggerCondition]
   - `action_type`: Literal['notify', 'check_in', 'briefing', 'analysis', 'reminder'] = 'notify'
   - `action_context`: str (required)
   - `action_priority`: Literal['low', 'normal', 'high', 'critical'] = 'normal'
   - `expires_at`: Optional[datetime]
   - `max_executions`: Optional[int]
   - `metadata`: Optional[Dict[str, Any]]

4. **AC4:** `IntentFireRequest` model validates execution reporting:
   - `status`: Literal['success', 'failed', 'gate_blocked', 'condition_not_met']
   - `trigger_data`: Optional[Dict[str, Any]]
   - `gate_result`: Optional[Dict[str, Any]]
   - `message_id`: Optional[str]
   - `message_preview`: Optional[str]
   - `evaluation_ms`, `generation_ms`, `delivery_ms`: Optional[int]
   - `error_message`: Optional[str]

5. **AC5:** Response models serialize all database fields correctly:
   - `ScheduledIntentResponse`: All 24 columns from scheduled_intents table
   - `IntentFireResponse`: intent_id, status, next_check, enabled, execution_count
   - `IntentExecutionResponse`: All 14 columns from intent_executions table
   - `ScheduledIntentUpdate`: Partial model for PATCH/PUT operations

## Tasks / Subtasks

- [x] **Task 1: Create TriggerSchedule and TriggerCondition models** (AC: 1, 2)
  - [x] 1.1 Create `src/schemas/intents.py` file following existing patterns
  - [x] 1.2 Implement `TriggerSchedule` with all fields and Field constraints
  - [x] 1.3 Implement `TriggerCondition` with all fields
  - [x] 1.4 Add docstrings explaining each model's purpose

- [x] **Task 2: Create ScheduledIntentCreate model** (AC: 3)
  - [x] 2.1 Define all required and optional fields
  - [x] 2.2 Use Literal types for enum fields matching DB CHECK constraints
  - [x] 2.3 Set appropriate defaults (action_type='notify', action_priority='normal')
  - [x] 2.4 Add Field validators if needed

- [x] **Task 3: Create IntentFireRequest model** (AC: 4)
  - [x] 3.1 Define status as Literal with valid execution statuses
  - [x] 3.2 Define optional fields for execution details
  - [x] 3.3 Add timing fields (evaluation_ms, generation_ms, delivery_ms)

- [x] **Task 4: Create Response models** (AC: 5)
  - [x] 4.1 Implement `ScheduledIntentResponse` with all DB columns
  - [x] 4.2 Implement `IntentFireResponse` for fire endpoint
  - [x] 4.3 Implement `IntentExecutionResponse` for history endpoint
  - [x] 4.4 Implement `ScheduledIntentUpdate` for partial updates
  - [x] 4.5 Add `model_config` with `from_attributes=True` for ORM mapping

- [x] **Task 5: Add model exports and tests** (AC: 1-5)
  - [x] 5.1 Export all models from schemas module
  - [x] 5.2 Write unit tests for validation rules
  - [x] 5.3 Test serialization/deserialization of sample data

## Dev Notes

### Architecture Patterns

- Follow existing `src/schemas.py` patterns for model structure
- Use Pydantic v2 style with `model_config` instead of `Config` class
- Literal types must match CHECK constraints from Story 5.1:
  - `trigger_type`: 'cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news'
  - `action_type`: 'notify', 'check_in', 'briefing', 'analysis', 'reminder'
  - `action_priority`: 'low', 'normal', 'high', 'critical'
  - `status`: 'success', 'failed', 'gate_blocked', 'condition_not_met'

### Project Structure Notes

- New file: `src/schemas/intents.py` (or add to existing `src/schemas.py`)
- Existing schemas in `src/schemas.py` use `Literal`, `Optional`, `Field`, `List`, `Dict`
- Import pattern: `from pydantic import BaseModel, Field`
- Use `datetime` from Python stdlib, not pydantic's

### Testing Considerations

- Test that invalid enum values are rejected
- Test that required fields raise ValidationError when missing
- Test that Optional fields accept None
- Test datetime serialization/deserialization
- Test Field constraints (ge=5 on check_interval_minutes)

### Learnings from Previous Story

**From Story 5-1-database-schema-migration (Status: done)**

- **Database Schema Available**: `scheduled_intents` (24 columns) and `intent_executions` (14 columns) created
- **CHECK Constraints to Match**: Pydantic Literal types must exactly match DB constraints
- **Extra Constraints Added**: DB has `execution_count >= 0`, `timing columns >= 0` - consider matching in Pydantic
- **JSONB Fields**: `trigger_schedule`, `trigger_condition`, `trigger_data`, `gate_result`, `metadata` stored as JSONB

[Source: docs/sprint-artifacts/5-1-database-schema-migration.md#Dev-Agent-Record]

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-5.md#Pydantic-Models]
- [Source: docs/epic-5-scheduled-intents.md#Story-5.2]
- [Source: src/schemas.py] - Existing Pydantic patterns

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/5-2-pydantic-models.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Added models to existing src/schemas.py following established patterns
- Renamed `datetime` field to `trigger_at` to avoid Python naming conflict
- Added UUID and ConfigDict imports for response models
- All Literal types match DB CHECK constraints exactly

### Completion Notes List

- Created 8 Pydantic models for Scheduled Intents API in src/schemas.py
- TriggerSchedule: cron, interval_minutes, trigger_at, check_interval_minutes (ge=5)
- TriggerCondition: ticker, operator, value, keywords, threshold_hours
- ScheduledIntentCreate: Required fields validated, Literal enums match DB constraints
- ScheduledIntentUpdate: All optional fields for partial PATCH/PUT
- ScheduledIntentResponse: All 24 DB columns with from_attributes=True
- IntentFireRequest: status Literal with timing fields
- IntentFireResponse: Fire result with next_check
- IntentExecutionResponse: All 14 execution columns with from_attributes=True
- 37 unit tests covering all ACs: validation, required fields, enums, serialization

### File List

- MODIFIED: src/schemas.py (added 8 new models, lines 235-403)
- NEW: tests/unit/test_intents_schemas.py (37 test cases)

## Change Log

| Date | Change |
|------|--------|
| 2025-12-22 | Story drafted from Epic 5 tech spec |
| 2025-12-22 | Context file generated, status: ready-for-dev |
| 2025-12-22 | Implementation complete: 8 models, 37 tests, all ACs verified, status: review |
| 2025-12-22 | Senior Developer Review: APPROVED, status: done |

## Senior Developer Review (AI)

**Reviewer:** Ankit (via Claude Opus 4.5)
**Date:** 2025-12-22
**Outcome:** APPROVE ✅

### Summary

All 5 acceptance criteria fully implemented with comprehensive test coverage. All 19 tasks/subtasks verified complete with file:line evidence. 8 Pydantic models created following project patterns. 37 unit tests passing. No issues found.

### Key Findings

No issues found. Implementation exceeds expectations with:
- Comprehensive docstrings on all models
- All Literal types match DB CHECK constraints exactly
- from_attributes=True for ORM mapping
- Field constraints (ge=5) for business rules

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | TriggerSchedule model | ✅ IMPLEMENTED | `src/schemas.py:239-248` |
| AC2 | TriggerCondition model | ✅ IMPLEMENTED | `src/schemas.py:251-264` |
| AC3 | ScheduledIntentCreate model | ✅ IMPLEMENTED | `src/schemas.py:267-284` |
| AC4 | IntentFireRequest model | ✅ IMPLEMENTED | `src/schemas.py:353-367` |
| AC5 | Response models (4 models) | ✅ IMPLEMENTED | `src/schemas.py:306-402` |

**Summary:** 5 of 5 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| 1.1 Create file | [x] | ✅ | Added to src/schemas.py:235-403 |
| 1.2 TriggerSchedule | [x] | ✅ | src/schemas.py:239-248 |
| 1.3 TriggerCondition | [x] | ✅ | src/schemas.py:251-264 |
| 1.4 Docstrings | [x] | ✅ | All models documented |
| 2.1-2.4 ScheduledIntentCreate | [x] | ✅ | src/schemas.py:267-284 |
| 3.1-3.3 IntentFireRequest | [x] | ✅ | src/schemas.py:353-367 |
| 4.1-4.5 Response models | [x] | ✅ | src/schemas.py:306-402 |
| 5.1-5.3 Exports and tests | [x] | ✅ | tests/unit/test_intents_schemas.py |

**Summary:** 19 of 19 completed tasks verified, 0 false completions

### Test Coverage and Gaps

- **37 unit tests** covering all acceptance criteria
- Tests for: validation rules, required fields, Literal constraints, Field constraints (ge=5), serialization/deserialization
- All tests passing

### Architectural Alignment

- Follows existing `src/schemas.py` patterns
- Uses Pydantic v2 style with `model_config = ConfigDict()`
- Literal types match DB CHECK constraints from Story 5.1
- from_attributes=True for ORM mapping

### Security Notes

No security concerns. Pydantic validation provides protection against invalid inputs.

### Best-Practices and References

- Pydantic 2.8.2 documentation patterns followed
- ConfigDict(from_attributes=True) for ORM compatibility
- Field(ge=5) for constraint enforcement

### Action Items

**Code Changes Required:**
(none)

**Advisory Notes:**
- Note: `datetime` field renamed to `trigger_at` to avoid Python naming conflict (documented in debug log)
