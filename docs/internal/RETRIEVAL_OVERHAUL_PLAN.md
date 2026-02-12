# Retrieval Overhaul Iteration: Persona Co-Pilot + Summarized Memory Tiers

## Vision Alignment
- Anchor the retrieval experience in the "Digital Soul" vision by weaving together emotionally aware persona agents and progressive summarization tiers.
- Empower the system to surface contextually relevant, empathetic responses while maintaining traceability to raw experiences.

## Guiding Principles
1. **Persona Continuity:** Retrieval always respects the active persona states (identity, relationships, health, finance, creativity, etc.) and maintains emotional consistency across sessions.
2. **Progressive Disclosure:** Serve the smallest sufficient memory artifact—summary first, with drill-down paths to episodic and raw memories.
3. **Feedback-Driven Adaptation:** Capture retrieval outcomes and user feedback to refine persona weighting, summarization freshness, and forgetting heuristics.
4. **Observability & Governance:** All retrieval decisions are explainable and auditable, with links to data lineage and scoring rationale.

---

## Phase 0 — Foundations & Discovery (Week 0-1)
### Objectives
- Validate current retrieval data models, metadata coverage, and service orchestration.
- Identify data gaps for persona tagging and summarization tiers.

### Key Activities
- Inventory memory metadata fields across Chroma, TimescaleDB, PostgreSQL, Neo4j.
- Audit existing ingestion flows to ensure persona tags, emotional scores, and importance ratings can be captured.
- Define standardized persona taxonomy and summary granularity (`raw`, `episodic`, `arc`).
- Establish evaluation metrics (persona coverage %, retrieval precision@k, summary freshness).

### Deliverables
- Discovery report with gap analysis and prioritized remediation backlog.
- Approved persona taxonomy and summary tier schema.

---

## Phase 1 — Persona Infrastructure (Week 1-3)
### Objectives
- Introduce persona-aware metadata and retrieval components.
- Stand up Persona Co-Pilot controller to orchestrate specialized retrieval agents.

### Workstreams
1. **Metadata Enhancements**
   - Extend ingestion pipelines to attach persona tags (multi-valued) and emotional context.
   - Backfill existing memories with inferred persona tags using rules/LLM assisted classification.
2. **Persona State Store**
   - Design Redis/Postgres backed session store tracking active personas, recent emotions, goals.
   - Define APIs for updating persona state based on interactions.
3. **Persona Retrieval Agents**
   - Implement agent interfaces wrapping existing retrieval endpoints with persona-specific weighting (e.g., override `_calculate_composite_score`).
   - Encode heuristics (e.g., recency decay, importance boost) per persona.
4. **Meta-Controller**
   - Build intent router (LLM or rule-based) to select relevant persona agents based on query parsing.
   - Aggregate and harmonize agent outputs, enforcing emotional consistency checks.

### Deliverables
- Persona metadata schema & migrations.
- Persona tagging tooling and backfill job results.
- Persona Co-Pilot service (controller + agents) with integration tests.
- Drafted API contract updates (`/v1/retrieve`, GraphQL, SDK) circulated for client feedback.

---

## Phase 2 — Summarization Tiers (Week 3-5)
### Objectives
- Generate and manage multi-granular summaries aligned with persona needs.
- Integrate summaries as first-class citizens in retrieval flows.

### Workstreams
1. **Summary Generation Pipeline**
   - Extend compaction jobs ("digital sleep") to create daily/weekly/thematic summaries via narrative builder.
   - Store summaries with metadata: persona coverage, confidence, freshness, source backlinks.
2. **Summary Retrieval API**
   - Update HybridRetrievalService to retrieve summary nodes alongside raw memories.
   - Support client-specified `granularity` parameter with defaults guided by persona states.
3. **Feedback Loop**
   - Capture user/agent signals (ratings, usage) to adjust summary importance and regeneration schedules.
   - Implement stale summary detection based on freshness thresholds and persona activity.

### Deliverables
- Scheduled summarization jobs with monitoring dashboards.
- Updated retrieval APIs returning multi-tier results and traceability links.
- Feedback ingestion endpoints feeding evaluation metrics.

---

## Phase 3 — Unified Retrieval Experience (Week 5-7)
### Objectives
- Seamlessly combine persona routing and summary tiers into the core retrieval endpoints.
- Provide narrative outputs that respect persona context and leverage summaries for coherence.

### Workstreams
1. **Endpoint Integration**
   - Refactor `/v1/retrieve` (and GraphQL equivalents) to call Persona Co-Pilot, fallback to hybrid retrieval when needed.
   - Ensure caching layers store persona-scoped results for latency gains.
2. **Narrative Reconstruction Upgrade**
   - Update narrative builder to reference summary tiers before expanding to raw memories.
   - Embed persona state in narrative prompts for empathetic tone control.
3. **Explainability Layer**
   - Produce retrieval audit trails: persona chosen, weights applied, summary tiers served, links to raw sources.
   - Add developer tooling to visualize persona decisions and summary utilization.

### Deliverables
- Unified retrieval endpoints with persona + summary awareness.
- Narrative outputs demonstrating persona-aligned storytelling.
- Observability dashboards/log formats for decision tracing.

### Client-Facing API Design
- **REST**
  - Extend `POST /v1/retrieve` request schema with optional fields:
    - `persona_context`: `{ active_personas: ["identity"], forced_persona?: "finance", mood?: "reflective" }`.
    - `granularity`: enum `raw|episodic|arc|auto` (default `auto`).
    - `include_narrative`: boolean toggling persona-aware narration.
    - `explain`: boolean to include audit metadata (persona chosen, summary tiers, scoring weights).
  - Response envelope structure:
    ```json
    {
      "persona": {
        "selected": "identity",
        "confidence": 0.82,
        "state_snapshot_id": "sess_123"
      },
      "results": {
        "granularity": "episodic",
        "memories": [ ... ],
        "summaries": [ ... ],
        "narrative": "string"
      },
      "explainability": {
        "weights": {"importance": 0.4, "recency": 0.3, "affinity": 0.3},
        "source_links": [ ... ]
      }
    }
    ```
