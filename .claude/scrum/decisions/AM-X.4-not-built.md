# Decision: AM-X.4 (active-context convenience query) — NOT BUILT in `agentic-memories`

**Epic:** AM-X (Memory Primitives)
**Date recorded:** 2026-05-08
**Decided by:** Parminder (architect), per the epic doc
**Recorded in scrum by:** Fenny

## What was proposed
A single endpoint that returns "what's currently relevant for this user," ranked by `recency × importance × proximity-to-expiry`, so the prompt builder doesn't reassemble the same query every turn.

## Decision
**Do not build this in `agentic-memories`.**

## Rationale
1. "Active" means different things in different prompt frames (chat vs. journal vs. desire-evaluation). Annie's prompt layer already composes context per-state — that's a consumer concern, not a substrate concern.
2. The ranking formula (`recency × importance × proximity-to-expiry`) is policy that will iterate weekly. Policy that iterates that fast does not belong in a backend that other clients consume.
3. Once AM-X.2 lands, the consumer call is one HTTP request and ~5 lines of formatting. Substrate is sufficient.

## Action
- Build the consumer-side composer in `annie-in-a-bottle` as a Story 5.2 follow-up.
- This file is the canonical scrum-side record. The original epic doc at `/Users/ankit/dev/agentic-memories/docs/epic-memory-primitives.md` (section "AM-X.4 — Active-context convenience query") is the long-form rationale.

## Reversibility
If, after AM-X.2 ships, three or more consumers independently re-implement the same ranking formula, revisit. Promote the consumer composer into a substrate endpoint at that point.
