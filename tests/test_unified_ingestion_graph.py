import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone

from src.schemas import TranscriptRequest, Message
from src.services import unified_ingestion_graph as graph


def test_node_build_memories_preserves_and_derives_context(monkeypatch):
    request = TranscriptRequest(
        user_id="user-1",
        history=[],
        metadata={"channel": "slack", "tags": ["external"]},
    )

    extracted_items = [
        {
            "content": "Met Alex at the Seattle office to plan the launch schedule.",
            "type": "explicit",
            "layer": "short-term",
            "confidence": 0.9,
            "tags": ["event", "planning"],
            "relationship": {"person": "Alex"},
            "entities": {
                "people": [{"name": "Alex"}],
                "places": ["Seattle office"],
            },
        }
    ]

    state = {
        "user_id": request.user_id,
        "request": request,
        "extracted_items": extracted_items,
        "t_start": 0.0,
        "metrics": {},
    }

    monkeypatch.setattr(graph, "generate_embedding", lambda content: [0.1, 0.2, 0.3])

    result_state = graph.node_build_memories(state)

    assert "memories" in result_state
    assert len(result_state["memories"]) == 1

    memory = result_state["memories"][0]
    metadata = memory.metadata

    assert metadata["relationship"] == extracted_items[0]["relationship"]
    assert metadata["location"] == {"place": "Seattle office"}
    assert metadata["participants"] == ["Alex"]
    assert metadata["channel"] == "slack"
    assert metadata["tags"] == ["event", "planning", "external"]
    assert request.metadata == {"channel": "slack", "tags": ["external"]}


def test_run_unified_ingestion_end_to_end(monkeypatch):
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: False)

    stored = {}

    class FakeEpisodicService:
        def __init__(self):
            stored["episodic"] = self
            self.memories = []

        def store_memory(self, memory):
            self.memories.append(memory)
            return True

    @dataclass
    class FakeEpisodicMemory:
        id: str
        user_id: str
        event_type: str
        event_timestamp: datetime
        content: str
        location: object = None
        participants: object = None
        emotional_valence: object = None
        emotional_arousal: object = None
        importance_score: object = None
        tags: object = None
        metadata: object = None

    class FakeEmotionalService:
        def __init__(self):
            stored["emotional"] = self
            self.records = []

        def record_emotional_state(self, **kwargs):
            self.records.append(kwargs)
            return True

    class FakeProceduralService:
        def __init__(self):
            stored["procedural"] = self
            self.practice_calls = []

        def practice_skill(self, **kwargs):
            self.practice_calls.append(kwargs)
            return True

    class FakePortfolioService:
        def __init__(self):
            stored["portfolio"] = self
            self.holdings = []

        def upsert_holding_from_memory(self, **kwargs):
            self.holdings.append(kwargs)

    fake_epi_module = types.ModuleType("src.services.episodic_memory")
    fake_epi_module.EpisodicMemoryService = FakeEpisodicService
    fake_epi_module.EpisodicMemory = FakeEpisodicMemory
    fake_emotional_module = types.ModuleType("src.services.emotional_memory")
    fake_emotional_module.EmotionalMemoryService = FakeEmotionalService
    fake_procedural_module = types.ModuleType("src.services.procedural_memory")
    fake_procedural_module.ProceduralMemoryService = FakeProceduralService
    fake_portfolio_module = types.ModuleType("src.services.portfolio_service")
    fake_portfolio_module.PortfolioService = FakePortfolioService

    monkeypatch.setitem(sys.modules, "src.services.episodic_memory", fake_epi_module)
    monkeypatch.setitem(sys.modules, "src.services.emotional_memory", fake_emotional_module)
    monkeypatch.setitem(sys.modules, "src.services.procedural_memory", fake_procedural_module)
    monkeypatch.setitem(sys.modules, "src.services.portfolio_service", fake_portfolio_module)

    monkeypatch.setattr(graph, "get_relevant_existing_memories", lambda request: [])
    monkeypatch.setattr(graph, "format_memories_for_llm_context", lambda memories: "")

    extracted_item = {
        "content": "Met Alex at the Seattle office to discuss the new trading model and felt excited.",
        "type": "explicit",
        "layer": "short-term",
        "confidence": 0.95,
        "tags": ["event", "emotion", "skill", "finance"],
        "relationship": {"person": "Alex"},
        "learning_journal": {"topic": "Trading strategy"},
        "portfolio": {"ticker": "AAPL", "intent": "buy"},
        "episodic_context": {
            "location": {"place": "Seattle office"},
            "participants": ["Alex"],
        },
        "entities": {
            "people": [{"name": "Alex"}],
            "places": ["Seattle office"],
        },
    }

    def fake_call_llm_json(prompt, payload, expect_array=False):
        if prompt == graph.WORTHINESS_PROMPT:
            return {"worthy": True}
        if prompt == graph.SENTIMENT_ANALYSIS_PROMPT:
            return {
                "has_emotional_content": True,
                "valence": 0.2,
                "arousal": 0.7,
                "dominant_emotion": "excited",
            }
        if expect_array:
            return [extracted_item]
        return {}

    monkeypatch.setattr(graph, "_call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(graph, "generate_embedding", lambda content: [0.1, 0.2, 0.3])
    monkeypatch.setattr(graph, "upsert_memories", lambda user_id, memories: [f"mem_{i}" for i in range(len(memories))])

    request = TranscriptRequest(
        user_id="user-42",
        history=[Message(role="user", content="Tell me about meeting Alex today.")],
        metadata={"tags": ["external"], "channel": "slack"},
    )

    final_state = graph.run_unified_ingestion(request)

    assert final_state["storage_results"]["chromadb_stored"] == 1
    assert final_state["storage_results"]["episodic_stored"] == 1
    assert final_state["storage_results"]["emotional_stored"] == 1
    assert final_state["storage_results"]["procedural_stored"] == 1
    assert final_state["storage_results"]["portfolio_stored"] == 1

    assert stored["episodic"].memories[0].metadata["location"] == {"place": "Seattle office"}
    assert stored["episodic"].memories[0].metadata["participants"] == ["Alex"]
    assert stored["emotional"].records[0]["emotional_state"] == "excited"
    assert stored["procedural"].practice_calls[0]["skill_name"] == "Trading strategy"
    assert stored["portfolio"].holdings[0]["portfolio_metadata"] == extracted_item["portfolio"]

    assert final_state["storage_summary"]["total_stored"] == 5
