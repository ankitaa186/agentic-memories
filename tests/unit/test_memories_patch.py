"""Unit tests for PATCH /v1/memories/{memory_id} (Story AM-X.1).

Covers ACs (see .claude/scrum/stories/AM-X.1.md):
- AC1: Identity preservation (memory_id, timestamp).
- AC2: Immutable fields rejected with 422.
- AC3: 403 on user_id mismatch.
- AC4: 404 on missing memory.
- AC5: Partial updates of each mutable field.
- AC6/AC7: Embedding regen on content change; skip on identical content_hash.
- AC8: Shallow-merge metadata + `__delete__` sentinel; system-managed keys 422.
- AC9: ttl_seconds recompute; explicit-null clears.
- AC10/AC11: Allowed and disallowed layer flips.
- AC13: Response shape with chroma_updated/typed_table_updated/embedding_*.
- AC19: SYSTEM_MANAGED_FIELDS single-source-of-truth invariant.
- AC20: update_chroma_record strips system-managed keys.
- AC22: Retry semantics — typed-table update always re-attempted.
"""

from unittest.mock import MagicMock, patch

import pytest


# -----------------------------------------------------------------------------
# Helpers / fixtures
# -----------------------------------------------------------------------------


def _existing_record(
    *,
    user_id: str = "user-1",
    content: str = "User likes pasta",
    layer: str = "semantic",
    extra_meta=None,
):
    """Build a fake record dict mirroring storage.get_chroma_record output."""
    import hashlib

    meta = {
        "user_id": user_id,
        "layer": layer,
        "type": "explicit",
        "timestamp": "2026-05-08T10:00:00+00:00",
        "content_hash": hashlib.sha256(content.strip().lower().encode()).hexdigest(),
        "importance": 0.8,
        "source": "chat",
    }
    if extra_meta:
        meta.update(extra_meta)
    return {"id": "mem_abc123", "document": content, "metadata": meta}


@pytest.fixture
def patch_chroma(monkeypatch):
    """Patch chroma helpers used by PATCH route. Yields the mocks."""
    chroma_client = MagicMock()
    chroma_client.health_check.return_value = True

    get_record = MagicMock()
    update_record = MagicMock()

    monkeypatch.setattr("src.routers.memories.get_chroma_client", lambda: chroma_client)
    monkeypatch.setattr("src.routers.memories.get_chroma_record", get_record)
    monkeypatch.setattr("src.routers.memories.update_chroma_record", update_record)

    yield {
        "client": chroma_client,
        "get_record": get_record,
        "update_record": update_record,
    }


# =============================================================================
# AC1 — identity preservation (memory_id echoed; timestamp untouched)
# =============================================================================


def test_patch_preserves_memory_id_and_timestamp(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.95},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["memory_id"] == rec["id"]
    # AC1: timestamp must NOT be in any update payload sent to Chroma.
    call_kwargs = patch_chroma["update_record"].call_args.kwargs
    internal = call_kwargs.get("internal_metadata") or {}
    assert internal.get("timestamp") == rec["metadata"]["timestamp"]


# =============================================================================
# AC2 — immutable fields rejected with 422
# =============================================================================


def test_patch_rejects_immutable_metadata_keys(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    for bad_key in (
        "user_id",
        "layer",
        "type",
        "ttl_epoch",
        "timestamp",
        "content_hash",
        "stored_in_episodic",
        "stored_in_emotional",
        "stored_in_procedural",
        "typed_table_id",
    ):
        response = api_client.patch(
            f"/v1/memories/{rec['id']}",
            params={"user_id": "user-1"},
            json={"metadata": {bad_key: "evil"}},
        )
        assert response.status_code == 422, f"key={bad_key} should be 422"
        detail = response.json()["detail"]
        assert "system_managed" in detail.get("error", "") or bad_key in str(detail)


# =============================================================================
# AC3 — 403 on user_id mismatch
# =============================================================================


def test_patch_403_on_user_mismatch(api_client, patch_chroma):
    rec = _existing_record(user_id="owner-A")
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "intruder-B"},
        json={"importance": 0.5},
    )
    assert response.status_code == 403


