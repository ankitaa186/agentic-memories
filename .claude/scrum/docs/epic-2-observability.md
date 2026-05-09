# Epic 2: Observability

Status: open
Owner: Disha (PM)
Opened: 2026-04-25

## Goal
Make Langfuse a reliable, low-noise window into what the system is actually doing — every embedding and LLM call attributable to a meaningful parent operation, every cost recorded, no silent duplicate calls.

## Why now
The user is actively using Langfuse to inspect production behavior. Three concrete pain points surfaced 2026-04-25:
1. OpenAI embedding traces appear as standalone top-level traces instead of nesting under their originating request — noise that hides the real shape of work.
2. All Langfuse cost values display as 0 — Langfuse-side pricing-key mismatch (resolved by user in the UI; no code work).
3. Worthiness LLM call duplicates back-to-back inside `unified_ingestion_graph` — wasted spend and a sign of a bug somewhere in the chain.

(2) is closed in the UI. (1) and (3) need code stories.

## Scope
**In scope:**
- Langfuse trace hierarchy correctness — every entry point that issues an instrumented OpenAI call wraps its work in a parent span (Story 2.1).
- Eliminating duplicate LLM calls inside the unified ingestion graph (Story 2.2 — pending Parminder's root-cause).
- Future: assertions / smoke tests against trace shape so regressions surface before the user notices.

**Out of scope:**
- Adding new tracing surfaces (e.g. tracing TimescaleDB ops). Defer until requested.
- Replacing or augmenting Langfuse with another vendor.
- Cost-attribution analytics — we're fixing recording, not building dashboards.

## Success criteria
- Zero unparented `langfuse.openai` observations under normal operation (every embedding/LLM call lands inside a named parent span).
- Worthiness LLM call executes exactly once per ingestion run.
- These properties hold across the documented entry points; Murat's tests cite them by name.

## Stories
- 2.1 — Wrap non-graph entry points in Langfuse spans (drafted)
- 2.2 — Eliminate duplicate worthiness LLM call (pending Parminder root-cause)

## Notes
- This is an operational epic, not a user-feature epic. No API contract changes expected from any story here.
- Parallel to Epic 1; does not block or unblock it.
