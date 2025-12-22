"""
Portfolio Service

Manages structured portfolio holdings for public equities.
Simplified schema (Story 3.3): 8 columns (id, user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated)
"""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from psycopg import Connection

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

logger = logging.getLogger(__name__)

# Ticker validation: 1-10 uppercase alphanumeric + dots (for BRK.B style)
TICKER_PATTERN = re.compile(r'^[A-Z0-9\.]{1,10}$')


def normalize_ticker(ticker: Optional[str]) -> Optional[str]:
    """Normalize ticker to uppercase and validate format."""
    if not ticker:
        return None

    normalized = ticker.upper().strip()

    if not normalized:
        return None

    if not TICKER_PATTERN.match(normalized):
        logger.warning("Invalid ticker format rejected: %s", ticker)
        return None

    return normalized


def validate_positive_float(value: Any, field_name: str, allow_zero: bool = False) -> Optional[float]:
    """Validate and convert numeric field to positive float."""
    if value is None:
        return None

    try:
        float_val = float(value)

        if allow_zero and float_val >= 0:
            return float_val
        elif not allow_zero and float_val > 0:
            return float_val
        else:
            logger.warning("Non-positive %s value rejected: %s", field_name, value)
            return None
    except (ValueError, TypeError):
        logger.warning("Invalid numeric %s value rejected: %s", field_name, value)
        return None


@dataclass
class PortfolioHolding:
    """Simplified portfolio holding model (Story 3.3)"""
    user_id: str
    ticker: str
    asset_name: Optional[str] = None
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    id: Optional[str] = None


