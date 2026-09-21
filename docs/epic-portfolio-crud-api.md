# Epic 3: Portfolio Direct CRUD API

> **Implementation update — September 2026:** MCP is now implemented at `/mcp` in the existing API process and port, and is the preferred agent integration. See [MCP.md](MCP.md) for the actual 43-tool contract and access controls. The planning content below is historical: deferred MCP language, custom discovery/tool URLs, standalone servers, and proposed aggregation tools do not describe the current implementation. This update does not mark those broader epics complete or claim deployment.


**Epic ID:** 3
**Author:** Claude Code (Based on team discussion 2025-12-12)
**Status:** Proposed
**Priority:** P1 (User-Requested Feature)
**Dependencies:** None (uses existing portfolio_holdings table from migrations 013-014)
**Target Timeline:** 1-2 weeks

---

## Executive Summary

Create direct CRUD API endpoints for portfolio management that bypass the memory extraction pipeline. These endpoints will be used by Annie (the chatbot) via MCP tools to directly fetch, store, update, and delete stock holdings without going through the LLM-based ingestion flow.

**Key Benefits:**
- **Direct control**: Annie can programmatically manage portfolio without LLM interpretation
- **Deterministic operations**: No ambiguity from extraction - explicit CRUD operations
- **Faster operations**: No LLM latency for simple CRUD operations
- **User corrections**: Users can directly fix portfolio data through Annie

---

## Background & Motivation

### Current Architecture

Currently, portfolio data flows through the memory extraction pipeline:
1. User says "I bought 100 shares of AAPL at $150"
2. Message goes to `/v1/store` endpoint
3. LLM extracts portfolio information from conversation
4. `portfolio_service.py` stores extracted holdings

**Problems with current approach:**
- **Indirect control**: Annie cannot directly add/remove holdings
- **LLM ambiguity**: "I want to buy AAPL" vs "I bought AAPL" interpretation issues
- **No direct correction**: Users can't easily fix extraction errors
- **Latency**: Simple operations require full LLM pipeline (~2-3 seconds)

### Proposed Solution

Create dedicated REST endpoints for portfolio CRUD operations:
- Annie wraps these in MCP tools (`get_portfolio`, `add_holding`, etc.)
- Direct database operations without LLM interpretation
- Fast, deterministic operations (~50-100ms)

### Annie MCP Tools Architecture

```
Annie Chatbot
    │
    ├── MCP Tool: get_portfolio
    │   └── GET /v1/portfolio
    │
    ├── MCP Tool: add_holding
    │   └── POST /v1/portfolio/holding
    │
    ├── MCP Tool: update_holding
    │   └── PUT /v1/portfolio/holding/{ticker}
    │
    ├── MCP Tool: remove_holding
    │   └── DELETE /v1/portfolio/holding/{ticker}
    │
    └── MCP Tool: clear_portfolio
        └── DELETE /v1/portfolio
```

---

## Goals & Success Criteria

### Primary Goals

1. **Provide direct portfolio management** for Annie via MCP tools
2. **Enable user corrections** to portfolio data without re-extraction
3. **Support fast operations** (<100ms for CRUD operations)
4. **Maintain data integrity** with existing portfolio_holdings table

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Response Time** | <100ms | Average latency for CRUD operations |
| **Data Integrity** | 100% | No orphaned or duplicate records |
| **Annie Integration** | All 5 tools working | MCP tools successfully calling endpoints |
| **Test Coverage** | >80% | pytest coverage for new endpoints |

### Non-Goals

- Changing the memory extraction pipeline (still works in parallel)
- Adding authentication (defer to post-MVP)
- Building UI for portfolio management
- Real-time price updates or market data

---

## Functional Requirements

### FR-PC1: Get Portfolio Holdings

**Given** a user_id
**When** calling `GET /v1/portfolio?user_id={user_id}`
**Then** the system returns all holdings for that user:
```json
{
  "user_id": "uuid",
  "holdings": [
    {
      "ticker": "AAPL",
      "asset_name": "Apple Inc.",
      "shares": 100.0,
      "avg_price": 150.00,
      "intent": "hold",
      "created_at": "2025-12-01T10:00:00Z",
      "updated_at": "2025-12-10T15:30:00Z"
    }
  ],
  "total_holdings": 5,
  "last_updated": "2025-12-10T15:30:00Z"
}
```

---

### FR-PC2: Add Single Holding

**Given** a valid holding request
**When** calling `POST /v1/portfolio/holding` with body:
```json
{
  "user_id": "uuid",
  "ticker": "AAPL",
  "asset_name": "Apple Inc.",
  "shares": 100.0,
  "avg_price": 150.00,
  "intent": "hold"
}
```
**Then** the system:
- Normalizes ticker to uppercase
- Validates intent is valid (`hold`, `wants-to-buy`, `wants-to-sell`, `watch`)
- Creates or updates the holding (UPSERT on user_id + ticker)
- Returns the created/updated holding with status

**Note:** Only `hold` intent entries are actual holdings. Other intents are watchlist/speculative.

---

### FR-PC3: Update Single Holding

