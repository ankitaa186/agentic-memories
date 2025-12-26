# Epic Technical Specification: Scheduled Intents API

Date: 2025-12-22
Author: Ankit
Epic ID: 5
Status: Draft

---

## Overview

Epic 5 creates a Scheduled Intents API in agentic-memories to store, manage, and track triggers for Annie's proactive messaging system. This API provides durable PostgreSQL storage for trigger definitions while Annie (the downstream AI companion) handles scheduling evaluation and message generation.

The architecture follows a clean separation of concerns: agentic-memories owns storage, state management, and audit trails, while Annie polls for pending triggers, evaluates conditions, and delivers messages. This approach leverages the existing PostgreSQL infrastructure, provides ACID durability, and enables queryability for user questions like "What NVDA alerts do I have?"

---

## Objectives and Scope

### In Scope

- **Database Schema:** Two new PostgreSQL tables (`scheduled_intents`, `intent_executions`)
- **REST API Endpoints:** CRUD operations, pending query, fire reporting, execution history
- **Pydantic Models:** Request/response validation for all endpoints
- **Input Validation:** Rate limiting triggers per user, cron frequency checks, future-only one-time triggers
- **State Management:** `next_check` calculation, auto-disable logic, execution counting
- **Audit Trail:** Full execution history with status, timing, and error tracking
- **Langfuse Tracing:** Observability on all endpoints

### Out of Scope

- **Condition Evaluation:** Annie evaluates price/silence/event conditions (not agentic-memories)
- **Message Generation:** Annie handles LLM-based message creation
- **Delivery:** Annie manages Telegram/notification delivery
- **Scheduler/Worker:** Annie runs the polling worker process
- **Authentication:** Deferred per MVP constraints (uses `user_id` parameter)

---

## System Architecture Alignment

### Component Placement

| Responsibility | Owner | Rationale |
|----------------|-------|-----------|
| Trigger storage & CRUD | agentic-memories | Existing PostgreSQL, ACID, audit trail |
| `next_check` calculation | agentic-memories | Centralized state management |
| Execution logging | agentic-memories | Single source of truth for history |
| Polling `/pending` | Annie worker | Decoupled scheduling logic |
| Condition evaluation | Annie | Access to yfinance, Redis, external APIs |
| LLM generation | Annie | Existing initiator mode |
| Delivery | Annie | Existing Telegram integration |

### Architecture Diagram

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
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ANNIE (Epic 13 - Downstream)                                   │
│  ├── Background worker polls /pending every 30s                 │
│  ├── Evaluates conditions (yfinance, Redis)                     │
│  ├── Subconscious gate (spam prevention)                        │
│  ├── LLM generation (initiator mode)                            │
│  └── Telegram delivery, then POST /fire                         │
└─────────────────────────────────────────────────────────────────┘
```

### Existing Patterns Followed

- **Router Structure:** New `src/routers/intents.py` following `profile.py` pattern (AD-008)
- **Service Layer:** `IntentsService` with dependency injection (AD-009)
- **Database Access:** Uses existing `get_timescale_conn()` psycopg pattern
- **Error Handling:** Graceful degradation with `{data, warnings, errors}` structure (AD-014)
- **Observability:** Langfuse tracing via existing `@observe` decorator

---

## Detailed Design

### Services and Modules

| Service/Module | Responsibility | Inputs | Outputs |
|----------------|----------------|--------|---------|
| `IntentsService` | CRUD operations, state management | User requests | Intent objects |
| `IntentValidationService` | Input validation, rate limiting | Create/update requests | Validation errors or None |
| `NextCheckCalculator` | Calculate next_check timestamps | Trigger config, fire result | datetime or None |
| `IntentsRouter` | HTTP endpoint handling | HTTP requests | HTTP responses |

### Data Models and Contracts

#### Table: `scheduled_intents`

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

#### Table: `intent_executions`

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

### APIs and Interfaces

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| POST | `/v1/intents` | Create trigger | `ScheduledIntentCreate` | `ScheduledIntentResponse` (201) |
| GET | `/v1/intents` | List triggers | `?user_id=X&trigger_type=Y` | `List[ScheduledIntentResponse]` |
| GET | `/v1/intents/pending` | Get due triggers | `?user_id=X` (optional) | `List[ScheduledIntentResponse]` |
| GET | `/v1/intents/{id}` | Get single trigger | - | `ScheduledIntentResponse` |
| PUT | `/v1/intents/{id}` | Update trigger | `ScheduledIntentUpdate` | `ScheduledIntentResponse` |
| DELETE | `/v1/intents/{id}` | Delete trigger | `?user_id=X` | `{"deleted": true}` |
| POST | `/v1/intents/{id}/fire` | Report execution | `IntentFireRequest` | `IntentFireResponse` |
| GET | `/v1/intents/{id}/history` | Get execution history | `?limit=50` | `List[IntentExecutionResponse]` |

#### Pydantic Models

```python
# Request Models
class TriggerSchedule(BaseModel):
    cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    datetime: Optional[datetime] = None
    check_interval_minutes: Optional[int] = Field(default=5, ge=5)

