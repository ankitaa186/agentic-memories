from typing import List
import importlib

from fastapi.testclient import TestClient


def _stub_persist(_: str, memories: List[object]) -> List[str]:
    return [f"mem-{idx}" for idx, _ in enumerate(memories, start=1)]


def _stub_search(user_id: str, query: str, filters, limit: int, offset: int):  # noqa: ANN001
    return (
        [
            {
                "id": "mem-123",
                "content": f"Context for {user_id}: {query}",
                "score": 0.1,
                "metadata": {"layer": "semantic"},
            }
        ],
        1,
    )


def _install_stubbed_orchestrator(monkeypatch):
    app_module = importlib.import_module("src.app")
    from src.memory_orchestrator import AdaptiveMemoryOrchestrator
    from src.services.chat_runtime import ChatRuntimeBridge

    orchestrator = AdaptiveMemoryOrchestrator()
    bridge = ChatRuntimeBridge(orchestrator)
    monkeypatch.setattr(app_module, "_memory_orchestrator", orchestrator, raising=False)
    monkeypatch.setattr(app_module, "_chat_runtime_bridge", bridge, raising=False)
    monkeypatch.setattr(app_module._memory_orchestrator, "_persist", _stub_persist)
    monkeypatch.setattr(app_module._memory_orchestrator, "_search", _stub_search)
    monkeypatch.setattr(app_module, "is_llm_configured", lambda: True, raising=False)
    return app_module


def test_orchestrator_message_endpoint(monkeypatch):
    app_module = _install_stubbed_orchestrator(monkeypatch)

    payload = {
        "conversation_id": "conv-message",
        "message_id": "msg-1",
        "role": "user",
        "content": "hello there",
        "metadata": {"user_id": "user-123"},
        "flush": True,
    }

    with TestClient(app_module.app) as client:
        response = client.post("/v1/orchestrator/message", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "injections" in data
    assert data["injections"][0]["memory_id"] == "mem-123"
    assert data["injections"][0]["source"] == "long_term"


def test_orchestrator_retrieve_endpoint(monkeypatch):
    app_module = _install_stubbed_orchestrator(monkeypatch)

    payload = {
        "conversation_id": "conv-retrieve",
        "query": "latest context",
        "metadata": {"user_id": "user-123"},
        "limit": 3,
    }

    with TestClient(app_module.app) as client:
        response = client.post("/v1/orchestrator/retrieve", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["injections"], "expected at least one injection"
    assert data["injections"][0]["content"].startswith("Context for user-123")


def test_orchestrator_transcript_endpoint(monkeypatch):
    app_module = _install_stubbed_orchestrator(monkeypatch)

    payload = {
        "user_id": "transcript-user",
        "history": [
            {"role": "user", "content": "summarize last interaction"},
        ],
    }

    with TestClient(app_module.app) as client:
        response = client.post("/v1/orchestrator/transcript", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["injections"], "expected at least one injection"
    assert data["injections"][0]["channel"] == "inline"
