"""Exercise real retrieval/ranking code with deterministic vectors, no services.

Unlike API response stubs, these tests catch unrelated SQL skills displacing
indexed facts, metric misinterpretation and persona-based reordering.
"""

import math
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from src.services import hybrid_retrieval as hybrid
from src.services import retrieval
from src.services.persona_retrieval import PersonaRetrievalAgent
from src.services.similarity import cosine_similarity


def vector(similarity):
    return [similarity, math.sqrt(1 - similarity**2)]


@pytest.mark.parametrize("scale", [0.1, 1, 4])
def test_actual_cosine_does_not_assume_unit_vectors_or_l2_distance(scale):
    candidate = [v * scale for v in vector(0.563)]
    assert cosine_similarity([1, 0], candidate) == pytest.approx(0.563)


@pytest.mark.parametrize(
    "query,candidate",
    [
        ([], []),
        ([1, 0], [1]),
        ([0, 0], [1, 0]),
        ([1, 0], [float("nan"), 1]),
        ([float("inf")], [1]),
    ],
)
def test_missing_invalid_vectors_never_receive_default_relevance(query, candidate):
    with pytest.raises(ValueError):
        cosine_similarity(query, candidate)


def result(mid, similarity, **metadata):
    return hybrid.RetrievalResult(
        memory_id=mid,
        memory_type="semantic",
        content=mid,
        relevance_score=0.9,
        recency_score=1,
        importance_score=1,
        semantic_similarity=similarity,
        metadata=metadata,
    )


def skill(mid, name):
    return SimpleNamespace(
        id=mid,
        skill_name=name,
        steps=[],
        context="",
        last_practiced=None,
        success_rate=None,
        proficiency_level="beginner",
        practice_count=0,
        tags=[],
    )


@pytest.fixture
def service(monkeypatch):
    hybrid._skill_embedding.cache_clear()
    instance = object.__new__(hybrid.HybridRetrievalService)
    instance.chroma_client = Mock()
    instance.procedural_service = Mock()
    instance.procedural_service.get_skills.return_value = []
    monkeypatch.setattr(retrieval, "_standard_collection_name", lambda: "memories_test")
    monkeypatch.setattr("src.config.is_langfuse_enabled", lambda: False)
    yield instance
    hybrid._skill_embedding.cache_clear()


def collection_response(ids, similarities, metadata=None):
    return {
        "ids": [ids],
        "documents": [ids],
        "metadatas": [metadata or [{} for _ in ids]],
        "embeddings": [[vector(v) for v in similarities]],
        # Intentionally squared L2. It must not be used as cosine distance.
        "distances": [[2 - 2 * v for v in similarities]],
    }


def test_printer_top_five_survives_five_unrelated_sql_skills(service, monkeypatch):
    ids = [f"printer-{i}" for i in range(5)]
    collection = service.chroma_client.get_collection.return_value
    collection.query.return_value = collection_response(ids, [0.8, 0.7, 0.6, 0.5, 0.4])
    service.procedural_service.get_skills.return_value = [
        skill(str(i), name)
        for i, name in enumerate(["Diet", "Project", "Gaming1", "Gaming2", "Gaming3"])
    ]

    def embed(texts):
        return [[1, 0] if t == "3D printer" else vector(0.1) for t in texts]

    monkeypatch.setattr(hybrid, "get_embeddings", embed)
    query = hybrid.RetrievalQuery(user_id="owner", query_text="3D printer", limit=5)
    matches = service.retrieve_memories(query)
    assert [r.memory_id for r in matches] == ids
    assert matches[0].relevance_score == pytest.approx(0.8)
    assert collection.query.call_args.kwargs["where"] == {"user_id": "owner"}
    service.procedural_service.get_skills.assert_called_once_with("owner")


def test_sql_only_skill_is_matched_not_lost(service, monkeypatch):
    service.chroma_client.get_collection.return_value.query.return_value = (
        collection_response(["printer"], [0.2])
    )
    service.procedural_service.get_skills.return_value = [
        skill("sql-only", "Stellaris")
    ]
    monkeypatch.setattr(hybrid, "get_embeddings", lambda texts: [[1, 0] for _ in texts])
    matches = service.retrieve_memories(
        hybrid.RetrievalQuery(user_id="owner", query_text="Stellaris", limit=1)
    )
    assert matches[0].memory_id == "sql-only"
    assert matches[0].relevance_score == pytest.approx(1)
    assert matches[0].metadata["layer"] == "procedural"


