# Epic: Ingestion Graph Performance & Architecture Optimization

**Epic ID:** TBD (Post-Profile Foundation)
**Author:** Claude Code (Based on analysis 2025-11-21)
**Status:** Proposed
**Priority:** P1 (Performance & Scalability)
**Dependencies:** Epic 1 (Profile Foundation) - Current implementation working
**Target Timeline:** 2-3 weeks

---

## Executive Summary

Optimize the unified ingestion graph to improve performance, reduce latency, and simplify architecture based on real-world usage analysis. This epic focuses on eliminating bottlenecks and architectural inefficiencies discovered during profile capture quality improvements.

**Key Improvements:**
- **-40% latency reduction** (eliminate one LLM call, parallelize storage)
- **-30% architectural complexity** (single-stage extraction, remove worthiness filter)
- **+100% data completeness** (already achieved via message windowing fix)
- **Better scalability** (parallel storage, reduced LLM costs)

---

## Background & Motivation

### Current Architecture Issues

During comprehensive profile capture quality testing (2025-11-21), we identified several architectural bottlenecks in `unified_ingestion_graph.py`:

1. **Two-Stage Extraction Inefficiency**
   - Current: Conversation → Memories (LLM call 1) → Profile (LLM call 2)
   - Problem: Information loss at each transformation, added latency (~1-2s), increased costs
   - Evidence: Profile extractor sees "User's name is Sarah Chen" instead of original conversation context

2. **Worthiness Check Latency**
   - Current: Every conversation runs worthiness check first (500-1000ms)
   - Problem: Adds fixed latency regardless of outcome
   - Evidence: Worthiness node blocks pipeline even when result is "worthy"

3. **Sequential Storage Slowness**
   - Current: Storage operations run sequentially (~400ms total)
   - Problem: Each storage waits for previous to complete unnecessarily
   - Evidence: Lines 976-982 in unified_ingestion_graph.py show sequential chain

4. **Message Windowing Bug (FIXED)**
   - Problem: Only processed last 6 messages, skipped first messages with basic info
   - Status: ✅ Fixed in lines 136 and 175 of unified_ingestion_graph.py
   - Evidence: Profile capture improved from 0% to 100% for basic info

### Performance Analysis

**Current Latency Breakdown (9-message conversation):**
```
Worthiness Check:    500-1000ms  (LLM call)
Memory Extraction:   1000-1500ms (LLM call)
Profile Extraction:  1000-1500ms (LLM call)
Storage (Sequential): 300ms       (ChromaDB + PostgreSQL)
-----------------------------------------------
Total:               2900-3400ms
```

**Proposed Latency (After Optimization):**
```
Combined Extraction:  1200-1800ms (Single LLM call with larger context)
Storage (Parallel):   150-200ms   (Fastest storage operation determines time)
-----------------------------------------------
Total:                1350-2000ms (40-58% improvement)
```

---

## Goals & Success Criteria

### Primary Goals

1. **Reduce ingestion latency by 40%+** through architectural optimization
2. **Simplify architecture by removing unnecessary complexity** (worthiness filter, two-stage extraction)
3. **Improve profile extraction quality** through richer context preservation
4. **Maintain 100% backward compatibility** with existing APIs and data structures

### Success Criteria

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Ingestion Latency** | 2900-3400ms | <2000ms | Average latency for 9-message conversation |
| **LLM Calls Per Ingestion** | 3 (worthiness, memory, profile) | 1 (combined) | Count of OpenAI API calls |
| **Profile Extraction Quality** | 71% (15/21 fields) | 80%+ (17/21 fields) | Comprehensive test with Alex Rodriguez |
| **Storage Latency** | 400ms (sequential) | <200ms (parallel) | Time from extraction complete to all storage done |
| **Architecture Complexity** | 13 graph nodes | <10 graph nodes | Node count in StateGraph |

### Non-Goals