# =============================================================================
# AC4 — 404 on missing memory
# =============================================================================


def test_patch_404_when_memory_missing(api_client, patch_chroma):
    patch_chroma["get_record"].return_value = None
    response = api_client.patch(
        "/v1/memories/mem_missing",
        params={"user_id": "user-1"},
        json={"content": "anything"},
    )
    assert response.status_code == 404


# =============================================================================
# AC5 — partial updates of each mutable field
# =============================================================================


def test_patch_partial_update_metadata_only(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"metadata": {"new_key": "new_value"}},
    )
    assert response.status_code == 200
    call_kwargs = patch_chroma["update_record"].call_args.kwargs
    # No content -> no document update
    assert call_kwargs.get("document") is None
    # No content -> no embedding regen
    assert call_kwargs.get("embedding") is None
    # Caller metadata contains the new key (and the preserved 'source' key).
    caller_meta = call_kwargs.get("metadata") or {}
    assert caller_meta.get("new_key") == "new_value"
    assert caller_meta.get("source") == "chat"  # preserved
    body = response.json()
    assert body["embedding_regenerated"] is False
    assert body["embedding_regen_duration_ms"] == 0


def test_patch_partial_update_importance_only(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.42},
    )
    assert response.status_code == 200
    call_kwargs = patch_chroma["update_record"].call_args.kwargs
    caller_meta = call_kwargs.get("metadata") or {}
    assert caller_meta["importance"] == 0.42


# =============================================================================
# AC6 / AC7 — embedding regen on content change; skip on identical hash
# =============================================================================


def test_patch_regenerates_embedding_on_content_change(api_client, patch_chroma):
    rec = _existing_record(content="User likes pasta")
    patch_chroma["get_record"].return_value = rec
    new_embedding = [0.5] * 1536

    with patch(
        "src.routers.memories.generate_embedding", return_value=new_embedding
    ) as mock_embed:
        response = api_client.patch(
            f"/v1/memories/{rec['id']}",
            params={"user_id": "user-1"},
            json={"content": "User likes risotto now"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["embedding_regenerated"] is True
    assert body["embedding_regen_duration_ms"] >= 0
    mock_embed.assert_called_once_with("User likes risotto now")
    # update_chroma_record was passed embedding=
    assert (
        patch_chroma["update_record"].call_args.kwargs.get("embedding") == new_embedding
    )


def test_patch_skips_embedding_regen_on_same_content_hash(api_client, patch_chroma):
    rec = _existing_record(content="User likes pasta")
    patch_chroma["get_record"].return_value = rec

    # Same content (same hash) -> embedding regen skipped (AC7).
    with patch("src.routers.memories.generate_embedding") as mock_embed:
        response = api_client.patch(
            f"/v1/memories/{rec['id']}",
            params={"user_id": "user-1"},
            json={"content": "User likes pasta"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["embedding_regenerated"] is False
    assert body["embedding_regen_duration_ms"] == 0
    mock_embed.assert_not_called()


# =============================================================================
# AC8 — shallow-merge metadata + `__delete__` sentinel
# =============================================================================


def test_patch_metadata_shallow_merge(api_client, patch_chroma):
    rec = _existing_record(extra_meta={"source": "chat", "session": "s1", "lang": "en"})
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"metadata": {"session": "s2", "new": "x"}},
    )
    assert response.status_code == 200
    caller_meta = patch_chroma["update_record"].call_args.kwargs.get("metadata") or {}
    assert caller_meta["session"] == "s2"  # overwritten
    assert caller_meta["new"] == "x"  # added
    assert caller_meta["source"] == "chat"  # preserved
    assert caller_meta["lang"] == "en"  # preserved


def test_patch_metadata_delete_sentinel(api_client, patch_chroma):
    rec = _existing_record(extra_meta={"old_key": "obsolete", "keeper": "yes"})
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"metadata": {"old_key": "__delete__"}},
    )
    assert response.status_code == 200
    caller_meta = patch_chroma["update_record"].call_args.kwargs.get("metadata") or {}
    assert "old_key" not in caller_meta
    assert caller_meta["keeper"] == "yes"


