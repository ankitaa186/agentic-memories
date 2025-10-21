from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.persona_state import PersonaState, PersonaStateStore
from src.services.persona_retrieval import (
        PersonaCoPilot,
        PersonaRetrievalAgent,
        PersonaRetrievalResult,
)
from src.services.summary_manager import SummaryManager, SummaryTier


def test_persona_state_store_in_memory():
        store = PersonaStateStore(ttl_seconds=1)
        store._redis = None  # force in-memory path

        state = store.get_state("user-1")
        assert state.active_personas == []

        store.update_state("user-1", active_personas=["identity"])
        updated = store.get_state("user-1")
        assert updated.active_personas == ["identity"]

        store.clear_state("user-1")
        cleared = store.get_state("user-1")
        assert cleared.active_personas == []


class StubSummaryManager(SummaryManager):
        def __init__(self):
                self.requested = False

        def resolve_tier(self, granularity: str | None) -> SummaryTier:
                return SummaryTier.EPISODIC

        def get_summaries(self, user_id: str, persona: str, tier: SummaryTier, limit: int = 3, regenerate_if_stale: bool = True):
                self.requested = True
                return [{"id": "sum1", "text": "summary", "tier": tier.value}]


class StubStateStore(PersonaStateStore):
        def __init__(self):
                super().__init__(ttl_seconds=1)
                self._redis = None

        def get_state(self, user_id: str) -> PersonaState:
                state = PersonaState(user_id=user_id)
                state.active_personas = ["identity"]
                state.updated_at = datetime.now(timezone.utc)
                return state


class StubAgent:
        persona = "identity"

        def retrieve(self, **kwargs):
                return PersonaRetrievalResult(
                        persona="identity",
                        items=[{"id": "m1", "content": "note", "score": 0.9, "metadata": {"type": "explicit"}}],
                        weight_profile={"semantic": 0.5},
                        source="hybrid",
                )


def test_persona_copilot_uses_summary_manager():
        summary_manager = StubSummaryManager()
        copilot = PersonaCoPilot(state_store=StubStateStore(), summary_manager=summary_manager)
        copilot._agents["identity"] = StubAgent()

        results = copilot.retrieve(
                user_id="user-x",
                query="hello",
                limit=1,
                include_summaries=True,
                granularity="episodic",
        )

        assert "identity" in results
        assert summary_manager.requested is True
        assert results["identity"].summaries[0]["tier"] == "episodic"


def test_persona_agent_preserves_untagged_memories(monkeypatch):
        """Persona retrieval should not drop memories without persona tags."""

        class DummyHybrid:
                def retrieve_memories(self, query):
                        return [
                                SimpleNamespace(
                                        memory_id="m1",
                                        content="legacy",
                                        relevance_score=0.8,
                                        metadata={"persona_tags": []},
                                )
                        ]

        agent = PersonaRetrievalAgent("identity", hybrid_service=DummyHybrid())

        def fail_search_memories(**kwargs):
                raise AssertionError("fallback search should not run when hybrid results exist")

        monkeypatch.setattr("src.services.persona_retrieval.search_memories", fail_search_memories)

        result = agent.retrieve(user_id="user", query="hello")

        assert [item["id"] for item in result.items] == ["m1"]
        assert result.source == "hybrid"


def test_persona_agent_respects_requested_persona_filters(monkeypatch):
        """Explicit persona filters should be enforced via fallback search."""

        class DummyHybrid:
                def retrieve_memories(self, query):
                        return [
                                SimpleNamespace(
                                        memory_id="m1",
                                        content="legacy",
                                        relevance_score=0.8,
                                        metadata={"persona_tags": []},
                                )
                        ]

        agent = PersonaRetrievalAgent("identity", hybrid_service=DummyHybrid())

        captured = {}

        def fake_search_memories(user_id, query, filters, limit, offset):
                captured["filters"] = filters
                return [
                        {
                                "id": "m2",
                                "content": "fallback",
                                "score": 0.6,
                                "metadata": {"persona_tags": ["identity"]},
                        }
                ], 0

        monkeypatch.setattr("src.services.persona_retrieval.search_memories", fake_search_memories)

        result = agent.retrieve(
                user_id="user",
                query="hello",
                metadata_filters={"persona_tags": ["identity"]},
        )

        assert captured["filters"]["persona_tags"] == ["identity"]
        assert [item["id"] for item in result.items] == ["m2"]
        assert result.source == "semantic"
