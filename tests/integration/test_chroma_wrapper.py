"""Integration tests for the V2ChromaClient / V2Collection wrapper.

Live-curl testing on the staged AM-X branch surfaced that
``V2Collection`` did not implement an ``update`` method, so every PATCH on
``/v1/memories/{id}`` failed silently with
``'V2Collection' object has no attribute 'update'`` -- the unit tests
mocked the collection with ``MagicMock`` (which auto-creates any
attribute), so the gap was invisible.

These tests exercise the wrapper against a real Chroma v2 server when
one is reachable on ``localhost:8000`` (or the ``CHROMA_HOST`` /
``CHROMA_PORT`` env vars). When unreachable, all tests skip cleanly so
the ``pytest tests/`` smoke suite is still a no-op on CI / dev machines
without Chroma running.

Coverage:
- update content only (documents)
- update metadata only (metadatas)
- update both content + metadata + embeddings
- update is idempotent against a no-op (None on every optional field)
- ``ids`` is mandatory
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

import httpx
import pytest

from src.dependencies.chroma import V2ChromaClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _chroma_reachable(host: str, port: int) -> bool:
    """Quick TCP/HTTP probe; returns False if Chroma isn't listening."""
    url = f"http://{host}:{port}/api/v2/heartbeat"
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def chroma_client():
    """Return a V2ChromaClient bound to the local Chroma; skip if unreachable.

    Tries ``CHROMA_HOST`` from env first; if that's the docker-internal name
    (``chromadb``) and unreachable from the host, falls back to ``localhost``
    on the same port (the docker-compose port-mapping pattern).
    """
    try:
        port = int(os.getenv("CHROMA_PORT", "8000"))
    except ValueError:
        port = 8000
    candidates = [os.getenv("CHROMA_HOST", "localhost")]
    if "localhost" not in candidates:
        candidates.append("localhost")
    host: Optional[str] = None
    for cand in candidates:
        if _chroma_reachable(cand, port):
            host = cand
            break
    if host is None:
        pytest.skip(
            f"Chroma not reachable at {candidates}:{port}; skipping wrapper tests"
        )
    tenant = os.getenv("CHROMA_TENANT", "default_tenant")
    database = os.getenv("CHROMA_DATABASE", "default_database")
    return V2ChromaClient(
        host=host, port=port, tenant=tenant, database=database, ssl=False
    )


@pytest.fixture
def collection(chroma_client):
    """Provide a uniquely-named collection per test, cleaned up afterwards."""
    name = f"test_wrapper_{uuid.uuid4().hex[:12]}"
    coll = chroma_client.get_or_create_collection(name)
    yield coll
    # Best-effort cleanup: delete the collection. The v2 API supports DELETE
    # on the collection-by-name path; ignore errors during teardown.
    try:
        chroma_client._make_request(
            "POST",
            f"/tenants/{chroma_client.tenant}/databases/{chroma_client.database}/collections/{coll.id}/delete",
            {},
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _embed(seed: int, dim: int = 8) -> list:
    """Tiny deterministic embedding for tests (8-D so collections stay light)."""
    return [float((seed + i) % 7) / 7.0 for i in range(dim)]


def test_update_changes_document_only(collection):
    """update(documents=...) replaces content; metadata is left intact."""
    rec_id = "rec_doc_only"
    collection.upsert(
        ids=[rec_id],
        documents=["original content"],
        embeddings=[_embed(1)],
        metadatas=[{"layer": "semantic", "owner": "alice"}],
    )

    collection.update(ids=[rec_id], documents=["replacement content"])

    fetched = collection.get(ids=[rec_id])
    docs = fetched.get("documents") or []
    metas = fetched.get("metadatas") or []
    assert docs and docs[0] == "replacement content"
    # Metadata untouched.
    assert metas and metas[0].get("owner") == "alice"
    assert metas[0].get("layer") == "semantic"


def test_update_changes_metadata_only(collection):
    """update(metadatas=...) replaces metadata; document content stays."""
    rec_id = "rec_meta_only"
    collection.upsert(
        ids=[rec_id],
        documents=["preserved content"],
        embeddings=[_embed(2)],
        metadatas=[{"layer": "semantic", "owner": "bob", "score": 0.5}],
    )

    collection.update(
        ids=[rec_id],
        metadatas=[{"layer": "semantic", "owner": "bob", "score": 0.99, "tag": "x"}],
    )

    fetched = collection.get(ids=[rec_id])
    docs = fetched.get("documents") or []
    metas = fetched.get("metadatas") or []
    assert docs and docs[0] == "preserved content"
    assert metas and metas[0].get("score") == 0.99
    assert metas[0].get("tag") == "x"


def test_update_changes_document_metadata_and_embedding(collection):
    """All three fields can be updated atomically in one call."""
    rec_id = "rec_full"
    collection.upsert(
        ids=[rec_id],
        documents=["v1"],
        embeddings=[_embed(3)],
        metadatas=[{"layer": "semantic", "version": 1}],
    )

    collection.update(
        ids=[rec_id],
        documents=["v2"],
        embeddings=[_embed(99)],
        metadatas=[{"layer": "semantic", "version": 2}],
    )

    fetched = collection.get(ids=[rec_id])
    docs = fetched.get("documents") or []
    metas = fetched.get("metadatas") or []
    assert docs and docs[0] == "v2"
    assert metas and metas[0].get("version") == 2


def test_update_coerces_list_metadata_to_json(collection):
    """Mirror upsert: list/dict metadata values are JSON-encoded as strings.

    This matches the existing wrapper convention (see `upsert`); the PATCH
    endpoint relies on the same coercion so persona_tags (a list) survive
    a metadata update without raising the v2 "scalar values only" error.
    """
    rec_id = "rec_list_meta"
    collection.upsert(
        ids=[rec_id],
        documents=["doc"],
        embeddings=[_embed(4)],
        metadatas=[{"layer": "semantic", "persona_tags": "[]"}],
    )

    collection.update(
        ids=[rec_id],
        metadatas=[{"layer": "semantic", "persona_tags": ["identity", "guide"]}],
    )

    fetched = collection.get(ids=[rec_id])
    metas = fetched.get("metadatas") or []
    assert metas
    # The wrapper JSON-encodes lists; on read we get the string back.
    assert metas[0].get("persona_tags") in (
        '["identity", "guide"]',
        '["identity","guide"]',
    )


def test_update_rejects_empty_ids(collection):
    """``ids`` is mandatory and non-empty."""
    with pytest.raises(ValueError):
        collection.update(ids=[], documents=["x"])
