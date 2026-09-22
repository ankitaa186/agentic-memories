"""
Portfolio CRUD API Endpoints
Provides REST API for reading, creating, updating, and deleting portfolio holdings.

Supports two asset classes (options support - migration 025):
- equity: standard stock holdings (ticker, shares, avg_price)
- option: options contracts (CSPs, covered calls, long/short positions) with
  underlying_ticker, option_type, action_type, strike_price, expiration_date,
  contracts, premium, and collateral_required.

Option positions store a deterministic OCC-style symbol in `ticker`
(e.g., TLN260821P00300000), so UNIQUE (user_id, ticker) enforces one row per
(underlying, expiration, option_type, strike) and UPSERT behavior is preserved.
Positions can be addressed by UUID position id, ticker/OCC symbol, or the
options key tuple (underlying_ticker, option_type, strike_price, expiration_date).
"""

import uuid as uuid_lib
from typing import Any, Dict, List, Optional, Tuple
from datetime import date, datetime
import logging

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from fastapi.responses import JSONResponse

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.services.portfolio_service import (
    ACTION_TYPES,
    ASSET_CLASSES,
    OPTION_TYPES,
    build_option_symbol,
    normalize_position_key,
    normalize_ticker,
    option_position_status,
    validate_expiration_date,
)

logger = logging.getLogger("agentic_memories.portfolio_api")

router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


# Column order shared by SELECT/RETURNING clauses and tuple-row conversion
HOLDING_COLUMNS = (
    "id",
    "ticker",
    "asset_name",
    "asset_class",
    "shares",
    "avg_price",
    "underlying_ticker",
    "option_type",
    "action_type",
    "strike_price",
    "expiration_date",
    "contracts",
    "premium",
    "collateral_required",
    "first_acquired",
    "last_updated",
)

HOLDING_SELECT = ", ".join(HOLDING_COLUMNS)


def _as_dict(row: Any, columns: Tuple[str, ...] = HOLDING_COLUMNS) -> Dict[str, Any]:
    """Normalize a cursor row (dict or tuple, psycopg3 compatibility) to a dict."""
    if isinstance(row, dict):
        return row
    return dict(zip(columns, row))


def _row_to_holding(row: Any) -> "HoldingResponse":
    """Convert a portfolio_holdings row into a HoldingResponse with computed status."""
    data = _as_dict(row)

    asset_class = data.get("asset_class") or "equity"
    status = None
    if asset_class == "option":
        status = option_position_status(
            data.get("action_type"), data.get("expiration_date")
        )

    return HoldingResponse(
        id=str(data["id"]) if data.get("id") is not None else None,
        ticker=data.get("ticker"),
        asset_name=data.get("asset_name"),
        asset_class=asset_class,
        shares=float(data["shares"]) if data.get("shares") is not None else None,
        avg_price=float(data["avg_price"])
        if data.get("avg_price") is not None
        else None,
        underlying_ticker=data.get("underlying_ticker"),
        option_type=data.get("option_type"),
        action_type=data.get("action_type"),
        strike_price=float(data["strike_price"])
        if data.get("strike_price") is not None
        else None,
        expiration_date=data.get("expiration_date"),
        contracts=int(data["contracts"]) if data.get("contracts") is not None else None,
        premium=float(data["premium"]) if data.get("premium") is not None else None,
        collateral_required=float(data["collateral_required"])
        if data.get("collateral_required") is not None
        else None,
        status=status,
        first_acquired=data.get("first_acquired"),
        last_updated=data.get("last_updated"),
    )


# Pydantic models for request/response validation
class HoldingResponse(BaseModel):
    """Response model for a single portfolio holding (equity or option)"""

    id: Optional[str] = None
    ticker: Optional[str] = None
    asset_name: Optional[str] = None
    asset_class: str = "equity"
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    # Option-specific fields (null for equities)
    underlying_ticker: Optional[str] = None
    option_type: Optional[str] = None
    action_type: Optional[str] = None
    strike_price: Optional[float] = None
    expiration_date: Optional[date] = None
    contracts: Optional[int] = None
    premium: Optional[float] = None
    collateral_required: Optional[float] = None
    status: Optional[str] = None  # options lifecycle: active | closed | expired
    first_acquired: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class PortfolioSummary(BaseModel):
    """Aggregate portfolio metrics"""

    total_equities: int = 0
    total_options: int = 0
    active_options: int = 0
    # Sum of collateral_required across active short (sell_to_open) options
    total_committed_options_collateral: float = 0.0


