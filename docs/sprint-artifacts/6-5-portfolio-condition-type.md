# Story 6.5: Portfolio Condition Type

Status: done

## Story

As an **Annie Proactive Worker**,
I want **portfolio-based condition triggers**,
so that **I can create proactive alerts when portfolio holdings change significantly (e.g., "any stock down 5%")**.

## Acceptance Criteria

1. **AC5.1:** 'portfolio' added to trigger_type CHECK constraint
   - Update CHECK constraint in `scheduled_intents` table to include 'portfolio'
   - Add 'portfolio' to trigger_type validation whitelist in Pydantic model
   - Existing CHECK constraint: `('cron', 'interval', 'once', 'price', 'silence')`
   - New CHECK constraint: `('cron', 'interval', 'once', 'price', 'silence', 'portfolio')`

2. **AC5.2:** Portfolio expressions validated
   - Given `condition_type='portfolio'`, validate expression format
   - Supported expressions:
     - `any_holding_change > X%` - any holding changed by X%
     - `any_holding_down > X%` - any holding down by X%
     - `any_holding_up > X%` - any holding up by X%
     - `total_value >= X` - total portfolio value threshold
     - `total_change > X%` - total portfolio changed by X%
   - Return validation error for unsupported expression formats
   - Regex pattern: `^(any_holding_change|any_holding_down|any_holding_up|total_change)\s*(>|>=|<|<=)\s*\d+(\.\d+)?%$` or `^total_value\s*(>|>=|<|<=)\s*\d+(\.\d+)?$`

3. **AC5.3:** Default check_interval_minutes=15 for portfolio triggers
   - When `trigger_type='portfolio'`, set default `check_interval_minutes=15`
   - Override default of 5 minutes (more frequent portfolio checks unnecessary)
   - User can still explicitly set lower values if needed
   - Require `condition_type='portfolio'` and valid `expression` for portfolio triggers

## Tasks / Subtasks

- [x] **Task 1: Database Migration - Add 'portfolio' Trigger Type** (AC: 5.1)
  - [x] 1.1 Already done in `migrations/postgres/019_intents_alignment.up.sql` (line 14)
  - [x] 1.2 Migration 019 drops and recreates CHECK constraint
  - [x] 1.3 CHECK constraint includes 'portfolio': `('cron', 'interval', 'once', 'price', 'silence', 'portfolio')`
  - [x] 1.4 Down migration exists in `019_intents_alignment.down.sql`

- [x] **Task 2: Update Pydantic Model Validation** (AC: 5.1)
  - [x] 2.1 `ScheduledIntentCreate.trigger_type` Literal already includes 'portfolio' (schemas.py:306)
  - [x] 2.2 'portfolio' already in `CONDITION_TRIGGER_TYPES` constant (intent_service.py:93)
  - [x] 2.3 OpenAPI schema includes 'portfolio' in trigger_type enum

- [x] **Task 3: Implement Portfolio Expression Validation** (AC: 5.2)
  - [x] 3.1 Enhanced existing validation in `src/services/intent_validation.py`
  - [x] 3.2 Added `PORTFOLIO_PERCENTAGE_PATTERN` and `PORTFOLIO_ABSOLUTE_PATTERN` regex patterns
  - [x] 3.3 Updated `_validate_condition_expression()` to use strict regex validation
  - [x] 3.4 Clear error messages with supported keywords and format examples

- [x] **Task 4: Set Default check_interval_minutes for Portfolio** (AC: 5.3)
  - [x] 4.1 Added detection for `trigger_type='portfolio'` in `intent_service.py:create_intent()`
  - [x] 4.2 Default `check_interval_minutes=15` applied for portfolio triggers
  - [x] 4.3 Portfolio triggers require `condition_type='portfolio'` (validated)
  - [x] 4.4 Expression field validated with strict regex patterns

- [x] **Task 5: Unit Tests** (AC: 5.1, 5.2, 5.3)
  - [x] 5.1 Test 'portfolio' is valid trigger_type
  - [x] 5.2 Test portfolio expression validation - valid cases (percentage + absolute patterns)
  - [x] 5.3 Test portfolio expression validation - invalid cases
  - [x] 5.4 Test default check_interval_minutes=15 for portfolio
  - [x] 5.5 Test explicit check_interval_minutes override
  - [x] 5.6 Test portfolio with cooldown/fire_mode support
  - [x] 5.7 Test full condition configuration

- [x] **Task 6: Integration Tests** (AC: 5.1, 5.2, 5.3)
  - [x] 6.1 Create portfolio intent with valid expression, verify stored
  - [x] 6.2 Create portfolio intent with total_value expression
  - [x] 6.3 Create portfolio intent with invalid expression, verify 400 error
  - [x] 6.4 Create portfolio intent, verify check_interval_minutes=15 default
  - [x] 6.5 Verify portfolio triggers appear in pending query
  - [x] 6.6 Test fire portfolio intent with fire_mode='once'

## Dev Notes

### Architecture Patterns

