# Epic Technical Specification: Intents API Alignment for Annie Proactive AI

Date: 2025-12-24
Author: Claude Code
Epic ID: 6
Status: Draft

---

## Overview

Epic 6 extends the Scheduled Intents API (Epic 5) to fully support Annie's redesigned LLM-driven proactive AI architecture. The current API lacks timezone support for user-local scheduling, flexible condition expressions for complex triggers, cooldown logic to prevent alert fatigue, and explicit fire modes for condition-based triggers.

This epic aligns agentic-memories with Annie Epic 13 requirements by adding 5 new database columns, extending Pydantic models, and enhancing the fire endpoint logic. All changes are backward-compatible with existing triggers.

## Objectives and Scope

**In Scope:**
- Add `trigger_timezone` column for IANA timezone support in scheduled triggers
- Add `condition_expression` field for flexible human-readable conditions (e.g., "NVDA < 130")
- Add `cooldown_hours` and `last_condition_fire` for alert fatigue prevention
- Add `fire_mode` column (once vs recurring) for condition triggers
- Add 'portfolio' trigger type for portfolio-based conditions
- Extend TriggerSchedule and TriggerCondition Pydantic models
- Update fire endpoint to handle cooldown and fire_mode logic
- Add validation for timezone, expression formats, and cooldown ranges

**Out of Scope:**
- Condition evaluation logic (handled by Annie)
- Portfolio data fetching (handled by Annie via get_portfolio tool)
- New trigger types beyond 'portfolio'
- Breaking changes to existing API contracts

## System Architecture Alignment

This epic extends the existing Scheduled Intents API architecture from Epic 5:

**Component Alignment:**
- **Database:** Adds 6 columns to `scheduled_intents` table (migration 019)
- **Pydantic Models:** Extends `TriggerSchedule` and `TriggerCondition` in `src/schemas.py`
- **Service Layer:** Updates `IntentService` for cooldown/fire_mode logic
- **Validation:** Extends `IntentValidationService` for new field validation
- **API Router:** No new endpoints; updates to existing `/fire` behavior

**Constraints from Architecture:**
- Uses existing psycopg3 connection pooling (AD-007)
- Follows existing FastAPI router pattern (AD-008)
- Maintains graceful degradation pattern (AD-014)
- All timestamps stored in UTC, converted at query time

## Detailed Design

### Services and Modules

| Module | Responsibility | Inputs | Outputs |
|--------|---------------|--------|---------|
| `src/schemas.py` | Extended Pydantic models | API requests | Validated models |
| `src/services/intent_service.py` | Cooldown/fire_mode logic | IntentFireRequest | IntentFireResponse with cooldown status |
| `src/services/intent_validation.py` | Timezone, expression, cooldown validation | TriggerSchedule, TriggerCondition | ValidationResult |
| `src/services/next_check.py` | Timezone-aware next_check calculation | TriggerSchedule with timezone | datetime (UTC) |
| `migrations/postgres/019_intents_alignment.up.sql` | Schema migration | - | New columns and constraints |

### Data Models and Contracts

**New Database Columns (migration 019):**

```sql
-- Timezone support
trigger_timezone VARCHAR(64) DEFAULT 'UTC'

-- Condition expression fields
condition_type VARCHAR(32)        -- 'price', 'portfolio', 'silence'
condition_expression TEXT         -- Human-readable expression

-- Cooldown fields
cooldown_hours INT DEFAULT 24     -- 1-168 range
last_condition_fire TIMESTAMPTZ   -- Last successful condition fire

-- Fire mode
fire_mode VARCHAR(16) DEFAULT 'recurring'  -- 'once' | 'recurring'
```

**Extended TriggerSchedule Model:**

```python
class TriggerSchedule(BaseModel):
    cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    trigger_at: Optional[datetime] = None
    check_interval_minutes: Optional[int] = Field(default=5, ge=5)
    # NEW
    timezone: str = Field(
        default="UTC",
        description="IANA timezone (e.g., 'America/Los_Angeles')"
    )
```

**Extended TriggerCondition Model:**

```python
class TriggerCondition(BaseModel):
    # Existing (backward compatible)
    ticker: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[float] = None
    keywords: Optional[List[str]] = None
    threshold_hours: Optional[int] = None
    # NEW
    condition_type: Optional[str] = None   # 'price', 'portfolio', 'silence'
    expression: Optional[str] = None       # "NVDA < 130", "any_holding_change > 5%"
    cooldown_hours: int = Field(default=24, ge=1, le=168)
    fire_mode: Literal["once", "recurring"] = "recurring"
```

### APIs and Interfaces

**Updated POST /v1/intents (create):**
- Accepts new fields in `trigger_schedule.timezone` and `trigger_condition.*`
- Validates timezone using Python `zoneinfo.ZoneInfo`
- Validates expression format based on condition_type
- Stores new fields in database

