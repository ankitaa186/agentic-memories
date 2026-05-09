from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json

import logging
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import HTTPException

from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_embedding_model_name, get_retrieve_max_fetch_cap
from src.services._constants import SYSTEM_MANAGED_FIELDS
from src.services.embedding_utils import generate_embedding


COLLECTION_NAME = "memories"
logger = logging.getLogger("agentic_memories.retrieval")


# AC22: Internally-derived metadata fields that `metadata_filter` MUST reject in
# addition to SYSTEM_MANAGED_FIELDS. These are populated per-record by the
# system (see ``_build_metadata`` in ``src/services/storage.py``); allowing
# generic `metadata_filter` access would expose internal scoring. Future
# stories that need filterable importance / confidence get a dedicated
# parameter, not generic metadata access.
INTERNAL_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "importance",
        "relevance_score",
        "confidence",
        "usage_count",
        "persona_tags",
        "emotional_signature",
    }
)


# AC18 timezone-normalization rejection message. Constant so tests can match it
# verbatim and so the route handler and the where-clause builder give the same
# error text.
NAIVE_DATETIME_MSG = "datetime must include timezone offset (e.g. Z or +00:00)"


def _normalize_iso_datetime(value: str, field_name: str) -> str:
    """Parse an ISO-8601 datetime, reject naive, normalize to UTC ISO.

    Stored ``timestamp`` is always UTC-aware ISO with ``+00:00`` shape (see
    ``src/services/storage.py:42``). Lex-compare in Chroma ``where`` only
    works correctly when the input is in the same shape, so callers MUST
    pass either a ``Z`` suffix or an explicit offset; non-UTC offsets are
    normalized to UTC before being returned.

    Raises:
        HTTPException(422) if the value is malformed or naive.
    """

    if value is None or value == "":
        raise HTTPException(status_code=422, detail=f"{field_name}: empty datetime")
    raw = value.strip()
    # Python 3.11+ accepts ``Z`` directly via fromisoformat; for safety on
    # 3.12 we still translate ``Z`` → ``+00:00`` so the parse path is the
    # same regardless of suffix style.
    parsed_input = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(parsed_input)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: invalid ISO 8601 datetime ({exc})",
        ) from exc
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: {NAIVE_DATETIME_MSG}",
        )
    return dt.astimezone(timezone.utc).isoformat()


def _coerce_expires_value(value: Any, field_name: str) -> int:
    """Normalize ``expires_after`` / ``expires_before`` to an epoch int.

    Accepts an int (interpreted as an epoch second) or a timezone-aware ISO
    8601 datetime string. Naive datetimes are rejected with 422 per AC18.
    """

    if isinstance(value, bool):  # bool subclasses int — reject explicitly
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: must be an epoch int or ISO 8601 datetime",
        )
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            raise HTTPException(status_code=422, detail=f"{field_name}: empty value")
        # Accept a bare integer string as epoch.
        if raw.lstrip("-").isdigit():
            try:
                return int(raw)
            except ValueError:
                pass
        normalized = _normalize_iso_datetime(raw, field_name)
        return int(datetime.fromisoformat(normalized).timestamp())
    raise HTTPException(
        status_code=422,
        detail=f"{field_name}: must be an epoch int or ISO 8601 datetime",
    )


def _parse_metadata_filter_pairs(
    raw_pairs: Optional[List[str]],
) -> Dict[str, List[str]]:
    """Parse repeatable ``metadata_filter`` query strings of form ``key:value``.

    Multiple values for the same key are AND-combined per AC1 (treated as
    "all values must match"); since Chroma where-equality is single-valued
    per key, multi-valued same-key entries are surfaced as a 422 (the user
    likely wants either OR or to issue separate calls). AC4/AC22 reject any
    key in the system-managed or internally-derived sets.
    """

    out: Dict[str, List[str]] = {}
    if not raw_pairs:
        return out
    for pair in raw_pairs:
        if not isinstance(pair, str) or ":" not in pair:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"metadata_filter: malformed entry {pair!r} (expected 'key:value')"
                ),
            )
        key, _, value = pair.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            raise HTTPException(
                status_code=422,
                detail=f"metadata_filter: empty key in entry {pair!r}",
            )
        if key in SYSTEM_MANAGED_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"metadata_filter: key '{key}' is system-managed and "
                    "cannot be filtered via metadata_filter; use the "
                    "dedicated query parameter if available."
                ),
            )
        if key in INTERNAL_METADATA_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"metadata_filter: key '{key}' is internally-derived "
                    "and not exposed via metadata_filter."
                ),
            )
        if key == "kind":
            raise HTTPException(
                status_code=422,
                detail=(
                    "metadata_filter: 'kind' must be filtered via the "
                    "dedicated `kind` query parameter."
                ),
            )
        out.setdefault(key, []).append(value)
    return out


