# Epic 6: Intents API Alignment for Annie Proactive AI

**Epic ID:** 6
**Author:** Claude Code
**Status:** Proposed
**Priority:** P1 (Blocks Annie Epic 13)
**Dependencies:** Epic 5 (Scheduled Intents API) - Must be complete
**Downstream Dependents:** Annie Epic 13 (Proactive AI Worker)

---

## Executive Summary

Extend the Scheduled Intents API (Epic 5) to fully support Annie's redesigned LLM-driven proactive AI architecture. This epic adds missing fields for timezone support, flexible condition expressions, cooldown logic, and enhanced action_context validation.

**Key Changes:**
- **Timezone support** for user-local scheduling
- **Flexible condition expressions** ("NVDA < 130", "any_holding_change > 5%")
- **Cooldown logic** to prevent alert fatigue
- **Fire mode** (once vs recurring) for condition triggers
- **action_context guidance** for rich JSON briefing documents

---

## Background & Motivation

### Annie's Redesigned Architecture

Annie's proactive AI has evolved from a code-driven to an **LLM-driven architecture**:

1. **Creation LLM** captures user intent in rich `action_context` briefing
2. **Wake-up LLM** reads briefing and decides what to do
3. Only **2 trigger types**: `scheduled` and `condition`
4. **Dynamic state injection** at wake-up time

### Gap Analysis

| Feature | Current (Epic 5) | Annie Needs | Status |
|---------|------------------|-------------|--------|
| Timezone | Not supported | IANA timezone per trigger | **MISSING** |
| Condition expression | Structured fields only | Flexible string expression | **MISSING** |
| Cooldown | Not supported | Hours between fires | **MISSING** |
| Fire mode | Implicit (once for `once` type) | Explicit for all conditions | **MISSING** |
| action_context | TEXT string | Rich JSON guidance | Compatible |
| Portfolio conditions | Not supported | "any_holding_change > 5%" | **MISSING** |

### Reference Documents

