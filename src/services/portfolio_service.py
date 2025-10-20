"""
Portfolio Service

Manages structured portfolio holdings, transactions, and preferences
with time-series snapshots and graph relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from psycopg import Connection

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.dependencies.neo4j_client import get_neo4j_driver


@dataclass
class PortfolioHolding:
    """Portfolio holding model"""
    user_id: str
    ticker: Optional[str]
    asset_name: Optional[str]
    asset_type: str
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    cost_basis: Optional[float] = None
    ownership_pct: Optional[float] = None
    position: Optional[str] = None
    intent: Optional[str] = None
    time_horizon: Optional[str] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
    source_memory_id: Optional[str] = None
    id: Optional[str] = None


class PortfolioService:
    """Service for managing portfolio holdings and financial tracking"""

    def __init__(self):
        self.neo4j_driver = get_neo4j_driver()

    def upsert_holding_from_memory(self, user_id: str, portfolio_metadata: Dict[str, Any], memory_id: str) -> Optional[str]:
        """
        Upsert portfolio holding from memory metadata
        
        Args:
            user_id: User ID
            portfolio_metadata: Portfolio dict from memory extraction
            memory_id: Source memory ID
            
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
            # Extract base portfolio data
            ticker = portfolio_metadata.get('ticker')
            intent = portfolio_metadata.get('intent')
            
            # Check if this is a holdings array (portfolio snapshot)
            holdings_array = portfolio_metadata.get('holdings')
            if holdings_array and isinstance(holdings_array, list):
                # Process each holding in the snapshot
                for holding_data in holdings_array:
                    self._upsert_single_holding(conn, user_id, holding_data, memory_id)
                end_span(output={"holding_id": None, "success": True, "processed_multiple": True})
                return None  # Multiple holdings processed

            # Single holding case
            holding = PortfolioHolding(
                user_id=user_id,
                ticker=ticker,
                asset_name=portfolio_metadata.get('name'),
                asset_type=portfolio_metadata.get('asset_type', 'public_equity' if ticker else 'other'),
                shares=portfolio_metadata.get('shares'),
                avg_price=portfolio_metadata.get('avg_price'),
                current_value=portfolio_metadata.get('current_value'),
                cost_basis=portfolio_metadata.get('cost_basis'),
                ownership_pct=portfolio_metadata.get('ownership_pct'),
                position=portfolio_metadata.get('position', 'long'),
                intent=intent,
                time_horizon=portfolio_metadata.get('time_horizon'),
                target_price=portfolio_metadata.get('target_price'),
                stop_loss=portfolio_metadata.get('stop_loss'),
                notes=portfolio_metadata.get('notes') or portfolio_metadata.get('concern') or portfolio_metadata.get('goal'),
                source_memory_id=memory_id
            )

            result = self._upsert_single_holding(conn, user_id, holding.__dict__, memory_id)
            end_span(output={"holding_id": result, "success": bool(result)})
            return result

        except Exception as e:
            print(f"Error upserting portfolio holding: {e}")
            end_span(output={"success": False, "error": str(e)}, level="ERROR")
            return None
        finally:
            release_timescale_conn(conn)

    def _upsert_single_holding(self, conn: Connection, user_id: str, holding_data: Dict[str, Any], memory_id: str) -> Optional[str]:
        """Insert or update a single holding"""
        if not conn:
            return None

        try:
            ticker = holding_data.get('ticker')
            asset_name = holding_data.get('asset_name') or holding_data.get('name')
            
            # For watch-list items or intents without shares, create a placeholder holding
            if not holding_data.get('shares') and holding_data.get('intent') == 'watch':
                holding_data['shares'] = None
                holding_data['asset_type'] = holding_data.get('asset_type', 'public_equity' if ticker else 'other')
            
            with conn.cursor() as cur:
                # Check if holding exists (by user_id + ticker/asset_name)
                if ticker:
                    cur.execute("""
                        SELECT id FROM portfolio_holdings
                        WHERE user_id = %s AND ticker = %s
                        LIMIT 1
                    """, (user_id, ticker))
                elif asset_name:
                    cur.execute("""
                        SELECT id FROM portfolio_holdings
                        WHERE user_id = %s AND asset_name = %s
                        LIMIT 1
                    """, (user_id, asset_name))
                else:
                    return None  # Can't identify holding
                
                existing = cur.fetchone()
                
                if existing:
                    # Update existing holding
                    holding_id = existing['id']
                    cur.execute("""
                        UPDATE portfolio_holdings
                        SET 
                            shares = COALESCE(%s, shares),
                            avg_price = COALESCE(%s, avg_price),
                            current_price = COALESCE(%s, current_price),
                            current_value = COALESCE(%s, current_value),
                            cost_basis = COALESCE(%s, cost_basis),
                            ownership_pct = COALESCE(%s, ownership_pct),
                            position = COALESCE(%s, position),
                            intent = COALESCE(%s, intent),
                            time_horizon = COALESCE(%s, time_horizon),
                            target_price = COALESCE(%s, target_price),
                            stop_loss = COALESCE(%s, stop_loss),
                            notes = COALESCE(%s, notes),
                            last_updated = NOW(),
                            source_memory_id = %s
                        WHERE id = %s
                    """, (
                        holding_data.get('shares'),
                        holding_data.get('avg_price'),
                        holding_data.get('current_price'),
                        holding_data.get('current_value'),
                        holding_data.get('cost_basis'),
                        holding_data.get('ownership_pct'),
                        holding_data.get('position'),
                        holding_data.get('intent'),
                        holding_data.get('time_horizon'),
                        holding_data.get('target_price'),
                        holding_data.get('stop_loss'),
                        holding_data.get('notes'),
                        memory_id,
                        holding_id
                    ))
                else:
                    # Insert new holding
                    holding_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO portfolio_holdings (
                            id, user_id, ticker, asset_name, asset_type,
                            shares, avg_price, current_price, current_value, cost_basis,
                            ownership_pct, position, intent, time_horizon,
                            target_price, stop_loss, notes, source_memory_id,
                            first_acquired, last_updated
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            NOW(), NOW()
                        )
                    """, (
                        holding_id, user_id,
                        ticker, asset_name,
                        holding_data.get('asset_type', 'public_equity' if ticker else 'other'),
                        holding_data.get('shares'),
                        holding_data.get('avg_price'),
                        holding_data.get('current_price'),
                        holding_data.get('current_value'),
                        holding_data.get('cost_basis'),
                        holding_data.get('ownership_pct'),
                        holding_data.get('position', 'long'),
                        holding_data.get('intent'),
                        holding_data.get('time_horizon'),
                        holding_data.get('target_price'),
                        holding_data.get('stop_loss'),
                        holding_data.get('notes'),
                        memory_id
                    ))

                # Commit the transaction
                conn.commit()

                # Create Neo4j node and relationships (async, fire-and-forget)
                self._create_holding_graph_node(holding_id, user_id, ticker, asset_name)

                return holding_id

        except Exception as e:
            # Rollback on error
            if conn:
                conn.rollback()
            print(f"Error in _upsert_single_holding: {e}")
            return None

    def _create_holding_graph_node(self, holding_id: str, user_id: str, ticker: Optional[str], asset_name: Optional[str]) -> None:
        """Create Neo4j node for holding (non-blocking)"""
        if not self.neo4j_driver or not (ticker or asset_name):
            return
        
        try:
            with self.neo4j_driver.session() as session:
                session.run("""
                    MERGE (h:Holding {id: $holding_id})
                    SET h.user_id = $user_id,
                        h.ticker = $ticker,
                        h.asset_name = $asset_name,
                        h.updated_at = datetime()
                """, {
                    "holding_id": holding_id,
                    "user_id": user_id,
                    "ticker": ticker,
                    "asset_name": asset_name
                })
        except Exception as e:
            print(f"Error creating holding graph node: {e}")
    
    def get_holdings(self, user_id: str, intent_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve current holdings for a user
        
        Args:
            user_id: User ID
            intent_filter: Optional filter by intent ('buy', 'sell', 'hold', 'watch')
            
        Returns:
            List of holding dictionaries
        """
        conn = get_timescale_conn()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                if intent_filter:
                    cur.execute("""
                        SELECT * FROM portfolio_holdings
                        WHERE user_id = %s AND intent = %s
                        ORDER BY last_updated DESC
                    """, (user_id, intent_filter))
                else:
                    cur.execute("""
                        SELECT * FROM portfolio_holdings
                        WHERE user_id = %s
                        ORDER BY last_updated DESC
                    """, (user_id,))
                
                rows = cur.fetchall()
                conn.commit()
                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error retrieving holdings: {e}")
            if conn:
                conn.rollback()
            return []
        finally:
            release_timescale_conn(conn)

    def create_snapshot(self, user_id: str) -> bool:
        """
        Create a portfolio value snapshot
        
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
            
            total_value = sum(h.get('current_value', 0) or 0 for h in holdings)
            cash_value = sum(h.get('current_value', 0) or 0 for h in holdings if h.get('asset_type') == 'cash')
            equity_value = sum(h.get('current_value', 0) or 0 for h in holdings if h.get('asset_type') in ('public_equity', 'private_equity', 'etf', 'mutual_fund'))
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolio_snapshots (
                        user_id, snapshot_timestamp, total_value,
                        cash_value, equity_value, holdings_snapshot
                    ) VALUES (%s, NOW(), %s, %s, %s, %s)
                """, (
                    user_id, total_value, cash_value, equity_value,
                    holdings  # Store full holdings JSON
                ))

            # Commit the transaction
            conn.commit()
            return True

        except Exception as e:
            print(f"Error creating portfolio snapshot: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            release_timescale_conn(conn)