- **GraphQL**
  - Introduce `retrievePersonaMemories` query:
    ```graphql
    query RetrievePersonaMemories($input: PersonaRetrieveInput!) {
      retrievePersonaMemories(input: $input) {
        persona { selected confidence stateSnapshotId }
        results {
          granularity
          memories { id text personaTags importance source }
          summaries { id tier text freshness sources }
          narrative
        }
        explainability { weights sourceLinks }
      }
    }
    ```
  - `PersonaRetrieveInput` mirrors REST fields and supports future expansion (e.g., `preferredModalities`).
- **SDK / Client Hooks**
  - Update TypeScript/ Python SDKs with helper methods (`retrievePersonaMemories`, `retrieveNarrative`) that accept high-level persona options and map them to API payloads.
  - Provide React hook `usePersonaRetrieval({ persona, granularity, includeNarrative })` returning loading state, results, and explainability metadata.
- **Backward Compatibility**
  - Maintain legacy behavior when `persona_context` and `granularity` are omitted.
  - Introduce feature flag `enablePersonaRetrieval` allowing gradual rollout per workspace/client.

---

## Phase 4 — Evaluation & Optimization (Week 7-8)
### Objectives
- Measure impact, tune heuristics, and prepare for iterative improvements.

### Key Activities
- Run offline + online evaluations (precision/recall, user satisfaction, latency impacts).
- Conduct A/B tests comparing persona-aware retrieval vs. baseline.
- Optimize scoring weights, caching strategies, and summary refresh cadences based on findings.
- Update documentation and handoff materials for subsequent roadmap items (e.g., graph lattice expansion).

### Deliverables
- Evaluation report with recommended parameter adjustments.
- Updated runbooks and API docs.
- Backlog of next-iteration enhancements (graph traversal, proactive outreach triggers).

---

## Cross-Cutting Concerns
- **Security & Privacy:** Enforce persona-specific access controls and audit logging. Ensure summaries do not leak sensitive details without authorization.
- **Testing Strategy:** Layered tests (unit, integration, simulation) covering persona routing, summary generation, and narrative coherence.
- **Change Management:** Communicate rollout stages to downstream teams; provide feature flags for phased adoption.
- **Tooling:** Create developer CLI commands to inspect persona states, regenerate summaries, and replay retrieval sessions.

---

## Success Criteria
- ≥90% of active memories tagged with at least one persona within first iteration.
- Retrieval satisfaction score improved by ≥15% relative to baseline.
- Average latency increase capped at ≤20% despite added orchestration, with caching mitigating hot-path queries.
- Narrative outputs rated as persona-consistent in ≥80% of evaluation sessions.

---

## Comparative Critique vs. External Memory Systems

### Alignment with Mem0 Patterns
- **Strengths:** The plan’s persona-aware routing echoes Mem0’s scoped recall (per-user/per-channel) and importance weighting, ensuring contextual retrieval without flooding clients. Introducing `persona_context` and `granularity` mirrors Mem0’s configurable recency/importance sliders, promoting a comfortable migration path for teams familiar with Mem0-style controls.
- **Gaps:** Mem0 emphasizes lightweight summaries embedded directly in conversational turns, whereas our summarization pipeline relies on nightly “digital sleep” jobs. Without an on-demand summarization capability, we risk lagging behind Mem0’s responsiveness to rapidly evolving contexts. Additionally, Mem0’s shard-level pruning and user-tunable forgetting policies are only partially addressed here via summary freshness heuristics.
- **Opportunities:** Borrow Mem0’s feedback-driven scoring adjustments by exposing fine-grained persona-level weighting overrides to clients, and consider incremental summary updates triggered by interaction volume instead of fixed schedules.

### Alignment with Supermemory Patterns
- **Strengths:** The multi-tier summary ladder and explainability layer follow Supermemory’s cascade retrieval philosophy (fast approximate search → re-rank → narrative). The inclusion of persona audit trails strengthens traceability, similar to Supermemory’s emphasis on consistent story arcs.
- **Gaps:** Supermemory leans heavily on automated consistency maintenance (e.g., contradiction detection, automatic re-summarization) and uses retrieval-time re-ranking informed by global knowledge graphs. Our plan defers graph-aware traversal and doesn’t yet specify contradiction detection, leaving potential coherence gaps when personas overlap. Moreover, Supermemory’s proactive prompts derived from trend analysis are only hinted at in future backlogs.
- **Opportunities:** Accelerate integration with the Neo4j knowledge lattice during Phase 3 to enable path-aware re-ranking, and schedule contradiction detection checks alongside summary generation. Explore proactive persona nudges by leveraging the evaluation loop to identify declining engagement or mood imbalances, mirroring Supermemory’s outreach triggers.

### Overall Critique
- **Execution Risk:** The phased approach concentrates significant change in Phase 3, creating a large bang release. Consider incremental client opt-in earlier (e.g., beta flag after Phase 1) to collect real-world telemetry sooner.
- **Observability:** While explainability is called out, the plan should specify concrete logging schemas and dashboards that map persona decisions to downstream satisfaction metrics, ensuring parity with the telemetry sophistication seen in Mem0/Supermemory.
- **Scalability:** Both reference systems rely on aggressive caching and vector index optimizations; the plan mentions caching but lacks detail on index tuning or sharding strategies. Adding capacity planning tasks would reduce operational surprises.

