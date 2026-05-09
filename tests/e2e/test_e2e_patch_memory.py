"""E2E tests for PATCH /v1/memories/{memory_id} (Story AM-X.1).

Covers:
- AC18: Annie-meals round-trip — store a memory, retrieve, PATCH to update
  content + metadata, retrieve again. Asserts memory_id continuity (same id
  before and after PATCH) and that the new content is reflected.
- AC21: Explicit-null-over-wire — PATCH with raw JSON body
  ``{"ttl_seconds": null}``. Asserts the stored Chroma metadata has
  `ttl_epoch` removed. Uses ``httpx.AsyncClient`` against the running app so
  the JSON body is parsed by FastAPI exactly as in production (mirrors the
  Pydantic auto-memory pitfall on key-name handling).

These tests run against a deployed instance at the URL from ``e2e_config``.
They are skipped automatically when the server is unreachable (the
``app_ready`` fixture handles the wait-and-fail case).
"""

from __future__ import annotations

import json

import httpx
import pytest


# ---------------------------------------------------------------------------
# AC18 — Annie meals round-trip
# ---------------------------------------------------------------------------


def test_e2e_annie_meals_round_trip(api_client, e2e_config, unique_user_id):
    """Annie stores a meal preference, retrieves it, PATCHes the content at
    lunch, and retrieves again. memory_id must be preserved across PATCH and
    the new content must surface on the next retrieve (AC18, AC1, AC15).
    """
    user_id = unique_user_id

    # Step 1 — store a memory via /v1/memories/direct.
    store_payload = {
        "user_id": user_id,
        "content": "Annie typically has oatmeal for breakfast.",
        "layer": "semantic",
        "type": "explicit",
        "importance": 0.7,
        "metadata": {"meal": "breakfast"},
    }
    store_resp = api_client.post(
        f"{e2e_config.api_base_url}/v1/memories/direct", json=store_payload
    )
    assert store_resp.status_code == 200, store_resp.text
    memory_id = store_resp.json()["memory_id"]
    assert memory_id and memory_id.startswith("mem_")

    # Step 2 — retrieve to confirm storage.
    retrieve_resp_1 = api_client.get(
        f"{e2e_config.api_base_url}/v1/retrieve",
        params={"query": "breakfast", "user_id": user_id, "limit": 5},
    )
    assert retrieve_resp_1.status_code == 200
    items_1 = retrieve_resp_1.json().get("memories", [])
    assert any(m.get("id") == memory_id for m in items_1), (
        "Stored memory not found on first retrieve"
    )

    # Step 3 — PATCH at lunch: Annie now prefers a salad. Add metadata.meal_v2.
    patch_resp = api_client.patch(
        f"{e2e_config.api_base_url}/v1/memories/{memory_id}",
        params={"user_id": user_id},
        json={
            "content": "Annie now prefers a salad for lunch.",
            "metadata": {"meal": "lunch", "updated_via": "patch_e2e"},
            "importance": 0.85,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    # AC1: memory_id preserved.
    assert body["memory_id"] == memory_id
    assert body["chroma_updated"] is True
    assert body["embedding_regenerated"] is True
    # No typed_table fan-out for a 'semantic' record.
    assert body["typed_table_updated"] is None

    # Step 4 — retrieve again with a query that matches the NEW content.
    retrieve_resp_2 = api_client.get(
        f"{e2e_config.api_base_url}/v1/retrieve",
        params={"query": "salad lunch", "user_id": user_id, "limit": 5},
    )
    assert retrieve_resp_2.status_code == 200
    items_2 = retrieve_resp_2.json().get("memories", [])

    # AC1 + AC15: the same memory_id must still be present, AND the content
    # surfaced must reflect the PATCH.
    target = next((m for m in items_2 if m.get("id") == memory_id), None)
    assert target is not None, "PATCHed memory not returned on retrieve after update"
    new_content = target.get("content") or target.get("text") or ""
    assert "salad" in new_content.lower(), (
        f"Expected new content to surface; got {new_content!r}"
    )


# ---------------------------------------------------------------------------
# AC21 — explicit-null over the wire (httpx)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_patch_explicit_null_ttl_clears_ttl_epoch(
    app_ready, e2e_config, unique_user_id
):
    """Send ``{"ttl_seconds": null}`` as raw JSON via httpx.AsyncClient (NOT
    via Pydantic-constructed request) and assert the resulting record has
    no ``ttl_epoch`` in its metadata (AC9, AC21).

    This is the wire-level test for the sentinel scheme — confirms explicit
    JSON null is distinguishable from omitted-field after FastAPI body parse.
    """
    user_id = unique_user_id
    base = e2e_config.api_base_url

    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        # Store a record with a TTL so we have something to clear.
        store_resp = await client.post(
            "/v1/memories/direct",
            json={
                "user_id": user_id,
                "content": "Annie's coffee preference (TTL = 1h).",
                "layer": "semantic",
                "ttl_seconds": 3600,
            },
        )
        assert store_resp.status_code == 200, store_resp.text
        memory_id = store_resp.json()["memory_id"]

        # Send raw JSON with explicit null for ttl_seconds.
        # IMPORTANT: pass via `content=` and Content-Type to bypass any
        # client-side serialization that might strip nulls.
        raw_body = json.dumps({"ttl_seconds": None})
        patch_resp = await client.patch(
            f"/v1/memories/{memory_id}",
            params={"user_id": user_id},
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )
        assert patch_resp.status_code == 200, patch_resp.text

        # Now retrieve the memory and inspect its metadata.
        retrieve_resp = await client.get(
            "/v1/retrieve",
            params={
                "query": "coffee",
                "user_id": user_id,
                "limit": 10,
            },
        )
        assert retrieve_resp.status_code == 200
        items = retrieve_resp.json().get("memories", [])
        target = next((m for m in items if m.get("id") == memory_id), None)
        assert target is not None

        meta = target.get("metadata") or {}
        assert "ttl_epoch" not in meta, (
            f"ttl_epoch should have been cleared but is present: {meta.get('ttl_epoch')}"
        )

    # Also assert the omitted-field path (control test): a PATCH that does
    # NOT include ttl_seconds at all must leave the record untouched.
    # Re-set a TTL, then PATCH only `importance`, then verify ttl_epoch is
    # still present.
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        re_set = await client.patch(
            f"/v1/memories/{memory_id}",
            params={"user_id": user_id},
            json={"ttl_seconds": 7200},
        )
        assert re_set.status_code == 200

        only_importance = await client.patch(
            f"/v1/memories/{memory_id}",
            params={"user_id": user_id},
            json={"importance": 0.42},
        )
        assert only_importance.status_code == 200

        retrieve_resp = await client.get(
            "/v1/retrieve",
            params={"query": "coffee", "user_id": user_id, "limit": 10},
        )
        items = retrieve_resp.json().get("memories", [])
        target = next((m for m in items if m.get("id") == memory_id), None)
        meta = target.get("metadata") or {}
        assert "ttl_epoch" in meta, (
            "Omitted ttl_seconds must leave ttl_epoch unchanged (AC9)"
        )
