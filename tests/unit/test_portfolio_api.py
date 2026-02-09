"""
Unit tests for Portfolio CRUD API endpoints (simplified schema - Story 3.3, 3.4, 3.5, 3.6)
Tests GET /v1/portfolio, POST /v1/portfolio/holding, PUT /v1/portfolio/holding/{ticker},
DELETE /v1/portfolio/holding/{ticker}, DELETE /v1/portfolio (clear all)
Schema: id, user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated
"""
from unittest.mock import patch
from datetime import datetime, timezone


# Mock database cursor and connection
class _MockCursor:
    """Mock database cursor for portfolio tests"""

    def __init__(self, results=None):
        self.results = results or []
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockConnection:
    """Mock database connection"""

    def __init__(self, cursor=None):
        self._cursor = cursor or _MockCursor()

    def cursor(self):
        return self._cursor


# Test GET /v1/portfolio endpoint
def test_get_portfolio_success_with_holdings(api_client, monkeypatch):
    """Test successful portfolio retrieval with holdings (AC1, AC2)"""
    # Setup mock data - 6-tuple format (simplified schema, no intent)
    mock_holdings = [
        ("AAPL", "Apple Inc.", 100.0, 150.50,
         datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
         datetime(2025, 12, 10, 15, 30, 0, tzinfo=timezone.utc)),
        ("GOOGL", "Alphabet Inc.", 50.0, 2800.00,
         datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc),
         datetime(2025, 12, 5, 12, 0, 0, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Patch the database connection
    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure (AC2)
    assert data["user_id"] == "test-user-123"
    assert data["total_holdings"] == 2
    assert len(data["holdings"]) == 2
    assert data["last_updated"] is not None

    # Verify holding fields (AC1 - simplified schema)
    holding = data["holdings"][0]
    assert holding["ticker"] == "AAPL"
    assert holding["asset_name"] == "Apple Inc."
    assert holding["shares"] == 100.0
    assert holding["avg_price"] == 150.50
    assert holding["first_acquired"] is not None
    assert holding["last_updated"] is not None
    # No intent field in simplified schema
    assert "intent" not in holding


def test_get_portfolio_empty(api_client, monkeypatch):
    """Test portfolio retrieval with no holdings returns empty array (AC3)"""
    mock_cursor = _MockCursor(results=[])
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=no-holdings-user")

    assert response.status_code == 200
    data = response.json()

    # Verify empty response (AC3)
    assert data["user_id"] == "no-holdings-user"
    assert data["holdings"] == []
    assert data["total_holdings"] == 0
    assert data["last_updated"] is None


def test_get_portfolio_missing_user_id(api_client):
    """Test GET without user_id returns 400 (AC4)"""
    response = api_client.get("/v1/portfolio")

    # FastAPI returns 422 for missing required query parameters
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_get_portfolio_dict_cursor_format(api_client, monkeypatch):
    """Test handling of dict cursor results (psycopg3 compatibility)"""
    # Setup mock data - dict format (simplified schema, no intent)
    mock_holdings = [
        {
            "ticker": "MSFT",
            "asset_name": "Microsoft Corp.",
            "shares": 75.0,
            "avg_price": 380.00,
            "first_acquired": datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            "last_updated": datetime(2025, 12, 1, 14, 0, 0, tzinfo=timezone.utc)
        }
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=dict-test-user")

    assert response.status_code == 200
    data = response.json()

    assert data["total_holdings"] == 1
    holding = data["holdings"][0]
    assert holding["ticker"] == "MSFT"
    assert holding["shares"] == 75.0


def test_get_portfolio_holdings_ordered_by_ticker(api_client, monkeypatch):
    """Test holdings are returned ordered by ticker ASC (AC1, AC2)"""
    # Data should come back ordered from DB, but verify query is correct
    mock_holdings = [
        ("AAPL", "Apple", 10.0, 150.0,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("MSFT", "Microsoft", 20.0, 380.0,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("TSLA", "Tesla", 5.0, 250.0,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=order-test-user")

    assert response.status_code == 200
    data = response.json()

    # Verify ORDER BY is in the query
    assert len(mock_cursor.queries) == 1
    query = mock_cursor.queries[0][0]
    assert "ORDER BY" in query

    # Verify holdings come back in order
    tickers = [h["ticker"] for h in data["holdings"]]
    assert tickers == ["AAPL", "MSFT", "TSLA"]


def test_get_portfolio_database_unavailable(api_client, monkeypatch):
    """Test handling when database connection is unavailable"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.get("/v1/portfolio?user_id=test-user")

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_get_portfolio_with_null_values(api_client, monkeypatch):
    """Test handling of holdings with NULL optional fields"""
    mock_holdings = [
        ("AAPL", None, None, None,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=null-test-user")

    assert response.status_code == 200
    data = response.json()

    holding = data["holdings"][0]
    assert holding["ticker"] == "AAPL"
    assert holding["asset_name"] is None
    assert holding["shares"] is None
    assert holding["avg_price"] is None


# ============================================================
# POST /v1/portfolio/holding tests (Story 3.2 / 3.3 simplified)
# ============================================================

class _MockCursorWithFetchone(_MockCursor):
    """Mock cursor that also supports fetchone for POST tests"""

    def __init__(self, results=None, fetchone_result=None):
        super().__init__(results)
        self._fetchone_result = fetchone_result

    def fetchone(self):
        return self._fetchone_result


class _MockConnectionWithCommit(_MockConnection):
    """Mock connection that also supports commit for POST tests"""

    def __init__(self, cursor=None):
        super().__init__(cursor)
        self._committed = False

    def commit(self):
        self._committed = True

    def rollback(self):
        pass


def test_post_holding_creates_new_holding(api_client):
    """Test POST creates new holding with valid data, returns 201 (AC1)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Mock result: new insert (inserted=True) - 8-tuple (simplified schema)
    mock_result = (
        holding_id,
        "AAPL",
        "Apple Inc.",
        100.0,
        150.50,
        datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc),
        True  # inserted (xmax = 0)
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user-123",
                "ticker": "AAPL",
                "asset_name": "Apple Inc.",
                "shares": 100.0,
                "avg_price": 150.50
            })

    assert response.status_code == 201
    data = response.json()

    assert data["id"] == holding_id
    assert data["ticker"] == "AAPL"
    assert data["asset_name"] == "Apple Inc."
    assert data["shares"] == 100.0
    assert data["avg_price"] == 150.50
    assert data["created"] is True
    # No intent field in simplified schema
    assert "intent" not in data


def test_post_holding_ticker_normalization(api_client):
    """Test lowercase ticker is normalized to uppercase (AC2)"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "AAPL", None, None, None,
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "aapl"  # lowercase input
            })

    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"  # Should be uppercase

    # Verify the query was called with uppercase ticker
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert params[1] == "AAPL"  # Second param is ticker


def test_post_holding_upsert_updates_existing(api_client):
    """Test UPSERT updates existing holding for same user+ticker, returns 200 (AC4)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Mock result: update (inserted=False) - simplified schema
    mock_result = (
        holding_id,
        "AAPL",
        "Apple Inc.",
        150.0,  # updated shares
        160.00,  # updated price
        datetime(2025, 11, 1, tzinfo=timezone.utc),  # original first_acquired
        datetime(2025, 12, 14, tzinfo=timezone.utc),  # new last_updated
        False  # NOT inserted, was updated
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "AAPL",
                "asset_name": "Apple Inc.",
                "shares": 150.0,
                "avg_price": 160.00
            })

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == holding_id
    assert data["shares"] == 150.0
    assert data["avg_price"] == 160.00
    assert data["created"] is False


def test_post_holding_missing_user_id(api_client):
    """Test missing user_id returns 422 (AC5)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "ticker": "AAPL"
    })

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_post_holding_missing_ticker(api_client):
    """Test missing ticker returns 422 (AC5)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "user_id": "test-user"
    })

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_post_holding_optional_fields_null(api_client):
    """Test optional fields (asset_name, shares, avg_price) can be null (AC1)"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "TSLA", None, None, None,
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "TSLA"
                # No asset_name, shares, avg_price
            })

    assert response.status_code == 201
    data = response.json()

    assert data["ticker"] == "TSLA"
    assert data["asset_name"] is None
    assert data["shares"] is None
    assert data["avg_price"] is None
    assert data["created"] is True


def test_post_holding_invalid_ticker_format(api_client):
    """Test invalid ticker format returns 400 (AC2)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "user_id": "test-user",
        "ticker": "this-is-way-too-long-for-a-ticker"
    })

    assert response.status_code == 400
    data = response.json()
    assert "Invalid ticker format" in data["detail"]