def test_skill_embedding_cache_is_bounded_owner_and_content_scoped(monkeypatch):
    hybrid._skill_embedding.cache_clear()
    embed = Mock(return_value=[[1, 0]])
    monkeypatch.setattr(hybrid, "get_embeddings", embed)
    for owner, text in [("one", "old"), ("one", "old"), ("two", "old"), ("one", "new")]:
        hybrid._skill_embedding(owner, "skill", text, "model")
    assert embed.call_count == 3
    assert hybrid._skill_embedding.cache_info().maxsize == 256
    hybrid._skill_embedding.cache_clear()


def test_deleted_skill_is_not_resurrected_from_embedding_cache(service, monkeypatch):
    monkeypatch.setattr(hybrid, "get_embeddings", lambda texts: [[1, 0]])
    query = hybrid.RetrievalQuery(user_id="owner", query_text="test")
    service.procedural_service.get_skills.return_value = [skill("s", "Skill")]
    assert service._procedural_retrieval(query, [1, 0])
    service.procedural_service.get_skills.return_value = []
    assert service._procedural_retrieval(query, [1, 0]) == []


def test_browse_does_not_embed_skills(service, monkeypatch):
    embed = Mock(side_effect=AssertionError("browse must not call embeddings"))
    monkeypatch.setattr(hybrid, "get_embeddings", embed)
    service.procedural_service.get_skills.return_value = [skill("s", "Skill")]
    assert service._procedural_retrieval(hybrid.RetrievalQuery(user_id="owner"))
    embed.assert_not_called()


def test_unscored_or_important_unrelated_memory_cannot_beat_match(service):
    matches = service._rank_results(
        [result("unscored", None), result("old-printer", 0.7), result("new-diet", 0.1)],
        hybrid.RetrievalQuery(
            user_id="owner",
            query_text="printer",
            weight_overrides={"semantic": 0, "importance": 1},
        ),
    )
    assert [r.memory_id for r in matches] == ["old-printer", "new-diet"]


def test_explicit_temporal_retrieval_retains_specialized_ranking(service):
    service._calculate_composite_score = Mock(return_value=0.9)
    now = datetime.now(timezone.utc)
    service._rank_results(
        [result("event", 0.1)],
        hybrid.RetrievalQuery(
            user_id="owner", query_text="meeting", time_range=(now, now)
        ),
    )
    service._calculate_composite_score.assert_called_once()


def test_vector_and_typed_copy_deduplicate(service):
    matches = service._deduplicate_results(
        [result("vector-copy", 0.7, typed_table_id="sql-copy"), result("sql-copy", 0.8)]
    )
    assert [r.memory_id for r in matches] == ["vector-copy"]


def test_postgres_uuid_skill_deduplicates_against_chroma_string(service, monkeypatch):
    mid = UUID("00000000-0000-0000-0000-000000000001")
    service.procedural_service.get_skills.return_value = [skill(mid, "Skill")]
    monkeypatch.setattr(hybrid, "get_embeddings", lambda texts: [[1, 0]])
    rows = service._procedural_retrieval(
        hybrid.RetrievalQuery(user_id="owner", query_text="skill"), [1, 0]
    )
    matches = service._deduplicate_results(
        [result("indexed", 0.8, typed_table_id=str(mid)), *rows]
    )
    assert [r.memory_id for r in matches] == ["indexed"]


def test_persona_does_not_reorder_ordinary_matches_but_explicit_filter_works():
    source = Mock()
    source.retrieve_memories.return_value = [
        result("printer", 0.8),
        result("diet", 0.2, persona_tags=["expert"]),
    ]
    agent = PersonaRetrievalAgent("expert", hybrid_service=source)
    matches = agent.retrieve("owner", "printer")
    assert [r["id"] for r in matches.items] == ["printer", "diet"]
    assert matches.weight_profile["semantic"] == 1
    filtered = agent.retrieve(
        "owner", "printer", metadata_filters={"persona_tags": ["expert"]}
    )
    assert [r["id"] for r in filtered.items] == ["diet"]


def test_baseline_search_uses_same_actual_cosine(monkeypatch):
    collection = Mock()
    collection.query.return_value = collection_response(
        ["printer", "diet"], [0.563, 0.1]
    )
    monkeypatch.setattr(retrieval, "_get_collection", lambda: collection)
    monkeypatch.setattr(retrieval, "get_redis_client", lambda: None)
    monkeypatch.setattr(retrieval, "generate_embedding", lambda text: [1, 0])
    matches, count = retrieval._search_memories_impl("owner", "printer", limit=5)
    assert count == 2
    assert [m["id"] for m in matches] == ["printer", "diet"]
    assert matches[0]["score"] == pytest.approx(0.563)
    assert collection.query.call_args.kwargs["where"] == {"user_id": "owner"}