**Updated GET /v1/intents/pending:**
- Excludes recently claimed intents (claimed_at > NOW() - 5 minutes)
- Adds `in_cooldown` flag to response for condition triggers
- Read-only query with no side effects

**NEW POST /v1/intents/{id}/claim:**
- Claims an intent for exclusive processing
- Returns 409 Conflict if already claimed (within 5 min timeout)
- Uses `FOR UPDATE SKIP LOCKED` to prevent race conditions
- Sets `claimed_at = NOW()` on success
- Returns `IntentClaimResponse` with intent data and claimed_at

**Updated POST /v1/intents/{id}/fire:**
- Clears `claimed_at` after processing (releases claim)
- Checks cooldown before processing condition triggers
- Returns `cooldown_active: true` with remaining hours if in cooldown
- Updates `last_condition_fire` on successful condition fires
- Disables intent if `fire_mode='once'` and status='success'

**New Response Fields (IntentFireResponse):**

```python
class IntentFireResponse(BaseModel):
    # Existing
    intent_id: UUID
    status: str
    next_check: Optional[datetime] = None
    enabled: bool
    execution_count: int
    was_disabled_reason: Optional[str] = None
    # NEW
    cooldown_active: bool = False
    cooldown_remaining_hours: Optional[float] = None
    last_condition_fire: Optional[datetime] = None
```

### Workflows and Sequencing

**Fire Intent with Cooldown Flow:**

```
1. Annie calls POST /v1/intents/{id}/fire with status='success'
2. IntentService checks if trigger_type is condition-based (price, silence, portfolio)
3. If condition-based:
   a. Load last_condition_fire and cooldown_hours
   b. Calculate hours_since_last = (NOW - last_condition_fire).hours
   c. If hours_since_last < cooldown_hours:
      - Return status='cooldown_active', cooldown_remaining_hours
      - Skip execution logging
   d. Else continue to normal fire processing
4. If status='success':
   a. Update last_condition_fire = NOW()
   b. If fire_mode='once': Set enabled=false, was_disabled_reason='fire_mode_once'
5. Calculate next_check based on trigger_type
6. Log to intent_executions
7. Return IntentFireResponse
```

**Timezone-aware Next Check Calculation:**

```
1. Load trigger_schedule.timezone (default 'UTC')
2. Validate timezone with zoneinfo.ZoneInfo
3. For cron triggers:
   - Use croniter with timezone parameter
   - Get next occurrence in user's timezone
   - Convert to UTC for storage
4. For interval triggers:
   - No timezone impact (relative intervals)
5. For once triggers:
   - Parse trigger_at in user's timezone
   - Convert to UTC for storage
```

## Non-Functional Requirements

### Performance

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| Create intent with timezone | < 50ms | ZoneInfo validation is O(1) |
| Fire with cooldown check | < 30ms | Single DB query for last_condition_fire |
| Expression validation | < 5ms | Regex-based format check |

### Security

- No new authentication requirements (follows existing MVP constraints)
- Timezone validation prevents injection (uses stdlib `zoneinfo`)
- Expression field is TEXT but not evaluated in agentic-memories (evaluation in Annie)
- Cooldown values capped at 168 hours (1 week) to prevent abuse

### Reliability/Availability

- All new columns have sensible defaults for backward compatibility
- Cooldown check failure defaults to allowing fire (fail-open for proactive messaging)
- Invalid timezone defaults to UTC with warning log
- Database migration is additive (no data loss risk)

### Observability

**Logging:**
- `[intents.fire] cooldown_active=true remaining_hours=X` when cooldown blocks
- `[intents.fire] fire_mode_once disabled intent_id=X` when once-mode triggers
- `[intents.validation] invalid_timezone=X defaulting_to=UTC`

**Metrics (via Langfuse):**
- Cooldown block rate per user
- Fire mode once trigger rate
- Timezone distribution across intents

## Dependencies and Integrations

**Python Dependencies (existing - no new deps):**
- `zoneinfo` (Python 3.9+ stdlib) - timezone validation
- `croniter` (existing) - timezone-aware cron parsing
- `psycopg[binary]` (existing) - PostgreSQL driver
- `pydantic` (existing) - model validation

**Integration Points:**
- **Annie Epic 13:** Consumes extended IntentFireResponse with cooldown fields
- **Annie Proactive Worker:** Uses timezone for user-local scheduling decisions
- **Annie Expression Evaluator:** Parses condition_expression field (not agentic-memories)

## Acceptance Criteria (Authoritative)

**Story 6.1: Timezone Support**
1. AC1.1: `trigger_timezone` column added with default 'UTC'
2. AC1.2: TriggerSchedule model accepts `timezone` field
3. AC1.3: Invalid timezones return validation error with IANA format example
4. AC1.4: Cron next_check calculated using user timezone, stored as UTC
5. AC1.5: API response includes timezone in trigger_schedule

