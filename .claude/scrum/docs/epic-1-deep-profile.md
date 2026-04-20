# Epic 1: Deep Profile — from resume to self-model

Owner: Disha (PM) — Design review: Parminder
Status: drafted (v2)
Date: 2026-04-20

## Version History

- **v1 (2026-04-20, ~00:50)** — Drafted under "don't break anything" constraint. 18 stories, 7 feature flags, every data change gated, depth tracked in a parallel `depth_completeness_pct` signal so the 27-field baseline stayed frozen.
- **v2 (2026-04-20, post [01:32])** — Reframed after user relaxed constraint to **API backward-compat only**. See bus message `2026-04-20.md` at `[01:32] FENNY -> TEAM: [DECISION]`. Data is now free to move, restructure, and recategorize. Completeness recomputes over a new expected set (27 → 35 per Parminder's §5.1 numbers at bus [02:15]); existing user scores WILL change and that is acceptable. Flag matrix shrinks from 7 → 3 (only dark-launch surfaces where shadow-verify or LLM-behavior-change genuinely warrants it). Destructive migrations added for dietary/health/allergies. A new category re-assignment pass (Story 1.19) relocates fitness content out of `interests.hobbies` into a new `health.exercise` structure. `depth_completeness_pct` is retired — one number, one signal.

---

## Why this epic exists

Today the profile is a **resume**: factually correct, temporally frozen, and epistemically mute about what it doesn't know. The audit (see `.claude/scrum/docs/profile-audit-findings.md`) surfaced three root problems:

1. **Epistemic blindness** — the extraction path writes fields but never records a confidence score, so the system can't tell a 10-source conviction from a 1-source guess. `profile_confidence_scores` exists but is only populated by manual PUT (which always writes 100).
2. **Temporal blindness** — 17 of the target user's fields are 90+ days stale; `last_updated` exists but is never used for decay, completeness doesn't reward recent touches, and contradictions silent-overwrite with no history.
3. **Emotional/relational sparsity** — no `life_stage`, no `current_inflection_point`, no `key_relationships`, no `growth_edges`. The LLM is allowed to mark `source_type: inferred` but rarely does, because we haven't given it places to put hypotheses.

The audit also surfaced **semantic contamination**: `dietary_needs` conflates medical/ethical requirements with food favorites; `health_conditions` is a flat string for a signal with 10 sources that deserves structure; `allergies: []` means both "confirmed none" and "never extracted" depending on who's reading. Fitness/exercise lives under `interests.hobbies` instead of `health` where any sensible consumer would look.

## Goal

Evolve the profile layer so the AI **knows the user better than they know themselves** — capturing not just *what* they are, but *who* they are *right now*, *how confident we should be*, and *where we're guessing*.

## Constraint frame (v2)

**The fence is the API contract, not the data behind it.**

### Frozen — breaking these is a regression

- `/v1/profile*` URL paths, HTTP methods, HTTP status codes
- Response top-level field names: `user_id`, `profile`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `last_updated`, `created_at`. Note: `missing` is nested under `categories[*].missing` per the live response model (Parminder §10 clarification, bus [02:15]); I'd previously listed it at top level. Frozen-key ACs on `/v1/profile/completeness` target the nested location.
- Query parameter names and semantics: `user_id`, `details`, `include_metadata`
- Request body shape for PUT/DELETE

### Free to change — not regressions

- Stored data: re-categorize fields, restructure value types (string → object), destructively migrate in place
- `EXPECTED_PROFILE_FIELDS` can grow and reshape; `completeness_pct` will recompute on a new denominator; existing user scores will shift
- UI: `Profile.tsx` can add tabs, reorganize cards, change rendering logic
- Feature flags: retain only where dark-launch or shadow-verify is genuinely earned; collapse everything else

## Non-goals (v2)

- Changing manual PUT semantics (manual always wins at confidence=100). Deferred to Epic 2 — confirmed.
- Retiring `basics.spouse` / `basics.children`. `relationships` complements, it does not replace.
- Bounded history retention. "Keep forever" is the current decision — confirmed.
- Scaling `recent_wins` decay by field type. Uniform decay shipped in Story 1.10 — confirmed.

## Success metrics (what "done" looks like)

Rephrased around observable user-value, not flag state.

- **Depth captured** — For the target user, at least 5 of `{life_stage, current_inflection_point, active_stressors, recent_wins, growth_edges, decision_style, energy_recovery_patterns, health.exercise, structured health_conditions}` are populated after one backfill run.
- **Conflicts surfaced** — Any contradicting extraction produces an observable conflict record (visible via `/v1/profile/conflicts`) rather than silent overwrite. At least one real conflict lands in the table during the target user's backfill.
- **Freshness visible** — `/v1/profile/completeness?details=true` exposes per-category freshness; the target user's output shows at least one category with `freshness_pct < 100` reflecting real staleness.
- **Confidence coverage** — >90% of extracted fields for the target user carry a non-null `profile_confidence_scores` row within one ingestion cycle (today: ~0%).
- **Relational context** — `relationships` category is populated for the known named entities (spouse, daughter) without disturbing `basics.spouse` / `basics.children`.
- **Semantic hygiene** — After migrations, `health.dietary_needs` contains only restriction data; food favorites live in `preferences.food_preferences`; `health.health_conditions` is a structured array; `health.allergies` distinguishes `null` (unknown) from `[]` (affirmed none); `health.exercise` exists and is populated from content previously miscategorized under `interests.hobbies`.
- **API contract intact** — All frozen response keys above return for every existing endpoint; existing integration tests pass; only `completeness_pct` numeric value is expected to shift (that's the recompute, and that's fine). Murat's golden-response contract tests (per Parminder's §7) are the gate.

