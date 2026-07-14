# Profile System Audit — Synthesis (2026-04-20)

Three parallel audit agents (coverage, taxonomy, pipeline) plus a focused health deep-dive. This is the input for the improvement epic.

## One-line verdict
The profile is **factually complete but emotionally sparse, temporally frozen, and epistemically blind to its own uncertainty.** It captures Ankit the resume, not Ankit the person.

## Where the 3 lenses agree (the real problems)

### 1. Single-source fragility — no confidence signal in the auto path
- 28 of user 1169491032's fields come from a single memory; 35/73 have ≤2 sources.
- `profile_confidence_scores` is **never written by the extraction path** — only by manual PUT (which forces every component score to 100).
- The LLM returns a `confidence` field (50-100); `store_profile_extractions` at profile_storage.py:97 reads it then discards it.
- Schema has `frequency_score, recency_score, explicitness_score, source_diversity_score` but they're dead code.

### 2. Temporal blindness — profile is a snapshot, not a trajectory
- 17 fields for user 1169491032 are 90+ days stale. `current_focus` last updated 110 days ago.
- `last_updated` is recorded but never used for decay.
- Contradictions silently overwrite — no history, no conflict flag.
- No `life_stage`, `turning_points`, `current_inflection_point`, or `active_stressors` fields.

### 3. Emotional/relational layer missing at every level
- `fears: "leaving stable job"` directly contradicts `long_term: "quit Intuit for entrepreneurship"` — zero resolution.
- Daughter Ava named but no dynamic. `aspirations` mentions childhood self-image wound — no triggers, context, or repair.
- No `key_relationships` (named people + dynamic + why_matter).
- No `growth_edges`, `decision_making_patterns`, `energy_recovery_patterns`, `hypocrisy_awareness`.
- `source_type: inferred` is allowed but barely used (12/421 sources). System refuses to form hypotheses.

### 4. Silent failures mask the gaps
- LLM extraction failures → empty list → indistinguishable from "no profile data."
- Manual PUT always wins with confidence=100, overriding accumulated knowledge.

## Health category — specific findings (user 1169491032)
5 fields stored:
- `allergies: []` — ambiguous (confirmed none vs never extracted?)
- `clothing_sizes: {"pants": "36x30"}` — only pants, no shirt/shoe/ring
- `dietary_needs: "Vegetarian (eats eggs). Favorites: Pizza, Noodles, Indian food."` — **conflates medical requirement with food preference**; also duplicates `preferences.food_preferences`
- `health_conditions: "stomach uneasiness"` — 10 sources (most-active signal), but captured as flat string. Missing: triggers, severity trajectory, management, correlation to stress/diet
- `vision_correction` — single source, 99 days stale

Entirely absent health dimensions: mental health / anxiety, sleep quality, exercise specifics (orphaned in `interests`), energy patterns, family medical history, healthcare relationships, life-stage health events, bodily self-perception.

## Schema mismatch to call out
- `TOTAL_EXPECTED_FIELDS` comment at profile_storage.py:39 says `# 25`, actual is 27. API correctly reports 27. Stale comment.

## Top 7 prioritized actions (deduped across audits)
1. **Wire extraction → `profile_confidence_scores`** with the freq+recency+explicitness+diversity formula already in the schema
2. **Contradiction detection + confidence blending** (don't silent-overwrite)
3. **Temporal decay + per-category freshness** in the completeness API
4. **New category: `relationships`** with {name, role, dynamic, why_matter}
5. **New fields: `life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins`** (the present tense)
6. **New fields: `growth_edges`, `decision_style`, `energy_recovery_patterns`** (the how, not the what)
7. **Profile change history** (`profile_fields_history` table) — auditable, self-correcting

## What's already good (don't break these)
- Array dedup within a batch
- Source provenance table exists & is populated
- Taxonomy consolidation rules (spouse/children objects, arrays for plurals)
- Anti-pattern rules (don't extract tasks, volatile portfolio, granular specs)

## Constraint from user
**"Improve without breaking anything."** Changes must be additive, backward-compatible, or feature-flagged. Existing API contracts, existing stored data, and existing UI paths must keep working untouched.