def test_post_holding_dict_cursor_format(api_client):
    """Test handling of dict cursor results (psycopg3 compatibility)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Dict format result (simplified schema)
    mock_result = {
        "id": holding_id,
        "ticker": "GOOGL",
        "asset_name": "Alphabet Inc.",
        "shares": 25.0,
        "avg_price": 140.00,
        "first_acquired": datetime(2025, 12, 14, tzinfo=timezone.utc),
        "last_updated": datetime(2025, 12, 14, tzinfo=timezone.utc),
        "inserted": True
    }

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "dict-test-user",
                "ticker": "GOOGL",
                "asset_name": "Alphabet Inc.",
                "shares": 25.0,
                "avg_price": 140.00
            })

    assert response.status_code == 201
    data = response.json()

    assert data["id"] == holding_id
    assert data["ticker"] == "GOOGL"
    assert data["shares"] == 25.0
    assert data["created"] is True


def test_post_holding_database_unavailable(api_client):
    """Test handling when database connection is unavailable"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.post("/v1/portfolio/holding", json={
            "user_id": "test-user",
            "ticker": "AAPL"
        })

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_post_holding_dotted_ticker(api_client):
    """Test dotted tickers like BRK.B are accepted"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "BRK.B", "Berkshire Hathaway B", 10.0, 420.00,
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "brk.b",  # lowercase with dot
                "asset_name": "Berkshire Hathaway B",
                "shares": 10.0,
                "avg_price": 420.00
            })

    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "BRK.B"  # Normalized to uppercase


# ============================================================
# PUT /v1/portfolio/holding/{ticker} tests (Story 3.4)
# ============================================================

class _MockCursorWithMultipleFetchone(_MockCursor):
    """Mock cursor that supports multiple fetchone calls for PUT tests (SELECT then UPDATE)"""

    def __init__(self, results=None, fetchone_results=None):
        super().__init__(results)
        self._fetchone_results = fetchone_results or []
        self._fetchone_index = 0

    def fetchone(self):
        if self._fetchone_index < len(self._fetchone_results):
            result = self._fetchone_results[self._fetchone_index]
            self._fetchone_index += 1
            return result
        return None


def test_put_holding_updates_existing(api_client):
    """Test PUT updates existing holding with valid data, returns 200 (AC1)"""
    # First fetchone: SELECT returns existing holding id
    # Second fetchone: UPDATE RETURNING returns updated holding
    mock_fetchone_results = [
        ("existing-holding-id",),  # SELECT result
        (
            "AAPL",
            "Apple Inc.",
            150.0,  # updated shares
            160.00,  # updated price
            datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),  # original first_acquired
            datetime(2025, 12, 14, 15, 30, 0, tzinfo=timezone.utc),  # new last_updated
        )
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/AAPL", json={
                "user_id": "test-user-123",
                "asset_name": "Apple Inc.",
                "shares": 150.0,
                "avg_price": 160.00
            })

    assert response.status_code == 200
    data = response.json()

    assert data["ticker"] == "AAPL"
    assert data["asset_name"] == "Apple Inc."
    assert data["shares"] == 150.0
    assert data["avg_price"] == 160.00
    assert data["first_acquired"] is not None
    assert data["last_updated"] is not None


def test_put_holding_ticker_normalization(api_client):
    """Test lowercase ticker in path is normalized to uppercase (AC2)"""
    mock_fetchone_results = [
        ("existing-id",),
        ("AAPL", "Apple", 100.0, 150.0,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 14, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/aapl", json={  # lowercase path
                "user_id": "test-user",
                "shares": 100.0
            })

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"  # Should be uppercase

    # Verify SELECT query used uppercase ticker
    assert len(mock_cursor.queries) >= 1
    select_query, select_params = mock_cursor.queries[0]
    assert "SELECT" in select_query
    assert select_params[1] == "AAPL"  # Normalized ticker


def test_put_holding_invalid_ticker_format(api_client):
    """Test invalid ticker format returns 400 (AC2)"""
    response = api_client.put("/v1/portfolio/holding/invalid-ticker-too-long", json={
        "user_id": "test-user",
        "shares": 100.0
    })

    assert response.status_code == 400
    data = response.json()
    assert "Invalid ticker format" in data["detail"]


def test_put_holding_not_found(api_client):
    """Test PUT on non-existent holding returns 404 (AC4)"""
    # SELECT returns None (no existing holding)
    mock_fetchone_results = [None]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/NOTEXIST", json={
                "user_id": "test-user",
                "shares": 100.0
            })

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_put_holding_missing_user_id(api_client):
    """Test missing user_id returns 422 (AC5)"""
    response = api_client.put("/v1/portfolio/holding/AAPL", json={
        "shares": 100.0
    })

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_put_holding_partial_update_shares_only(api_client):
    """Test updating only shares field preserves other values (AC3)"""
    mock_fetchone_results = [
        ("existing-id",),
        ("AAPL", "Apple Inc.", 200.0, 150.00,  # shares updated, avg_price preserved
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 14, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/AAPL", json={
                "user_id": "test-user",
                "shares": 200.0  # Only updating shares
                # asset_name and avg_price not provided
            })

    assert response.status_code == 200
    data = response.json()

    assert data["shares"] == 200.0
    # Other fields should be preserved (via COALESCE)
    assert data["asset_name"] == "Apple Inc."
    assert data["avg_price"] == 150.00


def test_put_holding_partial_update_avg_price_only(api_client):
    """Test updating only avg_price field preserves other values (AC3)"""
    mock_fetchone_results = [
        ("existing-id",),
        ("MSFT", "Microsoft Corp.", 50.0, 400.00,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 14, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/MSFT", json={
                "user_id": "test-user",
                "avg_price": 400.00  # Only updating avg_price
            })

    assert response.status_code == 200
    data = response.json()

    assert data["avg_price"] == 400.00
    assert data["shares"] == 50.0  # Preserved


def test_put_holding_partial_update_asset_name_only(api_client):
    """Test updating only asset_name field preserves other values (AC3)"""
    mock_fetchone_results = [
        ("existing-id",),
        ("GOOGL", "Alphabet Inc. (Updated)", 25.0, 140.00,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 14, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/GOOGL", json={
                "user_id": "test-user",
                "asset_name": "Alphabet Inc. (Updated)"  # Only updating asset_name
            })

    assert response.status_code == 200
    data = response.json()

    assert data["asset_name"] == "Alphabet Inc. (Updated)"
    assert data["shares"] == 25.0  # Preserved
    assert data["avg_price"] == 140.00  # Preserved


def test_put_holding_response_includes_all_fields(api_client):
    """Test response includes all expected fields (AC6)"""
    mock_fetchone_results = [
        ("existing-id",),
        ("TSLA", "Tesla Inc.", 10.0, 250.00,
         datetime(2025, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
         datetime(2025, 12, 14, 16, 30, 0, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/TSLA", json={
                "user_id": "test-user",
                "shares": 10.0
            })

    assert response.status_code == 200
    data = response.json()

    # Verify all expected fields are present (AC6)
    assert "ticker" in data
    assert "asset_name" in data
    assert "shares" in data
    assert "avg_price" in data
    assert "first_acquired" in data
    assert "last_updated" in data

    # Verify no extra fields (like 'id' or 'created')
    assert "id" not in data
    assert "created" not in data


def test_put_holding_dict_cursor_format(api_client):
    """Test handling of dict cursor results (psycopg3 compatibility) (AC6)"""
    mock_fetchone_results = [
        {"id": "existing-id"},  # SELECT result as dict
        {
            "ticker": "NVDA",
            "asset_name": "NVIDIA Corp.",
            "shares": 30.0,
            "avg_price": 500.00,
            "first_acquired": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "last_updated": datetime(2025, 12, 14, tzinfo=timezone.utc)
        }
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/NVDA", json={
                "user_id": "dict-test-user",
                "shares": 30.0
            })

    assert response.status_code == 200
    data = response.json()

    assert data["ticker"] == "NVDA"
    assert data["asset_name"] == "NVIDIA Corp."
    assert data["shares"] == 30.0
    assert data["avg_price"] == 500.00


def test_put_holding_database_unavailable(api_client):
    """Test handling when database connection is unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.put("/v1/portfolio/holding/AAPL", json={
            "user_id": "test-user",
            "shares": 100.0
        })

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_put_holding_dotted_ticker(api_client):
    """Test dotted tickers like BRK.B work in path parameter"""
    mock_fetchone_results = [
        ("existing-id",),
        ("BRK.B", "Berkshire Hathaway B", 15.0, 450.00,
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 14, tzinfo=timezone.utc))
    ]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.put("/v1/portfolio/holding/brk.b", json={  # lowercase with dot
                "user_id": "test-user",
                "shares": 15.0
            })

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "BRK.B"  # Normalized to uppercase