---

## Sequencing & dependency map

```
Foundation (P0):
  1.1  Stale comment fix (TOTAL_EXPECTED_FIELDS)
  1.3  3-flag harness (confidence, contradiction, inferred)

Epistemic layer (P0 → P1):
  1.2  Wire extraction → profile_confidence_scores (confidence flag-gated)
  1.4  Contradiction detection (flag-gated)
  1.5  Confidence-weighted conflict resolution (flag-gated)
  1.6  profile_fields_history table (unconditional write)

Temporal layer (P1):
  1.7  Per-category freshness in /completeness (unconditional, additive keys)
  1.8  Temporal decay factor in composite confidence (unconditional)

Depth layer (P1):
  1.9  relationships category (unconditional)
  1.10 Present-tense fields: life_stage, inflection, stressors, wins (unconditional)
  1.11 How-fields: decision_style, growth_edges, energy_recovery (unconditional)
  1.12 Inferred / soft-signal extraction (flag-gated)

Semantic cleanup — destructive data migrations (P1 → P2):
  1.13 dietary_needs cleanup — strip food favorites, move to preferences.food_preferences, add PUT guard
  1.14 allergies null-vs-empty — migrate ambiguous [] to null where unconfirmed
  1.15 health_conditions — string → structured object; rewrite existing rows
  1.19 Category re-assignment — exercise/fitness from interests.hobbies → health.exercise

Observability surface (P2):
  1.16 GET /v1/profile/history read endpoint
  1.17 GET /v1/profile/conflicts read endpoint
  1.18 Profile.tsx refresh — depth surfaces, freshness indicators, conflict badge
```

---

## Feature flag matrix (v2)

Three flags. Each earns its gate.

| Flag | Why it exists | Default |
|------|----------------|---------|
| `PROFILE_WRITE_CONFIDENCE` | Shadow-launch scoring to verify the formula against real data before it starts driving conflict resolution. | `false` |
| `PROFILE_CONTRADICTION_DETECTION` | Observe conflicts against real ingestion traffic before committing to confidence-weighted resolution. | `false` |
| `PROFILE_INFERRED_EXTRACTION` | Prompt change is a genuine behavior shift for the LLM. Dark-launch so we can compare extraction output with/without. | `false` |

### Retired from v1

- `PROFILE_LOG_HISTORY` — just ship; history table writes unconditionally.
- `PROFILE_ENABLE_RELATIONSHIPS` — just ship; relationships category goes live.
- `PROFILE_TEMPORAL_DECAY` — just ship; decay is a formula change, no cutover risk.
- `PROFILE_NEW_FIELDS_COUNT` — removed in v1-to-v2 reframe; completeness recomputes unconditionally.
- `PROFILE_DEPTH_FIELDS_ENABLED` — just ship; new fields are added to `EXPECTED_PROFILE_FIELDS` directly.

---

## Stories

### Story 1.1: Fix stale `TOTAL_EXPECTED_FIELDS` comment

- Priority: P0 (1-pointer)
- User problem: Future contributors trust the comment over the code; debt compounds. With v2 adding fields, this will drift further if not fixed now.
- API contract preserved: No response keys touched. This is a comment + test change; endpoints are unaffected.
- Acceptance criteria:
  - [ ] GIVEN `profile_storage.py:39` WHEN a reader inspects the `TOTAL_EXPECTED_FIELDS` comment THEN it reflects the actual summed count.
  - [ ] GIVEN the expected-fields dict changes in the future WHEN the comment drifts THEN a unit test asserts `TOTAL_EXPECTED_FIELDS == sum(len(v) for v in EXPECTED_PROFILE_FIELDS.values())` and fails loudly.
- Dependencies: none

---

### Story 1.2: Wire extraction pipeline to `profile_confidence_scores`

