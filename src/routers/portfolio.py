"""
Portfolio CRUD API Endpoints
Provides REST API for reading, creating, updating, and deleting portfolio holdings.
Simplified schema (Story 3.3): 8 columns (id, user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated)
"""

from typing import List, Optional
from datetime import datetime
import logging

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from fastapi.responses import JSONResponse

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.services.portfolio_service import normalize_ticker

logger = logging.getLogger("agentic_memories.portfolio_api")

router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


# Pydantic models for request/response validation
class HoldingResponse(BaseModel):
    """Response model for a single portfolio holding"""

    ticker: Optional[str] = None
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    first_acquired: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class PortfolioResponse(BaseModel):
    """Response model for complete portfolio"""

    user_id: str
    holdings: List[HoldingResponse]
    total_holdings: int
    last_updated: Optional[datetime] = None


class AddHoldingRequest(BaseModel):
    """Request model for adding a portfolio holding"""

    user_id: str
    ticker: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None


class UpdateHoldingRequest(BaseModel):
    """Request model for updating a portfolio holding (Story 3.4)"""

    user_id: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None


class HoldingCreateResponse(BaseModel):
    """Response model for holding create/update operations"""

    id: str
    ticker: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    first_acquired: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    created: bool  # True if new record, False if updated existing


class HoldingUpdateResponse(BaseModel):
    """Response model for holding update operations (Story 3.4)"""

    ticker: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    first_acquired: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class HoldingDeleteResponse(BaseModel):
    """Response model for holding delete operations (Story 3.5)"""

    deleted: bool
    ticker: str


class PortfolioClearResponse(BaseModel):
    """Response model for clearing entire portfolio (Story 3.6)"""

    deleted: bool
    holdings_removed: int


