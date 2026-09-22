"""
Unit tests for Portfolio CRUD API endpoints (options support - migration 025)
Tests GET /v1/portfolio, POST /v1/portfolio/holding, PUT /v1/portfolio/holding/{position_key},
DELETE /v1/portfolio/holding/{position_key}, DELETE /v1/portfolio (clear all)

Covers both asset classes:
- equity: ticker, asset_name, shares, avg_price
- option: underlying_ticker, option_type, action_type, strike_price, expiration_date,
  contracts, premium, collateral_required (OCC-style symbol stored in ticker)
"""

import uuid
from unittest.mock import patch
from datetime import date, datetime, timezone

from src.routers.portfolio import HOLDING_COLUMNS


# =============================================================================
# Mock database helpers
# =============================================================================


class _MockCursor:
    """Mock database cursor for portfolio tests"""

    def __init__(self, results=None, fetchone_results=None, rowcount=0):
        self.results = results or []
        # Single-element list repeats (e.g., resolve + update return same row);
        # multi-element list is consumed as a queue.
        self._fetchone_results = list(fetchone_results or [])
        self.queries = []
        self.rowcount = rowcount

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        return self.results

    def fetchone(self):
        if not self._fetchone_results:
            return None
        if len(self._fetchone_results) == 1:
            return self._fetchone_results[0]
        return self._fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockConnection:
    """Mock database connection"""

    def __init__(self, cursor=None):
        self._cursor = cursor or _MockCursor()
        self._committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self._committed = True

    def rollback(self):
        pass


def _patch_db(mock_conn):
    """Patch router db connection helpers"""
    return (
        patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn),
        patch("src.routers.portfolio.release_timescale_conn"),
    )


