# Epic 5: Scheduled Intents API

**Epic ID:** 5
**Author:** Claude Code (Based on technical research 2025-12-21)
**Status:** Proposed
**Priority:** P1 (Enables Annie Proactive AI)
**Dependencies:** None (uses existing PostgreSQL infrastructure)
**Downstream Dependents:** Annie Epic 13 (Proactive AI Worker)

---

## Executive Summary

Create a Scheduled Intents API in agentic-memories to store, manage, and track triggers for Annie's proactive messaging system. This API provides durable storage for trigger definitions while Annie handles the scheduling, evaluation, and message generation.

**Key Benefits:**
- **Durability**: Triggers survive restarts (PostgreSQL ACID)
- **Audit trail**: Full execution history for analytics
- **Queryability**: "What NVDA alerts do I have?"
- **Clean separation**: Storage in agentic-memories, logic in Annie

---

## Background & Motivation

### Current Architecture

Annie currently operates in reactive mode only - responding to user messages. To become a proactive AI companion, Annie needs to initiate contact based on:
- Time-based schedules (cron, intervals, one-time reminders)
- Price alerts (NVDA < $130)
- Silence detection (no message in 48h)
- Event triggers (news, calendar)

### Why Store in Agentic-Memories?

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Annie Redis | Fast, already there | No audit trail, limited queries | No |
| Annie PostgreSQL | Queryable | New infrastructure | No |
| **Agentic-Memories PostgreSQL** | Already exists, audit trail, Langfuse | API hop | **Yes** |

### Architecture: Storage vs Logic Split

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENTIC-MEMORIES (This Epic)                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Storage                                       │  │
│  │  ├── scheduled_intents table (definitions + state)        │  │
│  │  └── intent_executions table (audit trail)                │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  REST API                                                 │  │
│  │  ├── CRUD: /v1/intents                                    │  │
│  │  ├── Query: /v1/intents/pending                           │  │
│  │  └── State: /v1/intents/{id}/fire                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Owns:                                                    │  │
│  │  ├── next_check calculation                               │  │
│  │  ├── last_executed updates                                │  │
│  │  ├── Disabling one-time triggers                          │  │
│  │  └── Execution history logging                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ANNIE (Epic 13 - Depends on this)                              │
│  ├── Background worker polls /pending                           │
│  ├── Evaluates conditions (yfinance, Redis)                     │
│  ├── Subconscious gate (spam prevention)                        │
│  ├── LLM generation (initiator mode)                            │
│  └── Telegram delivery, then POST /fire                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Design

### Database Schema

**Table: `scheduled_intents`**

```sql
CREATE TABLE scheduled_intents (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    intent_name VARCHAR(256) NOT NULL,
    description TEXT,

    -- Trigger Definition
    trigger_type VARCHAR(32) NOT NULL,      -- 'cron', 'interval', 'once', 'price', 'silence', 'event'
    trigger_schedule JSONB,                  -- {"cron": "0 9 * * 1"} or {"interval_minutes": 60}
    trigger_condition JSONB,                 -- {"ticker": "NVDA", "operator": "<", "value": 130}

    -- Action Configuration
    action_type VARCHAR(64) DEFAULT 'notify',
    action_context TEXT NOT NULL,            -- Passed to LLM when firing
    action_priority VARCHAR(16) DEFAULT 'normal',

    -- Scheduling State (OWNED BY AGENTIC-MEMORIES)
    next_check TIMESTAMPTZ,
    last_checked TIMESTAMPTZ,
    last_executed TIMESTAMPTZ,
    execution_count INT DEFAULT 0,

    -- Execution Results
    last_execution_status VARCHAR(32),
    last_execution_error TEXT,
    last_message_id VARCHAR(128),

    -- Control
    enabled BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    max_executions INT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64),
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT chk_trigger_type CHECK (
        trigger_type IN ('cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news')
    ),
    CONSTRAINT chk_action_type CHECK (
        action_type IN ('notify', 'check_in', 'briefing', 'analysis', 'reminder')
    ),
    CONSTRAINT chk_priority CHECK (
        action_priority IN ('low', 'normal', 'high', 'critical')
    )
);

-- Indexes
CREATE INDEX idx_intents_user_enabled ON scheduled_intents (user_id, enabled) WHERE enabled = true;
CREATE INDEX idx_intents_pending ON scheduled_intents (next_check) WHERE enabled = true AND next_check IS NOT NULL;
CREATE INDEX idx_intents_type ON scheduled_intents (user_id, trigger_type);
```