**Given** an existing holding
**When** calling `PUT /v1/portfolio/holding/{ticker}` with body:
```json
{
  "user_id": "uuid",
  "shares": 150.0,
  "avg_price": 155.00,
  "intent": "hold"
}
```
**Then** the system:
- Finds holding by user_id + ticker
- Updates specified fields (partial update)
- Returns 404 if holding doesn't exist
- Returns updated holding

---

### FR-PC4: Remove Single Holding

**Given** an existing holding
**When** calling `DELETE /v1/portfolio/holding/{ticker}?user_id={user_id}`
**Then** the system:
- Deletes the specific holding by user_id + ticker
- Returns 404 if holding doesn't exist
- Returns confirmation: `{"deleted": true, "ticker": "AAPL"}`

---

### FR-PC5: Clear Entire Portfolio

**Given** a user request to delete all holdings
**When** calling `DELETE /v1/portfolio?user_id={user_id}&confirmation=DELETE_ALL`
**Then** the system:
- Validates confirmation string (case-sensitive)
- Deletes ALL holdings for the user
- Returns: `{"deleted": true, "holdings_removed": 5}`

---

## Technical Architecture

### Database Schema (Existing)

Using existing `portfolio_holdings` table from migrations 013-014:

```sql
CREATE TABLE portfolio_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    ticker VARCHAR(20),
    asset_name VARCHAR(255),
    shares NUMERIC(18, 8),
    avg_price NUMERIC(18, 8),
    intent VARCHAR(20) CHECK (intent IN ('hold', 'wants-to-buy', 'wants-to-sell', 'watch')),
    source_memory_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_user_ticker UNIQUE (user_id, UPPER(ticker))
);
```

### API Endpoints

| Endpoint | Method | Description | Annie MCP Tool |
|----------|--------|-------------|----------------|
| `/v1/portfolio` | GET | Get all holdings for user | `get_portfolio` |
| `/v1/portfolio/holding` | POST | Add new holding | `add_holding` |
| `/v1/portfolio/holding/{ticker}` | PUT | Update existing holding | `update_holding` |
| `/v1/portfolio/holding/{ticker}` | DELETE | Remove single holding | `remove_holding` |
| `/v1/portfolio` | DELETE | Clear all holdings | `clear_portfolio` |

### File Structure

```
src/
├── routers/
│   └── portfolio.py          # New FastAPI router (5 endpoints)
├── services/
│   └── portfolio_service.py  # Existing service (may need minor additions)
└── app.py                    # Add router registration

tests/
└── unit/
    └── test_portfolio_api.py # New test file
```

---

## Story Breakdown

### Story 3.1: Portfolio GET Endpoint

**Priority:** P0 (Foundation)
**Estimated Effort:** 1 day

As a **chatbot (Annie)**,
I want **to fetch all portfolio holdings for a user via API**,
So that **I can display the user's current portfolio and answer questions about it**.

**Acceptance Criteria:**

1. `GET /v1/portfolio?user_id={uuid}` returns all holdings
2. Response includes: ticker, asset_name, shares, avg_price, intent, timestamps
3. Returns empty array `[]` if user has no holdings
4. Returns 400 if user_id is missing or invalid UUID

**Tasks:**
- [ ] Create `src/routers/portfolio.py` with FastAPI router
- [ ] Implement `get_portfolio(user_id: str)` endpoint
- [ ] Query `portfolio_holdings` table for user
- [ ] Return structured JSON response
- [ ] Add router to `app.py`
- [ ] Write unit tests

---

### Story 3.2: Portfolio POST Endpoint (Add Holding)

**Priority:** P0 (Foundation)
**Estimated Effort:** 1 day

As a **chatbot (Annie)**,
I want **to add a new stock holding for a user via API**,
So that **I can record purchases the user tells me about directly**.

**Acceptance Criteria:**

1. `POST /v1/portfolio/holding` creates new holding
2. Request body includes: user_id, ticker, shares, avg_price, intent
3. Ticker is normalized to uppercase
4. Intent is validated against allowed values
5. UPSERT behavior: updates if ticker already exists for user
6. Returns created/updated holding with 201 status

**Tasks:**
- [ ] Add POST endpoint to portfolio router
- [ ] Create Pydantic model for request validation
- [ ] Implement ticker normalization (uppercase)
- [ ] Implement intent validation
- [ ] Use UPSERT pattern from existing portfolio_service
- [ ] Write unit tests

---

### Story 3.3: Portfolio PUT Endpoint (Update Holding)

**Priority:** P0 (Foundation)
**Estimated Effort:** 1 day

As a **chatbot (Annie)**,
I want **to update an existing stock holding via API**,
So that **users can correct their portfolio data through me**.

**Acceptance Criteria:**

1. `PUT /v1/portfolio/holding/{ticker}` updates existing holding
2. Request body includes: user_id, and fields to update (shares, avg_price, intent)
3. Returns 404 if holding doesn't exist
4. Partial updates supported (only update provided fields)
5. Returns updated holding

**Tasks:**
- [ ] Add PUT endpoint to portfolio router
- [ ] Create Pydantic model for update request
- [ ] Implement partial update logic
- [ ] Handle 404 for missing holdings
- [ ] Write unit tests