- Priority: P0
- User problem: LLM returns a confidence score per extraction; we discard it. Without recorded confidence we can't distinguish certain knowledge from guesses.
- API contract preserved: `/v1/profile` and `/v1/profile/{category}` responses retain `user_id`, `profile`, `categories`, `last_updated`, `created_at`. When `?include_metadata=true` is passed, existing metadata keys remain; new `confidence` metadata is additive only.
- Architecture: `ProfileConfidenceService` derives the 4-component score from `profile_sources` (0.30 freq + 0.25 recency + 0.25 explicitness + 0.20 diversity, per migration 011). Called from `store_profile_extractions` after sources are inserted. This is Parminder's architectural call; kept as-is.
- Acceptance criteria:
  - [ ] GIVEN an LLM extraction with `confidence` and `source_type` AND flag `PROFILE_WRITE_CONFIDENCE=true` WHEN `store_profile_extractions` runs THEN a row is upserted into `profile_confidence_scores` with all four component scores populated (frequency, recency, explicitness, source_diversity).
  - [ ] GIVEN the flag is off THEN no rows are written to `profile_confidence_scores` and confidence-related response keys are absent from `include_metadata=true` output (preserving today's shape exactly).
  - [ ] GIVEN re-extraction of an existing field THEN the confidence row is updated in place, not duplicated.
  - [ ] GIVEN manual PUT runs THEN existing manual behavior is preserved (confidence=100, `is_manual_override=true` exposed in read path); auto-computed scores are not silently overwritten by the manual write.
  - [ ] GIVEN extraction completes THEN `confidence_written: <count>` is logged.
- Edge cases:
  - LLM omits `confidence` → default to 70 and still write.
  - First-time extract (0 prior sources) → compute from the single new source.
  - LLM returns `confidence: 0` → still write, not skipped.
- Dependencies: 1.3

---

### Story 1.3: Three-flag harness for profile behavior changes

- Priority: P0
- User problem: Two of the v2 behaviors (confidence scoring formula, LLM prompt change for inferred extraction) are still behaviorally risky enough to earn a gate. Contradiction detection earns a gate to observe real conflicts before wiring resolution. Everything else ships unconditionally.
- API contract preserved: `/v1/profile/_flags` is an internal debug endpoint; it's additive and does not touch existing routes. No frozen response keys affected.
- Acceptance criteria:
  - [ ] GIVEN a new `src/config/profile_flags.py` module WHEN the app loads THEN it reads 3 env vars with safe default=false: `PROFILE_WRITE_CONFIDENCE`, `PROFILE_CONTRADICTION_DETECTION`, `PROFILE_INFERRED_EXTRACTION`.
  - [ ] GIVEN any flag is off THEN the related code path behaves as if the feature does not exist (not as "feature on without writes" — truly absent).
  - [ ] GIVEN tests THEN flags can be monkey-patched per test.
  - [ ] GIVEN `GET /v1/profile/_flags` THEN it returns current flag state (debug endpoint).
- Edge cases:
  - Env var unset → false.
  - Env var set to "true", "1", "yes" (case-insensitive) → true; anything else → false.
- Dependencies: none

---

### Story 1.4: Contradiction detection on extraction

- Priority: P0
- User problem: New extractions silently overwrite contradicting existing values. The profile gradually decoheres with no audit trail.
- API contract preserved: `/v1/profile` and `/v1/profile/{category}` responses unchanged (no new top-level keys). Conflict data is only surfaced via the new `/v1/profile/conflicts` endpoint in Story 1.17.
- Acceptance criteria:
  - [ ] GIVEN an extraction about to change a stored field AND flag `PROFILE_CONTRADICTION_DETECTION=true` THEN a row is appended to a new `profile_field_conflicts` table with existing value, new value, source context, and `resolution_status: 'unresolved'`.
  - [ ] GIVEN the flag is off THEN behavior matches today (upsert wins, no conflict row).
  - [ ] GIVEN the flag is on THEN the upsert still executes; this story observes, it does not block.
  - [ ] GIVEN repeated contradictions on the same field THEN each is appended (not deduped) so oscillation is visible.
- Edge cases:
  - Case-only differences ("Vegetarian" vs "vegetarian") → normalize before diff.
  - Array additions → NOT a conflict.
  - Array removals/replacements → conflict.
  - Object partial update → per-key comparison; only flag keys that changed.
- Dependencies: 1.3

---

### Story 1.5: Confidence-weighted conflict resolution

- Priority: P1
- User problem: Detection without resolution just logs noise. A 10-source conviction should not be overwritten by a 1-source guess.
- API contract preserved: `/v1/profile` and `/v1/profile/{category}` responses unchanged. Resolution outcomes surface only via `/v1/profile/conflicts` (Story 1.17).
- Acceptance criteria:
  - [ ] GIVEN a detected contradiction AND the existing field has higher composite confidence AND flag `PROFILE_CONTRADICTION_DETECTION=true` THEN the new value does NOT overwrite `profile_fields`; conflict row marked `kept_existing`.
  - [ ] GIVEN the new extraction has higher composite confidence THEN it overwrites; conflict row marked `promoted_new`.
  - [ ] GIVEN manual PUT THEN manual always wins (Epic 1 deferral); conflict row marked `manual_override` recording prior auto state.
  - [ ] GIVEN the flag is off THEN prior overwrite-always behavior holds.
- Edge cases:
  - Tied confidence → newer wins (recency tiebreaker).
  - No existing confidence row (pre-1.2 data) → treat as 50, not 100.
- Dependencies: 1.2, 1.4

---

### Story 1.6: `profile_fields_history` table

- Priority: P1
- User problem: We can't reconstruct what a field used to be, when it changed, or why. Recovery from a bad extraction means manual re-seeding.
- API contract preserved: No existing response keys touched. History is a new table written unconditionally; reads live at the new `/v1/profile/history` endpoint in Story 1.16.
- Architecture: App-side `ProfileHistoryService` (not a DB trigger) with `change_type` classification — `initial | refine | contradict | manual_override`. Parminder's architectural call; kept as-is. Backfill seeds one `initial` row per existing field.
- Acceptance criteria:
  - [ ] GIVEN a new `profile_fields_history` table WHEN a field is written via any path THEN a row is appended with `{user_id, category, field_name, field_value, previous_value, change_type, source_memory_id, changed_at}`.
  - [ ] GIVEN a no-op update (same value) THEN no history row is added.
  - [ ] GIVEN DELETE on a field THEN a history row is written with `field_value=null, change_type='manual_override'`.
  - [ ] GIVEN backfill runs once after migration THEN exactly one `initial` row exists per (user_id, category, field_name) currently in `profile_fields`.
- Edge cases:
  - JSON values → stored as JSONB.
  - Index `(user_id, category, field_name, changed_at DESC)` for reads.
- Dependencies: none (unconditional write — no flag gate in v2)

---

### Story 1.7: Per-category freshness in `/completeness`

- Priority: P1
- User problem: A 100% complete profile where everything is 6 months old looks identical to one updated yesterday. Staleness is invisible.
- API contract preserved: `/v1/profile/completeness` retains all top-level keys — `user_id`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `missing`. The `completeness_pct` numeric value is expected to change because the expected-field set grows (Stories 1.10, 1.11, 1.15, 1.19); that is not a contract break. New `freshness` object is additive under `details=true`.
- Acceptance criteria:
  - [ ] GIVEN `GET /v1/profile/completeness?details=true` THEN response gains an additive `freshness` object with `{overall_freshness_pct, categories: {<cat>: {freshness_pct, stalest_field, stalest_days}}}`.
  - [ ] GIVEN `GET /v1/profile/completeness` without `details=true` THEN response shape is byte-compatible with today (only `completeness_pct` numeric shifts because the denominator grew).
  - [ ] GIVEN freshness calculation: <30d=100%, 30-90d linear 100→50, >90d floor 50.
  - [ ] GIVEN empty category THEN `freshness_pct: null` (distinguish empty from stale).
- Edge cases:
  - `last_updated = NULL` → treat as oldest-possible.
  - UTC consistency to avoid skew.
- Dependencies: none (unconditional in v2)

---

### Story 1.8: Temporal decay factor in composite confidence

- Priority: P1
- User problem: Stale confidence looks the same as fresh confidence. 180-day-old data should not outrank yesterday's evidence on source count alone.
- API contract preserved: No response keys touched. Decay feeds into the confidence composite which is already exposed via `include_metadata=true`; metadata keys unchanged.
- Acceptance criteria:
  - [ ] GIVEN additive column `temporal_decay_factor` (default 1.0) on `profile_confidence_scores` THEN factor is derived from days-since-last-source: 1.0 at 0d, 0.7 at 90d, 0.5 at 180d, 0.3 floor at 365+.
  - [ ] GIVEN conflict resolution (1.5) THEN composite confidence is multiplied by decay factor before comparison.
  - [ ] GIVEN an existing `profile_confidence_scores` row THEN the decay factor is recomputed on every extraction cycle (not stale-cached).
- Edge cases:
  - None beyond standard date math.
- Dependencies: 1.2, 1.7

---

### Story 1.9: New category `relationships` with named-person objects

- Priority: P1
- User problem: We know the spouse's name and the daughter's age but not their dynamic or why they matter. AI can't empathize without relational context.
- API contract preserved: `/v1/profile` retains `categories`; `relationships` simply appears as a new key alongside existing categories (additive, not a rename). `basics.spouse` and `basics.children` remain in place unchanged. `completeness_pct` will recompute (expected).
- Architecture: Relationships is a new **category** on the existing `profile_fields` schema, not a new table. `field_name = "{role}:{slug}"` (e.g. `daughter:ava`); `field_value` is `value_type='dict'` JSON. Reuses dedup, sources, confidence, generic UI render. Parminder's architectural call; kept as-is. Migration widens `chk_category_valid` (same pattern as migration 023).
- Ships in three internal slices reviewed together:
  - (a) migration + `VALID_CATEGORIES` widening + `EXPECTED_PROFILE_FIELDS` entry
  - (b) extraction prompt extension + storage path
  - (c) UI surfacing (folded into Story 1.18)
- Acceptance criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS` gains `relationships` THEN `VALID_CATEGORIES` includes it and storage accepts writes under it.
  - [ ] GIVEN extraction runs over a memory describing a named person with a dynamic THEN LLM emits `{category: "relationships", field_name: "<role>:<slug>", field_value: {name, role, dynamic, why_matter, last_mentioned}}`.
  - [ ] GIVEN `basics.spouse` / `basics.children` exist THEN they are NOT migrated; `relationships` complements.
  - [ ] GIVEN `GET /v1/profile` AND the user has relationships data THEN `relationships` appears as an additional key under `profile`; all frozen top-level keys (`user_id`, `profile`, `categories`, `last_updated`, `created_at`) remain.
- Edge cases:
  - Same person in both `basics.spouse` and `relationships` → allowed; different purposes.
  - Slug collision (two Avas) → disambiguator (`daughter:ava`, `daughter:ava_2`).
- Dependencies: none (unconditional in v2)

---

### Story 1.10: Present-tense fields — life stage & current reality

- Priority: P1
- User problem: Profile captures goals and background but not where the user IS right now. No signal for "in the middle of a hard thing" vs "coasting." The AI can't meet the user where they are.
- API contract preserved: `/v1/profile` retains all frozen top-level keys. New fields appear under `profile.personality` (existing category), so structure is natural. `completeness_pct` numeric value shifts because denominator grows; key itself unchanged.
- Acceptance criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS['personality']` gains `life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins` THEN extraction prompt is extended to emit these fields when memories reference transitions / pressures / wins.
  - [ ] GIVEN an extraction emits `personality.active_stressors` as an array of strings AND `personality.recent_wins` as an array of `{description, occurred_at}` objects THEN storage accepts both shapes via `value_type=list`.
  - [ ] GIVEN a `recent_wins` entry is >90 days old AND extraction runs THEN the entry is evicted (recency-bounded, uniform decay — confirmed).
  - [ ] GIVEN `life_stage` overwrites on change THEN the previous value is captured in `profile_fields_history` (Story 1.6) so transitions are preserved.
  - [ ] GIVEN the four new field names THEN they are enumerated verbatim in Murat's regression tests: `life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins`.
- Edge cases:
  - LLM hallucinates a stressor not grounded in the memory → enforce `source_memory_id` traceability; reject extraction of that field otherwise.
- Dependencies: none (unconditional in v2)

---

### Story 1.11: How-fields — decision style, growth edges, energy recovery

- Priority: P2
- User problem: Profile captures what the user does, not how. Two "burned out" users need opposite interventions; the AI can't tell them apart.
- API contract preserved: Same as 1.10 — frozen top-level keys intact, new fields live under `profile.personality`. `completeness_pct` recomputes on the grown denominator.
- Acceptance criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS['personality']` gains `decision_style`, `growth_edges`, `energy_recovery_patterns` THEN extraction prompt is extended to emit these.
  - [ ] GIVEN a stored `growth_edge` AND a later "I've gotten better at X" memory THEN edge is NOT auto-removed (requires explicit retirement statement or manual edit — no premature victory).
  - [ ] GIVEN the three new field names THEN they are enumerated verbatim in regression tests: `decision_style`, `growth_edges`, `energy_recovery_patterns`.
  - [ ] GIVEN `decision_style` is a single string, `growth_edges` is an array of strings, `energy_recovery_patterns` is a single string THEN storage reflects those `value_type`s.
- Dependencies: 1.10 (land the prompt diff sequentially to keep LLM-behavior review tractable)

---

### Story 1.12: Enable inferred / soft-signal extraction

- Priority: P2
- User problem: LLM rarely uses `source_type: inferred` (12/421 sources). The system refuses to form hypotheses — the whole value-add of a deep profile.
- API contract preserved: `/v1/profile` and `/v1/profile/{category}` responses unchanged. When `include_metadata=true` AND flag is on AND a field is inferred, an additive `source_type` key appears in that field's metadata — additive only, clients ignoring unknown keys are unaffected.
- Acceptance criteria:
  - [ ] GIVEN flag `PROFILE_INFERRED_EXTRACTION=true` AND the extraction prompt THEN the prompt explicitly encourages hypothesis formation with examples (pattern across 3+ memories → inferred field) and caps inferred-field composite confidence at 75.
  - [ ] GIVEN an inferred extraction WHEN stored THEN `source_type='inferred'` is written and composite confidence is capped at 75.
  - [ ] GIVEN the flag is off THEN extraction matches today's behavior (inferred allowed but not encouraged).
  - [ ] GIVEN `GET /v1/profile?include_metadata=true` AND the flag is on AND inferred fields exist THEN metadata surfaces `source_type: "inferred"` for those fields; existing metadata keys unchanged.
- Dependencies: 1.2 (confidence writes must exist so the cap is enforceable)

---

### Story 1.13: Destructive cleanup — `dietary_needs` vs `food_preferences`

- Priority: P1
- User problem: `dietary_needs: "Vegetarian (eats eggs). Favorites: Pizza, Noodles, Indian food."` conflates a medical/ethical restriction with a preference. Downstream code asking "can this person eat this" gets a useless blob.
- API contract preserved: `/v1/profile/health` retains all frozen top-level keys. After migration, `health.dietary_needs` still exists (just cleaner); `preferences.food_preferences` still exists (just has more values). `completeness_pct` recomputes — likely unchanged because both fields were already populated.
- v2 reframe: This is now a **destructive one-shot migration** plus a manual-PUT input-validation guard. No shadow field; fix in place.
- Acceptance criteria:
  - [ ] GIVEN a migration script AND existing `health.dietary_needs` values THEN preference markers (substrings after "Favorites:", "likes", "prefers", followed by food tokens) are stripped from the value in place; `health.dietary_needs` is rewritten with restriction content only.
  - [ ] GIVEN the extracted favorites from the migration THEN they are merged into `preferences.food_preferences` — if that field does not exist, create it with `value_type=list`; if it exists, append missing items without duplicating.
  - [ ] GIVEN the migration is idempotent THEN running it twice produces no further change.
  - [ ] GIVEN a manual PUT to `health.dietary_needs` with a value containing preference-vocabulary tokens THEN the request is rejected with HTTP 400 and a message directing to `preferences.food_preferences`.
  - [ ] GIVEN the preference-vocabulary detector THEN it matches documented terms (`favorites:`, `likes`, `prefers`, `loves to eat`) and does NOT false-positive on restriction phrasing (`allergies: severe`, `avoids peanuts`).
  - [ ] GIVEN the migration runs THEN a `profile_fields_history` row is written for each changed field with `change_type='migration'`.
- Edge cases:
  - `health.dietary_needs` with no preference contamination → migration no-ops; no history row.
  - Manual PUT to `preferences.food_preferences` is unaffected by the guard.
- Dependencies: 1.6 (history table must exist for migration audit trail)

---

### Story 1.14: Destructive cleanup — `allergies: []` null-vs-empty

- Priority: P2
- User problem: `[]` ambiguously means "confirmed none" or "never extracted." Both readings are currently valid, which is worse than either.
- API contract preserved: `/v1/profile/health` retains all frozen top-level keys. `allergies` may transition from `[]` to `null` for rows where it was never affirmatively confirmed; clients reading the field see a type shift (array → null) — acceptable per v2 constraint.
- v2 reframe: Destructive migration. Set `null` where we never had affirmative confirmation.
- Acceptance criteria:
  - [ ] GIVEN a migration script AND each existing `health.allergies = []` row THEN if no `profile_sources` row exists for that field with an affirmative-confirmation marker, the value is rewritten to `null` (stored as `value_type='none'` or equivalent sentinel).
  - [ ] GIVEN a `health.allergies = []` row WHERE a source DOES affirmatively say "no known allergies" or equivalent THEN the value remains `[]` (meaning: affirmed none).
  - [ ] GIVEN the migration THEN each changed row produces a `profile_fields_history` entry with `change_type='migration'`.
  - [ ] GIVEN future manual PUT with body `{value: []}` THEN that is interpreted as "affirmed none" (explicit user intent).
  - [ ] GIVEN future extraction producing `allergies: []` THEN no value is written unless the extraction source contains affirmative-confirmation markers.
- Edge cases:
  - The same logic generalizes to other "confirmed-none-able" fields (e.g., `medications`); scope of THIS story is `allergies` only, but document the pattern for later application.
- Dependencies: 1.6

---

### Story 1.15: Destructive restructure — `health_conditions` string → object

- Priority: P1
- User problem: Most-active health signal is a flat string with 10 sources. No triggers, no severity, no management strategies captured.
- API contract preserved: `/v1/profile/health` retains all frozen top-level keys. `health.health_conditions` still exists by name, but its stored type shifts from string to array of objects — acceptable per v2 constraint. Clients reading this field receive the new object shape.
- v2 reframe: Destructive. String → array of objects `[{condition, triggers[], severity, onset, management[], status}]`. Migration rewrites existing string values as single-element arrays with `{condition: "<old string>", triggers: [], severity: null, onset: null, management: [], status: "unknown"}`.
- Acceptance criteria:
  - [ ] GIVEN a migration script AND existing `health.health_conditions` string values THEN each is rewritten as a single-element array: `[{condition: "<old string>", triggers: [], severity: null, onset: null, management: [], status: "unknown"}]` with `value_type='list'`.
  - [ ] GIVEN the migration THEN each changed row produces a `profile_fields_history` entry with `change_type='migration'` and `previous_value` set to the old string.
  - [ ] GIVEN the extraction prompt is updated THEN subsequent extractions emit `health.health_conditions` as an array of objects, never as a flat string.
  - [ ] GIVEN a manual PUT with the old flat-string shape THEN the request is rejected with HTTP 400 and a message explaining the new object shape.
  - [ ] GIVEN an extraction refining an existing condition THEN the matching element is updated in place (match on `condition` string, case-insensitive); a new element is appended if no match.
  - [ ] GIVEN `GET /v1/profile/health` THEN the field name `health_conditions` is preserved; only its stored shape changed.
- Edge cases:
  - Empty string pre-migration → skip (leave unchanged; treat as missing).
  - LLM produces severity as free-form text → coerce to one of `{mild, moderate, severe, unknown}` with `unknown` fallback.
- Dependencies: 1.6

---

### Story 1.16: `GET /v1/profile/history` read endpoint

- Priority: P2
- User problem: History is write-only without a read endpoint; the self-correcting promise is vapor.
- API contract preserved: Net-new endpoint under the existing `/v1/profile/*` path namespace. All existing routes untouched.
- Acceptance criteria:
  - [ ] GIVEN `GET /v1/profile/history?user_id=X&category=Y&field_name=Z&limit=N` THEN it returns a list of history rows ordered DESC by `changed_at`, each with `{field_value, previous_value, change_type, source_memory_id, changed_at}`.
  - [ ] GIVEN category/field_name omitted THEN returns history across all fields for the user, paginated (default 50).
  - [ ] GIVEN missing `user_id` THEN 400.
  - [ ] GIVEN a limit above the cap (500) THEN it's clamped silently.
- Edge cases:
  - Unknown `user_id` → 200 with empty list (consistent with other profile endpoints).
- Dependencies: 1.6

---

### Story 1.17: `GET /v1/profile/conflicts` read endpoint

- Priority: P2
- User problem: Conflicts detected in 1.4/1.5 are unobservable without this endpoint.
- API contract preserved: Net-new endpoint; all existing routes untouched.
- Acceptance criteria:
  - [ ] GIVEN `GET /v1/profile/conflicts?user_id=X&status=unresolved|all` AND flag `PROFILE_CONTRADICTION_DETECTION=true` THEN it returns conflict rows with full diff context (`existing_value`, `new_value`, `source_memory_id`, `detected_at`, `resolution_status`).
  - [ ] GIVEN the flag is off THEN 404 (consistent with "feature not enabled").
  - [ ] GIVEN POST / PUT / DELETE on this path THEN 405 (resolution UX deferred to Epic 2).
- Dependencies: 1.4

---

### Story 1.18: Profile.tsx refresh — depth, freshness, conflicts

- Priority: P2
- User problem: New data (relationships, present-tense fields, freshness, conflict counts) is invisible to the user until the UI surfaces it. The v1 constraint forced an additive-tab approach; v2 lets us redesign.
- API contract preserved: UI only. No backend contract touched. Frontend consumes existing endpoints plus `/v1/profile/history` and `/v1/profile/conflicts` (Stories 1.16, 1.17).
- Acceptance criteria:
  - [ ] GIVEN the existing Profile.tsx category sections THEN each section renders the updated shapes: `health.health_conditions` as structured list of condition cards, `health.exercise` as a new card (from Story 1.19), `relationships` as a named-person card list, new `personality` fields rendered with appropriate widgets.
  - [ ] GIVEN confidence metadata is available (Story 1.2) THEN each field displays a read-only confidence indicator.
  - [ ] GIVEN freshness data is available (Story 1.7) THEN each category header shows a freshness badge (green <30d, yellow 30-90d, red >90d).
  - [ ] GIVEN the user has open conflicts (Story 1.17) THEN a conflict count badge appears with a link to a modal / drawer listing them.
  - [ ] GIVEN a field of unknown shape arrives THEN the UI renders a generic key/value row, never crashes.
  - [ ] GIVEN the profile loads end-to-end THEN all frozen API response keys (`user_id`, `profile`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `missing`, `last_updated`, `created_at`) are still consumed as before; numeric `completeness_pct` may display a different number than pre-v2 (that's the recompute).
- Edge cases:
  - Partial data: any subset of new fields may be present; render graceful empties.
- Dependencies: 1.2, 1.7, 1.9, 1.10, 1.11, 1.15, 1.16, 1.17, 1.19

---

### Story 1.19: Category re-assignment pass

- Priority: P1 (NEW in v2)
- User problem: Exercise and fitness content lives under `interests.hobbies` ("barbell-based workouts"), where no consumer looking for health information would think to look. Categories aren't organized around user-intent queries; they're organized around whatever the LLM happened to emit first. Over time this erodes trust in the profile as a queryable self-model.
- API contract preserved: `/v1/profile` and `/v1/profile/{category}` retain all frozen top-level keys. `interests.hobbies` still exists (with exercise content removed); `health.exercise` is new. `completeness_pct` recomputes because `EXPECTED_PROFILE_FIELDS` gains `health.exercise`.
- Scope: destructive migration + extraction-prompt clarification.

**Concrete moves performed by this migration:**

| From | To | Transform |
|------|-----|-----------|
| `interests.hobbies` (exercise/fitness items: "barbell-based workouts", "running", "yoga", "gym", "strength training", any value with fitness vocabulary) | `health.exercise` | Move; merge into `health.exercise` (new field, `value_type='dict'`) with shape `{activities: [<items>], frequency: null, last_mentioned: <newest source date>}`. Items removed from `interests.hobbies`. |
| `preferences.sleep_schedule` | stays put | Add a cross-reference comment in `health` schema docs; no data move (sleep is both a preference and a health signal; leaving canonical home in preferences). |
| `health.dietary_needs` food favorites | `preferences.food_preferences` | Handled by Story 1.13 — referenced here for completeness of the re-categorization narrative. |

- Acceptance criteria:
  - [ ] GIVEN a migration script AND each user's `interests.hobbies` value THEN items matching the fitness vocabulary list (`barbell`, `workout`, `gym`, `strength training`, `running`, `yoga`, `cardio`, `lifting`, `hiit`, `cycling`, `swimming` — documented in the script) are extracted.
  - [ ] GIVEN extracted fitness items THEN they are written to `health.exercise` as `{activities: [<items>], frequency: null, last_mentioned: <latest source ts from moved items>}`; if `health.exercise` already exists, activities are merged without duplicates.
  - [ ] GIVEN the migration THEN `interests.hobbies` is rewritten with the fitness items removed; if the resulting list is empty, the field is deleted outright.
  - [ ] GIVEN the migration THEN `EXPECTED_PROFILE_FIELDS['health']` includes `exercise`.
  - [ ] GIVEN the extraction prompt is updated THEN future extractions emit exercise-related content under `health.exercise`, not `interests.hobbies`; a prompt example makes this explicit.
  - [ ] GIVEN the migration runs THEN `profile_fields_history` records a `change_type='migration'` row for both the source and destination rows of each move.
  - [ ] GIVEN a manual PUT to `interests.hobbies` with a fitness-vocabulary value THEN the request is rejected with HTTP 400 and a message directing to `health.exercise`.
  - [ ] GIVEN `GET /v1/profile` AND `GET /v1/profile/health` post-migration THEN `health.exercise` appears with the moved data; `interests.hobbies` appears without the fitness items (or is absent if emptied); all frozen top-level response keys remain.
- Edge cases:
  - Ambiguous item ("walking") — include in the vocabulary list; rationale documented.
  - User with no fitness content in hobbies → migration no-ops on that user.
  - Fitness item that's also a social hobby ("cycling with friends") → move anyway; the `interests.social_preferences` field captures the social aspect separately.
- Dependencies: 1.6

---

## Open questions

- **Severity vocabulary for `health.health_conditions`** (Story 1.15) — settled on `{mild, moderate, severe, unknown}` with `unknown` fallback. Re-raise if Parminder's tech spec proposes a richer ontology.
- **Fitness vocabulary list** (Story 1.19) — first-pass list documented inline; expect tuning once real migration runs against backfill data.

## Known risks

- **Migration ordering** — Stories 1.13, 1.14, 1.15, 1.19 all rewrite data. They must run in the order the dependency graph declares, and each must be idempotent so a mid-run failure can be recovered. Rollout script sequences them.
- **Completeness shock** — `completeness_pct` numeric value will change for every user once v2 lands (new fields, re-categorizations, recomputed denominator). This is expected and acceptable per user mandate; document in release notes so it isn't mistaken for a regression.
- **Prompt compounding** — Stories 1.10, 1.11, 1.12, 1.15, 1.19 all touch the extraction prompt. Sequence them (10 → 11 → 12 → 15 → 19 prompt edit) to keep LLM-behavior diffs reviewable.
- **UI churn** — Story 1.18 absorbs every surface change at once. Budget for follow-up polish in Epic 2 rather than cramming UX refinement into this sprint.
