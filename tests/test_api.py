from unittest.mock import patch

from src.services.prompts import EXTRACTION_PROMPT


def test_store_stub(api_client):
    """Store endpoint responds with 400 when LLM provider is not configured."""
    payload = {
        "user_id": "user-123",
        "history": [{"role": "user", "content": "I love sci-fi books."}],
    }
    with patch('src.app.is_llm_configured', return_value=False):
        resp = api_client.post("/v1/store", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"] == "LLM is not configured"
    assert "ids" not in data


def test_retrieve_stub(api_client):
    """Retrieve endpoint returns mocked search results."""
    from src.services.retrieval import search_memories

    def mock_search_memories(user_id: str, query: str, filters=None, limit=10, offset=0):
        mock_results = [
            {
                "id": "mem_1",
                "content": "User loves sci-fi books.",
                "layer": "semantic",
                "type": "explicit",
                "score": 0.9,
                "metadata": {"tags": ["behavior"]},
            }
        ]
        return mock_results, 1

    with patch('src.app.search_memories', side_effect=mock_search_memories):
        resp = api_client.get("/v1/retrieve", params={"query": "sci-fi", "limit": 5, "user_id": "user-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data and isinstance(data["results"], list)
        assert "pagination" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "User loves sci-fi books."


def test_health_full_structure(api_client):
    resp = api_client.get("/health/full")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data and isinstance(data["checks"], dict)


def test_extraction_prompt_normalization_rules():
    """Test that the extraction prompt includes comprehensive normalization rules."""
    assert "**Rule 1: NORMALIZATION**" in EXTRACTION_PROMPT
    assert "User loves sci-fi books." in EXTRACTION_PROMPT
    assert "DON'T: \"I love sci-fi\"" in EXTRACTION_PROMPT
    assert "Split compound statements" in EXTRACTION_PROMPT
    assert "Rule 3: DEDUPLICATION" in EXTRACTION_PROMPT
    assert "Rule 4: LAYER ASSIGNMENT" in EXTRACTION_PROMPT

