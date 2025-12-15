# Story 3.3: Portfolio Schema Simplification

Status: done

## Story

As a **system maintainer**,
I want **to simplify the portfolio_holdings table to only store public equity holdings**,
so that **the data model is focused, easier to maintain, and aligned with current usage patterns**.

## Background

Analysis of current production data shows:
- All 61 holdings are `public_equity` (no other asset types in use)
- Only 30% of records have shares/avg_price data
- Intent, position, time_horizon, and other trading metadata are not actively used by the API
- The complex schema adds maintenance overhead without providing value

## Acceptance Criteria

**AC1:** Simplified portfolio_holdings schema
- **Given** the current 19-column portfolio_holdings table
- **When** the migration is applied
- **Then** the table has only 8 columns:
  - `id` (uuid, PK)
  - `user_id` (varchar, required)
  - `ticker` (varchar, required, unique per user)
  - `asset_name` (varchar, optional)
  - `shares` (float, optional)
  - `avg_price` (float, optional)
  - `first_acquired` (timestamp)
  - `last_updated` (timestamp)

**AC2:** Columns removed
- **Given** the migration runs
- **When** checking the schema
- **Then** these columns are dropped:
  - `asset_type` (was always 'public_equity')
  - `current_price`, `current_value`, `cost_basis` (unused calculated fields)
  - `ownership_pct` (private equity only)
  - `position` (long/short - unused)
  - `intent` (hold/watch/etc - moved to separate concern)
  - `time_horizon`, `target_price`, `stop_loss` (trading metadata - unused)
  - `notes`, `source_memory_id` (unused)

**AC3:** Constraints simplified
- **Given** the migration runs
- **When** checking constraints
- **Then** these are removed:
  - `chk_asset_type` CHECK constraint
  - `chk_position` CHECK constraint
  - `chk_intent` CHECK constraint
  - `chk_time_horizon` CHECK constraint
- **And** `ticker` becomes NOT NULL (public equities require ticker)

**AC4:** Indexes cleaned up
- **Given** the migration runs
- **When** checking indexes
- **Then** these indexes are dropped:
  - `idx_holdings_user_asset_type` (no asset_type column)
  - `idx_holdings_user_intent` (no intent column)
  - `idx_holdings_user_asset_name_unique` (ticker-only model)
- **And** these indexes remain:
  - `portfolio_holdings_pkey` (primary key)
  - `idx_holdings_user_ticker_unique` (unique constraint)
  - `idx_holdings_last_updated` (for queries)

**AC5:** Existing data preserved
- **Given** 61 existing holdings in production
- **When** migration runs
- **Then** all records are preserved with their core data (id, user_id, ticker, asset_name, shares, avg_price, timestamps)
- **And** no data loss for essential fields

**AC6:** API responses updated
- **Given** the GET /v1/portfolio endpoint
- **When** fetching holdings
- **Then** response no longer includes `intent` field
- **And** response structure matches simplified schema

**AC7:** POST endpoint updated
- **Given** the POST /v1/portfolio/holding endpoint
- **When** creating/updating holdings
- **Then** request no longer accepts `intent` field
- **And** only accepts: user_id, ticker, asset_name, shares, avg_price

**AC8:** Service layer simplified
- **Given** the portfolio_service.py
- **When** processing holdings from memory extraction
- **Then** only extracts: ticker, asset_name, shares, avg_price
- **And** removes ownership gate logic (SPECULATIVE_INTENTS filtering)

## Tasks / Subtasks

- [x] **Task 1:** Create database migration (AC1, AC2, AC3, AC4, AC5)
  - [x] Create `migrations/postgres/015_simplify_portfolio.up.sql`
  - [x] Drop unused columns (12 columns)
  - [x] Drop unused constraints (4 constraints)
  - [x] Drop unused indexes (3 indexes)
  - [x] Alter ticker to NOT NULL
  - [x] Create `migrations/postgres/015_simplify_portfolio.down.sql` (rollback)
  - [x] Create `migrations/postgres/016_portfolio_unique_constraint_fix.up.sql` (fix partial index)