- **Database Constraint:** Extend existing CHECK constraint on `trigger_type` column
- **Pydantic Validation:** Extend `ScheduledIntentCreate` trigger_type Literal
- **Expression Validation:** New validation function in `intent_validation.py`
- **Default Handling:** Apply defaults in create/update logic before storage
- **Condition Types:** Portfolio joins price/silence as condition-based triggers

### Portfolio Trigger Flow (from Tech Spec)

```
1. Annie creates intent with trigger_type='portfolio'
2. Validation checks:
   a. condition_type must equal 'portfolio'
   b. expression must match supported patterns
   c. check_interval_minutes defaults to 15 if not set
3. Intent stored in scheduled_intents table
4. Annie's proactive worker polls pending intents
5. Worker evaluates portfolio expression using get_portfolio tool
6. If condition met, fire intent (subject to cooldown/fire_mode)
```

### Supported Portfolio Expressions

| Expression Pattern | Example | Description |
|-------------------|---------|-------------|
| `any_holding_change > X%` | `any_holding_change > 5%` | Any single holding changed ±5% |
| `any_holding_down > X%` | `any_holding_down > 10%` | Any single holding dropped 10% |
| `any_holding_up > X%` | `any_holding_up > 15%` | Any single holding gained 15% |
| `total_value >= X` | `total_value >= 100000` | Total portfolio value threshold |
| `total_change > X%` | `total_change > 3%` | Entire portfolio changed 3% |

### Validation Regex Patterns

```python
PORTFOLIO_EXPRESSION_PATTERNS = {
    "percentage": r"^(any_holding_change|any_holding_down|any_holding_up|total_change)\s*(>|>=|<|<=)\s*(\d+(\.\d+)?)%$",
    "absolute": r"^total_value\s*(>|>=|<|<=)\s*(\d+(\.\d+)?)$"
}
```

### Learnings from Previous Story

**From Story 6-4-fire-mode-support (Status: in-progress)**

- **Migration Numbering**: This story uses migration 023 (following 022 from fire_mode)
- **CONDITION_TRIGGER_TYPES constant**: Must update to include 'portfolio' alongside {'price', 'silence'}
- **Validation Pattern**: Follow existing `_validate_price_expression()` pattern for portfolio
- **Test Organization**: Create dedicated test file `tests/unit/test_portfolio_trigger.py`

**Key Files from Story 6.4:**
- `src/services/intent_validation.py` - Contains expression validation patterns
- `src/schemas.py` - Contains trigger_type Literal definition
- `tests/unit/test_fire_mode.py` - Pattern for unit test organization

[Source: docs/sprint-artifacts/6-4-fire-mode-support.md#Dev-Notes]

### Project Structure Notes

- Migration file: `migrations/postgres/023_portfolio_trigger_type.up.sql` (new file)
- Schema changes: `src/schemas.py::ScheduledIntentCreate` - add 'portfolio' to trigger_type
- Validation: `src/services/intent_validation.py` - add `_validate_portfolio_expression()`
- Constants: Update `CONDITION_TRIGGER_TYPES` to include 'portfolio'
- Unit tests: `tests/unit/test_portfolio_trigger.py` (new)
- Integration tests: `tests/integration/test_intents_api.py` (extend existing)

### Relationship to Other Condition Types

Portfolio triggers share behavior with price and silence triggers:
- Uses cooldown logic (Story 6.3)
- Uses fire_mode (Story 6.4)
- Evaluated by Annie, not agentic-memories

**CONDITION_TRIGGER_TYPES** after this story:
```python
CONDITION_TRIGGER_TYPES = {"price", "silence", "portfolio"}
```

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-6.md#Story-6.5-Portfolio-Condition-Type]
- [Source: docs/epic-6-intents-api-alignment.md#Story-6.5]
- [Source: src/services/intent_validation.py] - Existing expression validation patterns
- [Source: src/schemas.py] - trigger_type Literal definition

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/6-5-portfolio-condition-type.context.xml` (generated 2025-12-24)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Story not yet implemented

### Completion Notes List

(To be filled during implementation)

### File List

**Created:**
- `tests/unit/test_portfolio_trigger.py` - Unit tests for portfolio trigger validation (280+ lines)

**Modified:**
- `src/services/intent_validation.py` - Added `PORTFOLIO_PERCENTAGE_PATTERN` and `PORTFOLIO_ABSOLUTE_PATTERN` regex patterns; enhanced `_validate_condition_expression()` for strict portfolio validation
- `src/services/intent_service.py` - Added default `check_interval_minutes=15` for portfolio triggers in `create_intent()`
- `tests/integration/test_intents_api.py` - Added `TestPortfolioTrigger` class with 10 integration tests

**Previously Complete (from migration 019):**
- `migrations/postgres/019_intents_alignment.up.sql` - Already includes 'portfolio' in CHECK constraint
- `src/schemas.py` - Already has 'portfolio' in trigger_type Literal

## Change Log

| Date | Change |
|------|--------|
| 2025-12-24 | Story drafted from Epic 6 tech spec with learnings from Story 6.4 |
| 2025-12-24 | Context generated, status: ready-for-dev |
| 2025-12-24 | Implementation complete: regex validation, default interval, unit+integration tests |
| 2025-12-24 | Status changed to review |
| 2025-12-24 | Senior Developer Review: APPROVED → done |