def _holding_row(**overrides):
    """Full dict row for an equity holding (production dict_row shape)"""
    row = {
        "id": str(uuid.uuid4()),
        "ticker": "AAPL",
        "asset_name": "Apple Inc.",
        "asset_class": "equity",
        "shares": 100.0,
        "avg_price": 150.50,
        "underlying_ticker": None,
        "option_type": None,
        "action_type": None,
        "strike_price": None,
        "expiration_date": None,
        "contracts": None,
        "premium": None,
        "collateral_required": None,
        "first_acquired": datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        "last_updated": datetime(2025, 12, 10, 15, 30, 0, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


def _option_row(**overrides):
    """Full dict row for an option position (cash-secured put by default)"""
    row = _holding_row(
        ticker="TLN300118P00300000",
        asset_name="TLN $300 PUT 2030-01-18",
        asset_class="option",
        shares=None,
        avg_price=None,
        underlying_ticker="TLN",
        option_type="put",
        action_type="sell_to_open",
        strike_price=300.0,
        expiration_date=date(2030, 1, 18),
        contracts=1,
        premium=8.50,
        collateral_required=30000.0,
    )
    row.update(overrides)
    return row


def _row_tuple(row_dict):
    """Convert a dict row to tuple form matching HOLDING_COLUMNS order"""
    return tuple(row_dict[col] for col in HOLDING_COLUMNS)


# =============================================================================
# GET /v1/portfolio
# =============================================================================


def test_get_portfolio_success_with_holdings(api_client):
    """Successful portfolio retrieval with equity holdings"""
    mock_rows = [
        _holding_row(),
        _holding_row(
            ticker="GOOGL", asset_name="Alphabet Inc.", shares=50.0, avg_price=2800.00
        ),
    ]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == "test-user-123"
    assert data["total_holdings"] == 2
    assert len(data["holdings"]) == 2
    assert data["last_updated"] is not None

    holding = data["holdings"][0]
    assert holding["ticker"] == "AAPL"
    assert holding["asset_name"] == "Apple Inc."
    assert holding["asset_class"] == "equity"
    assert holding["shares"] == 100.0
    assert holding["avg_price"] == 150.50
    assert holding["id"] is not None
    assert holding["first_acquired"] is not None
    assert holding["last_updated"] is not None
    # No intent field in simplified schema
    assert "intent" not in holding

    # Grouping: all equities, no options
    assert len(data["equities"]) == 2
    assert data["options"] == []
    assert data["summary"]["total_equities"] == 2
    assert data["summary"]["total_options"] == 0
    assert data["summary"]["total_committed_options_collateral"] == 0.0


def test_get_portfolio_empty(api_client):
    """Portfolio retrieval with no holdings returns empty arrays"""
    mock_conn = _MockConnection(_MockCursor(results=[]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=empty-user")

    assert response.status_code == 200
    data = response.json()
    assert data["holdings"] == []
    assert data["equities"] == []
    assert data["options"] == []
    assert data["total_holdings"] == 0
    assert data["last_updated"] is None


def test_get_portfolio_missing_user_id(api_client):
    """Missing user_id query param returns 422"""
    response = api_client.get("/v1/portfolio")
    assert response.status_code == 422


def test_get_portfolio_tuple_cursor_format(api_client):
    """Tuple cursor rows (psycopg3 compatibility) are handled"""
    mock_rows = [_row_tuple(_holding_row()), _row_tuple(_option_row())]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["total_holdings"] == 2
    assert data["holdings"][0]["ticker"] == "AAPL"
    assert data["options"][0]["underlying_ticker"] == "TLN"
    assert data["options"][0]["strike_price"] == 300.0


def test_get_portfolio_database_unavailable(api_client):
    """Database unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 500


def test_get_portfolio_with_null_values(api_client):
    """Holdings with NULL shares/avg_price are returned as null"""
    mock_rows = [_holding_row(asset_name=None, shares=None, avg_price=None)]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    holding = response.json()["holdings"][0]
    assert holding["asset_name"] is None
    assert holding["shares"] is None
    assert holding["avg_price"] is None


def test_get_portfolio_groups_equities_and_options(api_client):
    """Mixed portfolio is grouped into equities and options with option fields"""
    mock_rows = [
        _holding_row(),
        _option_row(),
        _option_row(
            ticker="RKLB300118C00050000",
            asset_name="RKLB $50 CALL 2030-01-18",
            underlying_ticker="RKLB",
            option_type="call",
            strike_price=50.0,
            premium=2.10,
            collateral_required=None,
            action_type="buy_to_open",
        ),
    ]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert len(data["equities"]) == 1
    assert len(data["options"]) == 2
    assert data["equities"][0]["ticker"] == "AAPL"

    csp = data["options"][0]
    assert csp["underlying_ticker"] == "TLN"
    assert csp["option_type"] == "put"
    assert csp["action_type"] == "sell_to_open"
    assert csp["strike_price"] == 300.0
    assert csp["expiration_date"] == "2030-01-18"
    assert csp["contracts"] == 1
    assert csp["premium"] == 8.50
    assert csp["collateral_required"] == 30000.0

    assert data["summary"]["total_equities"] == 1
    assert data["summary"]["total_options"] == 2


def test_get_portfolio_excludes_inactive_options_by_default(api_client):
    """Default view returns equities + ACTIVE options only (closed/expired filtered)"""
    mock_rows = [
        _holding_row(),
        _option_row(),  # active
        _option_row(
            ticker="ISRG300118P00500000",
            underlying_ticker="ISRG",
            strike_price=500.0,
            action_type="buy_to_close",  # closed
        ),
        _option_row(
            ticker="TLN200117P00250000",
            strike_price=250.0,
            expiration_date=date(2020, 1, 17),  # expired
        ),
    ]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert len(data["equities"]) == 1
    assert len(data["options"]) == 1
    assert data["options"][0]["status"] == "active"
    assert data["total_holdings"] == 2
    assert len(data["holdings"]) == 2  # flat list is filtered too
    assert data["summary"]["total_options"] == 1
    assert data["summary"]["active_options"] == 1
    assert data["summary"]["total_committed_options_collateral"] == 30000.0


def test_get_portfolio_collateral_summary(api_client):
    """Total committed collateral sums only ACTIVE short (sell_to_open) options"""
    mock_rows = [
        # Active CSP: counts (30000)
        _option_row(),
        # Active covered call: counts (4500)
        _option_row(
            ticker="RKLB300118C00045000",
            underlying_ticker="RKLB",
            option_type="call",
            strike_price=45.0,
            collateral_required=4500.0,
        ),
        # Closed position: excluded
        _option_row(
            ticker="ISRG300118P00500000",
            underlying_ticker="ISRG",
            strike_price=500.0,
            action_type="buy_to_close",
            collateral_required=50000.0,
        ),
        # Expired position: excluded
        _option_row(
            ticker="TLN200117P00250000",
            strike_price=250.0,
            expiration_date=date(2020, 1, 17),
            collateral_required=25000.0,
        ),
        # Long option (buy_to_open): active but no short collateral
        _option_row(
            ticker="TLN300118C00350000",
            option_type="call",
            strike_price=350.0,
            action_type="buy_to_open",
            collateral_required=None,
        ),
    ]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get(
            "/v1/portfolio?user_id=test-user-123&include_inactive=true"
        )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total_options"] == 5
    assert summary["active_options"] == 3  # 2 short + 1 long, excluding closed/expired
    assert summary["total_committed_options_collateral"] == 34500.0


def test_get_portfolio_option_status_computed(api_client):
    """Option lifecycle status is computed: active / closed / expired (include_inactive=true)"""
    mock_rows = [
        _option_row(),
        _option_row(
            ticker="ISRG300118P00500000",
            underlying_ticker="ISRG",
            strike_price=500.0,
            action_type="buy_to_close",
        ),
        _option_row(
            ticker="TLN200117P00250000",
            strike_price=250.0,
            expiration_date=date(2020, 1, 17),
        ),
    ]
    mock_conn = _MockConnection(_MockCursor(results=mock_rows))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.get(
            "/v1/portfolio?user_id=test-user-123&include_inactive=true"
        )

    statuses = [o["status"] for o in response.json()["options"]]
    assert statuses == ["active", "closed", "expired"]
    # Equity rows have no status
    assert all(
        h["status"] is None
        for h in response.json()["holdings"]
        if h["asset_class"] == "equity"
    )


# =============================================================================
# POST /v1/portfolio/holding - equities
# =============================================================================


def test_post_holding_creates_new_holding(api_client):
    """POST creates new equity holding with valid data, returns 201"""
    row = _holding_row()
    row["inserted"] = True
    mock_conn = _MockConnection(_MockCursor(fetchone_results=[row]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json={
                "user_id": "test-user-123",
                "ticker": "AAPL",
                "asset_name": "Apple Inc.",
                "shares": 100.0,
                "avg_price": 150.50,
            },
        )

    assert response.status_code == 201
    data = response.json()

    assert data["id"] == row["id"]
    assert data["ticker"] == "AAPL"
    assert data["asset_class"] == "equity"
    assert data["asset_name"] == "Apple Inc."
    assert data["shares"] == 100.0
    assert data["avg_price"] == 150.50
    assert data["created"] is True
    assert "intent" not in data


def test_post_holding_ticker_normalization(api_client):
    """Lowercase ticker is normalized to uppercase"""
    row = _holding_row(asset_name=None, shares=None, avg_price=None)
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json={"user_id": "test-user-123", "ticker": "aapl"},
        )

    assert response.status_code == 201
    # Verify normalized ticker was sent to the database
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[1] == "AAPL"


def test_post_holding_upsert_updates_existing(api_client):
    """POST on existing ticker updates it and returns 200"""
    row = _holding_row(shares=150.0)
    row["inserted"] = False
    mock_conn = _MockConnection(_MockCursor(fetchone_results=[row]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json={"user_id": "test-user-123", "ticker": "AAPL", "shares": 150.0},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["created"] is False
    assert data["shares"] == 150.0


def test_post_holding_missing_user_id(api_client):
    """Missing user_id returns 422 (pydantic validation)"""
    response = api_client.post("/v1/portfolio/holding", json={"ticker": "AAPL"})
    assert response.status_code == 422


def test_post_holding_missing_ticker(api_client):
    """Missing ticker for an equity holding returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding", json={"user_id": "test-user-123"}
    )
    assert response.status_code == 400
    assert "ticker" in response.json()["detail"].lower()


def test_post_holding_invalid_ticker_format(api_client):
    """Invalid ticker format returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding",
        json={"user_id": "test-user-123", "ticker": "INVALID_TICKER_TOO_LONG!"},
    )
    assert response.status_code == 400
    assert "ticker" in response.json()["detail"].lower()


def test_post_holding_optional_fields_null(api_client):
    """Equity holding with only ticker succeeds; optional fields null"""
    row = _holding_row(asset_name=None, shares=None, avg_price=None)
    row["inserted"] = True
    mock_conn = _MockConnection(_MockCursor(fetchone_results=[row]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json={"user_id": "test-user-123", "ticker": "AAPL"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["asset_name"] is None
    assert data["shares"] is None
    assert data["avg_price"] is None


def test_post_holding_database_unavailable(api_client):
    """Database unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.post(
            "/v1/portfolio/holding",
            json={"user_id": "test-user-123", "ticker": "AAPL"},
        )
    assert response.status_code == 500


def test_post_holding_dotted_ticker(api_client):
    """Dotted tickers (BRK.B) are accepted"""
    row = _holding_row(ticker="BRK.B", asset_name=None, shares=None, avg_price=None)
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json={"user_id": "test-user-123", "ticker": "brk.b"},
        )

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[1] == "BRK.B"


# =============================================================================
# POST /v1/portfolio/holding - options
# =============================================================================


def _csp_payload(**overrides):
    """Valid cash-secured put payload (TLN $300 PUT expiring 2030-01-18)"""
    payload = {
        "user_id": "test-user-123",
        "asset_class": "option",
        "underlying_ticker": "TLN",
        "option_type": "put",
        "action_type": "sell_to_open",
        "strike_price": 300.0,
        "expiration_date": "2030-01-18",
        "contracts": 1,
        "premium": 8.50,
        "collateral_required": 30000.0,
    }
    payload.update(overrides)
    return payload


def test_post_option_creates_position(api_client):
    """POST creates a CSP with OCC-style symbol and option fields persisted"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post("/v1/portfolio/holding", json=_csp_payload())

    assert response.status_code == 201
    data = response.json()

    assert data["asset_class"] == "option"
    assert data["ticker"] == "TLN300118P00300000"
    assert data["underlying_ticker"] == "TLN"
    assert data["option_type"] == "put"
    assert data["action_type"] == "sell_to_open"
    assert data["strike_price"] == 300.0
    assert data["expiration_date"] == "2030-01-18"
    assert data["contracts"] == 1
    assert data["premium"] == 8.50
    assert data["collateral_required"] == 30000.0
    assert data["status"] == "active"
    assert data["created"] is True

    # Verify the generated OCC symbol and option values sent to the database
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[1] == "TLN300118P00300000"  # ticker
    assert insert_params[3] == "option"  # asset_class
    assert insert_params[6] == "TLN"  # underlying_ticker
    assert insert_params[7] == "put"  # option_type
    assert insert_params[8] == "sell_to_open"  # action_type
    assert insert_params[9] == 300.0  # strike_price
    assert insert_params[10] == "2030-01-18"  # expiration_date
    assert insert_params[11] == 1  # contracts
    assert insert_params[12] == 8.50  # premium
    assert insert_params[13] == 30000.0  # collateral_required


def test_post_option_infers_asset_class(api_client):
    """Option-defining fields without asset_class infer asset_class='option'"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    payload = _csp_payload()
    del payload["asset_class"]

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post("/v1/portfolio/holding", json=payload)

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[3] == "option"


def test_post_option_defaults_contracts_to_one(api_client):
    """Missing contracts defaults to 1"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    payload = _csp_payload()
    del payload["contracts"]

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post("/v1/portfolio/holding", json=payload)

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[11] == 1


def test_post_option_generates_display_name(api_client):
    """Missing asset_name gets a readable generated display name"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post("/v1/portfolio/holding", json=_csp_payload())

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[2] == "TLN $300 PUT 2030-01-18"


def test_post_option_underlying_fallback_to_ticker(api_client):
    """Options accept the underlying via `ticker` when underlying_ticker is absent"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    payload = _csp_payload(ticker="tln")
    del payload["underlying_ticker"]

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post("/v1/portfolio/holding", json=payload)

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[6] == "TLN"


def test_post_option_normalizes_enum_case(api_client):
    """option_type and action_type are case-insensitive"""
    row = _option_row()
    row["inserted"] = True
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.post(
            "/v1/portfolio/holding",
            json=_csp_payload(option_type="PUT", action_type="SELL_TO_OPEN"),
        )

    assert response.status_code == 201
    insert_params = mock_cursor.queries[0][1]
    assert insert_params[7] == "put"
    assert insert_params[8] == "sell_to_open"


def test_post_option_missing_underlying(api_client):
    """Option without underlying_ticker (or ticker fallback) returns 400"""
    payload = _csp_payload()
    del payload["underlying_ticker"]
    response = api_client.post("/v1/portfolio/holding", json=payload)
    assert response.status_code == 400
    assert "underlying_ticker" in response.json()["detail"]


def test_post_option_missing_option_type(api_client):
    """Option without option_type returns 400"""
    payload = _csp_payload(option_type=None)
    response = api_client.post("/v1/portfolio/holding", json=payload)
    assert response.status_code == 400
    assert "option_type" in response.json()["detail"]


def test_post_option_invalid_option_type(api_client):
    """Invalid option_type returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding", json=_csp_payload(option_type="straddle")
    )
    assert response.status_code == 400
    assert "option_type" in response.json()["detail"]


def test_post_option_missing_action_type(api_client):
    """Option without action_type returns 400"""
    payload = _csp_payload(action_type=None)
    response = api_client.post("/v1/portfolio/holding", json=payload)
    assert response.status_code == 400
    assert "action_type" in response.json()["detail"]


def test_post_option_invalid_action_type(api_client):
    """Invalid action_type returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding", json=_csp_payload(action_type="yolo")
    )
    assert response.status_code == 400
    assert "action_type" in response.json()["detail"]


def test_post_option_invalid_strike(api_client):
    """Non-positive strike_price returns 400"""
    for bad_strike in (0, -300, None):
        response = api_client.post(
            "/v1/portfolio/holding", json=_csp_payload(strike_price=bad_strike)
        )
        assert response.status_code == 400
        assert "strike_price" in response.json()["detail"]


def test_post_option_invalid_expiration(api_client):
    """Malformed or non-calendar expiration dates return 400"""
    for bad_date in ("01/18/2030", "2030-13-45", "not-a-date", None):
        response = api_client.post(
            "/v1/portfolio/holding", json=_csp_payload(expiration_date=bad_date)
        )
        assert response.status_code == 400
        assert "expiration_date" in response.json()["detail"]


def test_post_option_invalid_contracts(api_client):
    """Non-positive contracts returns 400"""
    for bad_contracts in (0, -2):
        response = api_client.post(
            "/v1/portfolio/holding", json=_csp_payload(contracts=bad_contracts)
        )
        assert response.status_code == 400
        assert "contracts" in response.json()["detail"]


def test_post_option_negative_collateral(api_client):
    """Negative collateral_required returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding", json=_csp_payload(collateral_required=-500)
    )
    assert response.status_code == 400
    assert "collateral_required" in response.json()["detail"]