**Story 6.2: Condition Expression Support**
1. AC2.1: `condition_type` and `condition_expression` columns added
2. AC2.2: TriggerCondition model accepts new fields
3. AC2.3: Price expressions validated as "TICKER OP VALUE" format
4. AC2.4: Portfolio expressions validated against supported keywords
5. AC2.5: Backward compatible with existing structured fields

**Story 6.3: Cooldown Logic**
1. AC3.1: `cooldown_hours` (default 24) and `last_condition_fire` columns added
2. AC3.2: Fire endpoint checks cooldown before processing condition triggers
3. AC3.3: Returns `cooldown_active=true` with remaining hours when blocked
4. AC3.4: Updates `last_condition_fire` on successful fires
5. AC3.5: Pending query excludes/flags triggers in cooldown

**Story 6.4: Fire Mode Support**
1. AC4.1: `fire_mode` column added with default 'recurring'
2. AC4.2: TriggerCondition model accepts `fire_mode` field
3. AC4.3: Fire endpoint disables intent when fire_mode='once' and status='success'
4. AC4.4: Response includes `was_disabled_reason='fire_mode_once'`

**Story 6.5: Portfolio Condition Type**
1. AC5.1: 'portfolio' added to trigger_type CHECK constraint
2. AC5.2: Portfolio expressions validated (any_holding_change, total_value, etc.)
3. AC5.3: Default check_interval_minutes=15 for portfolio triggers

**Story 6.6: API Documentation Update**
1. AC6.1: All new fields have OpenAPI descriptions
2. AC6.2: action_context guidance documented
3. AC6.3: Migration notes for existing triggers

## Traceability Mapping

| AC | Spec Section | Component/File | Test Idea |
|----|--------------|----------------|-----------|
| AC1.1 | Data Models | `migrations/019_intents_alignment.up.sql` | Verify column exists with default |
| AC1.2 | Data Models | `src/schemas.py::TriggerSchedule` | Unit test timezone field |
| AC1.3 | APIs | `src/services/intent_validation.py` | Test invalid timezone error |
| AC1.4 | Workflows | `src/services/next_check.py` | Test cron with America/Los_Angeles |
| AC2.1 | Data Models | `migrations/019_intents_alignment.up.sql` | Verify columns exist |
| AC2.2 | Data Models | `src/schemas.py::TriggerCondition` | Unit test new fields |
| AC2.3 | APIs | `src/services/intent_validation.py` | Test "NVDA < 130" validation |
| AC3.1 | Data Models | `migrations/019_intents_alignment.up.sql` | Verify columns and defaults |
| AC3.2-3.4 | Workflows | `src/services/intent_service.py::fire_intent` | Integration test cooldown flow |
| AC4.1-4.4 | Workflows | `src/services/intent_service.py::fire_intent` | Test once-mode disable |
| AC5.1 | Data Models | `migrations/019_intents_alignment.up.sql` | Verify constraint update |
| AC5.2 | APIs | `src/services/intent_validation.py` | Test portfolio expression validation |

## Risks, Assumptions, Open Questions

**Risks:**
- R1: Timezone conversion edge cases (DST transitions) may cause unexpected behavior. *Mitigation:* Use `zoneinfo` stdlib which handles DST correctly.
- R2: Large cooldown values (168h) may cause users to forget about triggers. *Mitigation:* Document recommended cooldown ranges.

**Assumptions:**
- A1: Annie evaluates condition expressions; agentic-memories only validates format
- A2: All existing triggers default to UTC timezone (no migration of historical data)
- A3: Cooldown only applies to condition triggers (price, silence, portfolio), not scheduled triggers

**Open Questions:**
- Q1: Should cooldown be per-condition-value or global per-trigger? *Resolution:* Global per-trigger (simpler)
- Q2: Should pending query filter by cooldown or return with flag? *Resolution:* Return with flag for Annie flexibility

## Test Strategy Summary

**Unit Tests:**
- Timezone validation (valid/invalid IANA strings)
- Expression validation by condition_type
- Cooldown calculation logic
- Fire mode state transitions

**Integration Tests:**
- Create intent with timezone, verify next_check in UTC
- Fire intent, verify cooldown updates
- Fire once-mode intent, verify disabled
- Create portfolio trigger with expression

**E2E Tests:**
- Full flow: Create → Pending → Fire → Cooldown → Fire again (blocked)
- Timezone-aware cron scheduling across DST boundary

**Test Coverage Targets:**
- Unit: 90%+ on new validation logic
- Integration: All 6 stories have dedicated test cases
- E2E: 2-3 scenario tests for critical flows
