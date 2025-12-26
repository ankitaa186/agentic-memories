# Story 5.1: Database Schema Migration

Status: done

## Story

As a **system administrator**,
I want **PostgreSQL tables created for scheduled intents and execution history**,
so that **Annie's proactive triggers have durable, queryable storage with audit trail**.

## Acceptance Criteria

1. **AC1:** Migration creates `scheduled_intents` table with all columns:
   - Identity: `id` (UUID PK), `user_id`, `intent_name`, `description`
   - Trigger definition: `trigger_type`, `trigger_schedule` (JSONB), `trigger_condition` (JSONB)
   - Action config: `action_type`, `action_context`, `action_priority`
   - Scheduling state: `next_check`, `last_checked`, `last_executed`, `execution_count`
   - Execution results: `last_execution_status`, `last_execution_error`, `last_message_id`
   - Control: `enabled`, `expires_at`, `max_executions`
   - Audit: `created_at`, `updated_at`, `created_by`, `metadata` (JSONB)

2. **AC2:** Migration creates `intent_executions` table with:
   - `id` (UUID PK), `intent_id` (FK to scheduled_intents), `user_id`
   - `executed_at`, `trigger_type`, `trigger_data` (JSONB), `status`
   - `gate_result` (JSONB), `message_id`, `message_preview`
   - Timing: `evaluation_ms`, `generation_ms`, `delivery_ms`
   - `error_message`

3. **AC3:** All CHECK constraints enforced:
   - `trigger_type` IN ('cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news')
   - `action_type` IN ('notify', 'check_in', 'briefing', 'analysis', 'reminder')
   - `action_priority` IN ('low', 'normal', 'high', 'critical')
   - `status` IN ('success', 'failed', 'gate_blocked', 'condition_not_met')

4. **AC4:** All indexes created for efficient queries:
   - `idx_intents_user_enabled` on (user_id, enabled) WHERE enabled = true
   - `idx_intents_pending` on (next_check) WHERE enabled = true AND next_check IS NOT NULL
   - `idx_intents_type` on (user_id, trigger_type)
   - `idx_executions_intent` on (intent_id, executed_at DESC)
   - `idx_executions_user` on (user_id, executed_at DESC)

5. **AC5:** Down migration drops tables cleanly:
   - DROP TABLE intent_executions (has FK dependency)
   - DROP TABLE scheduled_intents
   - No orphaned data or dangling references

## Tasks / Subtasks

- [x] **Task 1: Create scheduled_intents migration** (AC: 1, 3, 4)
  - [x] 1.1 Create `migrations/postgres/017_scheduled_intents.up.sql`
  - [x] 1.2 Define all columns with appropriate types and defaults
  - [x] 1.3 Add CHECK constraints for trigger_type, action_type, action_priority
  - [x] 1.4 Create partial indexes for pending queries and user lookups
  - [x] 1.5 Add COMMENT statements for documentation

- [x] **Task 2: Create intent_executions migration** (AC: 2, 4)
  - [x] 2.1 Create `migrations/postgres/018_intent_executions.up.sql`
  - [x] 2.2 Define FK relationship to scheduled_intents with ON DELETE CASCADE
  - [x] 2.3 Add CHECK constraint for status values
  - [x] 2.4 Create indexes for intent and user lookups

- [x] **Task 3: Create down migrations** (AC: 5)
  - [x] 3.1 Create `migrations/postgres/017_scheduled_intents.down.sql`
  - [x] 3.2 Create `migrations/postgres/018_intent_executions.down.sql`
  - [x] 3.3 Ensure proper DROP order (executions before intents)

- [x] **Task 4: Verify migration execution** (AC: 1-5)
  - [x] 4.1 Run migrations against local PostgreSQL
  - [x] 4.2 Verify tables created with `\d scheduled_intents` and `\d intent_executions`
  - [x] 4.3 Verify indexes created with `\di`
  - [x] 4.4 Test down migration and re-up to confirm clean cycle
  - [x] 4.5 Insert sample data to verify constraints work

## Dev Notes

