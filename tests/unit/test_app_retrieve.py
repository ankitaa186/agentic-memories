from src.services.persona_retrieval import PersonaRetrievalResult


def test_retrieve_uses_persona_results(api_client, monkeypatch):
    persona_result = PersonaRetrievalResult(
        persona="identity",
        items=[
            {
                "id": "mem-1",
                "content": "Call mom",
                "score": 0.9,
                "metadata": {
                    "layer": "semantic",
                    "type": "explicit",
                    "persona_tags": ["identity"],
                    "emotional_signature": {"mood": "calm"},
                    "importance": 0.7,
                },
            }
        ],
        weight_profile={"semantic": 0.5},
        source="hybrid",
    )

    monkeypatch.setattr("src.app._persona_copilot.retrieve", lambda **_: {"identity": persona_result})
    search_stub = lambda **_: (_ for _ in ()).throw(AssertionError("search_memories should not be called"))
    monkeypatch.setattr("src.app.search_memories", search_stub)
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get("/v1/retrieve", params={"user_id": "user-123", "query": "call"})
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["total"] == 1
    assert data["results"][0]["persona_tags"] == ["identity"]
    assert data["results"][0]["emotional_signature"] == {"mood": "calm"}
    assert data["results"][0]["importance"] == 0.7


def test_retrieve_falls_back_to_semantic_search(api_client, monkeypatch):
    monkeypatch.setattr("src.app._persona_copilot.retrieve", lambda **_: {})

    fallback_items = [
        {
            "id": "mem-42",
            "content": "Review quarterly goals",
            "score": 0.8,
            "metadata": {
                "layer": "semantic",
                "type": "explicit",
                "persona_tags": ["identity"],
            },
        }
    ]
    monkeypatch.setattr("src.app.search_memories", lambda **_: (fallback_items, 1))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get("/v1/retrieve", params={"user_id": "user-123", "query": "goals", "limit": 1})
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["total"] == 1
    assert data["results"][0]["id"] == "mem-42"
    assert data["results"][0]["layer"] == "semantic"
