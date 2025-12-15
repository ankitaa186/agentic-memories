# Story 3.3: Portfolio Schema Simplification

Status: ready-for-dev

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

- [ ] **Task 1:** Create database migration (AC1, AC2, AC3, AC4, AC5)
  - [ ] Create `migrations/postgres/015_simplify_portfolio.up.sql`
  - [ ] Drop unused columns (11 columns)
  - [ ] Drop unused constraints (4 constraints)
  - [ ] Drop unused indexes (3 indexes)
  - [ ] Alter ticker to NOT NULL
  - [ ] Create `migrations/postgres/015_simplify_portfolio.down.sql` (rollback)

- [ ] **Task 2:** Update service layer (AC8)
  - [ ] Simplify `PortfolioHolding` dataclass in `portfolio_service.py`
  - [ ] Remove: `VALID_INTENTS`, `SPECULATIVE_INTENTS`, `VALID_POSITIONS`, `VALID_ASSET_TYPES`, `VALID_TIME_HORIZONS`
  - [ ] Simplify `upsert_holding_from_memory()` - remove field extraction for dropped columns
  - [ ] Simplify `_upsert_single_holding()` - simplify INSERT/UPDATE queries
  - [ ] Remove ownership gate logic (speculative intent filtering)
  - [ ] Keep: `normalize_ticker()`, `validate_positive_float()`

- [ ] **Task 3:** Update schema models (AC6, AC7)
  - [ ] Simplify `PortfolioHolding` in `src/schemas.py`
  - [ ] Simplify `FinanceGoal` - remove intent, time_horizon, target_price, risk_tolerance, concern
  - [ ] Simplify `PortfolioSummaryResponse` - remove counts_by_asset_type

- [ ] **Task 4:** Update API layer (AC6, AC7)
  - [ ] Verify `src/routers/portfolio.py` models are correct (already simplified)
  - [ ] Clean up any remaining intent references
  - [ ] Update docstrings

- [ ] **Task 5:** Update prompts (AC8)
  - [ ] Simplify portfolio extraction schema in `src/services/prompts.py`
  - [ ] Remove intent detection logic from extraction prompts
  - [ ] Update examples to only show ticker, shares, avg_price

- [ ] **Task 6:** Update tests
  - [ ] Remove intent-related tests from `tests/unit/test_portfolio_api.py`
  - [ ] Update mock data to match new schema (6-tuple instead of 7-tuple)
  - [ ] Update assertions to not check intent field
  - [ ] Tests to remove: `test_post_holding_invalid_intent`, `test_post_holding_default_intent`, `test_post_holding_all_valid_intents`, `test_get_portfolio_multiple_intents`

- [ ] **Task 7:** Run migration and verify
  - [ ] Apply migration to production database
  - [ ] Verify schema changes
  - [ ] Run integration tests
  - [ ] Verify existing data integrity

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
