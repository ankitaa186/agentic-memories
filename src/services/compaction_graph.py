from __future__ import annotations

from typing import Any, Dict, List

import logging
import json
import time as _time

from langgraph.graph import StateGraph, END  # type: ignore

from src.services.compaction_ops import (
    ttl_cleanup,
    simple_deduplicate,
    deduplicate_episodic,
    deduplicate_emotional,
    ttl_cleanup_timescale,
    _get_collection,
)
from src.services.embedding_utils import generate_embedding
from src.services.storage import upsert_memories
from src.models import Memory
from src.services.extraction import extract_from_transcript
from src.schemas import TranscriptRequest, Message
from src.services.prompts import CONSOLIDATION_PROMPT


logger = logging.getLogger("agentic_memories.compaction_graph")


def _cluster_memories(
    memories: List[Dict[str, Any]], threshold: float = 0.75
) -> List[List[Dict[str, Any]]]:
    """Cluster memories by embedding similarity.

    Groups memories with cosine similarity > threshold into clusters.
    Requires minimum 5 memories to attempt clustering.
    Returns only clusters with 3-10 memories (skip pairs, prevent over-merging).

    Args:
            memories: List of memory dicts with 'id', 'content', 'metadata'
            threshold: Similarity threshold for clustering (default 0.75)

    Returns:
            List of clusters, where each cluster is a list of memory dicts
    """
    if len(memories) < 5:
        return []

    # Generate embeddings for all memories
    embeddings: List[List[float]] = []
    valid_memories: List[Dict[str, Any]] = []

    for mem in memories:
        content = mem.get("content", "")
        if not content:
            continue
        try:
            emb = generate_embedding(content)
            if emb:
                embeddings.append(emb)
                valid_memories.append(mem)
        except Exception as e:
            logger.warning("[cluster.embed.error] id=%s error=%s", mem.get("id"), e)
            continue

    if len(valid_memories) < 3:
        return []

    # Compute similarity matrix and cluster using greedy approach
    n = len(valid_memories)
    used = set()
    clusters: List[List[Dict[str, Any]]] = []

    for i in range(n):
        if i in used:
            continue

        cluster = [valid_memories[i]]
        used.add(i)

        for j in range(i + 1, n):
            if j in used:
                continue

            # Compute cosine similarity
            a, b = embeddings[i], embeddings[j]
            if len(a) != len(b):
                continue

            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5

            if na <= 0 or nb <= 0:
                continue

            cos_sim = dot / (na * nb)

            if cos_sim >= threshold:
                # Check similarity with ALL cluster members (complete linkage)
                is_similar_to_all = True
                for k_idx, k_mem in enumerate(cluster):
                    if k_idx == 0:
                        continue  # Already checked with i
                    k_orig_idx = valid_memories.index(k_mem)
                    k_emb = embeddings[k_orig_idx]
                    dot_k = sum(x * y for x, y in zip(k_emb, b))
                    na_k = sum(x * x for x in k_emb) ** 0.5
                    cos_k = dot_k / (na_k * nb) if na_k > 0 else 0
                    if cos_k < threshold:
                        is_similar_to_all = False
                        break

                if is_similar_to_all and len(cluster) < 10:  # Max cluster size
                    cluster.append(valid_memories[j])
                    used.add(j)

        # Only keep clusters with 3-10 memories
        if 3 <= len(cluster) <= 10:
            clusters.append(cluster)

    logger.info("[cluster] found=%s clusters from %s memories", len(clusters), n)
    return clusters