- [x] **Task 2:** Update service layer (AC8)
  - [x] Simplify `PortfolioHolding` dataclass in `portfolio_service.py`
  - [x] Remove: `VALID_INTENTS`, `SPECULATIVE_INTENTS`, `VALID_POSITIONS`, `VALID_ASSET_TYPES`, `VALID_TIME_HORIZONS`
  - [x] Simplify `upsert_holding_from_memory()` - remove field extraction for dropped columns
  - [x] Simplify `_upsert_single_holding()` - simplify INSERT/UPDATE queries
  - [x] Remove ownership gate logic (speculative intent filtering)
  - [x] Keep: `normalize_ticker()`, `validate_positive_float()`

- [x] **Task 3:** Update schema models (AC6, AC7)
  - [x] Simplify `PortfolioHolding` in `src/schemas.py`
  - [x] Simplify `FinanceGoal` - remove intent, time_horizon, target_price, risk_tolerance, concern
  - [x] Simplify `PortfolioSummaryResponse` - remove counts_by_asset_type

- [x] **Task 4:** Update API layer (AC6, AC7)
  - [x] Verify `src/routers/portfolio.py` models are correct (already simplified)
  - [x] Clean up any remaining intent references (removed asset_type from INSERT)
  - [x] Update docstrings

- [x] **Task 5:** Update prompts (AC8)
  - [x] Simplify portfolio extraction schema in `src/services/prompts.py`
  - [x] Remove intent detection logic from extraction prompts
  - [x] Update examples to only show ticker, shares, avg_price

- [x] **Task 6:** Update tests
  - [x] Remove intent-related tests from `tests/unit/test_portfolio_api.py`
  - [x] Update mock data to match new schema (6-tuple instead of 7-tuple)
  - [x] Update assertions to not check intent field
  - [x] Tests removed: `test_post_holding_invalid_intent`, `test_post_holding_default_intent`, `test_post_holding_all_valid_intents`, `test_get_portfolio_multiple_intents`

- [x] **Task 7:** Run migration and verify
  - [x] Apply migration to production database
  - [x] Verify schema changes (8 columns, proper unique constraint)
  - [x] Run integration tests (17 unit tests pass, curl tests pass)
  - [x] Verify existing data integrity (61 records preserved)

## Dev Notes

### Files to Modify

| File | Change Type | Est. Lines |
|------|-------------|------------|
| `migrations/postgres/015_simplify_portfolio.up.sql` | NEW | ~40 |
| `migrations/postgres/015_simplify_portfolio.down.sql` | NEW | ~60 |
| `src/services/portfolio_service.py` | MAJOR | ~200 |
| `src/schemas.py` | MODERATE | ~30 |
| `src/routers/portfolio.py` | MINOR (cleanup) | ~10 |
| `src/services/prompts.py` | MODERATE | ~50 |
| `tests/unit/test_portfolio_api.py` | MAJOR | ~200 |
| **Total** | | **~590** |

### Current Schema (19 columns)

```sql
portfolio_holdings (
    id, user_id, ticker, asset_name, asset_type,
    shares, avg_price, current_price, current_value, cost_basis,
    ownership_pct, position, intent, time_horizon,
    target_price, stop_loss, notes,
    first_acquired, last_updated, source_memory_id
)
```

### Target Schema (8 columns)

```sql
portfolio_holdings (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    ticker VARCHAR(16) NOT NULL,
    asset_name VARCHAR(256),
    shares FLOAT,
    avg_price FLOAT,
    first_acquired TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, ticker)
)
```

### Migration Strategy

1. **Safe column drops** - All dropped columns either have no data or data we're intentionally discarding
2. **Ticker NOT NULL** - All 61 existing records have tickers, so this is safe
3. **Rollback available** - Down migration can recreate columns (without data)

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| Data loss | Only dropping unused columns; core data preserved |
| Breaking API clients | API already updated in Story 3.2 hotfix |
| Ingestion breaks | Service layer update handles gracefully |

### Dependencies

- Story 3.1 (GET endpoint) - done
- Story 3.2 (POST endpoint) - done
- Story 3.2 hotfix (intent removal from API) - done

### Future Consideration

A separate `ticker_research` or `watchlist` table could be created later to store:
- Intent (wants-to-buy, wants-to-sell, watch)
- Target prices, stop losses
- Notes and research
- Time horizons