def _build_where_clause(
    user_id: str,
    *,
    layer: Optional[str] = None,
    type_: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    expires_after: Optional[int] = None,
    expires_before: Optional[int] = None,
    kind: Optional[str] = None,
    metadata_filter: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """Translate filter inputs into a single Chroma ``where`` document.

    Replaces the legacy whitelist (formerly at ``retrieval.py:117-122``)
    that recognized only ``user_id``, ``layer``, and ``type``.

    Inputs are assumed to be already-validated by the route layer:
    - ``created_after`` / ``created_before`` are UTC-normalized ISO strings.
    - ``expires_after`` / ``expires_before`` are epoch ints.
    - ``metadata_filter`` keys are already vetted against the blocklists.

    **Note on timestamp filters:** Chroma 1.x rejects ``$gte`` / ``$lt``
    operators when the operand is a STRING (only numeric inverted indexes
    support range operators). The original AM-X.2 design assumed lex-compare
    on the ISO ``timestamp`` field would work natively in the where-clause;
    live-curl testing on 2026-05-08 proved otherwise (HTTP 500 on every
    persona-fallback that filtered by ``created_after``/``created_before``).
    The fix: this builder no longer emits ``timestamp`` range clauses.
    Callers (``search_memories`` and ``_apply_x2_filters_to_hybrid``) apply
    the timestamp predicate in Python after fetching the page. The two
    arguments are still accepted for backward compatibility with callers
    that pass them through this helper unchanged, but they are silently
    dropped from the resulting where-doc; ``search_memories`` is responsible
    for re-applying them post-fetch.

    AC11: when more than one Chroma operator is needed across keys, the
    output uses ``$and`` so multi-field ranged filters are well-formed
    (Chroma requires this; a flat dict only supports one operator key).

    AC21 (note in code per the story): ``expires_*`` filter records WITH a
    TTL only. Immortal memories (no ``ttl_epoch`` set on the record) are
    excluded by Chroma's where-clause matching, since ``$gte`` / ``$lt``
    require the field to exist. ``ttl_epoch`` is an int field so the
    Chroma-native predicate works as expected (verified against live
    Chroma 1.x in tests/integration/test_chroma_wrapper.py).
    """

    # ``created_after`` / ``created_before`` are intentionally NOT consumed
    # here — see the docstring. Reference them so static analysis does not
    # flag the unused-arg pattern.
    _ = created_after
    _ = created_before

    clauses: List[Dict[str, Any]] = [{"user_id": user_id}]
    if layer:
        clauses.append({"layer": layer})
    if type_:
        clauses.append({"type": type_})
    if kind:
        clauses.append({"kind": kind})

    # Range comparisons on ttl_epoch (an int field — safe for $gte/$lt).
    ttl_range: Dict[str, Any] = {}
    if expires_after is not None:
        ttl_range["$gte"] = int(expires_after)
    if expires_before is not None:
        ttl_range["$lt"] = int(expires_before)
    if ttl_range:
        clauses.append({"ttl_epoch": ttl_range})

    if metadata_filter:
        for key, values in metadata_filter.items():
            # AC1: multiple values for the same key are AND-combined as the
            # literal user provided. Since Chroma where-equality is
            # single-valued, multiple same-key entries collapse to AND of
            # equality clauses (which is satisfiable iff all equal — i.e.
            # exactly one literal). We therefore require uniqueness.
            unique = list(dict.fromkeys(values))
            if len(unique) > 1:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"metadata_filter: key '{key}' has conflicting "
                        f"values {values}; pass a single value per key."
                    ),
                )
            clauses.append({key: unique[0]})

    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _filter_records_by_timestamp(
    records: List[Dict[str, Any]],
    *,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Apply ``created_after`` / ``created_before`` predicates in Python.

    Chroma 1.x rejects ``$gte``/``$lt`` operators on string-valued fields,
    so the timestamp range filter cannot be pushed into the where-clause.
    This helper applies the same lex-compare predicate the where-clause
    builder used to emit, but on already-fetched records.

    Inputs assumed UTC-normalized ISO strings (``+00:00`` shape) — the route
    normalizes both before calling. The stored ``metadata.timestamp`` is
    written by ``storage.py`` in the same shape, so a lex-compare here is
    equivalent to the chronological compare.

    Records whose ``metadata.timestamp`` is missing or non-string are
    EXCLUDED from any range filter (parity with the previous Chroma-side
    behavior, which required the field to exist for the operator to match).
    """

    if created_after is None and created_before is None:
        return records
    out: List[Dict[str, Any]] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        ts = meta.get("timestamp")
        if not isinstance(ts, str):
            continue
        if created_after is not None and ts < created_after:
            continue
        if created_before is not None and ts >= created_before:
            continue
        out.append(r)
    return out


def _ts_key(record: Dict[str, Any]) -> str:
    """Extract the ISO ``timestamp`` from a record's metadata for sorting.

    Shared by the ``sort=`` path in ``app.retrieve`` and the filter-only
    branch of ``search_memories`` so both paths use a single canonical
    sort-key extractor (AC23 — sort-logic consolidation).
    """

    if not isinstance(record, dict):
        return ""
    meta = record.get("metadata", {})
    if not isinstance(meta, dict):
        return ""
    ts = meta.get("timestamp", "")
    return ts if isinstance(ts, str) else ""


def sort_by_recency(
    records: List[Dict[str, Any]], *, newest_first: bool = True
) -> List[Dict[str, Any]]:
    """Return records sorted by ``metadata.timestamp`` (lex-compare).

    AC23: shared helper used by both the ``sort=`` path in ``app.retrieve``
    and the filter-only path here, so both paths can never drift apart.
    Uses Python sort stability for ties.
    """

    return sorted(records, key=_ts_key, reverse=bool(newest_first))


def _embedding_dim_from_model(model: str) -> int:
    name = (model or "").lower()
    if "text-embedding-3-large" in name:
        return 3072
    if "text-embedding-3-small" in name:
        return 1536
    # Default to 3072 if unknown
    return 3072


@lru_cache(maxsize=1)
def _standard_collection_name() -> str:
    """Resolve the dimension-suffixed collection name.

    Cached process-wide because the embedding-dimension probe (a real
    `generate_embedding` API call) is otherwise re-issued on every call
    site that touches Chroma. The fast eviction sweeper runs every 15
    minutes — without this cache, that's ~96 unnecessary embedding calls
    per day just to recompute a constant. Embedding dimension does not
    change mid-process, so the lru_cache is safe; a model swap requires
    a process restart, which clears the cache as a side effect.
    """
    # Prefer actual embedding dimension to align with storage collections
    try:
        probe = generate_embedding("dimension-probe") or []
        dim = len(probe)
    except Exception:
        dim = 0
    if dim <= 0:
        model = get_embedding_model_name()
        dim = _embedding_dim_from_model(model)
    return f"{COLLECTION_NAME}_{dim}"


def _get_collection() -> Any:
    client = get_chroma_client()
    if client is None:
        raise RuntimeError("Chroma client not available")

    # Ensure Chroma is healthy before making requests
    if not client.health_check():
        raise RuntimeError("Chroma database is not available or not ready")

    return client.get_collection(_standard_collection_name())  # type: ignore[attr-defined]


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _keyword_score(query: str, doc: str) -> float:
    q_tokens = set(query.lower().split())
    d_tokens = set(doc.lower().split())
    if not q_tokens or not d_tokens:
        return 0.0
    return len(q_tokens & d_tokens) / len(q_tokens)


def _hybrid_score(semantic: float, keyword: float) -> float:
    return 0.8 * semantic + 0.2 * keyword


def search_memories(
    user_id: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Public retrieval entry point.

    Story 2.1: wraps the body in a Langfuse root span (`retrieval`) so the
    embedding observation produced by `generate_embedding(...)` for non-empty
    queries nests under a single parent trace per call. The wrap also covers
    the empty-query metadata-only branch so its latency is visible. Falls
    through cleanly when Langfuse is unavailable or already-nested under a
    parent (e.g. a future graph caller). Filter semantics are documented on
    the inner ``_search_memories_impl``.
    """
    from src.services.tracing import root_span

    with root_span(
        name="retrieval",
        user_id=user_id,
        input={
            "user_id": user_id,
            "has_query": bool(query and query.strip()),
            "query_len": len(query or ""),
            "limit": limit,
            "offset": offset,
        },
        metadata={
            "filter_keys": list((filters or {}).keys()),
        },
    ) as _root_span:
        results, total = _search_memories_impl(
            user_id, query, filters=filters, limit=limit, offset=offset
        )
        if _root_span is not None:
            try:
                _root_span.update(
                    output={
                        "returned": len(results),
                        "total": total,
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("[retrieve] root_span.update failed: %s", exc)
        return results, total


def _search_memories_impl(
    user_id: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Inner search body (Story 2.1: extracted so ``search_memories`` can wrap
    the whole call in a Langfuse root span).

    Filter keys recognized (X.2):
    - ``layer``, ``type`` — existing equality filters.
    - ``kind`` — equality on ``metadata.kind`` (X.2 AC1).
    - ``created_after`` / ``created_before`` — UTC-normalized ISO 8601
      strings (X.2 AC1/AC18). The route layer is responsible for
      timezone-normalizing aware datetimes and rejecting naive ones; this
      function passes the strings through as-is to the where-clause builder.
    - ``expires_after`` / ``expires_before`` — epoch ints (X.2 AC1).
    - ``metadata_filter`` — dict of {key: [values]} pre-validated against
      ``SYSTEM_MANAGED_FIELDS`` and ``INTERNAL_METADATA_FIELDS``.
    - ``persona`` / ``persona_tags`` — post-fetch filtering (legacy).

    When ``query`` is empty AND any of the new filters are active, this
    function returns records sorted by ``metadata.timestamp`` DESC
    (recency-desc) per X.2 AC6 / AC20. Pagination on the filter-only path
    is best-effort within ``RETRIEVE_MAX_FETCH_CAP`` (X.2 AC12).
    """

    filters = filters or {}
    redis = get_redis_client()
    use_cache = redis is not None and (filters.get("layer") == "short-term")
    logger.info(
        "[retrieve] user_id=%s query_len=%s filters=%s limit=%s offset=%s use_cache=%s",
        user_id,
        len(query or ""),
        list(filters.keys()),
        limit,
        offset,
        use_cache,
    )

    # Detect new X.2 filters; if any are active we always sort by recency-desc
    # on the query-less path even if cache would otherwise be applicable. The
    # short-term cache is keyed on (user_id, query) and does NOT include the
    # filter dict, so we MUST bypass it whenever any new filter is set to
    # avoid returning stale cross-filter results.
    new_filter_keys = (
        "kind",
        "created_after",
        "created_before",
        "expires_after",
        "expires_before",
        "metadata_filter",
    )
    # `is not None` so falsy-but-real values (e.g. expires_after=0) still
    # disable the cache; truthy check would treat 0 as filter-not-present and
    # serve stale unfiltered cached results. (PR #62 review #8.)
    has_new_filter = any(filters.get(k) is not None for k in new_filter_keys)
    if has_new_filter:
        use_cache = False

    cache_key = None
    if use_cache:
        ns = redis.get(f"mem:ns:{user_id}") or "0"
        cache_key = f"mem:srch:{user_id}:{_hash_query(query)}:v{ns}"
        cached = redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            logger.info(
                "[retrieve.cache.hit] user_id=%s key=%s count=%s",
                user_id,
                cache_key,
                len(data.get("results", [])),
            )
            return data["results"], data.get("total", len(data["results"]))

    try:
        collection = _get_collection()
        logger.info(
            "[retrieve.chroma] collection=%s where_keys=%s",
            getattr(collection, "name", "?"),
            [],
        )
    except RuntimeError as e:
        # Chroma is not available, return empty results
        logger.warning("Chroma not available: %s", e)
        return [], 0

    # Build the Chroma where document via the unified builder (X.2 AC10).
    where = _build_where_clause(
        user_id=user_id,
        layer=filters.get("layer") or None,
        type_=filters.get("type") or None,
        created_after=filters.get("created_after") or None,
        created_before=filters.get("created_before") or None,
        expires_after=filters.get("expires_after"),
        expires_before=filters.get("expires_before"),
        kind=filters.get("kind") or None,
        metadata_filter=filters.get("metadata_filter") or None,
    )

    is_filter_only_path = not query or query.strip() == ""

    # ``created_*`` filters are applied in Python post-fetch (Chroma 1.x
    # rejects $gte/$lt on string fields). When either is set we must
    # over-fetch to compensate; the cap still applies.
    created_after_filter = filters.get("created_after") or None
    created_before_filter = filters.get("created_before") or None
    has_ts_filter = (
        created_after_filter is not None or created_before_filter is not None
    )

    if is_filter_only_path:
        # X.2 AC12: filter-only path uses ``get(where=...)`` without a Chroma
        # offset (Chroma `get` order is undefined), then sorts by timestamp
        # DESC in Python and slices the requested page.
        cap = get_retrieve_max_fetch_cap()
        # Buffer of 50 to absorb post-fetch persona filtering churn without
        # forcing the caller to over-allocate. Capped by RETRIEVE_MAX_FETCH_CAP.
        # When timestamp filters are active we cannot push them into the
        # where-clause (see _build_where_clause docstring), so we fetch up to
        # the cap to maximize the chance of finding records inside the
        # requested time window.
        if has_ts_filter:
            fetch_target = cap
        else:
            fetch_target = min(int(limit) + int(offset) + 50, cap)
        if fetch_target < 1:
            fetch_target = 1
        semantic_results = collection.get(where=where, limit=fetch_target)  # type: ignore[attr-defined]
        ids = semantic_results.get("ids", [])
        docs = semantic_results.get("documents", [])
        metas = semantic_results.get("metadatas", [])
        scores = [0.0] * len(ids)
    else:
        # Semantic query
        emb = generate_embedding(query) or []
        # When a timestamp filter is active alongside a semantic query,
        # fetch up to the full RETRIEVE_MAX_FETCH_CAP. The timestamp filter is
        # applied post-fetch in Python; Chroma returns results in semantic-
        # rank order, so a small +50 window can miss matches that fall just
        # outside it when the filter is selective. (PR #62 review #6.)
        if has_ts_filter:
            n_results = get_retrieve_max_fetch_cap()
        else:
            n_results = limit + offset
        if n_results < 1:
            n_results = 1
        semantic_results = collection.query(  # type: ignore[attr-defined]
            query_embeddings=[emb], n_results=n_results, where=where
        )
        ids = semantic_results.get("ids", [[]])[0]
        docs = semantic_results.get("documents", [[]])[0]
        scores = semantic_results.get("distances", [[]])[0]
        metas = semantic_results.get("metadatas", [[]])[0]

    items: List[Dict[str, Any]] = []
    for i, mem_id in enumerate(ids):
        if i >= len(docs) or i >= len(metas) or i >= len(scores):
            continue
        semantic_sim = 1.0 - float(scores[i]) if scores else 0.0
        k_score = _keyword_score(query, docs[i])
        final = _hybrid_score(semantic_sim, k_score)
        meta = metas[i] or {}
        if not isinstance(meta, dict):
            meta = {"raw": meta}
        if isinstance(meta, dict):
            persona_raw = meta.get("persona_tags")
            if isinstance(persona_raw, str):
                try:
                    meta["persona_tags"] = json.loads(persona_raw)
                except Exception:
                    meta["persona_tags"] = []
            emotional_raw = meta.get("emotional_signature")
            if isinstance(emotional_raw, str):
                try:
                    meta["emotional_signature"] = json.loads(emotional_raw)
                except Exception:
                    meta["emotional_signature"] = {}
            if "importance" in meta:
                try:
                    meta["importance"] = float(meta["importance"])
                except Exception:
                    meta["importance"] = 0.0
        item = {
            "id": mem_id,
            "content": docs[i],
            "score": final,
            "metadata": meta,
            "importance": (meta or {}).get("importance"),
            "persona_tags": (meta or {}).get("persona_tags"),
            "emotional_signature": (meta or {}).get("emotional_signature"),
        }
        items.append(item)

    # Apply timestamp range filters in Python (Chroma 1.x rejects $gte/$lt
    # on string fields, so this can't run in the where-clause). Mirrors the
    # predicate the where-clause builder used to emit pre-2026-05-08-fix.
    if has_ts_filter:
        items = _filter_records_by_timestamp(
            items,
            created_after=created_after_filter,
            created_before=created_before_filter,
        )

    # Sort by final score and paginate
    persona_filter = filters.get("persona") or filters.get("persona_tags")
    if persona_filter:
        if isinstance(persona_filter, str):
            target = {persona_filter}
        elif isinstance(persona_filter, list):
            target = {str(tag) for tag in persona_filter}
        else:
            target = {str(persona_filter)}
        filtered = []
        for item in items:
            tags = item.get("persona_tags") or []
            if isinstance(tags, list) and any(tag in target for tag in tags):
                filtered.append(item)
        items = filtered

    # X.2 AC6 / AC20: filter-only paths return results in recency-desc order
    # (newest `metadata.timestamp` first). The legacy ``score`` sort is kept
    # for ``query``-supplied paths so existing semantic ranking is unchanged.
    if is_filter_only_path:
        items = sort_by_recency(items, newest_first=True)
    else:
        items.sort(key=lambda x: x["score"], reverse=True)
    total = len(items)
    page = items[offset : offset + limit]
    logger.info(
        "[retrieve.results] user_id=%s returned=%s total=%s", user_id, len(page), total
    )

    # Cache short-term
    if use_cache and cache_key and redis is not None:
        redis.setex(cache_key, 180, json.dumps({"results": page, "total": total}))
        logger.info(
            "[retrieve.cache.store] user_id=%s key=%s count=%s ttl=%s",
            user_id,
            cache_key,
            len(page),
            180,
        )

    return page, total