class PortfolioResponse(BaseModel):
    """Response model for complete portfolio"""

    user_id: str
    holdings: List[HoldingResponse]  # flat list, backwards compatible
    equities: List[HoldingResponse]
    options: List[HoldingResponse]
    summary: PortfolioSummary
    total_holdings: int
    last_updated: Optional[datetime] = None


class AddHoldingRequest(BaseModel):
    """Request model for adding a portfolio holding (equity or option)"""

    user_id: str
    ticker: Optional[str] = None  # required for equities; optional for options
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    # Options contract fields (asset_class='option')
    asset_class: Optional[str] = None  # 'equity' (default) | 'option'
    underlying_ticker: Optional[str] = None
    option_type: Optional[str] = None  # 'put' | 'call'
    action_type: Optional[str] = (
        None  # sell_to_open | buy_to_open | sell_to_close | buy_to_close
    )
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None  # ISO YYYY-MM-DD
    contracts: Optional[int] = None  # 1 contract = 100 shares; defaults to 1
    premium: Optional[float] = None
    collateral_required: Optional[float] = None


class UpdateHoldingRequest(BaseModel):
    """Request model for updating a portfolio holding (Story 3.4 + options support)"""

    user_id: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    # Option updatable fields (lifecycle: e.g., action_type='buy_to_close' closes a CSP)
    contracts: Optional[int] = None
    premium: Optional[float] = None
    collateral_required: Optional[float] = None
    action_type: Optional[str] = None
    # Options key tuple - used only to LOCATE the position when the path segment
    # is the underlying ticker; contract terms themselves are immutable
    underlying_ticker: Optional[str] = None
    option_type: Optional[str] = None
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None


class HoldingCreateResponse(HoldingResponse):
    """Response model for holding create/update operations"""

    created: bool  # True if new record, False if updated existing


class HoldingUpdateResponse(HoldingResponse):
    """Response model for holding update operations (Story 3.4)"""


class HoldingDeleteResponse(BaseModel):
    """Response model for holding delete operations (Story 3.5)"""

    deleted: bool
    ticker: Optional[str] = None
    id: Optional[str] = None
    asset_class: Optional[str] = None


class PortfolioClearResponse(BaseModel):
    """Response model for clearing entire portfolio (Story 3.6)"""

    deleted: bool
    holdings_removed: int


def _validate_option_fields(
    *,
    underlying_ticker: Optional[str],
    fallback_ticker: Optional[str],
    option_type: Optional[str],
    action_type: Optional[str],
    strike_price: Optional[float],
    expiration_date: Optional[str],
    contracts: Optional[int],
    require_action: bool,
) -> Dict[str, Any]:
    """
    Validate and normalize option contract fields. Raises HTTPException(400) on
    invalid input. Returns dict with normalized values.
    """
    underlying = normalize_ticker(underlying_ticker or fallback_ticker)
    if underlying is None:
        raise HTTPException(
            status_code=400,
            detail="underlying_ticker is required for options and must be 1-10 alphanumeric characters (e.g., TLN, RKLB).",
        )

    normalized_type = (option_type or "").lower().strip()
    if normalized_type not in OPTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid option_type: '{option_type}'. Must be one of: put, call.",
        )

    normalized_action = None
    if action_type is not None:
        normalized_action = action_type.lower().strip()
        if normalized_action not in ACTION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type: '{action_type}'. Must be one of: {', '.join(sorted(ACTION_TYPES))}.",
            )
    elif require_action:
        raise HTTPException(
            status_code=400,
            detail="action_type is required for options (sell_to_open, buy_to_open, sell_to_close, buy_to_close).",
        )

    if strike_price is None or strike_price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strike_price: '{strike_price}'. Must be a positive number.",
        )

    normalized_expiration = validate_expiration_date(expiration_date)
    if normalized_expiration is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expiration_date: '{expiration_date}'. Must be a valid ISO date (YYYY-MM-DD).",
        )

    normalized_contracts = 1 if contracts is None else contracts
    if normalized_contracts <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid contracts: '{contracts}'. Must be a positive integer.",
        )

    return {
        "underlying_ticker": underlying,
        "option_type": normalized_type,
        "action_type": normalized_action,
        "strike_price": float(strike_price),
        "expiration_date": normalized_expiration,
        "contracts": normalized_contracts,
    }


