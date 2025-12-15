# Story 3.6: Portfolio DELETE All Endpoint (Clear Entire Portfolio)

Status: done

## Story

As a **chatbot (Annie)**,
I want **to clear a user's entire portfolio via API**,
so that **users can start fresh or remove all their data**.

## Acceptance Criteria

**AC1:** DELETE endpoint clears entire portfolio
- **Given** a user with one or more holdings
- **When** calling `DELETE /v1/portfolio?user_id={uuid}&confirmation=DELETE_ALL`
- **Then** the system deletes ALL holdings for that user
- **And** returns confirmation with 200 status

**AC2:** Requires confirmation parameter (safety check)
- **Given** a request without confirmation parameter
- **When** calling `DELETE /v1/portfolio?user_id={uuid}`
- **Then** the system returns 400 Bad Request
- **And** error message indicates confirmation is required

**AC3:** Validates confirmation value
- **Given** a request with incorrect confirmation value
- **When** calling `DELETE /v1/portfolio?user_id={uuid}&confirmation=WRONG`
- **Then** the system returns 400 Bad Request
- **And** error message indicates invalid confirmation value

**AC4:** Returns deletion count
- **Given** a successful deletion
- **When** the response is returned
- **Then** response includes: `{"deleted": true, "holdings_removed": 5}`
- **And** count reflects actual number of holdings deleted

**AC5:** Handles empty portfolio gracefully
- **Given** a user with no holdings
- **When** calling DELETE endpoint with valid confirmation
- **Then** the system returns 200 OK
- **And** response shows `{"deleted": true, "holdings_removed": 0}`

**AC6:** Request validation for user_id
- **Given** a request with missing user_id parameter
- **When** calling DELETE endpoint
- **Then** the system returns 422 Unprocessable Entity
- **And** error message indicates missing parameter

## Tasks / Subtasks

- [x] **Task 1:** Create Pydantic response model (AC4)
  - [x] Create `PortfolioClearResponse` model with fields: deleted (bool), holdings_removed (int)

- [x] **Task 2:** Implement confirmation validation (AC2, AC3)
  - [x] Add `confirmation` query parameter
  - [x] Validate confirmation equals "DELETE_ALL" (case-sensitive)
  - [x] Return 400 with descriptive error if missing or incorrect

- [x] **Task 3:** Implement DELETE all endpoint (AC1, AC4, AC5, AC6)
  - [x] Add `@router.delete("")` endpoint (route: `/v1/portfolio`)
  - [x] Accept user_id and confirmation from query parameters
  - [x] Use DELETE query with rowcount to get deletion count
  - [x] Return confirmation response with holdings_removed count
  - [x] Handle empty portfolio case (0 holdings deleted)

- [x] **Task 4:** Write unit tests (AC1, AC2, AC3, AC4, AC5, AC6)
  - [x] Test DELETE removes all holdings successfully
  - [x] Test confirmation parameter is required (400 if missing)
  - [x] Test invalid confirmation value returns 400
  - [x] Test response includes correct holdings_removed count
  - [x] Test empty portfolio returns 200 with holdings_removed=0
  - [x] Test missing user_id returns 422
  - [x] Test database unavailable returns 500

## Dev Notes

### Architecture Patterns

- **Router Pattern:** Extend `src/routers/portfolio.py` from Stories 3.1-3.5
- **Database Connection:** Use existing `get_timescale_conn()` / `release_timescale_conn()` pattern
- **Confirmation Safety:** Require explicit "DELETE_ALL" to prevent accidental mass deletion

### Database Operation

Use DELETE with row count to get number of deleted holdings:

```sql
DELETE FROM portfolio_holdings
WHERE user_id = %s
```

Use cursor.rowcount after execute to get deletion count (psycopg pattern).

Alternative using DELETE RETURNING with count:
```sql
WITH deleted AS (
    DELETE FROM portfolio_holdings
    WHERE user_id = %s
    RETURNING id
)
SELECT COUNT(*) FROM deleted;
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

**Key constraint:** Unique on `(user_id, ticker)`

### Difference from Single DELETE Endpoint

| Aspect | DELETE Single (Story 3.5) | DELETE All (Story 3.6) |
|--------|---------------------------|------------------------|
| Route | `/v1/portfolio/holding/{ticker}` | `/v1/portfolio` |
| Scope | One holding by ticker | All holdings for user |
| Safety | No confirmation needed | Requires `confirmation=DELETE_ALL` |
| Response | `{deleted: true, ticker: "AAPL"}` | `{deleted: true, holdings_removed: 5}` |
| 404 case | Returns 404 if not found | Returns 200 with count=0 |

### Learnings from Previous Story

**From Story 3-5-portfolio-delete-single-endpoint (Status: done)**

- **Model Pattern:** `HoldingDeleteResponse` with `deleted: bool` field - follow similar pattern for `PortfolioClearResponse`
- **DELETE Pattern:** DELETE RETURNING worked well for single record; for bulk delete use rowcount or CTE with COUNT
- **Connection Pattern:** try/except/finally with rollback on error, release_timescale_conn in finally
- **psycopg3 Compatibility:** Handle both dict and tuple cursor results
- **Response Code:** DELETE returns 200 (not 204) per API design
- **Query Parameters:** user_id from query parameter works well

[Source: docs/sprint-artifacts/3-5-portfolio-delete-single-endpoint.md#Dev-Agent-Record]

### References

- [Source: docs/epic-portfolio-crud-api.md#FR-PC5 (Clear Entire Portfolio)]
- [Source: docs/epic-portfolio-crud-api.md#Story-3.5 (Delete All endpoint)]
- [Source: src/routers/portfolio.py - Existing DELETE single endpoint pattern]
- [Source: docs/sprint-artifacts/3-5-portfolio-delete-single-endpoint.md - DELETE endpoint learnings]

---

**Story Created:** 2025-12-14
**Epic:** 3 (Portfolio Direct CRUD API)
**Depends On:** Story 3.1 (GET - done), Story 3.2 (POST - done), Story 3.3 (Schema - done), Story 3.4 (PUT - done), Story 3.5 (DELETE single - done)

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/3-6-portfolio-delete-all-endpoint.context.xml`