def _consolidate_cluster(user_id: str, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use LLM to consolidate a cluster of related memories into a single golden record.

    Args:
            user_id: User ID for the memories
            cluster: List of memory dicts to consolidate

    Returns:
            Dict with 'memory' (Memory object) and 'source_ids' (list of source IDs)
    """
    from src.services.extract_utils import _call_llm_json
    from datetime import datetime

    # Format memories for prompt with timestamps for conflict resolution
    # Sort by timestamp (oldest first) so LLM sees chronological order
    def get_timestamp(mem: Dict[str, Any]) -> str:
        meta = mem.get("metadata", {})
        # Try created_at first, fall back to updated_at
        ts = meta.get("created_at") or meta.get("updated_at") or ""
        if ts:
            # Format as date string if it's a valid timestamp
            try:
                if isinstance(ts, (int, float)):
                    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                elif isinstance(ts, str):
                    # Already a string, extract date portion
                    return ts[:10] if len(ts) >= 10 else ts
            except Exception:
                pass
        return "unknown"

    # Sort cluster by timestamp (oldest first)
    sorted_cluster = sorted(cluster, key=lambda m: get_timestamp(m))

    memories_text = "\n".join(
        [f"- [{get_timestamp(mem)}] {mem.get('content', '')}" for mem in sorted_cluster]
    )

    system_prompt = CONSOLIDATION_PROMPT.format(memories=memories_text)

    try:
        # Use the shared LLM call utility (supports OpenAI/xAI, retries, tracing)
        response = _call_llm_json(
            system_prompt, {"action": "consolidate"}, expect_array=False
        )

        if not response:
            logger.warning(
                "[consolidate.llm.empty] user_id=%s cluster_size=%s",
                user_id,
                len(cluster),
            )
            return {"memory": None, "source_ids": []}

        # Parse response
        content = response.get("content", "")
        if not content:
            logger.warning("[consolidate.parse.empty] user_id=%s", user_id)
            return {"memory": None, "source_ids": []}

        # Get max confidence from sources
        source_confidences = [
            float(mem.get("metadata", {}).get("confidence", 0.5)) for mem in cluster
        ]
        max_confidence = max(source_confidences) if source_confidences else 0.9

        # Merge tags from all sources (deduplicated)
        all_tags = set()
        for mem in cluster:
            meta = mem.get("metadata", {})
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            if isinstance(tags, list):
                all_tags.update(tags)

        # Get source IDs
        source_ids = [mem.get("id") for mem in cluster if mem.get("id")]

        # Create consolidated memory
        memory = Memory(
            user_id=user_id,
            content=content,
            layer="semantic",
            type="explicit",
            confidence=max_confidence,
            embedding=generate_embedding(content),
            metadata={
                "source": "consolidation",
                "tags": list(all_tags),
                "consolidated_from": source_ids,
                "consolidated_count": len(cluster),
            },
        )

        logger.info(
            "[consolidate.success] user_id=%s sources=%s content_len=%s",
            user_id,
            len(source_ids),
            len(content),
        )

        return {"memory": memory, "source_ids": source_ids}

    except Exception as e:
        logger.error("[consolidate.error] user_id=%s error=%s", user_id, e)
        return {"memory": None, "source_ids": []}


def _fetch_user_memories(
    user_id: str, limit: int = 200, offset: int = 0
) -> List[Dict[str, Any]]:
    """Fetch a batch of user memories with ids, content, and metadata.
    Best-effort using v2 collection get.
    """
    col = _get_collection()
    res = col.get(
        where={"user_id": user_id},
        limit=limit,
        offset=offset,
        include=["documents", "metadatas"],
    )  # type: ignore[attr-defined]
    ids = res.get("ids", [])
    docs = res.get("documents", [])
    metas = res.get("metadatas", [])
    items: List[Dict[str, Any]] = []
    for i, mid in enumerate(ids or []):
        if i >= len(docs) or i >= len(metas):
            continue
        items.append({"id": mid, "content": docs[i], "metadata": metas[i]})
    return items


def _reextract_memories(
    user_id: str, candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Re-run the store/extraction pipeline per memory content to reclassify and normalize.
    Returns dict with keys: new_memories (List[Memory]), delete_ids (List[str]).
    """
    new_mems: List[Memory] = []
    delete_ids: List[str] = []
    skipped_count = 0
    error_count = 0

    for c in candidates:
        mid = c.get("id")
        content = c.get("content", "")
        _metadata = c.get("metadata", {})

        # Validate candidate structure
        if not mid:
            logger.warning(
                "[graph.reextract.skip] user_id=%s reason=missing_id", user_id
            )
            skipped_count += 1
            continue

        if not content or not content.strip():
            logger.warning(
                "[graph.reextract.skip] user_id=%s id=%s reason=empty_content",
                user_id,
                mid,
            )
            skipped_count += 1
            continue

        # Create extraction request
        req = TranscriptRequest(
            user_id=user_id, history=[Message(role="user", content=content)]
        )

        try:
            result = extract_from_transcript(req)
            if result.memories and len(result.memories) > 0:
                # Validate that new memories have proper structure
                valid_memories = []
                for mem in result.memories:
                    if mem.content and mem.content.strip():
                        valid_memories.append(mem)
                    else:
                        logger.warning(
                            "[graph.reextract.skip_memory] user_id=%s id=%s reason=empty_extracted_content",
                            user_id,
                            mid,
                        )

                if valid_memories:
                    new_mems.extend(valid_memories)
                    delete_ids.append(mid)
                    logger.debug(
                        "[graph.reextract.success] user_id=%s id=%s extracted=%s",
                        user_id,
                        mid,
                        len(valid_memories),
                    )
                else:
                    logger.warning(
                        "[graph.reextract.skip] user_id=%s id=%s reason=no_valid_memories",
                        user_id,
                        mid,
                    )
                    skipped_count += 1
            else:
                logger.warning(
                    "[graph.reextract.skip] user_id=%s id=%s reason=no_memories_extracted",
                    user_id,
                    mid,
                )
                skipped_count += 1

        except Exception as exc:
            logger.error(
                "[graph.reextract.error] user_id=%s id=%s error=%s", user_id, mid, exc
            )
            error_count += 1
            continue

    logger.info(
        "[graph.reextract.summary] user_id=%s processed=%s new_memories=%s delete_ids=%s skipped=%s errors=%s",
        user_id,
        len(candidates),
        len(new_mems),
        len(delete_ids),
        skipped_count,
        error_count,
    )

    return {"new_memories": new_mems, "delete_ids": delete_ids}


def build_compaction_graph() -> StateGraph:
    graph = StateGraph(dict)

    def node_init(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        _span = start_span(
            "compaction_init",
            input={
                "user_id": state.get("user_id"),
                "limit": state.get("limit"),
                "dry_run": state.get("dry_run"),
            },
        )

        # Ensure required keys
        state.setdefault("metrics", {})
        state["t0"] = _time.perf_counter()
        logger.info(
            "[graph.init] user_id=%s limit=%s", state.get("user_id"), state.get("limit")
        )

        end_span(output={"initialized": True})
        return state

    def node_ttl(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        _span = start_span("compaction_ttl_cleanup", input={})

        # Global TTL cleanup (idempotent)
        _t = _time.perf_counter()
        deleted = ttl_cleanup()
        state["metrics"]["ttl_deleted"] = state["metrics"].get("ttl_deleted", 0) + int(
            deleted or 0
        )

        # TimescaleDB TTL cleanup (best-effort)
        ts_deleted = 0
        try:
            ts_deleted = ttl_cleanup_timescale()
            state["metrics"]["ttl_timescale_deleted"] = ts_deleted
        except Exception as exc:
            logger.warning("[graph.ttl.timescale_error] %s", exc)
            state["metrics"]["ttl_timescale_deleted"] = 0

        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.ttl] chromadb_deleted=%s timescale_deleted=%s latency_ms=%s",
            deleted,
            ts_deleted,
            latency_ms,
        )

        end_span(
            output={
                "deleted": deleted,
                "timescale_deleted": ts_deleted,
                "latency_ms": latency_ms,
            }
        )
        return state

    def node_dedup(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        user_id = state.get("user_id")
        lim = int(state.get("limit") or 500)

        _span = start_span(
            "compaction_deduplication", input={"user_id": user_id, "limit": lim}
        )

        _t = _time.perf_counter()

        # ChromaDB dedup
        stats = simple_deduplicate(str(user_id), limit=lim)
        state["metrics"].update(
            {
                "dedup_scanned": stats.get("scanned", 0),
                "dedup_removed": stats.get("removed", 0),
            }
        )

        # TimescaleDB episodic dedup (best-effort)
        try:
            ep_stats = deduplicate_episodic(str(user_id), limit=lim)
            state["metrics"]["dedup_episodic_scanned"] = ep_stats.get("scanned", 0)
            state["metrics"]["dedup_episodic_removed"] = ep_stats.get("removed", 0)
        except Exception as exc:
            logger.warning("[graph.dedup.episodic_error] user_id=%s %s", user_id, exc)
            state["metrics"]["dedup_episodic_scanned"] = 0
            state["metrics"]["dedup_episodic_removed"] = 0

        # TimescaleDB emotional dedup (best-effort)
        try:
            em_stats = deduplicate_emotional(str(user_id), limit=lim)
            state["metrics"]["dedup_emotional_scanned"] = em_stats.get("scanned", 0)
            state["metrics"]["dedup_emotional_removed"] = em_stats.get("removed", 0)
        except Exception as exc:
            logger.warning("[graph.dedup.emotional_error] user_id=%s %s", user_id, exc)
            state["metrics"]["dedup_emotional_scanned"] = 0
            state["metrics"]["dedup_emotional_removed"] = 0

        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.dedup] user_id=%s chromadb=%s episodic=%s emotional=%s latency_ms=%s",
            user_id,
            stats,
            state["metrics"].get("dedup_episodic_removed", 0),
            state["metrics"].get("dedup_emotional_removed", 0),
            latency_ms,
        )

        end_span(
            output={
                "scanned": stats.get("scanned", 0),
                "removed": stats.get("removed", 0),
                "episodic_removed": state["metrics"].get("dedup_episodic_removed", 0),
                "emotional_removed": state["metrics"].get("dedup_emotional_removed", 0),
                "latency_ms": latency_ms,
            }
        )
        return state

    def node_consolidate(state: Dict[str, Any]) -> Dict[str, Any]:
        """Consolidate semantically related memories into golden records."""
        from src.services.tracing import start_span, end_span

        user_id = str(state.get("user_id"))

        # Skip if consolidation is disabled (default: True = skip)
        if state.get("skip_consolidate", True):
            logger.info(
                "[graph.consolidate.skip] user_id=%s reason=skip_consolidate_flag",
                user_id,
            )
            return state

        _span = start_span(
            "compaction_consolidate",
            input={
                "user_id": user_id,
            },
        )

        _t = _time.perf_counter()

        # 1. Load all memories for user
        limit = int(state.get("limit") or 500)
        memories = _fetch_user_memories(user_id, limit=limit)

        if len(memories) < 5:
            logger.info(
                "[graph.consolidate.skip] user_id=%s reason=too_few_memories count=%s",
                user_id,
                len(memories),
            )
            state.setdefault("metrics", {})
            state["metrics"]["consolidated_count"] = 0
            state["metrics"]["sources_removed"] = 0
            end_span(output={"skipped": True, "reason": "too_few_memories"})
            return state

        # 2. Cluster by embedding similarity
        clusters = _cluster_memories(memories, threshold=0.75)

        if not clusters:
            logger.info(
                "[graph.consolidate.skip] user_id=%s reason=no_clusters", user_id
            )
            state.setdefault("metrics", {})
            state["metrics"]["consolidated_count"] = 0
            state["metrics"]["sources_removed"] = 0
            end_span(output={"skipped": True, "reason": "no_clusters"})
            return state

        # 3. For each cluster >= 3 memories: consolidate via LLM
        consolidated_count = 0
        sources_removed = 0
        dry_run = state.get("dry_run", False)

        for cluster in clusters:
            result = _consolidate_cluster(user_id, cluster)

            if result.get("memory") and result.get("source_ids"):
                if dry_run:
                    logger.info(
                        "[graph.consolidate.dry_run] user_id=%s would_merge=%s",
                        user_id,
                        len(result["source_ids"]),
                    )
                    consolidated_count += 1
                    sources_removed += len(result["source_ids"])
                else:
                    try:
                        # 4. Store consolidated, delete sources (transaction safety)
                        memory = result["memory"]
                        source_ids = result["source_ids"]

                        # Upsert consolidated memory first
                        upsert_memories(user_id, [memory])

                        # Delete source memories only after successful upsert
                        col = _get_collection()
                        col.delete(ids=source_ids)  # type: ignore[attr-defined]

                        consolidated_count += 1
                        sources_removed += len(source_ids)

                        logger.info(
                            "[graph.consolidate] merged %s → 1 user_id=%s",
                            len(source_ids),
                            user_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "[graph.consolidate.error] user_id=%s error=%s",
                            user_id,
                            exc,
                        )
                        continue

        state.setdefault("metrics", {})
        state["metrics"]["consolidated_count"] = consolidated_count
        state["metrics"]["sources_removed"] = sources_removed

        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.consolidate.done] user_id=%s clusters=%s consolidated=%s sources_removed=%s latency_ms=%s",
            user_id,
            len(clusters),
            consolidated_count,
            sources_removed,
            latency_ms,
        )

        end_span(
            output={
                "clusters": len(clusters),
                "consolidated_count": consolidated_count,
                "sources_removed": sources_removed,
                "latency_ms": latency_ms,
            }
        )
        return state

    def node_load(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        user_id = str(state.get("user_id"))
        limit = int(state.get("limit") or 200)

        _span = start_span(
            "compaction_load_memories", input={"user_id": user_id, "limit": limit}
        )

        _t = _time.perf_counter()
        cands = _fetch_user_memories(user_id, limit=limit)
        state["candidates"] = cands

        # Safety check: if no candidates, force skip re-extraction
        # Otherwise, respect the caller's skip_reextract flag
        if not cands:
            logger.info("[graph.load.empty] user_id=%s no_candidates_found", user_id)
            state["skip_reextract"] = True
        # Note: We no longer override skip_reextract=True when candidates exist
        # The caller's intent is respected (default: skip_reextract=True)

        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.load] user_id=%s loaded=%s skip_reextract=%s latency_ms=%s",
            user_id,
            len(cands),
            state.get("skip_reextract"),
            latency_ms,
        )

        end_span(
            output={
                "loaded_count": len(cands),
                "skip_reextract": state["skip_reextract"],
                "latency_ms": latency_ms,
            }
        )
        return state

    def node_reextract(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        user_id = str(state.get("user_id"))

        _span = start_span(
            "compaction_reextract",
            input={
                "user_id": user_id,
                "candidates_count": len(state.get("candidates", [])),
                "skip": state.get("skip_reextract", False),
            },
        )

        _t = _time.perf_counter()

        # Skip if flag is set (user requested skip or no candidates were loaded)
        if state.get("skip_reextract", False):
            logger.info(
                "[graph.reextract.skip] user_id=%s reason=skip_reextract_flag", user_id
            )
            state["reextract"] = {"new_memories": [], "delete_ids": []}
            end_span(output={"skipped": True})
            return state

        out = _reextract_memories(user_id, state.get("candidates", []))
        state["reextract"] = out
        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.reextract] user_id=%s new=%s delete=%s latency_ms=%s",
            user_id,
            len(out.get("new_memories", [])),
            len(out.get("delete_ids", [])),
            latency_ms,
        )

        end_span(
            output={
                "new_memories_count": len(out.get("new_memories", [])),
                "delete_ids_count": len(out.get("delete_ids", [])),
                "latency_ms": latency_ms,
            }
        )
        return state

    def node_apply(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        user_id = str(state.get("user_id"))
        dry_run = state.get("dry_run", False)
        out = state.get("reextract", {}) or {}
        new_mems: List[Memory] = list(out.get("new_memories", []))
        delete_ids: List[str] = list(set(out.get("delete_ids", [])))

        _span = start_span(
            "compaction_apply",
            input={
                "user_id": user_id,
                "dry_run": dry_run,
                "new_memories_count": len(new_mems),
                "delete_ids_count": len(delete_ids),
            },
        )

        _t = _time.perf_counter()

        upserted_count = 0
        deleted_count = 0

        if dry_run:
            logger.info(
                "[graph.apply.dry_run] user_id=%s would_upsert=%s would_delete=%s",
                user_id,
                len(new_mems),
                len(delete_ids),
            )
        else:
            # Transaction safety: Only proceed if we have both new memories and delete IDs
            # OR if we only have one type of operation
            if new_mems and delete_ids:
                # Both operations: try upsert first, then delete only if upsert succeeds
                try:
                    # Upsert in chunks to avoid payload limits
                    chunk = 500
                    for i in range(0, len(new_mems), chunk):
                        upsert_memories(user_id, new_mems[i : i + chunk])
                    upserted_count = len(new_mems)

                    # Only delete after successful upsert
                    col = _get_collection()
                    col.delete(ids=delete_ids)  # type: ignore[attr-defined]
                    deleted_count = len(delete_ids)
                    logger.info(
                        "[graph.apply.success] user_id=%s upserted=%s deleted=%s",
                        user_id,
                        upserted_count,
                        deleted_count,
                    )
                except Exception as exc:
                    logger.error(
                        "[graph.apply.error] user_id=%s upserted=%s failed=%s error=%s",
                        user_id,
                        upserted_count,
                        exc,
                    )
                    # Don't delete if upsert failed
            elif new_mems:
                # Only upsert
                try:
                    chunk = 500
                    for i in range(0, len(new_mems), chunk):
                        upsert_memories(user_id, new_mems[i : i + chunk])
                    upserted_count = len(new_mems)
                except Exception as exc:
                    logger.error(
                        "[graph.apply.upsert.error] user_id=%s error=%s", user_id, exc
                    )
            elif delete_ids:
                # Only delete
                try:
                    col = _get_collection()
                    col.delete(ids=delete_ids)  # type: ignore[attr-defined]
                    deleted_count = len(delete_ids)
                except Exception as exc:
                    logger.error(
                        "[graph.apply.delete.error] user_id=%s error=%s", user_id, exc
                    )

        state["metrics"]["applied_upserts"] = upserted_count
        state["metrics"]["applied_deletes"] = deleted_count
        latency_ms = int((_time.perf_counter() - _t) * 1000)
        logger.info(
            "[graph.apply] user_id=%s upserts=%s deletes=%s latency_ms=%s dry_run=%s",
            user_id,
            upserted_count,
            deleted_count,
            latency_ms,
            dry_run,
        )

        end_span(
            output={
                "upserted": upserted_count,
                "deleted": deleted_count,
                "dry_run": dry_run,
                "latency_ms": latency_ms,
            }
        )
        return state

    graph.add_node("init", node_init)
    graph.add_node("ttl", node_ttl)
    graph.add_node("dedup", node_dedup)
    graph.add_node("consolidate", node_consolidate)
    graph.add_node("load", node_load)
    graph.add_node("reextract", node_reextract)
    graph.add_node("apply", node_apply)
    graph.set_entry_point("init")
    graph.add_edge("init", "ttl")
    graph.add_edge("ttl", "dedup")
    graph.add_edge("dedup", "consolidate")
    graph.add_edge("consolidate", "load")
    graph.add_edge("load", "reextract")
    graph.add_edge("reextract", "apply")
    graph.add_edge("apply", END)
    return graph


def run_compaction_graph(
    user_id: str,
    *,
    dry_run: bool = False,
    limit: int = 10000,
    skip_reextract: bool = True,
    skip_consolidate: bool = False,
) -> Dict[str, Any]:
    """Run the minimal compaction graph for a single user and return the final state.

    Args:
            user_id: User to compact
            dry_run: If True, don't actually apply changes
            limit: Max memories to process
            skip_reextract: If True, skip expensive LLM re-extraction (default True for speed/cost)
            skip_consolidate: If True, skip memory consolidation (default False - runs by default)
    """
    from src.services.tracing import start_trace

    # Start a trace for this compaction job
    trace = start_trace(
        name="compaction_job",
        user_id=user_id,
        metadata={
            "dry_run": dry_run,
            "limit": limit,
            "skip_reextract": skip_reextract,
            "skip_consolidate": skip_consolidate,
            "trigger": "manual",
        },
    )

    graph = build_compaction_graph()
    _t0 = _time.perf_counter()
    initial = {
        "user_id": user_id,
        "dry_run": dry_run,
        "limit": limit,
        "skip_reextract": skip_reextract,
        "skip_consolidate": skip_consolidate,
    }
    final: Dict[str, Any] = graph.compile().invoke(initial)  # type: ignore
    final.setdefault("metrics", {})
    final["metrics"]["duration_ms"] = int((_time.perf_counter() - _t0) * 1000)
    logger.info("[graph.done] user_id=%s metrics=%s", user_id, final.get("metrics"))

    # Update trace with final metrics
    if trace:
        try:
            trace.update(output=final.get("metrics", {}))
        except Exception:
            pass

    return final