# =============================================================================
# AC9 — ttl_seconds recompute; explicit-null clears (sentinel scheme)
# =============================================================================


def test_patch_ttl_seconds_sets_ttl_epoch(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    fixed_now = 1_700_000_000.0
    with patch("src.routers.memories.time.time", return_value=fixed_now):
        response = api_client.patch(
            f"/v1/memories/{rec['id']}",
            params={"user_id": "user-1"},
            json={"ttl_seconds": 3600},
        )
    assert response.status_code == 200
    internal = (
        patch_chroma["update_record"].call_args.kwargs.get("internal_metadata") or {}
    )
    assert internal["ttl_epoch"] == int(fixed_now) + 3600


def test_patch_ttl_seconds_explicit_null_clears_ttl(api_client, patch_chroma):
    rec = _existing_record(extra_meta={"ttl_epoch": 9999999999})
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"ttl_seconds": None},  # explicit JSON null
    )
    assert response.status_code == 200
    internal = (
        patch_chroma["update_record"].call_args.kwargs.get("internal_metadata") or {}
    )
    # ttl_epoch must be REMOVED from the internal metadata payload (cleared).
    assert "ttl_epoch" not in internal


def test_patch_ttl_seconds_omitted_leaves_ttl_unchanged(api_client, patch_chroma):
    rec = _existing_record(extra_meta={"ttl_epoch": 9999999999})
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.5},  # no ttl_seconds
    )
    assert response.status_code == 200
    internal = (
        patch_chroma["update_record"].call_args.kwargs.get("internal_metadata") or {}
    )
    # ttl_epoch must be PRESERVED (not stripped, not changed).
    assert internal["ttl_epoch"] == 9999999999


def test_patch_ttl_seconds_invalid_negative_returns_422(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"ttl_seconds": -1},
    )
    assert response.status_code == 422


# =============================================================================
# AC10 / AC11 — layer flips
# =============================================================================


@pytest.mark.parametrize(
    "from_layer,to_layer",
    [
        ("short-term", "semantic"),
        ("semantic", "long-term"),
        ("long-term", "short-term"),
        ("short-term", "long-term"),
    ],
)
def test_patch_allowed_layer_flips(api_client, patch_chroma, from_layer, to_layer):
    rec = _existing_record(layer=from_layer)
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"layer": to_layer},
    )
    assert response.status_code == 200, response.text
    internal = (
        patch_chroma["update_record"].call_args.kwargs.get("internal_metadata") or {}
    )
    assert internal["layer"] == to_layer


@pytest.mark.parametrize(
    "from_layer,to_layer",
    [
        ("semantic", "episodic"),
        ("semantic", "procedural"),
        ("semantic", "emotional"),
        ("episodic", "semantic"),
        ("procedural", "long-term"),
        ("emotional", "short-term"),
    ],
)
def test_patch_disallowed_layer_flips_422(
    api_client, patch_chroma, from_layer, to_layer
):
    rec = _existing_record(layer=from_layer)
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"layer": to_layer},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "layer flip" in str(detail).lower() or "typed-storage" in str(detail).lower()


# =============================================================================
# AC13 — response shape with per-surface flags
# =============================================================================


def test_patch_response_shape_no_typed_fanout(api_client, patch_chroma):
    rec = _existing_record()
    patch_chroma["get_record"].return_value = rec

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.5},
    )
    body = response.json()
    assert set(body.keys()) >= {
        "status",
        "memory_id",
        "chroma_updated",
        "typed_table_updated",
        "embedding_regenerated",
        "embedding_regen_duration_ms",
        "warnings",
    }
    assert body["chroma_updated"] is True
    assert body["typed_table_updated"] is None  # no stored_in_*
    assert body["warnings"] == []


# =============================================================================
# AC12 / AC13 — typed-table fan-out happy path + partial failure
# =============================================================================