**Table: `intent_executions`**

```sql
CREATE TABLE intent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL REFERENCES scheduled_intents(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_type VARCHAR(32) NOT NULL,
    trigger_data JSONB,
    status VARCHAR(32) NOT NULL,             -- 'success', 'failed', 'gate_blocked', 'condition_not_met'
    gate_result JSONB,
    message_id VARCHAR(128),
    message_preview TEXT,
    evaluation_ms INT,
    generation_ms INT,
    delivery_ms INT,
    error_message TEXT
);

CREATE INDEX idx_executions_intent ON intent_executions (intent_id, executed_at DESC);
CREATE INDEX idx_executions_user ON intent_executions (user_id, executed_at DESC);
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/intents` | Create trigger (with validation) |
| GET | `/v1/intents` | List triggers for user |
| GET | `/v1/intents/pending` | Get due triggers (next_check <= NOW) |
| GET | `/v1/intents/{id}` | Get single trigger |
| PUT | `/v1/intents/{id}` | Update trigger |
| DELETE | `/v1/intents/{id}` | Delete trigger |
| POST | `/v1/intents/{id}/fire` | Report execution, update state |
| GET | `/v1/intents/{id}/history` | Get execution history |

### How `/pending` Works

Simple query - no scheduler logic:

```sql
SELECT * FROM scheduled_intents
WHERE enabled = true
  AND next_check <= NOW()
ORDER BY next_check ASC;
```

Annie polls this every 30 seconds. Agentic-memories just answers "which triggers are due?"

### Input Validation (Creation)

| Check | Limit | Error |
|-------|-------|-------|
| Max triggers per user | 25 | "Limit reached: 25 active triggers max" |
| Cron too frequent | 60s min | "Cron too frequent: every Xs. Minimum: 60s" |
| Cron fires too often | 96/day max | "Cron would fire Xx/day. Max: 96" |
| Interval too short | 5 min | "Interval too short: Xm. Minimum: 5m" |
| One-time in past | future only | "One-time trigger must be in the future" |
| Missing required fields | varies | "trigger_schedule required for type 'cron'" |

### `/fire` Endpoint State Management

When Annie calls POST `/v1/intents/{id}/fire`:

1. **Always**: Update `last_checked = NOW()`
2. **If success**: Update `last_executed`, increment `execution_count`
3. **Calculate next_check**:
   - `success (cron)` → croniter.get_next()
   - `success (interval)` → NOW() + interval_minutes
   - `success (once)` → NULL + enabled=false
   - `success (price)` → NOW() + check_interval
   - `condition_not_met` → NOW() + 5 minutes
   - `gate_blocked` → NOW() + 5 minutes
   - `failed` → NOW() + 15 minutes
4. **Auto-disable** if max_executions reached or expires_at passed
5. **Log** to intent_executions table

---

## Stories Breakdown

### Story 5.1: Database Schema Migration

**Goal:** Create PostgreSQL tables for scheduled intents

**Acceptance Criteria:**
- [ ] Migration creates `scheduled_intents` table with all columns
- [ ] Migration creates `intent_executions` table
- [ ] Indexes created for efficient queries
- [ ] Constraints enforce valid trigger_type, action_type, priority
- [ ] Down migration drops tables cleanly

**Estimated Effort:** 2 hours

---

### Story 5.2: Pydantic Models

**Goal:** Create request/response models for intents API

**Acceptance Criteria:**
- [ ] `TriggerSchedule` model (cron, interval_minutes, datetime, check_interval_minutes)
- [ ] `TriggerCondition` model (ticker, operator, value, keywords, threshold_hours)
- [ ] `ScheduledIntentCreate` model
- [ ] `ScheduledIntentResponse` model
- [ ] `ScheduledIntentUpdate` model
- [ ] `IntentFireRequest` model
- [ ] `IntentFireResponse` model