def _resolve_position(
    cur,
    user_id: str,
    position_key: str,
    *,
    underlying_ticker: Optional[str] = None,
    option_type: Optional[str] = None,
    strike_price: Optional[float] = None,
    expiration_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve a position by (in priority order):
    1. UUID position id
    2. Options key tuple (underlying_ticker, option_type, strike_price, expiration_date)
       - the underlying may come from the path segment when not passed explicitly
    3. Ticker / OCC option symbol

    Returns the holding row as a dict, or None if not found.
    Raises HTTPException(400) for malformed keys.
    """
    # 1. UUID position id
    try:
        uuid_lib.UUID(position_key)
        is_position_id = True
    except ValueError:
        is_position_id = False  # not a UUID; fall through to ticker/tuple resolution

    if is_position_id:
        cur.execute(
            f"""
            SELECT {HOLDING_SELECT}
            FROM portfolio_holdings
            WHERE user_id = %s AND id = %s
        """,
            (user_id, position_key),
        )
        row = cur.fetchone()
        return _as_dict(row) if row is not None else None

    normalized_key = normalize_position_key(position_key)
    if normalized_key is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position key: '{position_key}'. Must be a position id (UUID), ticker, or option symbol.",
        )

    # 2. Options key tuple (all three of option_type/strike_price/expiration_date)
    tuple_fields = (option_type, strike_price, expiration_date)
    if any(f is not None for f in tuple_fields) and not all(
        f is not None for f in tuple_fields
    ):
        raise HTTPException(
            status_code=400,
            detail="To address an option by its key tuple, provide option_type, strike_price, AND expiration_date together.",
        )

    if (
        option_type is not None
        and strike_price is not None
        and expiration_date is not None
    ):
        option_fields = _validate_option_fields(
            underlying_ticker=underlying_ticker,
            fallback_ticker=normalized_key,
            option_type=option_type,
            action_type=None,
            strike_price=strike_price,
            expiration_date=expiration_date,
            contracts=None,
            require_action=False,
        )
        cur.execute(
            f"""
            SELECT {HOLDING_SELECT}
            FROM portfolio_holdings
            WHERE user_id = %s
              AND asset_class = 'option'
              AND underlying_ticker = %s
              AND option_type = %s
              AND ABS(strike_price - %s) < 1e-6
              AND expiration_date = %s
        """,
            (
                user_id,
                option_fields["underlying_ticker"],
                option_fields["option_type"],
                option_fields["strike_price"],
                option_fields["expiration_date"],
            ),
        )
        row = cur.fetchone()
        return _as_dict(row) if row is not None else None

    # 3. Ticker or OCC option symbol
    cur.execute(
        f"""
        SELECT {HOLDING_SELECT}
        FROM portfolio_holdings
        WHERE user_id = %s AND ticker = %s
    """,
        (user_id, normalized_key),
    )
    row = cur.fetchone()
    return _as_dict(row) if row is not None else None


@router.get("", response_model=PortfolioResponse)
def get_portfolio(
    user_id: str = Query(..., description="User identifier"),
    include_inactive: bool = Query(
        False,
        description="If true, also return closed and expired option positions. Default: only equities and active options.",
    ),
) -> PortfolioResponse:
    """
    Get portfolio holdings for a user, grouped into equities and options.

    By default only equities and ACTIVE options are returned; closed and expired
    option positions are excluded unless include_inactive=true.

    Returns:
    - holdings: flat list of returned positions (backwards compatible)
    - equities: standard stock holdings
    - options: option positions with computed lifecycle status (active/closed/expired)
    - summary: counts + total committed options collateral (active short options)
    """
    logger.info(
        "[portfolio.api.get] user_id=%s include_inactive=%s", user_id, include_inactive
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[portfolio.api.get] user_id=%s database_unavailable", user_id)
            raise HTTPException(
                status_code=500, detail="Database connection unavailable"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {HOLDING_SELECT}
                FROM portfolio_holdings
                WHERE user_id = %s
                ORDER BY asset_class ASC, ticker ASC NULLS LAST, asset_name ASC
            """,
                (user_id,),
            )

            rows = cur.fetchall()

            holdings = [_row_to_holding(row) for row in rows]

            # Default view: equities + active options only (status is computed
            # from action_type/expiration, so filter after row conversion)
            if not include_inactive:
                holdings = [
                    h
                    for h in holdings
                    if h.asset_class != "option" or h.status == "active"
                ]

            latest_updated = None
            for holding in holdings:
                if holding.last_updated is not None:
                    if latest_updated is None or holding.last_updated > latest_updated:
                        latest_updated = holding.last_updated

            equities = [h for h in holdings if h.asset_class != "option"]
            options = [h for h in holdings if h.asset_class == "option"]
            active_options = [o for o in options if o.status == "active"]

            total_committed_collateral = round(
                sum(
                    o.collateral_required or 0.0
                    for o in active_options
                    if o.action_type == "sell_to_open"
                ),
                2,
            )

            summary = PortfolioSummary(
                total_equities=len(equities),
                total_options=len(options),
                active_options=len(active_options),
                total_committed_options_collateral=total_committed_collateral,
            )

            logger.info(
                "[portfolio.api.get] user_id=%s holdings_count=%d equities=%d options=%d committed_collateral=%.2f",
                user_id,
                len(holdings),
                len(equities),
                len(options),
                total_committed_collateral,
            )

            return PortfolioResponse(
                user_id=user_id,
                holdings=holdings,
                equities=equities,
                options=options,
                summary=summary,
                total_holdings=len(holdings),
                last_updated=latest_updated,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[portfolio.api.get] user_id=%s error=%s", user_id, str(e))
        raise HTTPException(
            status_code=500, detail=f"Error fetching portfolio: {str(e)}"
        )
    finally:
        if conn is not None:
            release_timescale_conn(conn)


@router.post("/holding", response_model=HoldingCreateResponse)
def add_holding(request: AddHoldingRequest):
    """
    Add or update a portfolio holding (equity or options contract).

    Equities: identified by user_id + ticker (UPSERT behavior).
    Options: identified by user_id + (underlying_ticker, option_type, strike_price,
    expiration_date); a deterministic OCC-style symbol is stored in `ticker`, so
    re-adding the same contract updates the existing position (UPSERT behavior).
    Returns 201 for new holding, 200 for update.
    """
    logger.info(
        "[portfolio.api.post] user_id=%s ticker=%s asset_class=%s",
        request.user_id,
        request.ticker,
        request.asset_class,
    )

    # Determine asset class; default to equity (backwards compatibility), but
    # infer 'option' when option-defining fields are supplied without asset_class.
    asset_class = (request.asset_class or "").lower().strip() or None
    if asset_class is None:
        has_option_fields = (
            request.option_type is not None
            or request.strike_price is not None
            or request.expiration_date is not None
        )
        asset_class = "option" if has_option_fields else "equity"

    if asset_class not in ASSET_CLASSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset_class: '{request.asset_class}'. Must be one of: equity, option.",
        )

    if asset_class == "option":
        # Watertight: options track quantity via contracts, not shares/avg_price
        if request.shares is not None or request.avg_price is not None:
            raise HTTPException(
                status_code=400,
                detail="Options positions must not set shares or avg_price; use contracts (1 contract = 100 shares) and premium instead.",
            )
        option_fields = _validate_option_fields(
            underlying_ticker=request.underlying_ticker,
            fallback_ticker=request.ticker,
            option_type=request.option_type,
            action_type=request.action_type,
            strike_price=request.strike_price,
            expiration_date=request.expiration_date,
            contracts=request.contracts,
            require_action=True,
        )
        if request.collateral_required is not None and request.collateral_required < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid collateral_required: '{request.collateral_required}'. Must be non-negative.",
            )

        normalized_ticker = build_option_symbol(
            option_fields["underlying_ticker"],
            option_fields["option_type"],
            option_fields["strike_price"],
            option_fields["expiration_date"],
        )
        # Human-readable display name, e.g. "TLN $300 PUT 2026-08-21"
        asset_name = request.asset_name or (
            f"{option_fields['underlying_ticker']} "
            f"${option_fields['strike_price']:g} "
            f"{option_fields['option_type'].upper()} "
            f"{option_fields['expiration_date']}"
        )
        insert_values = (
            request.user_id,
            normalized_ticker,
            asset_name,
            "option",
            None,  # shares (equity-only; DB chk_option_no_equity_fields)
            None,  # avg_price (equity-only)
            option_fields["underlying_ticker"],
            option_fields["option_type"],
            option_fields["action_type"],
            option_fields["strike_price"],
            option_fields["expiration_date"],
            option_fields["contracts"],
            request.premium,
            request.collateral_required,
        )
    else:
        # Watertight: equities must not carry any option fields
        provided_option_fields = [
            name
            for name, value in (
                ("underlying_ticker", request.underlying_ticker),
                ("option_type", request.option_type),
                ("action_type", request.action_type),
                ("strike_price", request.strike_price),
                ("expiration_date", request.expiration_date),
                ("contracts", request.contracts),
                ("premium", request.premium),
                ("collateral_required", request.collateral_required),
            )
            if value is not None
        ]
        if provided_option_fields:
            raise HTTPException(
                status_code=400,
                detail=f"asset_class is 'equity' but option fields were provided: {', '.join(provided_option_fields)}. Set asset_class='option' to log an options contract.",
            )

        # Equity path: ticker required
        normalized_ticker = normalize_ticker(request.ticker)
        if normalized_ticker is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ticker format: '{request.ticker}'. Ticker must be 1-10 alphanumeric characters.",
            )
        insert_values = (
            request.user_id,
            normalized_ticker,
            request.asset_name,
            "equity",
            request.shares,
            request.avg_price,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error(
                "[portfolio.api.post] user_id=%s database_unavailable", request.user_id
            )
            raise HTTPException(
                status_code=500, detail="Database connection unavailable"
            )

        with conn.cursor() as cur:
            # UPSERT query using ON CONFLICT (user_id, ticker). For options the
            # ticker is the OCC symbol, so the conflict key IS the contract key.
            cur.execute(
                f"""
                INSERT INTO portfolio_holdings (
                    user_id, ticker, asset_name, asset_class, shares, avg_price,
                    underlying_ticker, option_type, action_type, strike_price,
                    expiration_date, contracts, premium, collateral_required,
                    first_acquired, last_updated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id, ticker)
                DO UPDATE SET
                    asset_name = COALESCE(EXCLUDED.asset_name, portfolio_holdings.asset_name),
                    shares = COALESCE(EXCLUDED.shares, portfolio_holdings.shares),
                    avg_price = COALESCE(EXCLUDED.avg_price, portfolio_holdings.avg_price),
                    action_type = COALESCE(EXCLUDED.action_type, portfolio_holdings.action_type),
                    contracts = COALESCE(EXCLUDED.contracts, portfolio_holdings.contracts),
                    premium = COALESCE(EXCLUDED.premium, portfolio_holdings.premium),
                    collateral_required = COALESCE(EXCLUDED.collateral_required, portfolio_holdings.collateral_required),
                    last_updated = NOW()
                RETURNING {HOLDING_SELECT}, (xmax = 0) AS inserted
            """,
                insert_values,
            )

            row = cur.fetchone()
            conn.commit()

            data = _as_dict(row, HOLDING_COLUMNS + ("inserted",))
            inserted = data["inserted"]

            holding = _row_to_holding(
                {k: v for k, v in data.items() if k != "inserted"}
            )
            response = HoldingCreateResponse(**holding.model_dump(), created=inserted)

            status_code = 201 if inserted else 200
            logger.info(
                "[portfolio.api.post] user_id=%s ticker=%s asset_class=%s created=%s",
                request.user_id,
                normalized_ticker,
                asset_class,
                inserted,
            )

            return JSONResponse(
                content=response.model_dump(mode="json"), status_code=status_code
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[portfolio.api.post] user_id=%s ticker=%s error=%s",
            request.user_id,
            request.ticker,
            str(e),
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding holding: {str(e)}")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


@router.put("/holding/{position_key}", response_model=HoldingUpdateResponse)
def update_holding(position_key: str, request: UpdateHoldingRequest):
    """
    Update an existing portfolio holding (Story 3.4 + options support).

    The position is resolved by (in priority order):
    1. UUID position id
    2. Options key tuple: path segment (or body underlying_ticker) + body
       option_type, strike_price, expiration_date
    3. Ticker (equities) or OCC option symbol

    Supports partial updates - only provided fields are updated. Option lifecycle
    events are supported via action_type (e.g., 'buy_to_close' closes a short put).
    Contract terms (underlying, type, strike, expiration) are immutable - roll a
    position by closing/removing it and adding the new contract.
    Returns 404 if the holding doesn't exist (unlike POST which creates).
    """
    logger.info(
        "[portfolio.api.put] user_id=%s position_key=%s", request.user_id, position_key
    )

    normalized_action = None
    if request.action_type is not None:
        normalized_action = request.action_type.lower().strip()
        if normalized_action not in ACTION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type: '{request.action_type}'. Must be one of: {', '.join(sorted(ACTION_TYPES))}.",
            )

    if request.contracts is not None and request.contracts <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid contracts: '{request.contracts}'. Must be a positive integer.",
        )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error(
                "[portfolio.api.put] user_id=%s database_unavailable", request.user_id
            )
            raise HTTPException(
                status_code=500, detail="Database connection unavailable"
            )

        with conn.cursor() as cur:
            # Step 1: Resolve position (by id, options key tuple, or ticker)
            existing = _resolve_position(
                cur,
                request.user_id,
                position_key,
                underlying_ticker=request.underlying_ticker,
                option_type=request.option_type,
                strike_price=request.strike_price,
                expiration_date=request.expiration_date,
            )
            if existing is None:
                logger.info(
                    "[portfolio.api.put] user_id=%s position_key=%s not_found",
                    request.user_id,
                    position_key,
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Holding not found for user '{request.user_id}' and position '{position_key}'",
                )

            # Guard: option-only fields cannot be applied to an equity holding
            if existing.get("asset_class") != "option" and any(
                v is not None
                for v in (
                    request.contracts,
                    request.premium,
                    request.collateral_required,
                    normalized_action,
                )
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Position '{position_key}' is an equity holding; contracts, premium, collateral_required, and action_type only apply to options.",
                )

            # Guard: equity-only quantity fields cannot be applied to an option position
            if existing.get("asset_class") == "option" and (
                request.shares is not None or request.avg_price is not None
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Position '{position_key}' is an options position; shares and avg_price only apply to equities (use contracts and premium).",
                )

            # Step 2: Update with COALESCE for partial updates (AC1, AC3, AC6)
            cur.execute(
                f"""
                UPDATE portfolio_holdings
                SET
                    asset_name = COALESCE(%s, asset_name),
                    shares = COALESCE(%s, shares),
                    avg_price = COALESCE(%s, avg_price),
                    contracts = COALESCE(%s, contracts),
                    premium = COALESCE(%s, premium),
                    collateral_required = COALESCE(%s, collateral_required),
                    action_type = COALESCE(%s, action_type),
                    last_updated = NOW()
                WHERE user_id = %s AND id = %s
                RETURNING {HOLDING_SELECT}
            """,
                (
                    request.asset_name,
                    request.shares,
                    request.avg_price,
                    request.contracts,
                    request.premium,
                    request.collateral_required,
                    normalized_action,
                    request.user_id,
                    str(existing["id"]),
                ),
            )

            row = cur.fetchone()
            conn.commit()

            holding = _row_to_holding(row)
            response = HoldingUpdateResponse(**holding.model_dump())

            logger.info(
                "[portfolio.api.put] user_id=%s position_key=%s ticker=%s updated",
                request.user_id,
                position_key,
                holding.ticker,
            )

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[portfolio.api.put] user_id=%s position_key=%s error=%s",
            request.user_id,
            position_key,
            str(e),
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating holding: {str(e)}")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


