"""Tests for portfolio summary endpoint."""

import json
from unittest.mock import patch


@patch("src.app.search_memories")
def test_portfolio_summary_basic(mock_search, api_client):
    """Test basic portfolio summary with mocked data."""
    # Mock search results with portfolio metadata
    mock_search.return_value = (
        [
            {
                "id": "mem_001",
                "content": "User bought 100 shares of AAPL at $150",
                "metadata": {
                    "portfolio": json.dumps({
                        "ticker": "AAPL",
                        "shares": 100,
                        "avg_price": 150.0,
                        "intent": "hold"
                    })
                }
            },
            {
                "id": "mem_002",
                "content": "User owns 50 shares of TSLA",
                "metadata": {
                    "portfolio": json.dumps({
                        "ticker": "TSLA",
                        "shares": 50,
                        "avg_price": 200.0,
                        "position": "long"
                    })
                }
            }
        ],
        2
    )
    
    response = api_client.get("/v1/portfolio/summary?user_id=test_user")
    assert response.status_code == 200
    
    data = response.json()
    assert data["user_id"] == "test_user"
    assert len(data["holdings"]) == 2
    
    # Check first holding
    aapl_holding = next((h for h in data["holdings"] if h["ticker"] == "AAPL"), None)
    assert aapl_holding is not None
    assert aapl_holding["shares"] == 100
    assert aapl_holding["avg_price"] == 150.0
    
    # Check second holding
    tsla_holding = next((h for h in data["holdings"] if h["ticker"] == "TSLA"), None)
    assert tsla_holding is not None
    assert tsla_holding["shares"] == 50
    assert tsla_holding["avg_price"] == 200.0
    
    # Check counts by asset type
    assert "public_equity" in data["counts_by_asset_type"]
    assert data["counts_by_asset_type"]["public_equity"] == 2


@patch("src.app.search_memories")
def test_portfolio_summary_with_private_equity(mock_search, api_client):
    """Test portfolio summary with private equity holdings."""
    mock_search.return_value = (
        [
            {
                "id": "mem_003",
                "content": "User has investment in startup",
                "metadata": {
                    "portfolio": json.dumps({
                        "holdings": [
                            {
                                "asset_type": "private_equity",
                                "name": "AcmeAI",
                                "ownership_pct": 5.0,
                                "notes": "Early stage startup"
                            },
                            {
                                "asset_type": "public_equity",
                                "ticker": "GOOGL",
                                "shares": 25,
                                "avg_price": 140.0
                            }
                        ]
                    })
                }
            }
        ],
        1
    )
    
    response = api_client.get("/v1/portfolio/summary?user_id=test_user")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["holdings"]) == 2
    
    # Check private equity holding
    private_holding = next((h for h in data["holdings"] if h["name"] == "AcmeAI"), None)
    assert private_holding is not None
    assert private_holding["asset_type"] == "private_equity"
    assert private_holding["ownership_pct"] == 5.0
    
    # Check public equity holding
    public_holding = next((h for h in data["holdings"] if h["ticker"] == "GOOGL"), None)
    assert public_holding is not None
    assert public_holding["shares"] == 25
    
    # Check counts
    assert data["counts_by_asset_type"]["private_equity"] == 1
    assert data["counts_by_asset_type"]["public_equity"] == 1


@patch("src.app.search_memories")
def test_portfolio_summary_empty(mock_search, api_client):
    """Test portfolio summary with no holdings."""
    mock_search.return_value = ([], 0)
    
    response = api_client.get("/v1/portfolio/summary?user_id=test_user")
    assert response.status_code == 200
    
    data = response.json()
    assert data["user_id"] == "test_user"
    assert len(data["holdings"]) == 0
    assert len(data["counts_by_asset_type"]) == 0


@patch("src.app.search_memories")
def test_portfolio_summary_with_limit(mock_search, api_client):
    """Test portfolio summary with limit parameter."""
    # Mock more holdings than the limit
    holdings = []
    for i in range(10):
        holdings.append({
            "id": f"mem_{i:03d}",
            "content": f"Holding {i}",
            "metadata": {
                "portfolio": json.dumps({
                    "ticker": f"TICK{i}",
                    "shares": 10 * (i + 1)
                })
            }
        })
    
    mock_search.return_value = (holdings[:5], 5)  # Return only 5 items
    
    response = api_client.get("/v1/portfolio/summary?user_id=test_user&limit=5")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["holdings"]) <= 5


@patch("src.app.search_memories")
def test_portfolio_summary_mixed_formats(mock_search, api_client):
    """Test portfolio summary with mixed metadata formats."""
    mock_search.return_value = (
        [
            {
                "id": "mem_004",
                "content": "Portfolio item 1",
                "metadata": {
                    # Already parsed portfolio object (not JSON string)
                    "portfolio": {
                        "ticker": "NVDA",
                        "shares": 75,
                        "intent": "buy"
                    }
                }
            },
            {
                "id": "mem_005",
                "content": "Portfolio item 2",
                "metadata": {
                    # JSON string format
                    "portfolio": json.dumps({
                        "ticker": "AMZN",
                        "shares": 30
                    })
                }
            },
            {
                "id": "mem_006",
                "content": "No portfolio metadata",
                "metadata": {}  # No portfolio field
            }
        ],
        3
    )
    
    response = api_client.get("/v1/portfolio/summary?user_id=test_user")
    assert response.status_code == 200
    
    data = response.json()
    # Should have 2 holdings (skipping the one without portfolio metadata)
    assert len(data["holdings"]) == 2
    
    tickers = [h["ticker"] for h in data["holdings"]]
    assert "NVDA" in tickers
    assert "AMZN" in tickers


def test_portfolio_summary_missing_user_id(api_client):
    """Test portfolio summary without required user_id parameter."""
    response = api_client.get("/v1/portfolio/summary")
    assert response.status_code == 422  # Validation error