- [Annie Proactive AI Architecture](file:///Users/Ankit/dev/annie/docs/design/proactive-ai-architecture.md)
- [Annie Epic 13](file:///Users/Ankit/dev/annie/docs/epics/epic-13-proactive-ai.md)

---

## Technical Design

### Schema Changes

#### TriggerSchedule Additions

```python
class TriggerSchedule(BaseModel):
    # Existing fields
    cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    trigger_at: Optional[datetime] = None
    check_interval_minutes: Optional[int] = Field(default=5, ge=5)

    # NEW: Timezone support
    timezone: str = Field(
        default="America/Los_Angeles",
        description="IANA timezone (e.g., 'America/Los_Angeles', 'Europe/London')"
    )
```

**Migration SQL:**
```sql
ALTER TABLE scheduled_intents
ADD COLUMN trigger_timezone VARCHAR(64) DEFAULT 'America/Los_Angeles';

-- Update existing trigger_schedule JSONB to include timezone
UPDATE scheduled_intents
SET trigger_schedule = trigger_schedule || '{"timezone": "America/Los_Angeles"}'::jsonb
WHERE trigger_schedule IS NOT NULL;
```

#### TriggerCondition Additions

```python
class TriggerCondition(BaseModel):
    # Existing fields (for backward compatibility)
    ticker: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[float] = None
    keywords: Optional[List[str]] = None
    threshold_hours: Optional[int] = None

    # NEW: Flexible expression support
    condition_type: Optional[str] = Field(
        default=None,
        description="Condition category: 'price', 'portfolio', 'silence'"
    )
    expression: Optional[str] = Field(
        default=None,
        description="Human-readable condition expression (e.g., 'NVDA < 130', 'any_holding_change > 5%')"
    )

    # NEW: Cooldown to prevent alert fatigue
    cooldown_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Minimum hours between fires (1-168, default 24)"
    )

    # NEW: Fire mode
    fire_mode: Literal["once", "recurring"] = Field(
        default="recurring",
        description="'once' disables after first fire, 'recurring' continues"
    )
```

**Migration SQL:**
```sql
-- Add new columns to scheduled_intents
ALTER TABLE scheduled_intents
ADD COLUMN condition_type VARCHAR(32),
ADD COLUMN condition_expression TEXT,
ADD COLUMN cooldown_hours INT DEFAULT 24,
ADD COLUMN fire_mode VARCHAR(16) DEFAULT 'recurring',
ADD COLUMN last_condition_fire TIMESTAMPTZ;

-- Add constraint for fire_mode
ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_fire_mode CHECK (fire_mode IN ('once', 'recurring'));

-- Index for cooldown queries
CREATE INDEX idx_intents_cooldown ON scheduled_intents (user_id, last_condition_fire)
WHERE trigger_type IN ('price', 'portfolio', 'silence');
```

### API Changes

#### Updated Create/Update Request

```python
class ScheduledIntentCreate(BaseModel):
    # ... existing fields ...

    # Enhanced trigger_condition with new fields
    trigger_condition: Optional[TriggerConditionV2] = None

class TriggerConditionV2(BaseModel):
    """V2 condition with expression support."""

    # Legacy structured fields (still supported)
    ticker: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[float] = None
    threshold_hours: Optional[int] = None

    # New flexible fields
    condition_type: Optional[str] = None  # price, portfolio, silence
    expression: Optional[str] = None      # "NVDA < 130"
    cooldown_hours: int = 24
    fire_mode: Literal["once", "recurring"] = "recurring"
```

#### Updated Fire Endpoint Logic

```python
async def fire_intent(intent_id: UUID, request: IntentFireRequest):
    """
    Enhanced fire logic with cooldown support.
    """
    intent = await get_intent(intent_id)

    # Check cooldown for condition triggers
    if intent.trigger_type in ("price", "silence", "portfolio"):
        if intent.last_condition_fire:
            hours_since_last = (now - intent.last_condition_fire).total_seconds() / 3600
            if hours_since_last < intent.cooldown_hours:
                return IntentFireResponse(
                    status="cooldown_active",
                    next_check=intent.last_condition_fire + timedelta(hours=intent.cooldown_hours)
                )

    # Process fire request...

    # Update last_condition_fire on success
    if request.status == "success" and intent.trigger_type in ("price", "silence", "portfolio"):
        intent.last_condition_fire = now

    # Handle fire_mode='once' - disable after first success
    if request.status == "success" and intent.fire_mode == "once":
        intent.enabled = False
        was_disabled_reason = "fire_mode_once"
```

#### New Response Fields

```python
class IntentFireResponse(BaseModel):
    # ... existing fields ...

    # NEW: Cooldown information
    cooldown_active: bool = False
    cooldown_remaining_hours: Optional[float] = None
    last_condition_fire: Optional[datetime] = None
```

### Validation Updates

#### New Validation Rules

| Rule | Constraint | Error Message |
|------|------------|---------------|
| Valid timezone | Must be valid IANA timezone | "Invalid timezone: {tz}. Use IANA format (e.g., 'America/Los_Angeles')" |
| Cooldown range | 1-168 hours | "Cooldown must be between 1 and 168 hours" |
| Expression format (price) | `TICKER OP VALUE` | "Price expression must be format: 'TICKER < VALUE'" |
| Expression format (portfolio) | Supported expressions | "Unsupported portfolio expression. Supported: any_holding_change, total_change, total_value" |
| Expression format (silence) | `inactive_hours > N` | "Silence expression must be format: 'inactive_hours > N'" |

#### Timezone Validation

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

### action_context Guidance

While `action_context` remains a TEXT field (for flexibility), Annie expects a JSON structure. Add validation guidance in documentation:

**Recommended action_context Structure:**
```json
{
    "original_request": "User's exact words",
    "intent_summary": "Brief summary of intent",
    "user_context": {
        "name": "User name",
        "timezone": "User timezone",
        "communication_style": "Preferences"
    },
    "execution_instructions": "Step-by-step guide for wake-up LLM",
    "message_guidance": "Tone, length, examples",
    "available_tools": "Suggested tools to use",
    "edge_cases": "How to handle unusual situations",
    "meta": {
        "created_at": "ISO timestamp",
        "created_by": "Source"
    }
}
```

**Note:** Validation of action_context structure happens in Annie, not agentic-memories.

---

## Stories Breakdown

### Story 6.1: Timezone Support

**Goal:** Add timezone field to trigger scheduling.

**Acceptance Criteria:**

**AC #1: Schema Migration**
- Add `trigger_timezone` column to `scheduled_intents`
- Default value: 'America/Los_Angeles'
- Backfill existing records with 'America/Los_Angeles'

**AC #2: TriggerSchedule Model**
- Add `timezone: str` field with default 'America/Los_Angeles'
- Validate using `zoneinfo.ZoneInfo`
- Return validation error for invalid timezones

**AC #3: Next Check Calculation**
- Use timezone when calculating next cron occurrence
- Use timezone for one-time trigger comparisons
- Store next_check in UTC (convert from user timezone)

**AC #4: API Response**
- Include timezone in TriggerSchedule response
- Include effective timezone in pending query results

**Technical Notes:**
- Use Python 3.9+ `zoneinfo` module (no external deps)
- Store all timestamps in UTC, convert at query time
- croniter supports timezone via pytz/zoneinfo

**Estimated Effort:** 3 hours

---

### Story 6.2: Condition Expression Support

**Goal:** Add flexible expression field for conditions.

**Acceptance Criteria:**

**AC #1: Schema Migration**
- Add `condition_type` VARCHAR(32) column
- Add `condition_expression` TEXT column
- Nullable (for backward compatibility)

**AC #2: TriggerCondition Model**
- Add `condition_type: Optional[str]` (price, portfolio, silence)
- Add `expression: Optional[str]`
- Maintain backward compatibility with existing structured fields

**AC #3: Expression Validation**
Given expression provided, validate format:
- Price: `TICKER OP VALUE` (e.g., "NVDA < 130")
- Portfolio: Supported keywords (any_holding_change, total_change, total_value)
- Silence: `inactive_hours > N`

**AC #4: Response Model**
- Include condition_type and expression in responses
- Return both legacy fields AND new fields

**Technical Notes:**
- Annie does actual expression parsing/evaluation
- agentic-memories only validates format
- Regex patterns for basic format validation

**Estimated Effort:** 2 hours

---

### Story 6.3: Cooldown Logic

**Goal:** Prevent alert fatigue with configurable cooldown.

**Acceptance Criteria:**

**AC #1: Schema Migration**
- Add `cooldown_hours` INT column (default 24)
- Add `last_condition_fire` TIMESTAMPTZ column
- Add index for cooldown queries

**AC #2: TriggerCondition Model**
- Add `cooldown_hours: int` with range validation (1-168)
- Default: 24 hours

**AC #3: Fire Endpoint Logic**
Given condition trigger fires, when cooldown active, then:
- Return `status: "cooldown_active"`
- Return `cooldown_remaining_hours`
- Do NOT update next_check
- Do NOT log to executions (or log with special status)

**AC #4: Fire Success Update**
Given condition trigger fires successfully, then:
- Update `last_condition_fire = NOW()`
- Calculate next eligible fire time

**AC #5: Pending Query**
Given pending query, when returning condition triggers, then:
- Exclude triggers where `last_condition_fire + cooldown_hours > NOW()`
- OR include them with `cooldown_active: true` flag

**Technical Notes:**
- Cooldown only applies to condition triggers (price, portfolio, silence)
- Scheduled triggers (cron, once, interval) do not use cooldown

**Estimated Effort:** 3 hours

---

### Story 6.4: Fire Mode Support

**Goal:** Support once vs recurring for condition triggers.

**Acceptance Criteria:**

**AC #1: Schema Migration**
- Add `fire_mode` VARCHAR(16) column
- Default: 'recurring'
- Constraint: IN ('once', 'recurring')

**AC #2: TriggerCondition Model**
- Add `fire_mode: Literal["once", "recurring"]`
- Default: "recurring"

**AC #3: Fire Endpoint Logic**
Given fire_mode='once' and status='success', then:
- Set `enabled = false`
- Set `was_disabled_reason = "fire_mode_once"`
- Return disabled status in response

**AC #4: Validation**
- fire_mode only applies to condition triggers
- Warn (don't error) if fire_mode set on scheduled trigger

**Technical Notes:**
- Similar to existing one-time trigger logic
- Extends to all condition types

**Estimated Effort:** 1.5 hours

---

### Story 6.5: Portfolio Condition Type

**Goal:** Support portfolio-based conditions.

**Acceptance Criteria:**

**AC #1: Add 'portfolio' to Trigger Types**
- Update CHECK constraint to include 'portfolio'
- Add to validation whitelist

**AC #2: Portfolio Expression Validation**
Given condition_type='portfolio', validate expression:
- `any_holding_change > X%`
- `any_holding_down > X%`
- `any_holding_up > X%`
- `total_value >= X`
- `total_change > X%`

**AC #3: Required Fields**
Given trigger_type='portfolio', require:
- `condition_type = 'portfolio'`
- `expression` (validated format)
- `check_interval_minutes` (default 15 for portfolio)

**Technical Notes:**
- Annie evaluates portfolio conditions using get_portfolio tool
- agentic-memories only stores and validates format

**Estimated Effort:** 1 hour

---

### Story 6.6: API Documentation Update

**Goal:** Document all new fields and behaviors.

**Acceptance Criteria:**

**AC #1: OpenAPI Schema**
- Update Pydantic models with descriptions
- Generate updated OpenAPI spec
- All new fields documented with examples

**AC #2: action_context Guidance**
- Add documentation section explaining recommended JSON structure
- Note that validation happens in Annie
- Provide example action_context

**AC #3: Migration Guide**
- Document breaking changes (if any)
- Provide upgrade path for existing triggers
- Note backward compatibility

**Technical Notes:**
- Update docstrings for OpenAPI generation
- Add examples to Pydantic Field() definitions

**Estimated Effort:** 1.5 hours

---

## Database Migration Summary

```sql
-- Migration: 019_intents_alignment.up.sql

-- 1. Add timezone support
ALTER TABLE scheduled_intents
ADD COLUMN trigger_timezone VARCHAR(64) DEFAULT 'America/Los_Angeles';

-- 2. Add condition expression fields
ALTER TABLE scheduled_intents
ADD COLUMN condition_type VARCHAR(32),
ADD COLUMN condition_expression TEXT;

-- 3. Add cooldown fields
ALTER TABLE scheduled_intents
ADD COLUMN cooldown_hours INT DEFAULT 24,
ADD COLUMN last_condition_fire TIMESTAMPTZ;

-- 4. Add fire mode
ALTER TABLE scheduled_intents
ADD COLUMN fire_mode VARCHAR(16) DEFAULT 'recurring';

-- 5. Update constraints
ALTER TABLE scheduled_intents
DROP CONSTRAINT IF EXISTS chk_trigger_type;

ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_trigger_type CHECK (
    trigger_type IN ('cron', 'interval', 'once', 'price', 'silence', 'portfolio')
);

ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_fire_mode CHECK (
    fire_mode IN ('once', 'recurring')
);

ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_cooldown_hours CHECK (
    cooldown_hours >= 1 AND cooldown_hours <= 168
);

-- 6. Indexes
CREATE INDEX idx_intents_cooldown ON scheduled_intents (user_id, last_condition_fire)
WHERE trigger_type IN ('price', 'portfolio', 'silence');

-- 7. Backfill existing records
UPDATE scheduled_intents
SET
    trigger_timezone = 'America/Los_Angeles',
    cooldown_hours = 24,
    fire_mode = 'recurring'
WHERE trigger_timezone IS NULL;
```

---

## Success Criteria

1. All existing triggers continue to work (backward compatibility)
2. New triggers can specify timezone
3. Condition triggers support flexible expressions
4. Cooldown prevents duplicate alerts
5. fire_mode='once' disables after first success
6. Portfolio conditions validated correctly
7. OpenAPI documentation complete
8. Annie Epic 13 can integrate without changes

---

## Estimated Total Effort

| Story | Effort |
|-------|--------|
| 6.1 Timezone Support | 3 hours |
| 6.2 Condition Expression | 2 hours |
| 6.3 Cooldown Logic | 3 hours |
| 6.4 Fire Mode | 1.5 hours |
| 6.5 Portfolio Condition | 1 hour |
| 6.6 Documentation | 1.5 hours |
| **Total** | **12 hours (~1.5 days)** |

---

## References

- [Annie Proactive AI Architecture](file:///Users/Ankit/dev/annie/docs/design/proactive-ai-architecture.md)
- [Annie Epic 13: Proactive AI Worker](file:///Users/Ankit/dev/annie/docs/epics/epic-13-proactive-ai.md)
- [Epic 5: Scheduled Intents API](./epic-5-scheduled-intents.md)
- [IANA Time Zone Database](https://www.iana.org/time-zones)

---

*This epic ensures agentic-memories fully supports Annie's LLM-driven proactive AI architecture with timezone awareness, flexible conditions, and cooldown logic.*
