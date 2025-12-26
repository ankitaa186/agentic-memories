# Story 6.6: API Documentation Update

Status: done

## Story

As an **API consumer (Annie integration developer)**,
I want **complete OpenAPI documentation for all Epic 6 fields**,
so that **I can correctly integrate with the extended Scheduled Intents API without needing to read source code**.

## Acceptance Criteria

1. **AC6.1:** All new fields have OpenAPI descriptions
   - `trigger_schedule.timezone` field has description: "IANA timezone for trigger scheduling (e.g., 'America/Los_Angeles')"
   - `trigger_condition.condition_type` field has description
   - `trigger_condition.expression` field has description with examples
   - `trigger_condition.cooldown_hours` field has description with valid range (1-168)
   - `trigger_condition.fire_mode` field has description explaining 'once' vs 'recurring'
   - Response fields (`cooldown_active`, `cooldown_remaining_hours`, `last_condition_fire`, `was_disabled_reason`) have descriptions

2. **AC6.2:** action_context guidance documented
   - Add description to `action_context` field explaining its purpose
   - Document that `action_context` is passed to the LLM when firing the intent
   - Include examples of effective action_context values for different trigger types

3. **AC6.3:** Migration notes for existing triggers
   - Document default values for new fields on existing triggers
   - Explain backward compatibility: existing triggers continue to work unchanged
   - Note that `trigger_timezone` defaults to 'America/Los_Angeles' for existing triggers

## Tasks / Subtasks

- [x] **Task 1: Review Current Field Descriptions** (AC: 6.1)
  - [x] 1.1 Audit `src/schemas.py` for all Epic 6 fields
  - [x] 1.2 List fields missing `description=` parameter in Field()
  - [x] 1.3 List fields with inadequate descriptions

- [x] **Task 2: Add OpenAPI Descriptions to TriggerSchedule** (AC: 6.1)
  - [x] 2.1 Ensure `timezone` field has complete IANA description (already present)
  - [x] 2.2 Added `check_interval_minutes` description with portfolio default mention
  - [x] 2.3 Examples included in descriptions where helpful

- [x] **Task 3: Add OpenAPI Descriptions to TriggerCondition** (AC: 6.1)
  - [x] 3.1 `condition_type` field already has description with valid values
  - [x] 3.2 `expression` field already has description with format examples
  - [x] 3.3 `cooldown_hours` already has description with valid range and default
  - [x] 3.4 `fire_mode` already has description explaining behavior difference

- [x] **Task 4: Add OpenAPI Descriptions to Response Models** (AC: 6.1)
  - [x] 4.1 Added descriptions to all `IntentFireResponse` fields
  - [x] 4.2 Added `was_disabled_reason` description with possible values
  - [x] 4.3 `cooldown_active` and `cooldown_remaining_hours` already have descriptions

- [x] **Task 5: Document action_context Field** (AC: 6.2)
  - [x] 5.1 Added comprehensive description to `action_context` field
  - [x] 5.2 Description includes example for action_context usage
  - [x] 5.3 Documented that action_context is passed to LLM on fire

- [x] **Task 6: Create Migration Notes** (AC: 6.3)
  - [x] 6.1 Documented default values in field descriptions
  - [x] 6.2 Added backward compatibility note to module docstring (Epic 5/6 section)
  - [x] 6.3 CHATBOT_INTEGRATION_GUIDE.md not present - skipped

- [x] **Task 7: Verify OpenAPI Schema Generation** (AC: 6.1, 6.2, 6.3)
  - [x] 7.1 Verified via Python model_json_schema() inspection
  - [x] 7.2 All new fields appear with descriptions
  - [x] 7.3 Field descriptions include format examples
  - [x] 7.4 Enum values documented via Literal types

## Dev Notes

### Architecture Patterns

- **Pydantic Field Descriptions:** Use `Field(description="...")` for OpenAPI generation
- **Docstrings:** Module and class docstrings appear in OpenAPI schema info
- **Examples:** Use `Field(example=...)` for inline examples in Swagger UI
- **Enum Documentation:** Literal types automatically generate enum in OpenAPI

### Fields to Document (from Epic 6)