This keeps holdings (what you own) separate from research (what you're thinking about).

## References

- [Epic 3: Portfolio Direct CRUD API](../epic-portfolio-crud-api.md)
- [Story 3.1: Portfolio GET Endpoint](./3-1-portfolio-get-endpoint.md)
- [Story 3.2: Portfolio POST Endpoint](./3-2-portfolio-post-endpoint.md)
- [Original Migration: migrations/postgres/005_portfolio_holdings.up.sql]

---

**Story Created:** 2025-12-14
**Epic:** 3 (Portfolio Direct CRUD API)
**Depends On:** Story 3.1, Story 3.2

---

## Senior Developer Review (AI)

**Reviewer:** Ankit
**Date:** 2025-12-15
**Outcome:** APPROVE

### Summary

Story 3.3 successfully simplifies the portfolio_holdings table from 19 columns to 8 columns. All acceptance criteria are met, all tasks verified complete, and the implementation follows the established patterns. The migration was applied cleanly with data integrity preserved (62 records verified). Unit tests (17 tests) and integration tests all pass.

### Key Findings

No HIGH or MEDIUM severity issues found.

**LOW Severity:**
- Note: The unique constraint was renamed from `idx_holdings_user_ticker_unique` (partial index) to `portfolio_holdings_user_ticker_unique` (regular constraint) via migration 016. This is correct and necessary for ON CONFLICT to work.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Simplified schema (8 columns) | IMPLEMENTED | `\d portfolio_holdings` shows: id, user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated |
| AC2 | 12 columns removed | IMPLEMENTED | `migrations/postgres/015_simplify_portfolio.up.sql:17-29` drops all specified columns |
| AC3 | Constraints simplified | IMPLEMENTED | Migration drops 4 CHECK constraints (:11-14), ticker set NOT NULL (:34) |
| AC4 | Indexes cleaned up | IMPLEMENTED | 3 indexes dropped (:6-8), pkey + unique + last_updated remain |
| AC5 | Data preserved | IMPLEMENTED | `SELECT COUNT(*) = 62` (61 original + 1 test record) |
| AC6 | API responses updated | IMPLEMENTED | No `intent` in `src/routers/portfolio.py`, verified via grep |
| AC7 | POST endpoint updated | IMPLEMENTED | `src/routers/portfolio.py:173-190` - INSERT has 5 columns, no intent |
| AC8 | Service layer simplified | IMPLEMENTED | `src/services/portfolio_service.py:65-73` - PortfolioHolding has 6 fields only |

**Summary:** 8 of 8 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| Task 1: Create database migration | [x] | VERIFIED | `migrations/postgres/015_simplify_portfolio.up.sql`, `016_portfolio_unique_constraint_fix.up.sql` exist |
| Task 2: Update service layer | [x] | VERIFIED | `portfolio_service.py:1-6` docstring updated, no VALID_INTENTS constants |
| Task 3: Update schema models | [x] | VERIFIED | No `intent` in `src/schemas.py` |
| Task 4: Update API layer | [x] | VERIFIED | `src/routers/portfolio.py:4` docstring updated |
| Task 5: Update prompts | [x] | VERIFIED | No `"intent":` in `src/services/prompts.py` |
| Task 6: Update tests | [x] | VERIFIED | `tests/unit/test_portfolio_api.py:80-81` asserts intent not in response |
| Task 7: Run migration and verify | [x] | VERIFIED | Schema shows 8 columns, 17 unit tests pass, curl tests pass |

**Summary:** 7 of 7 completed tasks verified, 0 questionable, 0 false completions

### Test Coverage and Gaps

- **Unit Tests:** 17 tests in `test_portfolio_api.py` - all pass
- **Integration Tests:** GET and POST endpoints verified via curl
- **Coverage:** All ACs have corresponding test coverage
- **Gaps:** None identified

### Architectural Alignment

- Schema simplification aligns with "public equities only" scope
- ON CONFLICT upsert pattern correctly implemented with regular unique constraint
- Service layer simplified as documented in context file
- Migration 016 properly fixes partial index issue for ON CONFLICT compatibility

### Security Notes

No security concerns. No sensitive data handling changes.

### Best-Practices and References

- [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
- ON CONFLICT requires regular unique constraint, not partial index with WHERE clause

### Action Items

**Code Changes Required:**
- None

**Advisory Notes:**
- Note: Consider documenting the future `ticker_research`/`watchlist` table design in architecture docs when needed
- Note: Migration 016 was added to fix partial index → regular constraint for ON CONFLICT compatibility