---

### Story 3.4: Portfolio DELETE Endpoint (Remove Holding)

**Priority:** P0 (Foundation)
**Estimated Effort:** 0.5 days

As a **chatbot (Annie)**,
I want **to remove a specific stock holding via API**,
So that **users can remove stocks they no longer hold**.

**Acceptance Criteria:**

1. `DELETE /v1/portfolio/holding/{ticker}?user_id={uuid}` removes holding
2. Returns 404 if holding doesn't exist
3. Returns confirmation with deleted ticker

**Tasks:**
- [ ] Add DELETE endpoint for single holding
- [ ] Query and delete by user_id + ticker
- [ ] Handle 404 for missing holdings
- [ ] Write unit tests

---

### Story 3.5: Portfolio Clear Endpoint (Delete All)

**Priority:** P1 (Important)
**Estimated Effort:** 0.5 days

As a **chatbot (Annie)**,
I want **to clear a user's entire portfolio via API**,
So that **users can start fresh or remove all their data**.

**Acceptance Criteria:**

1. `DELETE /v1/portfolio?user_id={uuid}&confirmation=DELETE_ALL` clears portfolio
2. Requires confirmation parameter (safety check)
3. Returns 400 if confirmation doesn't match
4. Returns count of deleted holdings

**Tasks:**
- [ ] Add DELETE endpoint for entire portfolio
- [ ] Implement confirmation validation
- [ ] Delete all holdings for user
- [ ] Return deletion count
- [ ] Write unit tests

---

## Annie MCP Tools Specification

After API endpoints are complete, Annie's MCP tools will need to be updated:

### Tool: get_portfolio

```python
@tool
async def get_portfolio(user_id: str) -> dict:
    """Fetch all stock holdings for a user."""
    response = await http_client.get(
        f"{MEMORIES_API}/v1/portfolio",
        params={"user_id": user_id}
    )
    return response.json()
```

### Tool: add_holding

```python
@tool
async def add_holding(
    user_id: str,
    ticker: str,
    shares: float,
    avg_price: float,
    intent: str = "hold"
) -> dict:
    """Add a stock holding to user's portfolio."""
    response = await http_client.post(
        f"{MEMORIES_API}/v1/portfolio/holding",
        json={
            "user_id": user_id,
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
            "intent": intent
        }
    )
    return response.json()
```

### Tool: update_holding

```python
@tool
async def update_holding(
    user_id: str,
    ticker: str,
    shares: float = None,
    avg_price: float = None,
    intent: str = None
) -> dict:
    """Update an existing stock holding."""
    body = {"user_id": user_id}
    if shares is not None:
        body["shares"] = shares
    if avg_price is not None:
        body["avg_price"] = avg_price
    if intent is not None:
        body["intent"] = intent

    response = await http_client.put(
        f"{MEMORIES_API}/v1/portfolio/holding/{ticker}",
        json=body
    )
    return response.json()
```

### Tool: remove_holding

```python
@tool
async def remove_holding(user_id: str, ticker: str) -> dict:
    """Remove a stock from user's portfolio."""
    response = await http_client.delete(
        f"{MEMORIES_API}/v1/portfolio/holding/{ticker}",
        params={"user_id": user_id}
    )
    return response.json()
```

### Tool: clear_portfolio

```python
@tool
async def clear_portfolio(user_id: str) -> dict:
    """Delete all holdings from user's portfolio. Use with caution."""
    response = await http_client.delete(
        f"{MEMORIES_API}/v1/portfolio",
        params={"user_id": user_id, "confirmation": "DELETE_ALL"}
    )
    return response.json()
```

---

## Testing Strategy

### Unit Tests

- Test each endpoint with valid inputs
- Test validation (invalid UUID, missing fields, invalid intent)
- Test 404 handling for non-existent holdings
- Test UPSERT behavior (create vs update)
- Test confirmation validation for delete all

### Integration Tests

- End-to-end test: add → get → update → delete
- Test concurrent operations (race conditions)
- Test with actual database

### Manual Testing

- Test via curl commands
- Test via Annie MCP tools after integration

---

## Risks & Mitigations

### Risk 1: Conflict with Memory Extraction

**Description:** Both extraction pipeline and direct API could modify same holdings

**Mitigation:**
- Direct API sets `source_memory_id = NULL` to indicate manual entry
- Extraction pipeline sets `source_memory_id` to memory reference
- UPSERT handles conflicts gracefully (last write wins)

### Risk 2: Data Inconsistency

**Description:** User's stated portfolio doesn't match extracted portfolio

**Mitigation:**
- Direct API is authoritative when used
- Clear documentation that direct updates override extractions
- Users can use Annie to correct extraction errors

---

## References

- **Migration 013:** Unique constraint on portfolio_holdings
- **Migration 014:** Intent value changes (hold, wants-to-buy, wants-to-sell, watch)
- **portfolio_service.py:** Existing service with validation helpers
- **Annie tools.py:** MCP tools to be updated

---

## Revision History

- **v1.0 (2025-12-12):** Initial epic definition based on team discussion