- ❌ Changing memory data structures (keep existing tables)
- ❌ Rewriting existing extraction prompts (enhance but don't replace)
- ❌ Modifying public API contracts (internal optimization only)
- ❌ Adding new memory types or categories

---

## Functional Requirements

### FR-IG1: Combined Memory & Profile Extraction

**Given** a conversation submitted via `/v1/store`
**When** the ingestion pipeline runs
**Then** the system extracts both memories AND profile information in a single LLM call
**And** the extraction produces:
- Semantic memories (array of memory objects)
- Profile updates (array of profile field updates)
- Metadata (entities, tags, confidence scores)

**Rationale:** Reduces LLM calls from 3 to 1, preserves full conversation context for better extraction quality

---

### FR-IG2: Optional Worthiness Check

**Given** a conversation ingestion request
**When** the pipeline starts
**Then** the worthiness check is OPTIONAL (configurable via environment variable)
**And** when disabled, the system proceeds directly to extraction
**And** when enabled, the check runs asynchronously without blocking extraction

**Rationale:** 500-1000ms fixed latency is not justified when most conversations are "worthy"

---

### FR-IG3: Parallel Storage Operations

**Given** extraction results (memories + profile updates)
**When** storing to multiple databases
**Then** the system parallelizes storage operations:
- ChromaDB vector storage (semantic + episodic memories)
- PostgreSQL structured storage (all memory types + profile updates)

**And** the pipeline waits for ALL storage operations to complete
**And** if one storage fails, others continue (partial success handling)

**Rationale:** Storage operations are I/O bound and independent, can run concurrently

---

### FR-IG4: Enhanced Extraction Context

**Given** the combined extraction prompt
**When** calling the LLM for extraction
**Then** the prompt includes:
- Full conversation history (not windowed)
- Existing memories context (for deduplication)
- Profile extraction rules (from PROFILE_EXTRACTION_PROMPT)
- Memory extraction rules (from EXTRACTION_PROMPT)

**And** the response follows structured format:
```json
{
  "memories": [
    {
      "content": "...",
      "layer": "semantic|episodic|procedural|emotional|portfolio",
      "tags": ["..."],
      "entities": {...},
      "confidence": 0.95
    }
  ],
  "profile_updates": [
    {
      "category": "basics|preferences|goals|interests|background",
      "field_name": "...",
      "field_value": "...",
      "confidence": 95,
      "source_type": "explicit|implicit|inferred"
    }
  ]
}
```

**Rationale:** Single LLM call with comprehensive context produces higher quality extractions

---

### FR-IG5: Graceful Degradation & Error Handling

**Given** any component failure in the ingestion pipeline
**When** the error occurs
**Then** the system:
- Logs detailed error with context
- Continues processing other components if possible
- Returns partial success status to client
- Queues failed operations for retry (if applicable)

**And** client receives response indicating:
- Which operations succeeded
- Which operations failed
- Retry recommendations

**Rationale:** Ingestion should be resilient, not all-or-nothing

---

## Technical Architecture

### Current Architecture (Before Optimization)

```
┌─────────────────────────────────────────────────────────────┐
│                    unified_ingestion_graph.py                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  init_node     │
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  worth_node    │  ← LLM Call 1 (500-1000ms)
                     └────────┬───────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
              [not worthy]        [worthy]
                  END                  │
                                       ▼
                              ┌────────────────┐
                              │ extract_node   │  ← LLM Call 2 (1000-1500ms)
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ classify_node  │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │build_mem_node  │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │extract_prof_n  │  ← LLM Call 3 (1000-1500ms)
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_prof_node │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_chroma_n  │  ← Sequential
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_episodic  │  ← Sequential
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_emotional │  ← Sequential
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_procedrl  │  ← Sequential
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │store_portfolio │  ← Sequential
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ summarize_node │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ finalize_node  │
                              └────────────────┘

Total Nodes: 13
Total LLM Calls: 3
Sequential Storage: 5 operations
```

### Proposed Architecture (After Optimization)

```
┌─────────────────────────────────────────────────────────────┐
│              unified_ingestion_graph_v2.py                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  init_node     │
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ extract_all_n  │  ← Single LLM Call (1200-1800ms)
                     │                │     Extracts memories + profile
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ classify_node  │
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │build_objs_node │  ← Build memories + profile objects
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ store_all_node │  ← Parallel Storage (150-200ms)
                     │                │
                     │  ┌──────────┐  │
                     │  │ ChromaDB │  │  ← Parallel
                     │  ├──────────┤  │
                     │  │PostgreSQL│  │  ← Parallel
                     │  └──────────┘  │
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ finalize_node  │
                     └────────────────┘

Total Nodes: 6 (down from 13, -54% reduction)
Total LLM Calls: 1 (down from 3, -67% reduction)
Parallel Storage: All operations concurrent
```

### Key Architectural Changes

#### 1. Combined Extraction Node

**File:** `src/services/unified_ingestion_graph_v2.py` (new file, don't break existing)

**New Node: `extract_all_node()`**

```python
def extract_all_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combined extraction node - extracts memories AND profile in single LLM call.

    Replaces:
    - worth_node (removed entirely)
    - extract_node (memory extraction)
    - extract_profile_node (profile extraction)
    """
    from src.services.tracing import start_span, end_span

    span = start_span("combined_extraction", input={
        "history_count": len(state["history"]),
        "existing_memories": len(state.get("existing_memories", []))
    })

    # Prepare context
    history_dicts = state["history"]
    existing_context = format_memories_for_llm_context(state.get("existing_memories", []))

    # Build combined prompt (see FR-IG4)
    payload = {
        "history": history_dicts,  # ALL messages, not windowed
        "existing_memories_context": existing_context
    }

    # Single LLM call for both memories and profile
    result = _call_llm_json(
        COMBINED_EXTRACTION_PROMPT,  # New prompt combining EXTRACTION_PROMPT + PROFILE_EXTRACTION_PROMPT
        payload,
        expect_array=False  # Returns object with memories + profile_updates
    )

    # Split results
    state["items"] = result.get("memories", [])
    state["profile_extractions"] = result.get("profile_updates", [])

    end_span(output={
        "memories_extracted": len(state["items"]),
        "profile_updates_extracted": len(state["profile_extractions"])
    })

    return state
```

#### 2. Parallel Storage Node

**New Node: `store_all_node()`**

```python
import asyncio
from typing import List, Dict, Any

async def store_all_parallel(
    memories: List[Memory],
    profile_updates: List[Dict[str, Any]],
    user_id: str
) -> Dict[str, Any]:
    """
    Store all data in parallel across multiple databases.

    Returns:
        {
            "chromadb": {"status": "success", "stored": 10},
            "postgresql": {"status": "success", "stored": 15},
            "profile": {"status": "success", "updated": 5}
        }
    """
    # Define storage operations
    async def store_chromadb():
        try:
            result = await chromadb_client.store_vectors(memories)
            return {"status": "success", "stored": len(memories)}
        except Exception as e:
            logger.error(f"ChromaDB storage failed: {e}")
            return {"status": "error", "error": str(e)}

    async def store_postgresql():
        try:
            result = await postgres_client.store_memories(memories)
            return {"status": "success", "stored": len(memories)}
        except Exception as e:
            logger.error(f"PostgreSQL storage failed: {e}")
            return {"status": "error", "error": str(e)}

    async def store_profile():
        try:
            result = await profile_service.apply_updates(user_id, profile_updates)
            return {"status": "success", "updated": len(profile_updates)}
        except Exception as e:
            logger.error(f"Profile storage failed: {e}")
            return {"status": "error", "error": str(e)}

    # Execute all in parallel
    results = await asyncio.gather(
        store_chromadb(),
        store_postgresql(),
        store_profile(),
        return_exceptions=True
    )

    return {
        "chromadb": results[0],
        "postgresql": results[1],
        "profile": results[2]
    }

def store_all_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for parallel storage (LangGraph nodes must be sync).
    """
    from src.services.tracing import start_span, end_span

    span = start_span("parallel_storage", input={
        "memories_count": len(state.get("memories", [])),
        "profile_updates_count": len(state.get("profile_extractions", []))
    })

    # Run async storage
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(
        store_all_parallel(
            state.get("memories", []),
            state.get("profile_extractions", []),
            state["user_id"]
        )
    )

    state["storage_results"] = results

    # Check for failures
    failures = [k for k, v in results.items() if v.get("status") == "error"]
    if failures:
        logger.warning(f"Storage failures: {failures}")
        state["storage_status"] = "partial"
    else:
        state["storage_status"] = "complete"

    end_span(output={
        "storage_status": state["storage_status"],
        "results": results
    })

    return state
```

#### 3. Combined Extraction Prompt

**File:** `src/services/prompts.py`

**New Prompt: `COMBINED_EXTRACTION_PROMPT`**

```python
COMBINED_EXTRACTION_PROMPT = """You are a comprehensive memory and profile extraction system for a personal AI memory assistant.

Your task is to analyze conversations and extract TWO types of information:
1. **Memories** - Semantic facts, episodic events, procedural knowledge, emotional patterns, portfolio/financial data
2. **Profile Updates** - User profile information (basics, preferences, goals, interests, background)

## PART 1: Memory Extraction

[Full EXTRACTION_PROMPT content from lines 1-250 in prompts.py]

## PART 2: Profile Extraction

[Full PROFILE_EXTRACTION_PROMPT content from lines 14-111 in profile_extraction.py]

## Output Format

Return a JSON object with this structure:

{
  "memories": [
    {
      "content": "string",
      "layer": "semantic|episodic|procedural|emotional|portfolio",
      "tags": ["string"],
      "entities": {
        "people": ["string"],
        "places": ["string"],
        "organizations": ["string"],
        "topics": ["string"]
      },
      "confidence": 0.0-1.0,
      "timestamp_type": "explicit|inferred|none",
      "timestamp": "ISO8601 or null"
    }
  ],
  "profile_updates": [
    {
      "category": "basics|preferences|goals|interests|background",
      "field_name": "string",
      "field_value": "any",
      "confidence": 0-100,
      "source_type": "explicit|implicit|inferred",
      "source_memory_id": "string"
    }
  ]
}

## Important Notes

1. **Extract BOTH memories and profile updates** - don't skip either section
2. **Be comprehensive** - extract ALL valuable information from the conversation
3. **Avoid duplicates** - if information is already in existing_memories_context, don't re-extract
4. **Maintain consistency** - use the same tags, entities, and field names as existing data
5. **Confidence scores** - be realistic, don't over-inflate confidence

Return ONLY the JSON object, no additional text.
"""
```

---

## Story Breakdown

### Story IG-1: Combined Extraction Prompt Engineering

**Priority:** P0 (Foundation)
**Estimated Effort:** 3 days
**Depends On:** None

As a **backend developer**,
I want **a unified extraction prompt that produces both memories and profile updates in a single LLM call**,
So that **we reduce latency and preserve full conversation context for better extraction quality**.

**Acceptance Criteria:**

1. **Given** the existing EXTRACTION_PROMPT and PROFILE_EXTRACTION_PROMPT
   **When** merging them into COMBINED_EXTRACTION_PROMPT
   **Then** the new prompt includes:
   - All memory extraction rules (semantic, episodic, procedural, emotional, portfolio)
   - All profile extraction rules (basics, preferences, goals, interests, background)
   - Clear output format with separate `memories` and `profile_updates` arrays
   - Examples demonstrating extraction of both types

2. **And** the prompt is tested with 5 diverse conversation examples:
   - Simple introduction (1 message)
   - Multi-turn conversation (9 messages)
   - Technical discussion (procedural + semantic memories)
   - Personal storytelling (episodic + emotional memories)
   - Goal-setting conversation (goals + interests profile)

3. **And** extraction quality meets or exceeds current implementation:
   - Memory extraction: ≥90% of items extracted by current pipeline
   - Profile extraction: ≥90% of fields extracted by current pipeline
   - No significant regression in confidence scores

**Technical Notes:**
- Create `src/services/prompts.py::COMBINED_EXTRACTION_PROMPT`
- Use structured output with Pydantic models for response validation
- Test with GPT-4o (not GPT-3.5, quality matters more than cost for extraction)
- Include existing memories context to avoid duplicates
- Maintain backward compatibility with existing tag/entity formats

**Testing:**
- Unit tests: `tests/services/test_combined_extraction_prompt.py`
- Integration tests with real LLM calls (mark as slow tests)
- Compare output to current two-stage pipeline on 10 test conversations

---

### Story IG-2: Unified Extraction Node Implementation

**Priority:** P0 (Foundation)
**Estimated Effort:** 5 days
**Depends On:** IG-1

As a **backend developer**,
I want **a new graph node that performs combined memory and profile extraction**,
So that **we can replace the three-node sequence (worthiness → memory → profile) with a single node**.

**Acceptance Criteria:**

1. **Given** a new file `src/services/unified_ingestion_graph_v2.py`
   **When** implementing the graph
   **Then** it includes `extract_all_node()` that:
   - Accepts state with `history` and `existing_memories`
   - Calls LLM with COMBINED_EXTRACTION_PROMPT
   - Parses response into `memories` and `profile_updates`
   - Updates state with extraction results
   - Includes tracing/logging for observability

2. **And** the node handles errors gracefully:
   - LLM call timeout (retry once, then fail)
   - Invalid JSON response (log error, return empty results)
   - Partial success (some memories extracted, profile failed → keep memories)

3. **And** the node includes comprehensive logging:
   - Input: conversation length, existing memories count
   - Output: memories extracted, profile updates extracted
   - Performance: LLM call duration, token usage
   - Errors: full exception details

4. **And** Langfuse tracing captures:
   - Prompt template used
   - Full LLM request/response
   - Extraction duration
   - Token costs

**Technical Notes:**
- Copy unified_ingestion_graph.py → unified_ingestion_graph_v2.py (don't break existing)
- Use `_call_llm_json()` from extract_utils.py
- Response validation with Pydantic models
- Async-compatible (for future optimization)
- Feature flag: `ENABLE_COMBINED_EXTRACTION=true` environment variable

**Testing:**
- Unit tests with mocked LLM responses
- Integration tests with real OpenAI API
- Performance benchmarking against current pipeline
- Error handling tests (timeout, invalid response, etc.)

---

### Story IG-3: Parallel Storage Implementation

**Priority:** P0 (Foundation)
**Estimated Effort:** 5 days
**Depends On:** IG-2

As a **backend developer**,
I want **storage operations to run in parallel instead of sequentially**,
So that **storage latency is determined by the slowest operation, not the sum of all operations**.

**Acceptance Criteria:**

1. **Given** extraction results with memories and profile updates
   **When** storing to multiple databases
   **Then** the system parallelizes using `asyncio.gather()`:
   - ChromaDB vector storage
   - PostgreSQL structured storage
   - Profile updates

2. **And** each storage operation returns status:
   ```python
   {
     "chromadb": {"status": "success", "stored": 10, "duration_ms": 120},
     "postgresql": {"status": "success", "stored": 15, "duration_ms": 85},
     "profile": {"status": "success", "updated": 5, "duration_ms": 60}
   }
   ```

3. **And** partial success is handled gracefully:
   - If one storage fails, others continue
   - Overall status: "complete" (all success) or "partial" (some failed)
   - Failed operations logged with full context

4. **And** storage performance meets targets:
   - Parallel storage: <200ms (fastest operation + overhead)
   - Previous sequential storage: ~400ms
   - Target improvement: >50% reduction

**Technical Notes:**
- Create `store_all_parallel()` async function
- Wrap in `store_all_node()` sync function for LangGraph compatibility
- Use `asyncio.gather(return_exceptions=True)` to prevent one failure from stopping others
- Add storage duration metrics to each result
- Update existing storage functions to be async-compatible

**Testing:**
- Unit tests with mocked storage clients
- Integration tests with real databases
- Performance benchmarking (sequential vs parallel)
- Failure simulation (intentionally fail one storage, verify others succeed)
- Load testing (100 concurrent ingestion requests)

---

### Story IG-4: Graph Architecture Refactoring

**Priority:** P0 (Integration)
**Estimated Effort:** 3 days
**Depends On:** IG-2, IG-3

As a **backend developer**,
I want **to rebuild the StateGraph with the new combined extraction and parallel storage nodes**,
So that **the optimized pipeline is fully integrated and production-ready**.

**Acceptance Criteria:**

1. **Given** the new extract_all_node and store_all_node
   **When** building the StateGraph
   **Then** the graph structure is:
   ```python
   init_node → extract_all_node → classify_node → build_objects_node → store_all_node → finalize_node
   ```

2. **And** the old nodes are removed:
   - ❌ worth_node (removed entirely)
   - ❌ extract_node (replaced by extract_all_node)
   - ❌ extract_profile_node (replaced by extract_all_node)
   - ❌ store_profile_node (replaced by store_all_node)
   - ❌ store_chromadb_node (replaced by store_all_node)
   - ❌ store_episodic_node (replaced by store_all_node)
   - ❌ store_emotional_node (replaced by store_all_node)
   - ❌ store_procedural_node (replaced by store_all_node)
   - ❌ store_portfolio_node (replaced by store_all_node)

3. **And** feature flag controls rollout:
   - `ENABLE_OPTIMIZED_INGESTION=true` → use unified_ingestion_graph_v2.py
   - `ENABLE_OPTIMIZED_INGESTION=false` → use unified_ingestion_graph.py (existing)
   - Default: false (safe rollout)

4. **And** the `/v1/store` endpoint response includes optimization metadata:
   ```json
   {
     "memories_created": 18,
     "profile_fields_updated": 5,
     "optimization_enabled": true,
     "performance": {
       "total_duration_ms": 1850,
       "extraction_duration_ms": 1600,
       "storage_duration_ms": 180,
       "llm_calls": 1
     }
   }
   ```

**Technical Notes:**
- Use environment variable for feature flag
- Keep unified_ingestion_graph.py as fallback
- Update `/v1/store` endpoint to use correct graph based on flag
- Add performance metrics to response
- Ensure backward compatibility with existing clients

**Testing:**
- End-to-end tests with both graphs (old and new)
- Feature flag toggling tests
- Performance comparison tests
- Regression tests (ensure no data loss)

---

### Story IG-5: Performance Testing & Benchmarking

**Priority:** P1 (Validation)
**Estimated Effort:** 3 days
**Depends On:** IG-4

As a **QA engineer / backend developer**,
I want **comprehensive performance benchmarks comparing old and new architectures**,
So that **we can validate the latency improvements and identify any regressions**.

**Acceptance Criteria:**

1. **Given** the new optimized pipeline (IG-4)
   **When** running performance benchmarks
   **Then** the system measures:
   - Total ingestion latency (end-to-end)
   - LLM call duration
   - Storage duration
   - Memory usage
   - Token usage / cost

2. **And** benchmarks run on diverse scenarios:
   - Simple conversation (1 message, basic intro)
   - Medium conversation (5 messages, mixed content)
   - Complex conversation (9 messages, comprehensive profile)
   - Large conversation (20 messages, edge case)

3. **And** results are compared to baseline:
   ```
   Scenario: Complex (9 messages)
   ┌──────────────────┬─────────────┬─────────────┬─────────┐
   │ Metric           │ Old         │ New         │ Change  │
   ├──────────────────┼─────────────┼─────────────┼─────────┤
   │ Total Latency    │ 3200ms      │ 1850ms      │ -42%    │
   │ LLM Calls        │ 3           │ 1           │ -67%    │
   │ LLM Duration     │ 2500ms      │ 1600ms      │ -36%    │
   │ Storage Duration │ 400ms       │ 180ms       │ -55%    │
   │ Token Usage      │ 8500 tokens │ 6000 tokens │ -29%    │
   │ Cost             │ $0.085      │ $0.048      │ -44%    │
   └──────────────────┴─────────────┴─────────────┴─────────┘
   ```

4. **And** quality metrics are validated:
   - Memory extraction accuracy: ≥95% of old pipeline
   - Profile extraction accuracy: ≥95% of old pipeline
   - Confidence scores: within ±5% of old pipeline

**Technical Notes:**
- Use `pytest-benchmark` for automated benchmarking
- Create test suite: `tests/benchmarks/test_ingestion_performance.py`
- Run benchmarks on production-like hardware
- Measure P50, P95, P99 latencies (not just average)
- Generate benchmark report with visualizations

**Testing:**
- Automated benchmark suite (run in CI/CD)
- Manual load testing (100 concurrent requests)
- Memory profiling (identify leaks or bloat)
- Cost analysis (OpenAI token usage)

---

### Story IG-6: Documentation & Rollout Plan

**Priority:** P1 (Operations)
**Estimated Effort:** 2 days
**Depends On:** IG-5

As a **platform operator / backend developer**,
I want **comprehensive documentation and a phased rollout plan**,
So that **we can safely deploy the optimized pipeline to production with minimal risk**.

**Acceptance Criteria:**

1. **Given** the completed optimization work
   **When** preparing for production rollout
   **Then** documentation includes:
   - Architecture diagram (before/after comparison)
   - Performance benchmarks summary
   - Migration guide (how to enable feature flag)
   - Rollback plan (how to revert if issues occur)
   - Monitoring guidelines (what metrics to watch)

2. **And** rollout plan follows phased approach:
   - **Phase 1 (Week 1):** Enable for 5% of requests (canary deployment)
   - **Phase 2 (Week 2):** Enable for 25% of requests (if no issues)
   - **Phase 3 (Week 3):** Enable for 50% of requests
   - **Phase 4 (Week 4):** Enable for 100% of requests (full rollout)

3. **And** monitoring includes:
   - Ingestion latency (P50, P95, P99)
   - LLM call duration and token usage
   - Storage success rate
   - Profile extraction quality (manual spot checks)
   - Error rate and error types

4. **And** rollback criteria are defined:
   - Latency P95 increases >20% from baseline
   - Storage failure rate >5%
   - Profile extraction quality drops >10%
   - Any critical errors or data loss

**Technical Notes:**
- Update `docs/architecture/ingestion-pipeline.md`
- Create `docs/operations/ingestion-optimization-rollout.md`
- Add monitoring dashboards (Grafana / Datadog)
- Set up alerts for rollback criteria
- Document feature flag: `ENABLE_OPTIMIZED_INGESTION`

**Deliverables:**
- Architecture documentation
- Rollout plan document
- Monitoring dashboard
- Alert configuration
- Rollback runbook

---

## Testing Strategy

### Unit Tests

**Coverage Target:** >85% for new code

- **Prompt Engineering (IG-1)**
  - Test prompt with various conversation types
  - Validate structured output format
  - Test error handling (invalid JSON, missing fields)

- **Extraction Node (IG-2)**
  - Mock LLM responses, test parsing
  - Test error handling (timeout, invalid response)
  - Test state updates

- **Parallel Storage (IG-3)**
  - Mock storage clients
  - Test partial failure scenarios
  - Test result aggregation

### Integration Tests

**Coverage Target:** All user-facing flows

- **End-to-End Ingestion**
  - Submit conversation via `/v1/store`
  - Verify memories created in all databases
  - Verify profile fields updated
  - Verify response format

- **Performance Tests**
  - Measure latency across conversation sizes
  - Validate parallel storage actually runs in parallel
  - Compare to baseline performance

### Load Tests

**Target:** 100 concurrent requests, <5% failure rate

- **Stress Testing**
  - 100 simultaneous ingestion requests
  - Measure latency degradation
  - Monitor database connection pools
  - Verify no deadlocks or race conditions

### Regression Tests

**Target:** 100% backward compatibility

- **Data Integrity**
  - Run test suite with both old and new pipelines
  - Compare output (memories, profile updates)
  - Ensure no data loss or corruption

---

## Migration & Rollback Plan

### Phase 1: Canary Deployment (Week 1)

**Goal:** Validate optimization with minimal user impact

1. Deploy code to production with `ENABLE_OPTIMIZED_INGESTION=false`
2. Enable flag for 5% of requests (random selection)
3. Monitor metrics for 7 days:
   - Latency (compare to baseline)
   - Error rate (compare to baseline)
   - Profile extraction quality (manual spot checks)

**Success Criteria:**
- P95 latency ≤2000ms (vs 3400ms baseline)
- Error rate <1% (same as baseline)
- No critical issues or data loss

**Rollback Trigger:**
- Any critical error or data loss
- P95 latency >20% worse than baseline
- Error rate >2% higher than baseline

### Phase 2: Expanded Rollout (Week 2)

**Goal:** Increase coverage to 25% of requests

1. If Phase 1 successful, update flag to 25%
2. Monitor for 7 days
3. Continue manual quality checks

**Success Criteria:**
- Same as Phase 1
- No new issues discovered

### Phase 3: Majority Rollout (Week 3)

**Goal:** Increase coverage to 50% of requests

1. If Phase 2 successful, update flag to 50%
2. Monitor for 7 days
3. Prepare for full rollout

**Success Criteria:**
- Same as Phase 1
- Validated cost savings from reduced LLM calls

### Phase 4: Full Rollout (Week 4)

**Goal:** Enable for 100% of requests

1. If Phase 3 successful, update flag to 100%
2. Monitor for 14 days
3. Remove old pipeline code (unified_ingestion_graph.py) after validation

**Success Criteria:**
- System stable for 2 weeks
- Performance improvements validated
- No outstanding issues

### Rollback Plan

**If issues discovered at any phase:**

1. **Immediate:** Set `ENABLE_OPTIMIZED_INGESTION=false` (reverts to old pipeline)
2. **Verify:** Confirm issue is resolved with old pipeline
3. **Investigate:** Identify root cause in new pipeline
4. **Fix:** Address issue in new pipeline code
5. **Retest:** Validate fix in staging environment
6. **Retry:** Resume rollout from previous phase

**No Data Loss Risk:** Both pipelines write to same databases, rollback is safe

---

## Risks & Mitigations

### Risk 1: LLM Quality Regression

**Description:** Combined prompt may produce lower quality extractions than two separate prompts

**Likelihood:** Medium
**Impact:** High (affects core functionality)

**Mitigation:**
- Extensive prompt engineering and testing (IG-1)
- Quality validation tests comparing outputs (IG-5)
- Canary deployment to catch issues early
- Rollback plan if quality drops

---

### Risk 2: Parallel Storage Race Conditions

**Description:** Concurrent writes to databases may cause conflicts or deadlocks

**Likelihood:** Low
**Impact:** Medium (storage failures)

**Mitigation:**
- Use database transactions where appropriate
- Test parallel storage extensively (IG-3)
- Implement retry logic for transient failures
- Monitor storage error rates closely

---

### Risk 3: Increased Token Usage

**Description:** Combined prompt may use more tokens than two separate prompts

**Likelihood:** Medium
**Impact:** Low (cost increase)

**Mitigation:**
- Benchmark token usage in IG-5
- Calculate cost savings from reduced API calls (3 → 1)
- Optimize prompt length if needed
- Set OpenAI token limits to prevent runaway costs

---

### Risk 4: Breaking Changes to API

**Description:** Response format changes may break existing clients

**Likelihood:** Low
**Impact:** High (client disruptions)

**Mitigation:**
- Maintain backward compatibility with existing response format
- Add new fields without removing old ones
- Feature flag allows instant rollback
- Version API endpoints if needed (future)

---

## Cost-Benefit Analysis

### Implementation Cost

| Story | Effort | Cost Estimate |
|-------|--------|---------------|
| IG-1: Prompt Engineering | 3 days | $2,400 |
| IG-2: Extraction Node | 5 days | $4,000 |
| IG-3: Parallel Storage | 5 days | $4,000 |
| IG-4: Graph Refactoring | 3 days | $2,400 |
| IG-5: Performance Testing | 3 days | $2,400 |
| IG-6: Documentation & Rollout | 2 days | $1,600 |
| **Total** | **21 days** | **$16,800** |

*Assuming $800/day engineering cost*

### Ongoing Cost Savings

**Latency Savings:**
- Current: 3200ms average ingestion latency
- Optimized: 1850ms average ingestion latency
- **Improvement:** 42% faster, better user experience

**OpenAI Cost Savings (per 1000 ingestion requests):**
- Current: 3 LLM calls × 2800 tokens × $0.01/1K tokens = **$84/1K requests**
- Optimized: 1 LLM call × 6000 tokens × $0.01/1K tokens = **$60/1K requests**
- **Savings:** $24/1K requests (29% reduction)

**At 100K requests/month:**
- Current cost: $8,400/month
- Optimized cost: $6,000/month
- **Monthly savings:** $2,400/month
- **Annual savings:** $28,800/year

**Break-even:** ~0.7 months (3 weeks)

### Intangible Benefits

- **Better user experience** (42% faster ingestion)
- **Higher profile extraction quality** (richer context)
- **Simpler architecture** (6 nodes vs 13 nodes, -54% complexity)
- **Better scalability** (parallel storage handles load better)
- **Lower operational overhead** (fewer nodes to monitor/debug)

---

## Dependencies & Prerequisites

### Technical Dependencies

- ✅ **Epic 1 Complete:** Profile Foundation (database schema, extraction pipeline, APIs)
- ✅ **Message Windowing Fixed:** Lines 136, 175 in unified_ingestion_graph.py
- ✅ **Existing Tests Passing:** Current ingestion pipeline must be stable

### Infrastructure Dependencies

- ✅ **OpenAI API Access:** GPT-4o for combined extraction
- ✅ **Async Support:** Python asyncio for parallel storage
- ✅ **Feature Flags:** Environment variable support
- ✅ **Monitoring:** Langfuse tracing, metrics collection

### Team Dependencies

- **Backend Engineer:** 1 FTE for 3-4 weeks (Stories IG-1 through IG-6)
- **QA Engineer:** 0.5 FTE for 1 week (Testing support for IG-5)
- **DevOps:** 0.2 FTE for 1 week (Rollout support for IG-6)

---

## Success Metrics & KPIs

### Performance KPIs

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| **Ingestion Latency (P95)** | 3400ms | <2000ms | Prometheus histogram |
| **LLM Calls per Ingestion** | 3 | 1 | Counter metric |
| **Storage Latency (P95)** | 400ms | <200ms | Prometheus histogram |
| **Token Usage** | 8500 tokens | <6500 tokens | OpenAI API logs |
| **Cost per 1K Requests** | $84 | <$65 | Cost tracking |

### Quality KPIs

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| **Memory Extraction Accuracy** | 100% (baseline) | ≥95% | Manual spot checks |
| **Profile Extraction Accuracy** | 71% (15/21 fields) | ≥80% (17/21 fields) | Automated tests |
| **Storage Success Rate** | 100% | 100% | Error rate monitoring |
| **Confidence Score Accuracy** | Baseline (avg 85%) | ±5% of baseline | Automated tests |

### Operational KPIs

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| **Error Rate** | <1% | <1% | Error logs |
| **Rollout Time** | N/A | 4 weeks | Project timeline |
| **Code Coverage** | 80% | >85% | pytest-cov |
| **Graph Node Count** | 13 nodes | <10 nodes | Code inspection |

---

## Appendix: Research & Analysis

### Analysis Source

This epic is based on comprehensive profiling and analysis conducted on 2025-11-21 during profile capture quality testing. See `/tmp/profile_capture_final_report.md` for full details.

### Key Findings

1. **Message Windowing Bug (Fixed)**
   - Only processed last 6 messages, skipped first 3 with basic info
   - Fixed in lines 136, 175 of unified_ingestion_graph.py
   - Result: Profile capture improved from 0% to 100% for basic info

2. **Two-Stage Extraction Inefficiency**
   - Profile extractor sees "User's name is Sarah Chen" instead of original conversation
   - Information loss at each transformation
   - Added latency: 1000-1500ms for second LLM call

3. **Worthiness Check Overhead**
   - Fixed 500-1000ms latency even for worthy conversations
   - Most conversations are worthy (>90% in testing)
   - Minimal value for cost

4. **Sequential Storage Bottleneck**
   - 5 storage operations running sequentially: 400ms total
   - Operations are independent, can run in parallel
   - Parallel storage could reduce to <200ms

### User Agreement

User explicitly agreed to these architectural improvements:

> "Agreed with everything - combine extraction, remove worthiness check, parallelize storage and process all messages."

---

## References

- **PRD:** `docs/PRD.md` - Product requirements for profile system
- **Epics:** `docs/epics.md` - Epic 1 (Profile Foundation)
- **Test Report:** `/tmp/profile_capture_final_report.md` - Profile capture quality analysis
- **Source Code:** `src/services/unified_ingestion_graph.py` - Current implementation
- **Prompts:** `src/services/prompts.py` - Current extraction prompts
- **Profile Extraction:** `src/services/profile_extraction.py` - Current profile extractor

---

## Revision History

- **v1.0 (2025-11-21):** Initial epic definition based on performance analysis
