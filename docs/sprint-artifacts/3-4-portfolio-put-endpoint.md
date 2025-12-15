# Story 3.4: Portfolio PUT Endpoint (Update Holding)

Status: done

## Story

As a **chatbot (Annie)**,
I want **to update an existing stock holding via API**,
so that **users can correct their portfolio data through me**.

## Acceptance Criteria

**AC1:** PUT endpoint updates existing holding
- **Given** an existing holding for user_id + ticker
- **When** calling `PUT /v1/portfolio/holding/{ticker}` with body:
  ```json
  {
    "user_id": "uuid",
    "asset_name": "Apple Inc.",
    "shares": 150.0,
    "avg_price": 155.00
  }
  ```
- **Then** the system updates the existing holding
- **And** returns the updated holding with 200 status

**AC2:** Ticker normalization in path
- **Given** a request with lowercase ticker in path (e.g., `/holding/aapl`)
- **When** processing the request
- **Then** ticker is normalized to uppercase ("AAPL") for database lookup
- **And** update succeeds if holding exists for normalized ticker

**AC3:** Partial updates supported
- **Given** an existing holding
- **When** calling PUT with only some fields (e.g., only `shares`)
- **Then** only provided fields are updated
- **And** other fields retain their existing values (COALESCE pattern)

**AC4:** Returns 404 for non-existent holding
- **Given** no holding exists for user_id + ticker
- **When** calling PUT endpoint
- **Then** the system returns 404 Not Found
- **And** error message indicates holding not found

**AC5:** Request validation
- **Given** a request with missing required field (user_id)
- **When** calling PUT endpoint
- **Then** the system returns 422 Unprocessable Entity
- **And** error message indicates missing field

**AC6:** Returns updated holding data
- **Given** a successful update
- **When** the response is returned
- **Then** response includes: ticker, asset_name, shares, avg_price, first_acquired, last_updated
- **And** `last_updated` timestamp reflects the update time

## Tasks / Subtasks

- [x] **Task 1:** Create Pydantic request model (AC1, AC5)
  - [x] Create `UpdateHoldingRequest` model with fields: user_id (required), asset_name (optional), shares (optional), avg_price (optional)
  - [x] Note: ticker comes from path parameter, not body

- [x] **Task 2:** Implement ticker normalization for path parameter (AC2)
  - [x] Use existing `normalize_ticker()` from `portfolio_service.py`
  - [x] Validate ticker format (alphanumeric + dots, 1-10 chars)
  - [x] Return 400 if ticker format is invalid

- [x] **Task 3:** Implement PUT endpoint (AC1, AC3, AC4, AC6)
  - [x] Add `@router.put("/holding/{ticker}")` endpoint
  - [x] Accept ticker from path, `UpdateHoldingRequest` from body
  - [x] Check if holding exists first (SELECT query)
  - [x] If not exists, return 404
  - [x] If exists, UPDATE with COALESCE for partial updates
  - [x] Return updated holding with 200 status

- [x] **Task 4:** Write unit tests (AC1, AC2, AC3, AC4, AC5, AC6)
  - [x] Test PUT updates existing holding successfully
  - [x] Test ticker normalization (lowercase path → uppercase lookup)
  - [x] Test partial update (only shares, only avg_price, etc.)
  - [x] Test 404 for non-existent holding
  - [x] Test missing user_id returns 422
  - [x] Test response includes all expected fields

## Dev Notes

### Architecture Patterns

- **Router Pattern:** Extend `src/routers/portfolio.py` from Story 3.1/3.2
- **Database Connection:** Use existing `get_timescale_conn()` / `release_timescale_conn()` pattern
- **Validation:** Use existing `normalize_ticker()` from `src/services/portfolio_service.py`

### Database Operation

Two-step pattern (SELECT then UPDATE) to properly handle 404:

```sql
-- Step 1: Check if holding exists
SELECT id FROM portfolio_holdings WHERE user_id = %s AND ticker = %s;

-- Step 2: If exists, update with COALESCE for partial updates
UPDATE portfolio_holdings
SET
    asset_name = COALESCE(%s, asset_name),
    shares = COALESCE(%s, shares),
    avg_price = COALESCE(%s, avg_price),
    last_updated = NOW()
WHERE user_id = %s AND ticker = %s
RETURNING ticker, asset_name, shares, avg_price, first_acquired, last_updated;
```