class PortfolioService:
    """Service for managing portfolio holdings and financial tracking"""

    def __init__(self):
        pass

    def upsert_holding_from_memory(self, user_id: str, portfolio_metadata: Dict[str, Any], memory_id: str) -> Optional[str]:
        """
        Upsert portfolio holding from memory metadata (simplified schema - Story 3.3)

        Args:
            user_id: User ID
            portfolio_metadata: Portfolio dict from memory extraction
            memory_id: Source memory ID (not stored, used for logging)

        Returns:
            Holding ID if successful, None otherwise
        """
        from src.services.tracing import start_span, end_span

        span = start_span("portfolio_upsert",
                         input={"ticker": portfolio_metadata.get("ticker") if portfolio_metadata else None})

        if not portfolio_metadata or not isinstance(portfolio_metadata, dict):
            end_span(output={"success": False, "reason": "invalid_metadata"})
            return None

        conn = get_timescale_conn()
        if not conn:
            end_span(output={"success": False, "reason": "timescale_unavailable"})
            return None

        try:
            # Check if this is a holdings array (portfolio snapshot)
            holdings_array = portfolio_metadata.get('holdings')
            if holdings_array and isinstance(holdings_array, list):
                # Process each holding in the snapshot
                for holding_data in holdings_array:
                    self._upsert_single_holding(conn, user_id, holding_data, memory_id)
                end_span(output={"holding_id": None, "success": True, "processed_multiple": True})
                return None  # Multiple holdings processed

            # Extract and validate ticker (required for simplified schema)
            ticker = normalize_ticker(portfolio_metadata.get('ticker'))
            if not ticker:
                logger.warning("Portfolio holding rejected: missing or invalid ticker")
                end_span(output={"success": False, "reason": "missing_ticker"})
                return None

            # Extract asset_name (optional)
            asset_name = portfolio_metadata.get('name') or portfolio_metadata.get('asset_name')
            if asset_name:
                asset_name = str(asset_name).strip() or None

            # Validate numeric fields (handle alternate field names from extraction)
            shares = validate_positive_float(
                portfolio_metadata.get('shares') or portfolio_metadata.get('quantity'),
                'shares'
            )
            avg_price = validate_positive_float(
                portfolio_metadata.get('avg_price') or portfolio_metadata.get('price'),
                'avg_price'
            )

            # Build holding data
            holding_data = {
                'ticker': ticker,
                'asset_name': asset_name,
                'shares': shares,
                'avg_price': avg_price
            }

            result = self._upsert_single_holding(conn, user_id, holding_data, memory_id)
            end_span(output={"holding_id": result, "success": bool(result)})
            return result

        except Exception as e:
            logger.error("Error upserting portfolio holding: %s", e)
            end_span(output={"success": False, "error": str(e)}, level="ERROR")
            return None
        finally:
            release_timescale_conn(conn)

    def _upsert_single_holding(self, conn: Connection, user_id: str, holding_data: Dict[str, Any], memory_id: str) -> Optional[str]:
        """Insert or update a single holding (simplified schema - Story 3.3)"""
        if not conn:
            return None

        try:
            # Validate and normalize ticker (required)
            ticker = normalize_ticker(holding_data.get('ticker'))
            if not ticker:
                logger.warning("Holding rejected in _upsert_single_holding: missing ticker")
                return None

            # Extract asset_name (optional)
            asset_name = holding_data.get('asset_name') or holding_data.get('name')
            if asset_name:
                asset_name = str(asset_name).strip() or None

            # Validate numeric fields
            shares = validate_positive_float(
                holding_data.get('shares') or holding_data.get('quantity'),
                'shares'
            )
            avg_price = validate_positive_float(
                holding_data.get('avg_price') or holding_data.get('price'),
                'avg_price'
            )

            with conn.cursor() as cur:
                # Use ON CONFLICT for upsert (unique constraint on user_id, ticker)
                holding_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO portfolio_holdings (
                        id, user_id, ticker, asset_name, shares, avg_price,
                        first_acquired, last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    ON CONFLICT (user_id, ticker)
                    DO UPDATE SET
                        asset_name = COALESCE(EXCLUDED.asset_name, portfolio_holdings.asset_name),
                        shares = COALESCE(EXCLUDED.shares, portfolio_holdings.shares),
                        avg_price = COALESCE(EXCLUDED.avg_price, portfolio_holdings.avg_price),
                        last_updated = NOW()
                    RETURNING id
                """, (
                    holding_id, user_id, ticker, asset_name, shares, avg_price
                ))

                result = cur.fetchone()
                if result:
                    holding_id = result['id'] if isinstance(result, dict) else result[0]
                    logger.debug("Upserted holding %s for user %s ticker=%s", holding_id, user_id, ticker)

                # Commit the transaction
                conn.commit()

                return holding_id

        except Exception as e:
            # Rollback on error
            if conn:
                conn.rollback()
            logger.error("Error in _upsert_single_holding: %s", e)
            return None

    def get_holdings(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve current holdings for a user (simplified schema - Story 3.3)

        Args:
            user_id: User ID

        Returns:
            List of holding dictionaries with: id, ticker, asset_name, shares, avg_price, first_acquired, last_updated
        """
        conn = get_timescale_conn()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, ticker, asset_name, shares, avg_price, first_acquired, last_updated
                    FROM portfolio_holdings
                    WHERE user_id = %s
                    ORDER BY ticker ASC
                """, (user_id,))

                rows = cur.fetchall()
                conn.commit()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error("Error retrieving holdings: %s", e)
            if conn:
                conn.rollback()
            return []
        finally:
            release_timescale_conn(conn)

    def create_snapshot(self, user_id: str) -> bool:
        """
        Create a portfolio value snapshot (simplified - Story 3.3)

        Note: With simplified schema, current_value is no longer stored per-holding.
        This method creates a basic snapshot for future value tracking integration.

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        conn = get_timescale_conn()
        if not conn:
            return False

        try:
            holdings = self.get_holdings(user_id)

            # With simplified schema, we don't have current_value
            # Calculate estimated value if shares and avg_price are available
            estimated_value = sum(
                (h.get('shares', 0) or 0) * (h.get('avg_price', 0) or 0)
                for h in holdings
            )

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolio_snapshots (
                        user_id, snapshot_timestamp, total_value,
                        cash_value, equity_value, holdings_snapshot
                    ) VALUES (%s, NOW(), %s, %s, %s, %s)
                """, (
                    user_id, estimated_value, 0.0, estimated_value,
                    holdings  # Store full holdings JSON
                ))

            conn.commit()
            return True

        except Exception as e:
            logger.error("Error creating portfolio snapshot: %s", e)
            if conn:
                conn.rollback()
            return False
        finally:
            release_timescale_conn(conn)