# ============================================================
# DELETE /v1/portfolio/holding/{ticker} tests (Story 3.5)
# ============================================================

def test_delete_holding_removes_existing(api_client):
    """Test DELETE removes existing holding successfully, returns 200 (AC1)"""
    # DELETE RETURNING returns the deleted ticker
    mock_fetchone_results = [("AAPL",)]  # RETURNING ticker

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/AAPL?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["deleted"] is True
    assert data["ticker"] == "AAPL"


def test_delete_holding_response_structure(api_client):
    """Test response includes deleted=true and ticker fields (AC4)"""
    mock_fetchone_results = [("MSFT",)]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/MSFT?user_id=test-user")

    assert response.status_code == 200
    data = response.json()

    # Verify exact response structure (AC4)
    assert "deleted" in data
    assert "ticker" in data
    assert data["deleted"] is True
    assert data["ticker"] == "MSFT"

    # Should only have these two fields
    assert len(data) == 2


def test_delete_holding_ticker_normalization(api_client):
    """Test lowercase ticker in path is normalized to uppercase (AC2)"""
    mock_fetchone_results = [("GOOGL",)]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/googl?user_id=test-user")  # lowercase

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "GOOGL"  # Should be uppercase

    # Verify DELETE query used uppercase ticker
    assert len(mock_cursor.queries) >= 1
    delete_query, delete_params = mock_cursor.queries[0]
    assert "DELETE" in delete_query
    assert delete_params[1] == "GOOGL"  # Normalized ticker