### Simplified Schema (Story 3.3)

After Story 3.3 schema simplification, `portfolio_holdings` has only 8 columns:
- `id` (uuid, PK)
- `user_id` (varchar, required)
- `ticker` (varchar, required, NOT NULL)
- `asset_name` (varchar, optional)
- `shares` (float, optional)
- `avg_price` (float, optional)
- `first_acquired` (timestamp)
- `last_updated` (timestamp)

**Key changes from original epic:**
- No `intent` field (removed in Story 3.3)
- Unique constraint is `(user_id, ticker)` - NOT `(user_id, ticker, intent)`
- Regular constraint (not partial index) - works with ON CONFLICT

### Difference from POST Endpoint

| Aspect | POST (Story 3.2) | PUT (Story 3.4) |
|--------|------------------|-----------------|
| Behavior | UPSERT (create or update) | Update only |
| Missing holding | Creates new | Returns 404 |
| Status codes | 201 (create) or 200 (update) | 200 (success) or 404 |
| Ticker source | Request body | URL path parameter |

### Learnings from Previous Stories

**From Story 3.1 (GET):**
- Use `get_timescale_conn()` / `release_timescale_conn()` pattern
- Handle both dict and tuple cursor results for psycopg3 compatibility
- Column names: `first_acquired`, `last_updated` (not created_at/updated_at)

**From Story 3.2 (POST):**
- `normalize_ticker()` returns `None` for invalid format - return 400
- Use parameterized queries (%s) to prevent SQL injection
- Proper try/except/finally for connection cleanup with rollback on error

**From Story 3.3 (Schema Simplification):**
- No `intent` field - don't include in queries
- Unique constraint is `portfolio_holdings_user_ticker_unique` (user_id, ticker)
- 8 columns only in simplified schema

### References

