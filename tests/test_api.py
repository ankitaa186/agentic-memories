from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.app import app
from src.services.prompts import EXTRACTION_PROMPT
from tests.fixtures.chroma_mock import create_mock_v2_chroma_client
from src.services.persona_retrieval import PersonaRetrievalResult


client = TestClient(app)


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


def test_retrieve_stub():
    """Retrieve endpoint returns mocked search results."""
    from src.services.retrieval import search_memories
    
    def mock_search_memories(user_id: str, query: str, filters=None, limit=10, offset=0):
        # Return mock results
        mock_results = [
            {
                "id": "mem_1",
                "content": "User loves sci-fi books.",
                "layer": "semantic",
                "type": "explicit",
                "score": 0.9,
                "metadata": {"tags": ["behavior"]}
            }
        ]
        return mock_results, 1
    
    with patch('src.app.search_memories', side_effect=mock_search_memories):
        resp = client.get("/v1/retrieve", params={"query": "sci-fi", "limit": 5, "user_id": "user-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data and isinstance(data["results"], list)
        assert "pagination" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "User loves sci-fi books."


def test_persona_post_endpoint(monkeypatch):
    """Test the persona retrieval POST endpoint."""
    mock_result = PersonaRetrievalResult(
        persona="identity",
        items=[{
            "id": "mem_42",
            "content": "User started journaling.",
            "score": 0.8,
            "metadata": {"layer": "semantic", "type": "explicit"},
        }],
        weight_profile={"semantic": 0.5, "temporal": 0.3, "importance": 0.2},
        source="hybrid",
        summaries=[{"id": "sum1", "text": "Summary"}],
    )

    monkeypatch.setattr("src.app._persona_copilot.retrieve", lambda **kwargs: {"identity": mock_result})

    class DummyState:
        def __init__(self, user_id: str):
            self.user_id = user_id
            self.updated_at = datetime.now(timezone.utc)

    monkeypatch.setattr("src.app._persona_copilot.state_store.get_state", lambda user_id: DummyState(user_id))
    monkeypatch.setattr("src.app._reconstruction.build_narrative", lambda **kwargs: type("N", (), {"text": "Story"}))

    payload = {
        "user_id": "user-abc",
        "query": "journaling",
        "limit": 1,
        "offset": 0,
        "include_narrative": True,
        "explain": True,
    }

    resp = client.post("/v1/retrieve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["persona"]["selected"] == "identity"
    assert data["results"]["narrative"] == "Story"
    assert data["results"]["memories"][0]["content"] == "User started journaling."
    assert data["explainability"]["weights"]["semantic"] == 0.5


def test_health_full_structure(api_client):
    """Test health endpoint returns full structure."""
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