### Architecture Patterns

- Follow existing migration numbering pattern (001-016 used, start at 017)
- Use `gen_random_uuid()` for UUID PKs (PostgreSQL 13+ built-in)
- Use JSONB for flexible trigger_schedule and trigger_condition storage
- Use TIMESTAMPTZ for all timestamps (UTC storage)
- Add COMMENT statements for self-documenting schema

### Project Structure Notes

- Migration files location: `migrations/postgres/`
- Naming convention: `NNN_description.up.sql` and `NNN_description.down.sql`
- Existing migrations use `migrate.sh` script for execution
- No ORM - raw SQL migrations with psycopg for runtime access

### Testing Considerations

- Manual verification via psql commands
- Insert test data to verify CHECK constraints reject invalid values
- Verify FK cascade deletes executions when intent deleted
- Check index usage with EXPLAIN ANALYZE on pending query

### References

- [Source: docs/sprint-artifacts/tech-spec-epic-5.md#Data-Models-and-Contracts]
- [Source: docs/epic-5-scheduled-intents.md#Technical-Design]
- [Source: docs/architecture.md#Database-Schema-Design]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/5-1-database-schema-migration.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Discovered existing migrations go up to 016, corrected story to use 017/018
- Followed pattern from 009_user_profiles.up.sql for table structure
- Added extra indexes (idx_intents_user_id, idx_intents_created, idx_executions_status) beyond requirements

### Completion Notes List

- Created 4 migration files following existing project patterns
- scheduled_intents table: 24 columns with 5 CHECK constraints, 5 indexes
- intent_executions table: 14 columns with 4 CHECK constraints, 3 indexes
- FK cascade delete verified working (deleting intent removes executions)
- CHECK constraints verified (invalid trigger_type correctly rejected)
- All COMMENT statements added for schema documentation

### File List

- NEW: migrations/postgres/017_scheduled_intents.up.sql
- NEW: migrations/postgres/017_scheduled_intents.down.sql
- NEW: migrations/postgres/018_intent_executions.up.sql
- NEW: migrations/postgres/018_intent_executions.down.sql

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.5 (claude-opus-4-5-20251101)
**Review Date:** 2025-12-22
**Decision:** APPROVE ✅

### Acceptance Criteria Validation

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC1 | scheduled_intents table with all columns | ✅ PASS | `017_scheduled_intents.up.sql:7-42` - 24 columns in 7 groups |
| AC2 | intent_executions table with FK | ✅ PASS | `018_intent_executions.up.sql:5-35` - FK with CASCADE |
| AC3 | CHECK constraints enforced | ✅ PASS | `017:47-61`, `018:38-50` - trigger_type, action_type, priority, status |
| AC4 | All indexes created | ✅ PASS | `017:65-84`, `018:54-63` - 5 required + 3 bonus indexes |
| AC5 | Down migrations clean | ✅ PASS | Both down files exist with correct DROP order |

### Task Completion

- **Task 1:** 5/5 subtasks complete (scheduled_intents migration)
- **Task 2:** 4/4 subtasks complete (intent_executions migration)
- **Task 3:** 3/3 subtasks complete (down migrations)
- **Task 4:** 5/5 subtasks complete (verification)

### Code Quality Assessment

**Strengths:**
- Follows project patterns (IF NOT EXISTS, gen_random_uuid, TIMESTAMPTZ)
- Extra defensive constraints (execution_count >= 0, timing columns >= 0)
- Extra indexes beyond requirements for future query patterns
- Comprehensive COMMENT documentation (19 comments in scheduled_intents)

**Issues Found:** None

### Recommendation

Story meets all acceptance criteria. Implementation exceeds requirements with additional safeguards. Recommend moving to DONE status.

## Change Log

| Date | Change |
|------|--------|
| 2025-12-22 | Story drafted from Epic 5 tech spec |
| 2025-12-22 | Context file generated, status: ready-for-dev |
| 2025-12-22 | Implementation complete, all ACs verified, status: review |
| 2025-12-22 | Code review APPROVED, status: done |