def test_post_option_rejects_shares_and_avg_price(api_client):
    """Options must not set equity quantity fields (shares/avg_price)"""
    for equity_field in ({"shares": 100.0}, {"avg_price": 8.5}):
        response = api_client.post(
            "/v1/portfolio/holding", json=_csp_payload(**equity_field)
        )
        assert response.status_code == 400
        assert "contracts" in response.json()["detail"]


def test_post_equity_rejects_option_fields(api_client):
    """Equities must not carry option fields"""
    response = api_client.post(
        "/v1/portfolio/holding",
        json={
            "user_id": "test-user-123",
            "ticker": "AAPL",
            "asset_class": "equity",
            "strike_price": 300.0,
            "premium": 8.5,
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "strike_price" in detail
    assert "premium" in detail


def test_post_invalid_asset_class(api_client):
    """Unknown asset_class returns 400"""
    response = api_client.post(
        "/v1/portfolio/holding",
        json={"user_id": "test-user-123", "ticker": "AAPL", "asset_class": "crypto"},
    )
    assert response.status_code == 400
    assert "asset_class" in response.json()["detail"]


# =============================================================================
# PUT /v1/portfolio/holding/{position_key}
# =============================================================================


def test_put_holding_updates_existing(api_client):
    """PUT updates an existing equity holding by ticker"""
    row = _holding_row(shares=200.0)
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/AAPL",
            json={"user_id": "test-user-123", "shares": 200.0},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["shares"] == 200.0
    assert data["asset_class"] == "equity"


def test_put_holding_ticker_normalization(api_client):
    """Lowercase ticker path segment is normalized"""
    row = _holding_row()
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/aapl",
            json={"user_id": "test-user-123", "shares": 200.0},
        )

    assert response.status_code == 200
    resolve_params = mock_cursor.queries[0][1]
    assert resolve_params == ("test-user-123", "AAPL")


def test_put_holding_not_found(api_client):
    """PUT on non-existent holding returns 404"""
    mock_conn = _MockConnection(_MockCursor(fetchone_results=[]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/MSFT",
            json={"user_id": "test-user-123", "shares": 10.0},
        )

    assert response.status_code == 404


def test_put_holding_missing_user_id(api_client):
    """Missing user_id returns 422"""
    response = api_client.put("/v1/portfolio/holding/AAPL", json={"shares": 10.0})
    assert response.status_code == 422


def test_put_holding_invalid_position_key(api_client):
    """Malformed position key returns 400"""
    mock_conn = _MockConnection(_MockCursor())

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/BAD!!KEY",
            json={"user_id": "test-user-123", "shares": 10.0},
        )

    assert response.status_code == 400


def test_put_holding_partial_update_shares_only(api_client):
    """Partial update: only shares provided; other fields passed as NULL (COALESCE)"""
    row = _holding_row(shares=250.0)
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/AAPL",
            json={"user_id": "test-user-123", "shares": 250.0},
        )

    assert response.status_code == 200
    update_params = mock_cursor.queries[1][1]
    # (asset_name, shares, avg_price, contracts, premium, collateral, action_type, user_id, id)
    assert update_params[0] is None
    assert update_params[1] == 250.0
    assert update_params[2] is None


