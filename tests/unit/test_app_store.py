from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_store_transcript_requires_llm_configuration(api_client, monkeypatch):
    monkeypatch.setattr("src.app.is_llm_configured", lambda: False)

    payload = {"user_id": "user-123", "history": [{"role": "user", "content": "hi"}]}
    response = api_client.post("/v1/store", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "LLM is not configured"


def test_store_transcript_returns_summary_and_updates_cache(
    api_client, monkeypatch, redis_stub
):
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    memories = [
        SimpleNamespace(
            content="Call mom",
            layer="semantic",
            type="explicit",
            confidence=0.95,
            ttl=None,
            timestamp=timestamp,
            metadata={"layer": "semantic", "type": "explicit"},
        ),
        SimpleNamespace(
            content="Review goals",
            layer="semantic",
            type="explicit",
            confidence=0.88,
            ttl=None,
            timestamp=timestamp,
            metadata={"layer": "semantic", "type": "explicit"},
        ),
    ]
    final_state = {
        "memories": memories,
        "memory_ids": ["mem-1", "mem-2"],
        "storage_results": {"episodic_stored": 1, "procedural_stored": 1},
        "existing_memories": ["mem-old"],
    }

    run_unified_ingestion = MagicMock(return_value=final_state)
    monkeypatch.setattr(
        "src.services.unified_ingestion_graph.run_unified_ingestion",
        run_unified_ingestion,
    )

    payload = {
        "user_id": "user-456",
        "history": [
            {"role": "user", "content": "Remember to call mom"},
            {"role": "assistant", "content": "Will do"},
        ],
    }

    response = api_client.post("/v1/store", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["memories_created"] == 2
    assert data["ids"] == ["mem-1", "mem-2"]
    assert "Stored: 1 episodic, 1 procedural" in data["summary"]
    assert data["existing_memories_checked"] == 1
    assert {item["id"] for item in data["memories"]} == {"mem-1", "mem-2"}

    namespace_key = f"mem:ns:{payload['user_id']}"
    assert redis_stub.counters[namespace_key] == 1
    day_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert payload["user_id"] in redis_stub.sets[f"recent_users:{day_key}"]
    assert payload["user_id"] in redis_stub.sets["all_users"]

    run_unified_ingestion.assert_called_once()