**Estimated Effort:** 1 hour

---

### Story 5.3: Input Validation

**Goal:** Reject bad triggers at creation time

**Acceptance Criteria:**
- [ ] Validates max triggers per user (25)
- [ ] Validates cron minimum interval (60 seconds)
- [ ] Validates cron max daily fires (96)
- [ ] Validates interval minimum (5 minutes)
- [ ] Validates one-time is in future
- [ ] Validates required fields by trigger type
- [ ] Returns all validation errors in response

**Estimated Effort:** 2 hours

---

### Story 5.4: CRUD Endpoints

**Goal:** Implement basic CRUD for intents

**Acceptance Criteria:**
- [ ] `POST /v1/intents` - creates intent with initial next_check
- [ ] `GET /v1/intents?user_id=X` - lists with optional filters
- [ ] `GET /v1/intents/{id}` - gets single intent
- [ ] `PUT /v1/intents/{id}` - updates, recalculates next_check if schedule changes
- [ ] `DELETE /v1/intents/{id}` - deletes intent
- [ ] Langfuse tracing on all endpoints

**Estimated Effort:** 3 hours

---

### Story 5.5: Pending Endpoint

**Goal:** Implement `/pending` for Annie's worker

**Acceptance Criteria:**
- [ ] `GET /v1/intents/pending` returns due triggers
- [ ] Query: `WHERE enabled = true AND next_check <= NOW()`
- [ ] Optional `user_id` filter
- [ ] Ordered by `next_check ASC`
- [ ] Uses index for fast query

**Estimated Effort:** 1 hour

---

### Story 5.6: Fire Endpoint with State Management

**Goal:** Implement `/fire` that owns state transitions

**Acceptance Criteria:**
- [ ] Updates `last_checked` on every call
- [ ] Updates `last_executed`, `execution_count` on success
- [ ] Calculates `next_check` based on trigger type and result
- [ ] Disables one-time triggers after success
- [ ] Disables if max_executions reached
- [ ] Disables if expires_at passed
- [ ] Logs to intent_executions table
- [ ] Returns next_check and enabled status

**Estimated Effort:** 3 hours

---

### Story 5.7: Execution History Endpoint

**Goal:** Query access to execution history

**Acceptance Criteria:**
- [ ] `GET /v1/intents/{id}/history` returns executions
- [ ] Paginated with limit parameter
- [ ] Ordered by `executed_at DESC`
- [ ] Includes status, trigger_data, gate_result, timings

**Estimated Effort:** 1 hour

---

### Story 5.8: Next Check Calculation Logic

**Goal:** Accurate next_check calculations

**Acceptance Criteria:**
- [ ] `calculate_next_check()` for creation
- [ ] `calculate_next_check_after_fire()` for post-execution
- [ ] Handles all trigger types correctly
- [ ] Uses croniter for cron expressions
- [ ] Unit tests for each scenario

**Estimated Effort:** 2 hours

---

## Success Criteria

1. All endpoints functional with proper error handling
2. Validation prevents bad triggers at creation
3. State transitions correct - next_check calculated accurately
4. Execution history logged for all fire events
5. Langfuse traces for observability
6. Annie can integrate (endpoints match expected contract)

---

## Estimated Total Effort

| Story | Effort |
|-------|--------|
| 5.1 Database Schema | 2 hours |
| 5.2 Pydantic Models | 1 hour |
| 5.3 Input Validation | 2 hours |
| 5.4 CRUD Endpoints | 3 hours |
| 5.5 Pending Endpoint | 1 hour |
| 5.6 Fire Endpoint | 3 hours |
| 5.7 History Endpoint | 1 hour |
| 5.8 Next Check Logic | 2 hours |
| **Total** | **15 hours (~2 days)** |

---

## References

- [Annie Technical Research - Proactive AI Architecture](/home/ankit/dev/annie/docs/research-technical-2025-12-21.md)