def test_patch_typed_fanout_happy_path(api_client, patch_chroma, monkeypatch):
    rec = _existing_record(
        layer="episodic",
        extra_meta={
            "stored_in_episodic": True,
            "stored_in_emotional": False,
            "stored_in_procedural": False,
            "typed_table_id": "11111111-2222-3333-4444-555555555555",
        },
    )
    patch_chroma["get_record"].return_value = rec
    fanout = MagicMock(return_value=True)
    monkeypatch.setattr("src.routers.memories._update_episodic_row", fanout)

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.95},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["typed_table_updated"]["episodic"] is True
    assert body["typed_table_updated"]["emotional"] is False
    assert body["typed_table_updated"]["procedural"] is False
    assert body["warnings"] == []
    fanout.assert_called_once()


def test_patch_typed_fanout_partial_failure_returns_200_with_warnings(
    api_client, patch_chroma, monkeypatch
):
    rec = _existing_record(
        layer="episodic",
        extra_meta={
            "stored_in_episodic": True,
            "stored_in_emotional": True,
            "stored_in_procedural": False,
            "typed_table_id": "11111111-2222-3333-4444-555555555555",
        },
    )
    patch_chroma["get_record"].return_value = rec
    monkeypatch.setattr(
        "src.routers.memories._update_episodic_row", MagicMock(return_value=True)
    )
    monkeypatch.setattr(
        "src.routers.memories._update_emotional_row", MagicMock(return_value=False)
    )

    response = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"importance": 0.5},
    )
    # AC13: HTTP 200 even on partial failure (NOT 207).
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["chroma_updated"] is True
    assert body["typed_table_updated"]["episodic"] is True
    assert body["typed_table_updated"]["emotional"] is False
    assert any("emotional" in w for w in body["warnings"])


# =============================================================================
# AC22 — typed-table update is always re-attempted (idempotent retry)
# =============================================================================


def test_patch_retry_reattempts_typed_table_even_when_content_unchanged(
    api_client, patch_chroma, monkeypatch
):
    """Same content twice -> embedding regen is correctly skipped, but the
    typed-table UPDATE must STILL be attempted on each call (AC22)."""
    rec = _existing_record(
        content="Annie loves pasta",
        layer="episodic",
        extra_meta={
            "stored_in_episodic": True,
            "stored_in_emotional": False,
            "stored_in_procedural": False,
            "typed_table_id": "11111111-2222-3333-4444-555555555555",
        },
    )
    patch_chroma["get_record"].return_value = rec

    # First call fails on typed-table; second call succeeds.
    episodic_calls = MagicMock(side_effect=[False, True])
    monkeypatch.setattr("src.routers.memories._update_episodic_row", episodic_calls)

    # First call — fails fan-out
    r1 = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"content": "Annie loves pasta"},  # same content
    )
    assert r1.status_code == 200
    assert r1.json()["embedding_regenerated"] is False
    assert r1.json()["typed_table_updated"]["episodic"] is False

    # Second call — same content_hash, same payload, must STILL try fan-out
    r2 = api_client.patch(
        f"/v1/memories/{rec['id']}",
        params={"user_id": "user-1"},
        json={"content": "Annie loves pasta"},  # same content again
    )
    assert r2.status_code == 200
    assert r2.json()["embedding_regenerated"] is False
    assert r2.json()["typed_table_updated"]["episodic"] is True

    # AC22 invariant: helper called twice (NOT short-circuited on retry).
    assert episodic_calls.call_count == 2


# =============================================================================
# AC19 — SYSTEM_MANAGED_FIELDS single-source-of-truth invariant
# =============================================================================


def test_system_managed_fields_single_source_of_truth():
    """The constant must be defined ONCE in src/services/_constants.py and
    imported by both router (X.1) and storage (X.1) code paths. This test
    grep-checks for accidental duplication.
    """
    import re
    from pathlib import Path

    expected_set = {
        "user_id",
        "layer",
        "type",
        "ttl_epoch",
        "timestamp",
        "content_hash",
        "stored_in_episodic",
        "stored_in_emotional",
        "stored_in_procedural",
        "typed_table_id",
    }

    from src.services._constants import SYSTEM_MANAGED_FIELDS

    assert set(SYSTEM_MANAGED_FIELDS) == expected_set
    assert isinstance(SYSTEM_MANAGED_FIELDS, frozenset)

    # Scan src/ for any redefinition of the constant outside _constants.py.
    src_root = Path("src")
    pattern = re.compile(r"^\s*SYSTEM_MANAGED_FIELDS\s*[:=]")
    redefinitions = []
    for path in src_root.rglob("*.py"):
        if path.name == "_constants.py":
            continue
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.match(line):
                redefinitions.append(f"{path}:{i}")
    assert redefinitions == [], (
        f"SYSTEM_MANAGED_FIELDS redefined outside _constants.py: {redefinitions}"
    )