class TriggerCondition(BaseModel):
    ticker: Optional[str] = None
    operator: Optional[str] = None  # '<', '>', '<=', '>=', '=='
    value: Optional[float] = None
    keywords: Optional[List[str]] = None
    threshold_hours: Optional[int] = None

class ScheduledIntentCreate(BaseModel):
    user_id: str
    intent_name: str
    description: Optional[str] = None
    trigger_type: Literal['cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news']
    trigger_schedule: Optional[TriggerSchedule] = None
    trigger_condition: Optional[TriggerCondition] = None
    action_type: Literal['notify', 'check_in', 'briefing', 'analysis', 'reminder'] = 'notify'
    action_context: str
    action_priority: Literal['low', 'normal', 'high', 'critical'] = 'normal'
    expires_at: Optional[datetime] = None
    max_executions: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class IntentFireRequest(BaseModel):
    status: Literal['success', 'failed', 'gate_blocked', 'condition_not_met']
    trigger_data: Optional[Dict[str, Any]] = None
    gate_result: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    message_preview: Optional[str] = None
    evaluation_ms: Optional[int] = None
    generation_ms: Optional[int] = None
    delivery_ms: Optional[int] = None
    error_message: Optional[str] = None

# Response Models
class ScheduledIntentResponse(BaseModel):
    id: UUID
    user_id: str
    intent_name: str
    description: Optional[str]
    trigger_type: str
    trigger_schedule: Optional[Dict[str, Any]]
    trigger_condition: Optional[Dict[str, Any]]
    action_type: str
    action_context: str
    action_priority: str
    next_check: Optional[datetime]
    last_executed: Optional[datetime]
    execution_count: int
    enabled: bool
    expires_at: Optional[datetime]
    max_executions: Optional[int]
    created_at: datetime
    updated_at: datetime

class IntentFireResponse(BaseModel):
    intent_id: UUID
    status: str
    next_check: Optional[datetime]
    enabled: bool
    execution_count: int
```

### Workflows and Sequencing

#### Create Intent Flow

```
1. POST /v1/intents
   │
   ├─► Validate user trigger count (max 25)
   ├─► Validate trigger schedule (cron freq, interval min, once future)
   ├─► Calculate initial next_check
   ├─► Insert into scheduled_intents
   └─► Return ScheduledIntentResponse
```

#### Fire Intent Flow

```
1. POST /v1/intents/{id}/fire
   │
   ├─► Update last_checked = NOW()
   │
   ├─► If status == 'success':
   │   ├─► Update last_executed = NOW()
   │   ├─► Increment execution_count
   │   └─► Calculate next_check based on trigger_type
   │
   ├─► If status == 'condition_not_met' or 'gate_blocked':
   │   └─► Set next_check = NOW() + 5 minutes
   │
   ├─► If status == 'failed':
   │   └─► Set next_check = NOW() + 15 minutes
   │
   ├─► Check auto-disable conditions:
   │   ├─► One-time trigger after success → enabled = false, next_check = NULL
   │   ├─► max_executions reached → enabled = false
   │   └─► expires_at passed → enabled = false
   │
   ├─► Log to intent_executions table
   └─► Return IntentFireResponse with next_check and enabled status