def test_put_holding_by_position_id(api_client):
    """PUT resolves a position by UUID id"""
    row = _holding_row()
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            f"/v1/portfolio/holding/{row['id']}",
            json={"user_id": "test-user-123", "shares": 300.0},
        )

    assert response.status_code == 200
    resolve_query, resolve_params = mock_cursor.queries[0]
    assert "id = %s" in resolve_query
    assert resolve_params == ("test-user-123", row["id"])


def test_put_option_by_key_tuple(api_client):
    """PUT resolves an option position by (underlying, type, strike, expiration)"""
    row = _option_row(contracts=2)
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/TLN",
            json={
                "user_id": "test-user-123",
                "option_type": "put",
                "strike_price": 300.0,
                "expiration_date": "2030-01-18",
                "contracts": 2,
            },
        )

    assert response.status_code == 200
    resolve_query, resolve_params = mock_cursor.queries[0]
    assert "asset_class = 'option'" in resolve_query
    assert "underlying_ticker" in resolve_query
    assert resolve_params[1] == "TLN"
    assert resolve_params[2] == "put"

    data = response.json()
    assert data["contracts"] == 2


def test_put_option_by_occ_symbol(api_client):
    """PUT resolves an option position directly by its OCC symbol"""
    row = _option_row(premium=9.25)
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/TLN300118P00300000",
            json={"user_id": "test-user-123", "premium": 9.25},
        )

    assert response.status_code == 200
    resolve_params = mock_cursor.queries[0][1]
    assert resolve_params == ("test-user-123", "TLN300118P00300000")