# =============================================================================
# AC20 — update_chroma_record strips system-managed keys
# =============================================================================


def test_update_chroma_record_strips_system_managed_keys(monkeypatch):
    """Call update_chroma_record directly with a payload that includes
    system-managed keys; assert the resulting Chroma `update` call drops them.
    """
    from src.services import storage

    captured = {}

    class _Coll:
        def update(self, **kwargs):
            captured.update(kwargs)

    coll = _Coll()
    monkeypatch.setattr(storage, "init_chroma_collection", lambda _name: coll)

    storage.update_chroma_record(
        "mem_xyz",
        document="hello",
        metadata={
            "user_id": "evil",
            "layer": "evil",
            "ttl_epoch": 12345,
            "content_hash": "evil",
            "typed_table_id": "evil",
            "source": "good",
            "session": "s1",
        },
    )
    written_meta = captured.get("metadatas", [{}])[0]
    # System-managed keys MUST be stripped.
    for k in ("user_id", "layer", "ttl_epoch", "content_hash", "typed_table_id"):
        assert k not in written_meta, f"{k} leaked through"
    # Caller-domain keys must pass through.
    assert written_meta["source"] == "good"
    assert written_meta["session"] == "s1"


def test_update_chroma_record_internal_metadata_bypasses_strip(monkeypatch):
    """Internal metadata escape hatch must NOT be stripped — that's how the
    PATCH router writes server-computed ttl_epoch/layer/content_hash safely."""
    from src.services import storage

    captured = {}

    class _Coll:
        def update(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(storage, "init_chroma_collection", lambda _name: _Coll())

    storage.update_chroma_record(
        "mem_xyz",
        metadata={"source": "chat"},
        internal_metadata={
            "ttl_epoch": 99999,
            "layer": "long-term",
            "content_hash": "abc",
        },
    )
    written_meta = captured.get("metadatas", [{}])[0]
    assert written_meta["ttl_epoch"] == 99999
    assert written_meta["layer"] == "long-term"
    assert written_meta["content_hash"] == "abc"
    assert written_meta["source"] == "chat"


# =============================================================================
# AC2/AC8 — schema-level guard: ttl_seconds must distinguish null vs omitted
# =============================================================================


def test_patch_request_ttl_sentinel_distinguishes_null_from_omitted():
    """Test the Pydantic sentinel scheme directly (no HTTP). Mirrors AC9."""
    from src.schemas import UNSET, PatchMemoryRequest, _Unset

    omitted = PatchMemoryRequest()
    assert isinstance(omitted.ttl_seconds, _Unset)
    assert omitted.ttl_seconds is UNSET

    explicit_null = PatchMemoryRequest(ttl_seconds=None)
    assert explicit_null.ttl_seconds is None
    assert not isinstance(explicit_null.ttl_seconds, _Unset)

    explicit_int = PatchMemoryRequest(ttl_seconds=600)
    assert explicit_int.ttl_seconds == 600


def test_patch_request_ttl_sentinel_via_json_round_trip():
    """The sentinel scheme must survive JSON-to-Pydantic parsing (mirrors
    AC21 but at the model level — full e2e wire test is in tests/e2e)."""
    from src.schemas import PatchMemoryRequest, _Unset

    # Pydantic v2: model_validate_json mirrors what FastAPI body-parse does.
    omitted = PatchMemoryRequest.model_validate_json("{}")
    assert isinstance(omitted.ttl_seconds, _Unset)

    explicit_null = PatchMemoryRequest.model_validate_json('{"ttl_seconds": null}')
    assert explicit_null.ttl_seconds is None

    explicit_int = PatchMemoryRequest.model_validate_json('{"ttl_seconds": 60}')
    assert explicit_int.ttl_seconds == 60