@router.delete("/holding/{position_key}", response_model=HoldingDeleteResponse)
def delete_holding(
    position_key: str,
    user_id: str = Query(..., description="User identifier"),
    underlying_ticker: Optional[str] = Query(
        None, description="Options: underlying ticker (defaults to path segment)"
    ),
    option_type: Optional[str] = Query(
        None,
        description="Options: 'put' or 'call' (with strike/expiration resolves an option position)",
    ),
    strike_price: Optional[float] = Query(None, description="Options: strike price"),
    expiration_date: Optional[str] = Query(
        None, description="Options: expiration date (YYYY-MM-DD)"
    ),
):
    """
    Delete a portfolio holding (Story 3.5 + options support).

    The position is resolved by UUID position id, options key tuple
    (underlying_ticker/option_type/strike_price/expiration_date query params),
    or ticker/OCC option symbol. Use this to remove expired or closed contracts.
    Returns 404 if holding doesn't exist.
    """
    logger.info(
        "[portfolio.api.delete] user_id=%s position_key=%s", user_id, position_key
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error(
                "[portfolio.api.delete] user_id=%s database_unavailable", user_id
            )
            raise HTTPException(
                status_code=500, detail="Database connection unavailable"
            )

        with conn.cursor() as cur:
            existing = _resolve_position(
                cur,
                user_id,
                position_key,
                underlying_ticker=underlying_ticker,
                option_type=option_type,
                strike_price=strike_price,
                expiration_date=expiration_date,
            )
            if existing is None:
                logger.info(
                    "[portfolio.api.delete] user_id=%s position_key=%s not_found",
                    user_id,
                    position_key,
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Holding not found for user '{user_id}' and position '{position_key}'",
                )

            cur.execute(
                """
                DELETE FROM portfolio_holdings
                WHERE user_id = %s AND id = %s
                RETURNING id, ticker, asset_class
            """,
                (user_id, str(existing["id"])),
            )

            row = cur.fetchone()
            conn.commit()

            data = _as_dict(row, ("id", "ticker", "asset_class"))

            logger.info(
                "[portfolio.api.delete] user_id=%s position_key=%s ticker=%s deleted",
                user_id,
                position_key,
                data.get("ticker"),
            )

            return HoldingDeleteResponse(
                deleted=True,
                ticker=data.get("ticker"),
                id=str(data["id"]) if data.get("id") is not None else None,
                asset_class=data.get("asset_class"),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[portfolio.api.delete] user_id=%s position_key=%s error=%s",
            user_id,
            position_key,
            str(e),
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting holding: {str(e)}")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


@router.delete("", response_model=PortfolioClearResponse)
def clear_portfolio(
    user_id: str = Query(..., description="User identifier"),
    confirmation: Optional[str] = Query(
        None, description="Must be 'DELETE_ALL' to confirm"
    ),
):
    """
    Clear all portfolio holdings for a user (Story 3.6).

    Deletes ALL holdings for the specified user.
    Requires confirmation parameter set to 'DELETE_ALL' for safety.
    Returns count of deleted holdings (can be 0 if portfolio was already empty).
    """
    logger.info(
        "[portfolio.api.clear] user_id=%s confirmation=%s", user_id, confirmation
    )

    # Validate confirmation parameter (AC2, AC3)
    if confirmation is None:
        logger.info("[portfolio.api.clear] user_id=%s confirmation_missing", user_id)
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set confirmation='DELETE_ALL' to clear all holdings.",
        )

    if confirmation != "DELETE_ALL":
        logger.info(
            "[portfolio.api.clear] user_id=%s invalid_confirmation=%s",
            user_id,
            confirmation,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid confirmation value: '{confirmation}'. Must be exactly 'DELETE_ALL'.",
        )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error(
                "[portfolio.api.clear] user_id=%s database_unavailable", user_id
            )
            raise HTTPException(
                status_code=500, detail="Database connection unavailable"
            )

        with conn.cursor() as cur:
            # Delete all holdings for user and get count via rowcount
            cur.execute(
                """
                DELETE FROM portfolio_holdings
                WHERE user_id = %s
            """,
                (user_id,),
            )

            # Get count of deleted rows (psycopg pattern)
            holdings_removed = cur.rowcount

            conn.commit()

            logger.info(
                "[portfolio.api.clear] user_id=%s holdings_removed=%d",
                user_id,
                holdings_removed,
            )

            return PortfolioClearResponse(
                deleted=True, holdings_removed=holdings_removed
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[portfolio.api.clear] user_id=%s error=%s", user_id, str(e))
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error clearing portfolio: {str(e)}"
        )
    finally:
        if conn is not None:
            release_timescale_conn(conn)