def test_put_option_close_position(api_client):
    """Lifecycle: closing a CSP via action_type='buy_to_close' -> status 'closed'"""
    row = _option_row(action_type="buy_to_close")
    mock_cursor = _MockCursor(fetchone_results=[_option_row(), row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/TLN300118P00300000",
            json={"user_id": "test-user-123", "action_type": "buy_to_close"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["action_type"] == "buy_to_close"
    assert data["status"] == "closed"


def test_put_holding_partial_option_tuple_400(api_client):
    """Providing only part of the option key tuple returns 400"""
    mock_conn = _MockConnection(_MockCursor())

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/TLN",
            json={
                "user_id": "test-user-123",
                "option_type": "put",
                "contracts": 2,
            },
        )

    assert response.status_code == 400
    assert "tuple" in response.json()["detail"].lower()


def test_put_option_fields_on_equity_400(api_client):
    """Option-only fields on an equity holding return 400"""
    row = _holding_row()
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/AAPL",
            json={"user_id": "test-user-123", "contracts": 2},
        )

    assert response.status_code == 400
    assert "equity" in response.json()["detail"].lower()


def test_put_equity_fields_on_option_400(api_client):
    """Equity quantity fields on an option position return 400"""
    row = _option_row()
    mock_cursor = _MockCursor(fetchone_results=[row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.put(
            "/v1/portfolio/holding/TLN300118P00300000",
            json={"user_id": "test-user-123", "shares": 100.0},
        )

    assert response.status_code == 400
    assert "options position" in response.json()["detail"].lower()


def test_put_holding_invalid_action_type(api_client):
    """Invalid action_type on update returns 400"""
    response = api_client.put(
        "/v1/portfolio/holding/TLN300118P00300000",
        json={"user_id": "test-user-123", "action_type": "exercise"},
    )
    assert response.status_code == 400
    assert "action_type" in response.json()["detail"]


def test_put_holding_database_unavailable(api_client):
    """Database unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.put(
            "/v1/portfolio/holding/AAPL",
            json={"user_id": "test-user-123", "shares": 10.0},
        )
    assert response.status_code == 500


# =============================================================================
# DELETE /v1/portfolio/holding/{position_key}
# =============================================================================


def test_delete_holding_removes_existing(api_client):
    """DELETE removes an equity holding by ticker"""
    row = _holding_row()
    delete_row = {"id": row["id"], "ticker": "AAPL", "asset_class": "equity"}
    mock_cursor = _MockCursor(fetchone_results=[row, delete_row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete("/v1/portfolio/holding/AAPL?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["ticker"] == "AAPL"
    assert data["id"] == row["id"]
    assert data["asset_class"] == "equity"


def test_delete_holding_ticker_normalization(api_client):
    """Lowercase ticker path segment is normalized"""
    row = _holding_row()
    delete_row = {"id": row["id"], "ticker": "AAPL", "asset_class": "equity"}
    mock_cursor = _MockCursor(fetchone_results=[row, delete_row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete("/v1/portfolio/holding/aapl?user_id=test-user-123")

    assert response.status_code == 200
    resolve_params = mock_cursor.queries[0][1]
    assert resolve_params == ("test-user-123", "AAPL")


def test_delete_holding_not_found(api_client):
    """DELETE on non-existent holding returns 404"""
    mock_conn = _MockConnection(_MockCursor(fetchone_results=[]))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete("/v1/portfolio/holding/MSFT?user_id=test-user-123")

    assert response.status_code == 404


def test_delete_holding_by_position_id(api_client):
    """DELETE resolves a position by UUID id"""
    row = _option_row()
    delete_row = {"id": row["id"], "ticker": row["ticker"], "asset_class": "option"}
    mock_cursor = _MockCursor(fetchone_results=[row, delete_row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            f"/v1/portfolio/holding/{row['id']}?user_id=test-user-123"
        )

    assert response.status_code == 200
    resolve_query, resolve_params = mock_cursor.queries[0]
    assert "id = %s" in resolve_query
    assert resolve_params == ("test-user-123", row["id"])
    assert response.json()["asset_class"] == "option"


def test_delete_option_by_key_tuple(api_client):
    """DELETE resolves an option via query params (underlying/type/strike/expiration)"""
    row = _option_row()
    delete_row = {"id": row["id"], "ticker": row["ticker"], "asset_class": "option"}
    mock_cursor = _MockCursor(fetchone_results=[row, delete_row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            "/v1/portfolio/holding/TLN"
            "?user_id=test-user-123&option_type=put&strike_price=300"
            "&expiration_date=2030-01-18"
        )

    assert response.status_code == 200
    resolve_query, resolve_params = mock_cursor.queries[0]
    assert "asset_class = 'option'" in resolve_query
    assert resolve_params[1] == "TLN"
    data = response.json()
    assert data["deleted"] is True
    assert data["ticker"] == "TLN300118P00300000"


def test_delete_option_by_occ_symbol(api_client):
    """DELETE resolves an option position directly by its OCC symbol (up to 32 chars)"""
    row = _option_row()
    delete_row = {"id": row["id"], "ticker": row["ticker"], "asset_class": "option"}
    mock_cursor = _MockCursor(fetchone_results=[row, delete_row])
    mock_conn = _MockConnection(mock_cursor)

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            "/v1/portfolio/holding/TLN300118P00300000?user_id=test-user-123"
        )

    assert response.status_code == 200
    resolve_params = mock_cursor.queries[0][1]
    assert resolve_params == ("test-user-123", "TLN300118P00300000")


def test_delete_holding_missing_user_id(api_client):
    """Missing user_id returns 422"""
    response = api_client.delete("/v1/portfolio/holding/AAPL")
    assert response.status_code == 422


def test_delete_holding_invalid_key(api_client):
    """Malformed position key returns 400"""
    mock_conn = _MockConnection(_MockCursor())

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            "/v1/portfolio/holding/BAD!!KEY?user_id=test-user-123"
        )

    assert response.status_code == 400


def test_delete_holding_database_unavailable(api_client):
    """Database unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.delete("/v1/portfolio/holding/AAPL?user_id=test-user-123")
    assert response.status_code == 500


# =============================================================================
# DELETE /v1/portfolio (clear all)
# =============================================================================


def test_clear_portfolio_removes_all_holdings(api_client):
    """Clear portfolio deletes all holdings with confirmation"""
    mock_conn = _MockConnection(_MockCursor(rowcount=3))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            "/v1/portfolio?user_id=test-user-123&confirmation=DELETE_ALL"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["holdings_removed"] == 3


def test_clear_portfolio_missing_confirmation(api_client):
    """Clear without confirmation returns 400"""
    response = api_client.delete("/v1/portfolio?user_id=test-user-123")
    assert response.status_code == 400


def test_clear_portfolio_invalid_confirmation(api_client):
    """Clear with wrong confirmation returns 400"""
    response = api_client.delete("/v1/portfolio?user_id=test-user-123&confirmation=YES")
    assert response.status_code == 400


def test_clear_portfolio_confirmation_case_sensitive(api_client):
    """Confirmation value is case-sensitive"""
    response = api_client.delete(
        "/v1/portfolio?user_id=test-user-123&confirmation=delete_all"
    )
    assert response.status_code == 400


def test_clear_portfolio_empty_portfolio(api_client):
    """Clearing an empty portfolio returns count 0"""
    mock_conn = _MockConnection(_MockCursor(rowcount=0))

    p1, p2 = _patch_db(mock_conn)
    with p1, p2:
        response = api_client.delete(
            "/v1/portfolio?user_id=test-user-123&confirmation=DELETE_ALL"
        )

    assert response.status_code == 200
    assert response.json()["holdings_removed"] == 0


def test_clear_portfolio_missing_user_id(api_client):
    """Missing user_id returns 422"""
    response = api_client.delete("/v1/portfolio?confirmation=DELETE_ALL")
    assert response.status_code == 422


def test_clear_portfolio_database_unavailable(api_client):
    """Database unavailable returns 500"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.delete(
            "/v1/portfolio?user_id=test-user-123&confirmation=DELETE_ALL"
        )
    assert response.status_code == 500