### File List

| File | Action | Description |
|------|--------|-------------|
| `src/routers/portfolio.py` | Modified | Added `PortfolioClearResponse` model (lines 87-90) and `clear_portfolio` DELETE endpoint (lines 457-522) |
| `tests/unit/test_portfolio_api.py` | Modified | Added 8 unit tests for DELETE all endpoint (lines 973-1094), added `_MockCursorWithRowcount` class |

### Completion Notes

**Implementation Summary:**
- Added `PortfolioClearResponse` Pydantic model with `deleted: bool` and `holdings_removed: int` fields
- Implemented DELETE endpoint at `/v1/portfolio` with required `confirmation=DELETE_ALL` safety parameter
- Used `cursor.rowcount` pattern for efficient bulk delete count (simpler than CTE approach)
- Returns 200 with `holdings_removed=0` for empty portfolio (differs from single DELETE which returns 404)

**Test Coverage:**
- 8 new tests covering all 6 acceptance criteria plus database unavailability
- Added `_MockCursorWithRowcount` helper class for testing rowcount behavior
- All 46 portfolio API tests pass

**Patterns Applied:**
- Followed try/except/finally with rollback on error from Story 3.5
- Used Query parameters with `...` for required user_id (FastAPI validation returns 422)
- Used Optional Query for confirmation with explicit None check for 400 error

**Completed:** 2025-12-14

## Senior Developer Review (AI)

### Review Details
- **Reviewer:** Ankit
- **Date:** 2025-12-14
- **Outcome:** APPROVE

### Summary
All 6 acceptance criteria are fully implemented with clear evidence. All 4 tasks marked complete have been verified. Implementation follows established patterns from Stories 3.1-3.5 with proper error handling, logging, and security measures.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | DELETE endpoint clears entire portfolio | IMPLEMENTED | `src/routers/portfolio.py:457-522` |
| AC2 | Requires confirmation parameter | IMPLEMENTED | `src/routers/portfolio.py:472-477` |
| AC3 | Validates confirmation value | IMPLEMENTED | `src/routers/portfolio.py:479-484` |
| AC4 | Returns deletion count | IMPLEMENTED | `src/routers/portfolio.py:87-90,501,508-511` |
| AC5 | Handles empty portfolio gracefully | IMPLEMENTED | `src/routers/portfolio.py:501` (rowcount=0) |
| AC6 | Request validation for user_id | IMPLEMENTED | `src/routers/portfolio.py:459` |

**Summary: 6 of 6 acceptance criteria fully implemented**

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: Create PortfolioClearResponse model | [x] | ✓ VERIFIED | `portfolio.py:87-90` |
| Task 2: Implement confirmation validation | [x] | ✓ VERIFIED | `portfolio.py:460,472-484` |
| Task 3: Implement DELETE all endpoint | [x] | ✓ VERIFIED | `portfolio.py:457-522` |
| Task 4: Write unit tests | [x] | ✓ VERIFIED | `test_portfolio_api.py:974-1096` |

**Summary: 4 of 4 completed tasks verified, 0 questionable, 0 false completions**

### Test Coverage and Gaps
- 8 unit tests covering all ACs plus edge cases
- Tests verify: success with count, missing confirmation (400), invalid confirmation (400), case sensitivity, empty portfolio (200 with 0), missing user_id (422), database unavailable (500)
- All 46 portfolio API tests pass
- No coverage gaps identified

### Architectural Alignment
- Follows established router pattern from Stories 3.1-3.5
- Uses `cursor.rowcount` for efficient bulk delete count (simpler than CTE)
- Proper try/except/finally with rollback on error, connection release in finally
- Parameterized queries (`%s`) prevent SQL injection

### Security Notes
- Confirmation parameter ("DELETE_ALL") prevents accidental mass deletion
- Case-sensitive validation prevents bypassing safety check
- No secrets or sensitive data exposure

### Action Items
**Code Changes Required:**
- None

**Advisory Notes:**
- Note: Consider adding rate limiting for DELETE all endpoint in production (no action required now)