| Field | Model | Current Description Status |
|-------|-------|---------------------------|
| `timezone` | TriggerSchedule | Needs verification |
| `condition_type` | TriggerCondition | Needs description |
| `expression` | TriggerCondition | Needs examples |
| `cooldown_hours` | TriggerCondition | Has ge/le, needs prose description |
| `fire_mode` | TriggerCondition | Needs behavior description |
| `cooldown_active` | IntentFireResponse | Needs description |
| `cooldown_remaining_hours` | IntentFireResponse | Needs description |
| `last_condition_fire` | IntentFireResponse | Needs description |
| `was_disabled_reason` | IntentFireResponse | Needs possible values |
| `action_context` | ScheduledIntentCreate | Needs comprehensive description |

### Example Descriptions to Add

```python
# TriggerSchedule.timezone
timezone: str = Field(
    default="UTC",
    description="IANA timezone for cron scheduling. Cron expressions are evaluated "
                "in this timezone. Examples: 'America/Los_Angeles', 'Europe/London', 'UTC'. "
                "Default: 'UTC'. For existing triggers, defaults to 'America/Los_Angeles'."
)

# TriggerCondition.expression
expression: Optional[str] = Field(
    default=None,
    description="Human-readable condition expression. Format depends on condition_type: "
                "- price: 'TICKER OP VALUE' (e.g., 'NVDA < 130', 'AAPL >= 200') "
                "- portfolio: 'any_holding_change > 5%', 'total_value >= 100000' "
                "- silence: 'inactive_hours > 48'. "
                "Expression is validated but evaluated by the caller (Annie)."
)

# TriggerCondition.fire_mode
fire_mode: Literal["once", "recurring"] = Field(
    default="recurring",
    description="Fire mode for condition triggers. 'once': Disable intent after first "
                "successful fire. 'recurring': Continue firing (subject to cooldown). "
                "Default: 'recurring'. Only applies to condition triggers (price, silence, portfolio)."
)
```

### Learnings from Previous Story

**From Story 6-5-portfolio-condition-type (Status: review)**

- **Regex Patterns Added**: `PORTFOLIO_PERCENTAGE_PATTERN` and `PORTFOLIO_ABSOLUTE_PATTERN` - document supported formats
- **Default Interval**: Portfolio triggers default to `check_interval_minutes=15` - document in field description
- **CONDITION_TRIGGER_TYPES**: Now `{"price", "silence", "portfolio"}` - document which fields apply to these types
- **File Modified**: `src/services/intent_validation.py` - error messages already contain format guidance

[Source: docs/sprint-artifacts/6-5-portfolio-condition-type.md#Dev-Agent-Record]

### Project Structure Notes

- Schema changes: `src/schemas.py` - add Field descriptions
- Response models: `src/schemas.py` - IntentFireResponse, ScheduledIntentResponse
- Request models: `src/schemas.py` - ScheduledIntentCreate, TriggerSchedule, TriggerCondition
- Integration guide: `CHATBOT_INTEGRATION_GUIDE.md` (if exists)

### Testing Approach

This is primarily a documentation story. Testing involves:
1. Verify OpenAPI schema includes all descriptions via `/docs` endpoint
2. Manual review of Swagger UI for completeness
3. Optionally: automated test that parses OpenAPI JSON and checks for descriptions

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-6.md#Acceptance-Criteria]
- [Source: docs/sprint-artifacts/tech-spec-epic-6.md#Data-Models-and-Contracts]
- [Source: src/schemas.py] - Current Pydantic model definitions
- [Source: docs/CHATBOT_INTEGRATION_GUIDE.md] - Integration documentation

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/6-6-api-documentation-update.context.xml` (generated 2025-12-24)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Documentation story

### Completion Notes List

(To be filled during implementation)

### File List

**Modified:**
- `src/schemas.py` - Added Field descriptions to: check_interval_minutes, action_type, action_context, action_priority, status, next_check, enabled, execution_count, was_disabled_reason. Added backward compatibility notes to module header.

**No New Files Created**

## Change Log

| Date | Change |
|------|--------|
| 2025-12-24 | Story drafted from Epic 6 tech spec |
| 2025-12-24 | Context generated, status: ready-for-dev |
| 2025-12-24 | Implementation complete: Added OpenAPI descriptions to all Epic 6 fields |
| 2025-12-24 | Status changed to review |
| 2025-12-24 | Senior Developer Review: APPROVED → done |