- [Source: docs/epic-portfolio-crud-api.md#Story-3.3 (PUT endpoint)]
- [Source: docs/epic-portfolio-crud-api.md#FR-PC3]
- [Source: src/services/portfolio_service.py - normalize_ticker]
- [Source: src/routers/portfolio.py - Existing GET/POST endpoint patterns]
- [Source: docs/sprint-artifacts/3-3-portfolio-simplification.md - Schema simplification learnings]

---

**Story Created:** 2025-12-14
**Epic:** 3 (Portfolio Direct CRUD API)
**Depends On:** Story 3.1 (GET - done), Story 3.2 (POST - done), Story 3.3 (Schema Simplification - done)

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/3-4-portfolio-put-endpoint.context.xml`

### File List

| File | Change Type | Description |
|------|-------------|-------------|
| `src/routers/portfolio.py` | MODIFIED | Added UpdateHoldingRequest, HoldingUpdateResponse models and PUT endpoint |
| `tests/unit/test_portfolio_api.py` | MODIFIED | Added 12 unit tests for PUT endpoint |

### Completion Notes

**Implementation Summary:**
- Added `PUT /v1/portfolio/holding/{ticker}` endpoint for updating existing holdings
- Two-step pattern: SELECT to check existence, UPDATE with COALESCE for partial updates
- Returns 404 if holding doesn't exist (unlike POST which creates)
- Ticker normalization via `normalize_ticker()` for path parameter
- Supports partial updates - only provided fields are updated, others preserved

**Tests Added (12 new tests):**
- test_put_holding_updates_existing (AC1)
- test_put_holding_ticker_normalization (AC2)
- test_put_holding_invalid_ticker_format (AC2)
- test_put_holding_not_found (AC4)
- test_put_holding_missing_user_id (AC5)
- test_put_holding_partial_update_shares_only (AC3)
- test_put_holding_partial_update_avg_price_only (AC3)
- test_put_holding_partial_update_asset_name_only (AC3)
- test_put_holding_response_includes_all_fields (AC6)
- test_put_holding_dict_cursor_format (AC6)
- test_put_holding_database_unavailable
- test_put_holding_dotted_ticker

**Test Results:**
- 29 total tests pass (17 existing + 12 new)
- Integration test verified via curl (POST create → PUT update → GET verify)

### Change Log

| Date | Change |
|------|--------|
| 2025-12-15 | Story implementation complete - all 4 tasks done, 12 unit tests added |

---

## Senior Developer Review (AI)

**Reviewer:** Ankit
**Date:** 2025-12-15
**Outcome:** APPROVE

### Summary

Story 3.4 successfully implements the PUT endpoint for updating existing portfolio holdings. All 6 acceptance criteria are met, all 4 tasks are verified complete, and the implementation follows established patterns from Stories 3.1-3.3. The 12 new unit tests provide comprehensive coverage including edge cases. Integration testing via curl confirms the endpoint works correctly with the production database.

### Key Findings

No HIGH or MEDIUM severity issues found.

**LOW Severity:**
- None identified

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | PUT endpoint updates existing holding | IMPLEMENTED | `portfolio.py:264-352` - `@router.put("/holding/{ticker}")` with UPDATE + RETURNING |
| AC2 | Ticker normalization in path | IMPLEMENTED | `portfolio.py:276-282` - `normalize_ticker()` on path param, 400 for invalid format |
| AC3 | Partial updates supported | IMPLEMENTED | `portfolio.py:308-316` - COALESCE pattern for asset_name, shares, avg_price |
| AC4 | Returns 404 for non-existent holding | IMPLEMENTED | `portfolio.py:293-305` - SELECT first, HTTPException(404) if None |
| AC5 | Request validation | IMPLEMENTED | `portfolio.py:51-56` - `UpdateHoldingRequest` with required user_id, Pydantic returns 422 |
| AC6 | Returns updated holding data | IMPLEMENTED | `portfolio.py:329-347` - Returns all 6 fields including timestamps |

**Summary:** 6 of 6 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| Task 1: Create Pydantic request model | [x] | VERIFIED | `portfolio.py:51-56` - `UpdateHoldingRequest(user_id: str, asset_name: Optional, shares: Optional, avg_price: Optional)` |
| Task 2: Implement ticker normalization | [x] | VERIFIED | `portfolio.py:276-282` - Uses `normalize_ticker()`, returns 400 Bad Request for invalid format |
| Task 3: Implement PUT endpoint | [x] | VERIFIED | `portfolio.py:264-364` - Full implementation with two-step SELECT+UPDATE pattern |
| Task 4: Write unit tests | [x] | VERIFIED | `test_portfolio_api.py:505-821` - 12 comprehensive tests covering all ACs |

**Summary:** 4 of 4 completed tasks verified, 0 questionable, 0 false completions

### Test Coverage and Gaps

- **Unit Tests:** 12 new tests for PUT endpoint (29 total in file)
- **Tests pass:** All 29 tests pass
- **Integration Tests:** Verified via curl (POST create → PUT update → GET verify)
- **Coverage by AC:**
  - AC1: test_put_holding_updates_existing
  - AC2: test_put_holding_ticker_normalization, test_put_holding_invalid_ticker_format
  - AC3: test_put_holding_partial_update_shares_only, test_put_holding_partial_update_avg_price_only, test_put_holding_partial_update_asset_name_only
  - AC4: test_put_holding_not_found
  - AC5: test_put_holding_missing_user_id
  - AC6: test_put_holding_response_includes_all_fields, test_put_holding_dict_cursor_format
  - Extra: test_put_holding_database_unavailable, test_put_holding_dotted_ticker
- **Gaps:** None identified

### Architectural Alignment

- Follows FastAPI router pattern from Stories 3.1/3.2
- Uses same database connection pattern (`get_timescale_conn`/`release_timescale_conn`)
- Implements two-step SELECT+UPDATE pattern (differs from POST's UPSERT, appropriate for 404 semantics)
- COALESCE pattern for partial updates matches POST behavior
- Handles both dict and tuple cursor results (psycopg3 compatibility)
- Proper try/except/finally with rollback on error

### Security Notes

- No SQL injection risk (parameterized queries)
- Input validation via Pydantic
- No authentication (per MVP constraints)

### Best-Practices and References

- [FastAPI Path Parameters](https://fastapi.tiangolo.com/tutorial/path-params/)
- [PostgreSQL UPDATE with COALESCE](https://www.postgresql.org/docs/current/functions-conditional.html)

### Action Items

**Code Changes Required:**
- None

**Advisory Notes:**
- PUT returns 200 (update success) while POST returns 201 (create) or 200 (update) - this is correct REST semantics
- Consider adding OpenAPI examples to endpoint docstrings in future iteration