def test_delete_holding_not_found(api_client):
    """Test DELETE on non-existent holding returns 404 (AC3)"""
    # DELETE RETURNING returns None (no row deleted)
    mock_fetchone_results = [None]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/NOTEXIST?user_id=test-user")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_delete_holding_missing_user_id(api_client):
    """Test missing user_id query param returns 422 (AC5)"""
    response = api_client.delete("/v1/portfolio/holding/AAPL")  # No user_id query param

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_delete_holding_invalid_ticker_format(api_client):
    """Test invalid ticker format returns 400 (AC6)"""
    response = api_client.delete("/v1/portfolio/holding/invalid-ticker-too-long?user_id=test-user")

    assert response.status_code == 400
    data = response.json()
    assert "Invalid ticker format" in data["detail"]


def test_delete_holding_database_unavailable(api_client):
    """Test handling when database connection is unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.delete("/v1/portfolio/holding/AAPL?user_id=test-user")

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_delete_holding_dotted_ticker(api_client):
    """Test dotted tickers like BRK.B work in path parameter"""
    mock_fetchone_results = [("BRK.B",)]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/brk.b?user_id=test-user")  # lowercase with dot

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "BRK.B"  # Normalized to uppercase


def test_delete_holding_dict_cursor_format(api_client):
    """Test handling of dict cursor results (psycopg3 compatibility)"""
    # DELETE RETURNING returns dict format
    mock_fetchone_results = [{"ticker": "NVDA"}]

    mock_cursor = _MockCursorWithMultipleFetchone(fetchone_results=mock_fetchone_results)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio/holding/NVDA?user_id=dict-test-user")

    assert response.status_code == 200
    data = response.json()

    assert data["deleted"] is True
    assert data["ticker"] == "NVDA"


# ============================================================
# DELETE /v1/portfolio (Clear All) tests (Story 3.6)
# ============================================================

class _MockCursorWithRowcount(_MockCursor):
    """Mock cursor that supports rowcount for DELETE all tests"""

    def __init__(self, results=None, rowcount=0):
        super().__init__(results)
        self.rowcount = rowcount

    def execute(self, query, params=None):
        super().execute(query, params)
        # rowcount is set after execute


def test_clear_portfolio_removes_all_holdings(api_client):
    """Test DELETE all removes all holdings successfully, returns 200 (AC1)"""
    mock_cursor = _MockCursorWithRowcount(rowcount=5)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio?user_id=test-user-123&confirmation=DELETE_ALL")

    assert response.status_code == 200
    data = response.json()

    assert data["deleted"] is True
    assert data["holdings_removed"] == 5


def test_clear_portfolio_returns_count(api_client):
    """Test response includes correct holdings_removed count (AC4)"""
    mock_cursor = _MockCursorWithRowcount(rowcount=3)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio?user_id=test-user&confirmation=DELETE_ALL")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure (AC4)
    assert "deleted" in data
    assert "holdings_removed" in data
    assert data["deleted"] is True
    assert data["holdings_removed"] == 3

    # Should only have these two fields
    assert len(data) == 2


def test_clear_portfolio_missing_confirmation(api_client):
    """Test missing confirmation parameter returns 400 (AC2)"""
    response = api_client.delete("/v1/portfolio?user_id=test-user")

    assert response.status_code == 400
    data = response.json()
    assert "confirmation" in data["detail"].lower()
    assert "required" in data["detail"].lower()


def test_clear_portfolio_invalid_confirmation(api_client):
    """Test invalid confirmation value returns 400 (AC3)"""
    response = api_client.delete("/v1/portfolio?user_id=test-user&confirmation=WRONG")

    assert response.status_code == 400
    data = response.json()
    assert "invalid" in data["detail"].lower()
    assert "WRONG" in data["detail"]


def test_clear_portfolio_confirmation_case_sensitive(api_client):
    """Test confirmation must be exactly 'DELETE_ALL' (case-sensitive) (AC3)"""
    # Test lowercase
    response = api_client.delete("/v1/portfolio?user_id=test-user&confirmation=delete_all")

    assert response.status_code == 400
    data = response.json()
    assert "invalid" in data["detail"].lower()

    # Test mixed case
    response2 = api_client.delete("/v1/portfolio?user_id=test-user&confirmation=Delete_All")

    assert response2.status_code == 400


def test_clear_portfolio_empty_portfolio(api_client):
    """Test empty portfolio returns 200 with holdings_removed=0 (AC5)"""
    mock_cursor = _MockCursorWithRowcount(rowcount=0)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.delete("/v1/portfolio?user_id=empty-user&confirmation=DELETE_ALL")

    assert response.status_code == 200
    data = response.json()

    assert data["deleted"] is True
    assert data["holdings_removed"] == 0


def test_clear_portfolio_missing_user_id(api_client):
    """Test missing user_id query param returns 422 (AC6)"""
    response = api_client.delete("/v1/portfolio?confirmation=DELETE_ALL")

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_clear_portfolio_database_unavailable(api_client):
    """Test handling when database connection is unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.delete("/v1/portfolio?user_id=test-user&confirmation=DELETE_ALL")

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]
