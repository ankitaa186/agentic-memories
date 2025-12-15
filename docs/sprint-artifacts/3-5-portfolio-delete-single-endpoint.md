# Story 3.5: Portfolio DELETE Endpoint (Remove Single Holding)

Status: review

## Story

As a **chatbot (Annie)**,
I want **to remove a specific stock holding via API**,
so that **users can remove stocks they no longer hold**.

## Acceptance Criteria

**AC1:** DELETE endpoint removes existing holding
- **Given** an existing holding for user_id + ticker
- **When** calling `DELETE /v1/portfolio/holding/{ticker}?user_id={uuid}`
- **Then** the system deletes the holding from the database
- **And** returns confirmation with 200 status

**AC2:** Ticker normalization in path
- **Given** a request with lowercase ticker in path (e.g., `/holding/aapl`)
- **When** processing the request
- **Then** ticker is normalized to uppercase ("AAPL") for database lookup
- **And** delete succeeds if holding exists for normalized ticker

**AC3:** Returns 404 for non-existent holding
- **Given** no holding exists for user_id + ticker
- **When** calling DELETE endpoint
- **Then** the system returns 404 Not Found
- **And** error message indicates holding not found

**AC4:** Returns confirmation response
- **Given** a successful delete
- **When** the response is returned
- **Then** response includes: `{"deleted": true, "ticker": "AAPL"}`
- **And** response confirms which ticker was deleted

**AC5:** Request validation
- **Given** a request with missing required query parameter (user_id)
- **When** calling DELETE endpoint
- **Then** the system returns 422 Unprocessable Entity
- **And** error message indicates missing parameter

**AC6:** Invalid ticker format returns 400
- **Given** a request with invalid ticker format in path
- **When** calling DELETE endpoint
- **Then** the system returns 400 Bad Request
- **And** error message indicates invalid ticker format

## Tasks / Subtasks

- [x] **Task 1:** Create Pydantic response model (AC4)
  - [x] Create `HoldingDeleteResponse` model with fields: deleted (bool), ticker (str)
  - [x] Note: user_id comes from query parameter, ticker from path

- [x] **Task 2:** Implement ticker normalization for path parameter (AC2, AC6)
  - [x] Use existing `normalize_ticker()` from `portfolio_service.py`
  - [x] Validate ticker format (alphanumeric + dots, 1-10 chars)
  - [x] Return 400 if ticker format is invalid

- [x] **Task 3:** Implement DELETE endpoint (AC1, AC3, AC4, AC5)
  - [x] Add `@router.delete("/holding/{ticker}")` endpoint
  - [x] Accept ticker from path, user_id from query parameter
  - [x] Used DELETE RETURNING pattern (more efficient than SELECT+DELETE)
  - [x] If RETURNING empty, return 404
  - [x] If exists, DELETE the record
  - [x] Return confirmation response with 200 status

- [x] **Task 4:** Write unit tests (AC1, AC2, AC3, AC4, AC5, AC6)
  - [x] Test DELETE removes existing holding successfully
  - [x] Test ticker normalization (lowercase path → uppercase lookup)
  - [x] Test 404 for non-existent holding
  - [x] Test response includes deleted=true and ticker
  - [x] Test missing user_id returns 422
  - [x] Test invalid ticker format returns 400
  - [x] Test dotted tickers like BRK.B
  - [x] Test database unavailable returns 500
  - [x] Test dict cursor format (psycopg3 compatibility)

## Dev Notes

### Architecture Patterns

- **Router Pattern:** Extend `src/routers/portfolio.py` from Stories 3.1-3.4
- **Database Connection:** Use existing `get_timescale_conn()` / `release_timescale_conn()` pattern
- **Validation:** Use existing `normalize_ticker()` from `src/services/portfolio_service.py`

### Database Operation

Two-step pattern (SELECT then DELETE) to properly handle 404:

```sql
-- Step 1: Check if holding exists
SELECT id FROM portfolio_holdings WHERE user_id = %s AND ticker = %s;

-- Step 2: If exists, delete
DELETE FROM portfolio_holdings WHERE user_id = %s AND ticker = %s;
```

**Note:** Could also use single DELETE with RETURNING to check if row was deleted:

```sql
DELETE FROM portfolio_holdings
WHERE user_id = %s AND ticker = %s
RETURNING ticker;
```

If RETURNING returns nothing, the holding didn't exist (404).

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

**Key constraint:** Unique on `(user_id, ticker)`

### Difference from PUT Endpoint

| Aspect | PUT (Story 3.4) | DELETE (Story 3.5) |
|--------|-----------------|-------------------|
| user_id source | Request body | Query parameter |
| Ticker source | URL path parameter | URL path parameter |
| Operation | UPDATE | DELETE |
| Response | Updated holding | Confirmation |

### Learnings from Previous Story

**From Story 3-4-portfolio-put-endpoint (Status: done)**

- **New Models Created:** `UpdateHoldingRequest`, `HoldingUpdateResponse` - follow similar pattern for DELETE response
- **Architectural Pattern:** Two-step SELECT+UPDATE worked well, use similar SELECT+DELETE or DELETE RETURNING
- **Ticker Normalization:** Use `normalize_ticker()` which returns `None` for invalid format - return 400
- **Connection Pattern:** try/except/finally with rollback on error, release_timescale_conn in finally
- **psycopg3 Compatibility:** Handle both dict and tuple cursor results
- **Review Finding:** PUT returns 200 (success) - DELETE should also return 200 for success

[Source: docs/sprint-artifacts/3-4-portfolio-put-endpoint.md#Dev-Agent-Record]

### References

- [Source: docs/epic-portfolio-crud-api.md#Story-3.4 (DELETE single endpoint)]
- [Source: docs/epic-portfolio-crud-api.md#FR-PC4]
- [Source: src/services/portfolio_service.py - normalize_ticker]
- [Source: src/routers/portfolio.py - Existing GET/POST/PUT endpoint patterns]
- [Source: docs/sprint-artifacts/3-4-portfolio-put-endpoint.md - PUT endpoint learnings]

---

**Story Created:** 2025-12-15
**Epic:** 3 (Portfolio Direct CRUD API)
**Depends On:** Story 3.1 (GET - done), Story 3.2 (POST - done), Story 3.3 (Schema - done), Story 3.4 (PUT - done)

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/3-5-portfolio-delete-single-endpoint.context.xml`

### File List

| File | Change Type | Description |
|------|-------------|-------------|
| `src/routers/portfolio.py` | Modified | Added `HoldingDeleteResponse` model and DELETE endpoint (lines 81-85, 373-448) |
| `tests/unit/test_portfolio_api.py` | Modified | Added 9 unit tests for DELETE endpoint (test_delete_holding_*) |

### Completion Notes

**Implementation Date:** 2025-12-14

**Approach:**
- Used DELETE RETURNING pattern for efficiency (single query instead of SELECT+DELETE)
- user_id from query parameter (different from PUT which uses request body)
- Ticker from path parameter, normalized to uppercase via `normalize_ticker()`
- Returns `{"deleted": true, "ticker": "AAPL"}` on success (200)
- Returns 404 if holding doesn't exist, 400 for invalid ticker, 422 for missing user_id

**Test Results:**
- All 38 portfolio API tests passing (9 new DELETE tests + 29 existing)
- Tests cover: AC1-AC6, database unavailable, dotted tickers, psycopg3 dict cursor format

**Key Implementation Details:**
- `HoldingDeleteResponse(BaseModel)`: deleted (bool), ticker (str)
- DELETE RETURNING pattern: If RETURNING returns nothing, holding didn't exist (404)
- Handles both dict and tuple cursor results for psycopg3 compatibility
- try/except/finally pattern with rollback on error, release_timescale_conn in finally