@router.get("", response_model=PortfolioResponse)
def get_portfolio(
    user_id: str = Query(..., description="User identifier"),
) -> PortfolioResponse:
    """
    Get all portfolio holdings for a user.

    Returns all holdings with ticker, asset_name, shares, avg_price, and timestamps.
    Returns empty array if user has no holdings.
    """
    logger.info("[portfolio.api.get] user_id=%s", user_id)

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
                """
                SELECT ticker, asset_name, shares, avg_price, first_acquired, last_updated
                FROM portfolio_holdings
                WHERE user_id = %s
                ORDER BY ticker ASC NULLS LAST, asset_name ASC
            """,
                (user_id,),
            )

            rows = cur.fetchall()

            holdings = []
            latest_updated = None

            for row in rows:
                # Handle both dict and tuple cursor results (psycopg3 compatibility)
                if isinstance(row, dict):
                    holding = HoldingResponse(
                        ticker=row.get("ticker"),
                        asset_name=row.get("asset_name"),
                        shares=float(row["shares"])
                        if row.get("shares") is not None
                        else None,
                        avg_price=float(row["avg_price"])
                        if row.get("avg_price") is not None
                        else None,
                        first_acquired=row.get("first_acquired"),
                        last_updated=row.get("last_updated"),
                    )
                    row_updated = row.get("last_updated")
                else:
                    # Tuple: (ticker, asset_name, shares, avg_price, first_acquired, last_updated)
                    holding = HoldingResponse(
                        ticker=row[0],
                        asset_name=row[1],
                        shares=float(row[2]) if row[2] is not None else None,
                        avg_price=float(row[3]) if row[3] is not None else None,
                        first_acquired=row[4],
                        last_updated=row[5],
                    )
                    row_updated = row[5]

                holdings.append(holding)

                # Track latest updated timestamp
                if row_updated is not None:
                    if latest_updated is None or row_updated > latest_updated:
                        latest_updated = row_updated

            logger.info(
                "[portfolio.api.get] user_id=%s holdings_count=%d",
                user_id,
                len(holdings),
            )

            return PortfolioResponse(
                user_id=user_id,
                holdings=holdings,
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
    Add or update a portfolio holding.

    Creates a new holding if one doesn't exist for user_id + ticker.
    Updates the existing holding if it already exists (UPSERT behavior).
    Returns 201 for new holding, 200 for update.
    """
    logger.info(
        "[portfolio.api.post] user_id=%s ticker=%s", request.user_id, request.ticker
    )

    # Normalize ticker to uppercase
    normalized_ticker = normalize_ticker(request.ticker)
    if normalized_ticker is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: '{request.ticker}'. Ticker must be 1-10 alphanumeric characters.",
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
            # UPSERT query using ON CONFLICT (simplified schema - Story 3.3)
            # The unique constraint is (user_id, ticker) - one holding per ticker per user
            cur.execute(
                """
                INSERT INTO portfolio_holdings (user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id, ticker)
                DO UPDATE SET
                    asset_name = COALESCE(EXCLUDED.asset_name, portfolio_holdings.asset_name),
                    shares = COALESCE(EXCLUDED.shares, portfolio_holdings.shares),
                    avg_price = COALESCE(EXCLUDED.avg_price, portfolio_holdings.avg_price),
                    last_updated = NOW()
                RETURNING id, ticker, asset_name, shares, avg_price, first_acquired, last_updated,
                          (xmax = 0) AS inserted
            """,
                (
                    request.user_id,
                    normalized_ticker,
                    request.asset_name,
                    request.shares,
                    request.avg_price,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            # Handle both dict and tuple cursor results (psycopg3 compatibility)
            if isinstance(row, dict):
                holding_id = str(row["id"])
                ticker = row["ticker"]
                asset_name = row.get("asset_name")
                shares = float(row["shares"]) if row.get("shares") is not None else None
                avg_price = (
                    float(row["avg_price"])
                    if row.get("avg_price") is not None
                    else None
                )
                first_acquired = row.get("first_acquired")
                last_updated = row.get("last_updated")
                inserted = row["inserted"]
            else:
                # Tuple: (id, ticker, asset_name, shares, avg_price, first_acquired, last_updated, inserted)
                holding_id = str(row[0])
                ticker = row[1]
                asset_name = row[2]
                shares = float(row[3]) if row[3] is not None else None
                avg_price = float(row[4]) if row[4] is not None else None
                first_acquired = row[5]
                last_updated = row[6]
                inserted = row[7]

            response = HoldingCreateResponse(
                id=holding_id,
                ticker=ticker,
                asset_name=asset_name,
                shares=shares,
                avg_price=avg_price,
                first_acquired=first_acquired,
                last_updated=last_updated,
                created=inserted,
            )

            status_code = 201 if inserted else 200
            logger.info(
                "[portfolio.api.post] user_id=%s ticker=%s created=%s",
                request.user_id,
                normalized_ticker,
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


@router.put("/holding/{ticker}", response_model=HoldingUpdateResponse)
def update_holding(ticker: str, request: UpdateHoldingRequest):
    """
    Update an existing portfolio holding (Story 3.4).

    Updates the holding identified by user_id + ticker.
    Returns 404 if holding doesn't exist (unlike POST which creates).
    Supports partial updates - only provided fields are updated.
    """
    logger.info("[portfolio.api.put] user_id=%s ticker=%s", request.user_id, ticker)

    # Normalize ticker to uppercase (AC2)
    normalized_ticker = normalize_ticker(ticker)
    if normalized_ticker is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: '{ticker}'. Ticker must be 1-10 alphanumeric characters.",
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
            # Step 1: Check if holding exists (AC4)
            cur.execute(
                """
                SELECT id FROM portfolio_holdings
                WHERE user_id = %s AND ticker = %s
            """,
                (request.user_id, normalized_ticker),
            )

            existing = cur.fetchone()
            if existing is None:
                logger.info(
                    "[portfolio.api.put] user_id=%s ticker=%s not_found",
                    request.user_id,
                    normalized_ticker,
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Holding not found for user '{request.user_id}' and ticker '{normalized_ticker}'",
                )

            # Step 2: Update with COALESCE for partial updates (AC1, AC3, AC6)
            cur.execute(
                """
                UPDATE portfolio_holdings
                SET
                    asset_name = COALESCE(%s, asset_name),
                    shares = COALESCE(%s, shares),
                    avg_price = COALESCE(%s, avg_price),
                    last_updated = NOW()
                WHERE user_id = %s AND ticker = %s
                RETURNING ticker, asset_name, shares, avg_price, first_acquired, last_updated
            """,
                (
                    request.asset_name,
                    request.shares,
                    request.avg_price,
                    request.user_id,
                    normalized_ticker,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            # Handle both dict and tuple cursor results (psycopg3 compatibility)
            if isinstance(row, dict):
                response = HoldingUpdateResponse(
                    ticker=row["ticker"],
                    asset_name=row.get("asset_name"),
                    shares=float(row["shares"])
                    if row.get("shares") is not None
                    else None,
                    avg_price=float(row["avg_price"])
                    if row.get("avg_price") is not None
                    else None,
                    first_acquired=row.get("first_acquired"),
                    last_updated=row.get("last_updated"),
                )
            else:
                # Tuple: (ticker, asset_name, shares, avg_price, first_acquired, last_updated)
                response = HoldingUpdateResponse(
                    ticker=row[0],
                    asset_name=row[1],
                    shares=float(row[2]) if row[2] is not None else None,
                    avg_price=float(row[3]) if row[3] is not None else None,
                    first_acquired=row[4],
                    last_updated=row[5],
                )

            logger.info(
                "[portfolio.api.put] user_id=%s ticker=%s updated",
                request.user_id,
                normalized_ticker,
            )

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[portfolio.api.put] user_id=%s ticker=%s error=%s",
            request.user_id,
            ticker,
            str(e),
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating holding: {str(e)}")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


@router.delete("/holding/{ticker}", response_model=HoldingDeleteResponse)
def delete_holding(
    ticker: str, user_id: str = Query(..., description="User identifier")
):
    """
    Delete a portfolio holding (Story 3.5).

    Deletes the holding identified by user_id + ticker.
    Returns 404 if holding doesn't exist.
    Returns confirmation with deleted ticker on success.
    """
    logger.info("[portfolio.api.delete] user_id=%s ticker=%s", user_id, ticker)

    # Normalize ticker to uppercase (AC2)
    normalized_ticker = normalize_ticker(ticker)
    if normalized_ticker is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: '{ticker}'. Ticker must be 1-10 alphanumeric characters.",
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
            # Use DELETE RETURNING pattern for efficiency (AC1, AC3, AC4)
            # If RETURNING returns nothing, the holding didn't exist
            cur.execute(
                """
                DELETE FROM portfolio_holdings
                WHERE user_id = %s AND ticker = %s
                RETURNING ticker
            """,
                (user_id, normalized_ticker),
            )

            row = cur.fetchone()

            if row is None:
                logger.info(
                    "[portfolio.api.delete] user_id=%s ticker=%s not_found",
                    user_id,
                    normalized_ticker,
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Holding not found for user '{user_id}' and ticker '{normalized_ticker}'",
                )

            conn.commit()

            # Handle both dict and tuple cursor results (psycopg3 compatibility)
            if isinstance(row, dict):
                deleted_ticker = row["ticker"]
            else:
                # Tuple: (ticker,)
                deleted_ticker = row[0]

            logger.info(
                "[portfolio.api.delete] user_id=%s ticker=%s deleted",
                user_id,
                normalized_ticker,
            )

            return HoldingDeleteResponse(deleted=True, ticker=deleted_ticker)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[portfolio.api.delete] user_id=%s ticker=%s error=%s",
            user_id,
            ticker,
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