```

#### Next Check Calculation Rules

| Trigger Type | After Success | After Condition Not Met | After Failed |
|--------------|---------------|-------------------------|--------------|
| cron | croniter.get_next() | NOW() + 5 min | NOW() + 15 min |
| interval | NOW() + interval_minutes | NOW() + 5 min | NOW() + 15 min |
| once | NULL + disable | N/A | NOW() + 15 min |
| price | NOW() + check_interval_minutes | NOW() + 5 min | NOW() + 15 min |
| silence | NOW() + threshold_hours | NOW() + 5 min | NOW() + 15 min |
| event | NULL (event-driven) | NOW() + 5 min | NOW() + 15 min |

---

## Non-Functional Requirements

### Performance

| Metric | Target | Rationale |
|--------|--------|-----------|
| POST /v1/intents latency | < 100ms | Simple insert with validation |
| GET /v1/intents/pending latency | < 50ms | Index-optimized query |
| POST /v1/intents/{id}/fire latency | < 100ms | Update + insert + calculation |
| Maximum triggers per user | 25 | Prevent abuse, reasonable for personal use |
| Polling interval (Annie) | 30 seconds | Balance between responsiveness and load |

### Security

- **No Authentication (MVP):** Relies on `user_id` parameter per existing system constraints
- **Input Validation:** All inputs validated via Pydantic with strict constraints
- **SQL Injection Prevention:** Parameterized queries via psycopg
- **Rate Limiting (trigger count):** Max 25 active triggers per user enforced at creation
- **Future Auth:** Will integrate with existing Cloudflare Access pattern post-MVP

### Reliability/Availability

- **Durability:** PostgreSQL ACID guarantees for all trigger state
- **Graceful Degradation:** If pending query fails, Annie retries next poll cycle
- **No Single Point of Failure:** Annie polling is idempotent (re-firing same trigger is safe)
- **State Recovery:** All state in PostgreSQL, survives restarts

### Observability

| Signal | Implementation |
|--------|----------------|
| Request tracing | Langfuse `@observe` decorator on all endpoints |
| Execution metrics | `intent_executions` table with timing columns |
| Error tracking | `error_message` field in executions table |
| Trigger counts | Query `scheduled_intents` GROUP BY user_id |
| Pending queue depth | Query `/pending` COUNT(*) |

---

## Dependencies and Integrations

### Existing Dependencies (No Changes)

```
fastapi==0.111.0      # API framework
pydantic==2.8.2       # Request/response validation
psycopg[binary]       # PostgreSQL driver
psycopg-pool==3.2.1   # Connection pooling
langfuse==2.36.0      # Observability
redis==5.0.6          # Caching (optional for future use)
```

### New Dependencies

```
croniter==2.0.1       # Cron expression parsing and next occurrence calculation
```

### Integration Points

| System | Integration | Direction |
|--------|-------------|-----------|
| PostgreSQL | Primary storage | Read/Write |
| Annie Worker | Polls `/pending`, calls `/fire` | Inbound API calls |
| Langfuse | Trace all API calls | Outbound telemetry |

---

## Acceptance Criteria (Authoritative)

### Story 5.1: Database Schema Migration
1. Migration creates `scheduled_intents` table with all columns and constraints
2. Migration creates `intent_executions` table with foreign key relationship
3. All indexes created for efficient queries
4. Down migration drops tables cleanly without orphaned data

### Story 5.2: Pydantic Models
1. `TriggerSchedule` model validates cron, interval_minutes, datetime, check_interval_minutes
2. `TriggerCondition` model validates ticker, operator, value, keywords, threshold_hours
3. `ScheduledIntentCreate` model enforces required fields and valid enums
4. `IntentFireRequest` model validates execution reporting fields
5. Response models serialize all database fields correctly

### Story 5.3: Input Validation
1. Rejects creation if user has 25+ active triggers (HTTP 400)
2. Rejects cron expressions firing more frequently than every 60 seconds
3. Rejects cron expressions that would fire more than 96 times per day
4. Rejects interval less than 5 minutes
5. Rejects one-time triggers with datetime in the past
6. Returns all validation errors in single response

### Story 5.4: CRUD Endpoints
1. POST `/v1/intents` creates intent with calculated next_check
2. GET `/v1/intents?user_id=X` lists all triggers for user
3. GET `/v1/intents/{id}` returns single intent or 404
4. PUT `/v1/intents/{id}` updates intent, recalculates next_check if schedule changed
5. DELETE `/v1/intents/{id}` removes intent (cascades to executions)
6. All endpoints have Langfuse tracing

### Story 5.5: Pending Endpoint
1. GET `/v1/intents/pending` returns triggers where `enabled=true AND next_check <= NOW()`
2. Results ordered by `next_check ASC`
3. Optional `user_id` filter works correctly
4. Uses index for sub-50ms query performance

### Story 5.6: Fire Endpoint with State Management
1. Updates `last_checked` on every call
2. Updates `last_executed` and `execution_count` on success
3. Calculates correct `next_check` based on trigger type and status
4. Disables one-time triggers after success
5. Disables triggers when max_executions reached
6. Disables triggers when expires_at passed
7. Logs execution to intent_executions table
8. Returns next_check and enabled in response

### Story 5.7: Execution History Endpoint
1. GET `/v1/intents/{id}/history` returns execution records
2. Paginated with `limit` parameter (default 50)
3. Ordered by `executed_at DESC`
4. Includes all timing and status fields

### Story 5.8: Next Check Calculation Logic
1. `calculate_initial_next_check()` sets correct value at creation
2. `calculate_next_check_after_fire()` handles all trigger types
3. Uses croniter for cron expression parsing
4. Handles timezone-aware datetimes correctly
5. Unit tests cover all trigger type × status combinations

---

## Traceability Mapping

| AC ID | Spec Section | Component(s) | Test Idea |
|-------|--------------|--------------|-----------|
| 5.1.1-4 | Data Models | migrations/*.sql | Migration up/down cycle test |
| 5.2.1-5 | Data Models | src/schemas/intents.py | Pydantic validation unit tests |
| 5.3.1-6 | APIs/Interfaces | IntentValidationService | Validation rejection tests |
| 5.4.1-6 | APIs/Interfaces | IntentsRouter, IntentsService | Integration tests per endpoint |
| 5.5.1-4 | APIs/Interfaces | IntentsRouter.get_pending | Query performance benchmark |
| 5.6.1-8 | Workflows | IntentsService.fire | State machine transition tests |
| 5.7.1-4 | APIs/Interfaces | IntentsRouter.get_history | Pagination and ordering tests |
| 5.8.1-5 | Workflows | NextCheckCalculator | Unit tests for each scenario |

---

## Risks, Assumptions, Open Questions

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Annie polling delays** | Triggers fire late | Monitor pending queue depth, alert if > 100 |
| **Croniter edge cases** | Invalid next_check | Wrap in try/except, disable on parse error |
| **Race conditions** | Double-firing | Annie worker single-threaded, idempotent fire |
| **Database growth** | Slow queries | Auto-archive executions older than 90 days |

### Assumptions

1. **Single Annie worker:** No need for distributed locking on pending triggers
2. **30-second poll interval:** Acceptable latency for all trigger types
3. **User honesty:** user_id parameter trusted (no auth in MVP)
4. **Timezone:** All timestamps stored in UTC, Annie handles user timezone conversion

### Open Questions

1. **Q:** Should we add a `/v1/intents/{id}/pause` endpoint for temporary disable?
   **A:** Deferred - users can use PUT to set enabled=false

2. **Q:** Should execution history have a retention policy?
   **A:** Recommend 90-day auto-archive, implement in future story

---

## Test Strategy Summary

### Unit Tests

- **NextCheckCalculator:** Test all trigger_type × status combinations
- **IntentValidationService:** Test all validation rules with edge cases
- **Pydantic Models:** Test serialization/deserialization

### Integration Tests

- **CRUD Lifecycle:** Create → Read → Update → Delete
- **Fire Workflow:** Create → Pending → Fire → Verify state changes
- **Validation Rejection:** Test all 400 error scenarios

### Performance Tests

- **Pending Query:** Benchmark with 1000 triggers, verify < 50ms
- **Concurrent Fire:** Test multiple fire requests on same trigger

### Manual Testing

- **Annie Integration:** End-to-end test with Annie worker polling
- **Croniter Expressions:** Test complex cron patterns (monthly, yearly)

---

## File Structure

```
src/
├── routers/
│   └── intents.py              # NEW: FastAPI router (8 endpoints)
├── services/
│   ├── intents_service.py      # NEW: CRUD + state management
│   ├── intent_validation.py    # NEW: Input validation
│   └── next_check_calculator.py # NEW: next_check logic
├── schemas/
│   └── intents.py              # NEW: Pydantic models
└── app.py                      # MODIFIED: Add intents router

migrations/
└── postgres/
    ├── 020_scheduled_intents.up.sql    # NEW
    ├── 020_scheduled_intents.down.sql  # NEW
    ├── 021_intent_executions.up.sql    # NEW
    └── 021_intent_executions.down.sql  # NEW

tests/
├── unit/
│   ├── test_next_check_calculator.py   # NEW
│   └── test_intent_validation.py       # NEW
└── integration/
    └── test_intents_api.py             # NEW
```

---

**END OF TECHNICAL SPECIFICATION**
