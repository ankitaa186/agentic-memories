# Sprint Status — agentic-memories

Last Updated: 2026-04-20

## Active Epic
**Epic 1: Deep Profile — from resume to self-model** (drafted v2 by Disha, design-reviewed v1 by Parminder — parallel v2 tech-spec rewrite in flight)
Goal: Evolve the profile layer so the AI knows the user better than they know themselves.
Constraint (v2): **API backward-compat only** — URL paths, HTTP methods, status codes, response top-level keys, query params, PUT/DELETE body shapes are frozen. Stored data, `EXPECTED_PROFILE_FIELDS`, `completeness_pct` math, UI, category assignments — all free to change. See `.claude/scrum/bus/2026-04-20.md` [01:32] for the reframe.
Full epic doc: `.claude/scrum/docs/epic-1-deep-profile.md` (v2)
Wave plan: `.claude/scrum/docs/wave-plan.md` — 4 waves, 19 stories. Wave 1 = 3 parallel foundations (1.1, 1.3, 1.6). Wave 2 = 5 parallel + 5 sequential prompt-chain. Wave 3 = 3 parallel + 2 sequential. Wave 4 = UI.
Flag matrix (3): `PROFILE_WRITE_CONFIDENCE`, `PROFILE_CONTRADICTION_DETECTION`, `PROFILE_INFERRED_EXTRACTION`. Retired: `PROFILE_LOG_HISTORY`, `PROFILE_ENABLE_RELATIONSHIPS`, `PROFILE_TEMPORAL_DECAY`, `PROFILE_NEW_FIELDS_COUNT`, `PROFILE_DEPTH_FIELDS_ENABLED`.
Destructive migrations in v2: 1.13 (dietary cleanup), 1.14 (allergies null-vs-empty), 1.15 (health_conditions string→object), 1.19 (exercise/fitness re-categorization). All use `profile_fields_history` (`change_type='migration'`) for audit.
Pending: Parminder transitions Wave 1 stories to `ready` once v2 tech spec is posted.

## Backlog

### Story 1.1: Fix stale `TOTAL_EXPECTED_FIELDS` comment
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: none
- Review Cycles: 0
- User Problem: Future contributors trust a stale comment (says 25, actual is 27 and growing in v2). Debt compounds as v2 adds fields.
- API Contract Preserved: No response keys touched; comment + test only.
- Acceptance Criteria:
  - [ ] GIVEN `profile_storage.py:39` WHEN a reader inspects the `TOTAL_EXPECTED_FIELDS` comment THEN it reflects the actual summed count.
  - [ ] GIVEN the expected-fields dict changes in the future WHEN the comment drifts THEN a unit test asserts `TOTAL_EXPECTED_FIELDS == sum(len(v) for v in EXPECTED_PROFILE_FIELDS.values())` and fails loudly.
- Edge Cases:
  - None substantive.

### Story 1.2: Wire extraction pipeline to `profile_confidence_scores`
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: 1.3
- Review Cycles: 0
- User Problem: LLM returns a confidence score per extraction; we discard it. System can't distinguish certain knowledge from guesses.
- API Contract Preserved: `/v1/profile`, `/v1/profile/{category}` retain `user_id`, `profile`, `categories`, `last_updated`, `created_at`. When `?include_metadata=true`, existing metadata keys remain; new `confidence` metadata additive only.
- Architecture: `ProfileConfidenceService` derives from `profile_sources` (0.30 freq + 0.25 recency + 0.25 explicitness + 0.20 diversity). Called from `store_profile_extractions` post-source-insert.
- Acceptance Criteria:
  - [ ] GIVEN an LLM extraction with `confidence` and `source_type` AND flag `PROFILE_WRITE_CONFIDENCE=true` WHEN `store_profile_extractions` runs THEN a row is upserted into `profile_confidence_scores` with all four component scores populated.
  - [ ] GIVEN the flag is off THEN no rows are written and `include_metadata=true` output matches today's shape exactly.
  - [ ] GIVEN re-extraction of an existing field THEN the confidence row is updated in place, not duplicated.
  - [ ] GIVEN manual PUT runs THEN existing manual behavior is preserved (confidence=100, `is_manual_override=true` exposed); auto-computed scores not silently overwritten.
  - [ ] GIVEN extraction completes THEN `confidence_written: <count>` is logged.
- Edge Cases:
  - LLM omits `confidence` → default to 70 and still write.
  - First-time extract (0 prior sources) → compute from the single new source.
  - LLM returns `confidence: 0` → still write.

### Story 1.3: Three-flag harness for profile behavior changes
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: none
- Review Cycles: 0
- User Problem: Confidence scoring formula, contradiction observation, and inferred-extraction prompt change each still earn a gate (shadow verify / observe before resolve / LLM-behavior dark launch). Everything else ships unconditionally.
- API Contract Preserved: `/v1/profile/_flags` is additive and internal; no existing routes touched.
- Acceptance Criteria:
  - [ ] GIVEN a new `src/config/profile_flags.py` module WHEN the app loads THEN it reads 3 env vars with safe default=false: `PROFILE_WRITE_CONFIDENCE`, `PROFILE_CONTRADICTION_DETECTION`, `PROFILE_INFERRED_EXTRACTION`.
  - [ ] GIVEN any flag is off THEN the related code path behaves as if the feature does not exist.
  - [ ] GIVEN tests THEN flags can be monkey-patched per test.
  - [ ] GIVEN `GET /v1/profile/_flags` THEN it returns current flag state.
- Edge Cases:
  - Env var unset → false.
  - "true", "1", "yes" (case-insensitive) → true; anything else → false.

### Story 1.4: Contradiction detection on extraction
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: 1.3
- Review Cycles: 0
- User Problem: New extractions silently overwrite contradicting existing values. Profile gradually decoheres with no audit trail.
- API Contract Preserved: `/v1/profile` and `/v1/profile/{category}` response shapes unchanged. Conflicts surface only via `/v1/profile/conflicts` (Story 1.17).
- Acceptance Criteria:
  - [ ] GIVEN an extraction about to change a stored field AND flag `PROFILE_CONTRADICTION_DETECTION=true` THEN a row is appended to `profile_field_conflicts` with existing value, new value, source context, `resolution_status: 'unresolved'`.
  - [ ] GIVEN the flag is off THEN behavior matches today (upsert wins, no conflict row).
  - [ ] GIVEN the flag is on THEN the upsert still executes; detection observes, does not block.
  - [ ] GIVEN repeated contradictions on the same field THEN each is appended (not deduped) so oscillation is visible.
- Edge Cases:
  - Case-only differences → normalize before diff.
  - Array additions → NOT a conflict.
  - Array removals/replacements → conflict.
  - Object partial update → per-key comparison.

### Story 1.5: Confidence-weighted conflict resolution
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: 1.2, 1.4
- Review Cycles: 0
- User Problem: Detection without resolution just logs noise. 10-source conviction shouldn't be overwritten by 1-source guess.
- API Contract Preserved: `/v1/profile` and `/v1/profile/{category}` response shapes unchanged. Resolution outcomes surface only via `/v1/profile/conflicts`.
- Acceptance Criteria:
  - [ ] GIVEN a detected contradiction AND existing field has higher composite confidence AND flag on THEN new value does NOT overwrite; conflict row marked `kept_existing`.
  - [ ] GIVEN the new extraction has higher confidence THEN it overwrites; conflict row marked `promoted_new`.
  - [ ] GIVEN manual PUT THEN manual always wins (Epic 1 deferral); row marked `manual_override` recording prior auto state.
  - [ ] GIVEN the flag is off THEN prior overwrite-always behavior holds.
- Edge Cases:
  - Tied confidence → newer wins.
  - No existing confidence row → treat as 50, not 100.

### Story 1.6: `profile_fields_history` table
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: none
- Review Cycles: 0
- User Problem: We can't reconstruct what a field used to be, when it changed, or why. Recovery from a bad extraction means manual re-seeding. Also: required audit surface for destructive migrations 1.13/1.14/1.15/1.19.
- API Contract Preserved: No existing response keys touched; reads live at new `/v1/profile/history` endpoint (Story 1.16). In v2, writes are unconditional (no flag).
- Architecture: App-side `ProfileHistoryService` with `change_type` classification — `initial | refine | contradict | manual_override | migration`. Backfill seeds one `initial` row per existing field.
- Acceptance Criteria:
  - [ ] GIVEN a new `profile_fields_history` table WHEN a field is written via any path THEN a row is appended with `{user_id, category, field_name, field_value, previous_value, change_type, source_memory_id, changed_at}`.
  - [ ] GIVEN a no-op update (same value) THEN no history row added.
  - [ ] GIVEN DELETE on a field THEN a row is written with `field_value=null, change_type='manual_override'`.
  - [ ] GIVEN backfill runs once after migration THEN exactly one `initial` row exists per (user_id, category, field_name) currently in `profile_fields`.
- Edge Cases:
  - JSON values → stored as JSONB.
  - Index `(user_id, category, field_name, changed_at DESC)` for reads.

### Story 1.7: Per-category freshness in `/completeness`
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: none
- Review Cycles: 0
- User Problem: A 100% complete profile where everything is 6 months old looks identical to one updated yesterday. Staleness is invisible.
- API Contract Preserved: `/v1/profile/completeness` retains `user_id`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `missing`. Numeric `completeness_pct` value will shift (denominator grew across v2 stories); key itself unchanged. New `freshness` object is additive under `details=true`.
- Acceptance Criteria:
  - [ ] GIVEN `GET /v1/profile/completeness?details=true` THEN response gains additive `freshness` object with `{overall_freshness_pct, categories: {<cat>: {freshness_pct, stalest_field, stalest_days}}}`.
  - [ ] GIVEN `GET /v1/profile/completeness` without `details=true` THEN response shape is byte-compatible with today (only `completeness_pct` numeric shifts).
  - [ ] GIVEN freshness calculation: <30d=100%, 30-90d linear 100→50, >90d floor 50.
  - [ ] GIVEN empty category THEN `freshness_pct: null`.
- Edge Cases:
  - `last_updated = NULL` → treat as oldest-possible.
  - UTC consistency.

### Story 1.8: Temporal decay factor in composite confidence
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: 1.2, 1.7
- Review Cycles: 0
- User Problem: Stale confidence looks like fresh confidence. 180-day-old data shouldn't outrank yesterday's evidence on source count alone. In v2 this ships unconditionally (formula change, no cutover risk).
- API Contract Preserved: No response keys touched. Decay feeds the confidence composite exposed via `include_metadata=true`; metadata keys unchanged.
- Acceptance Criteria:
  - [ ] GIVEN additive column `temporal_decay_factor` (default 1.0) on `profile_confidence_scores` THEN factor is derived from days-since-last-source: 1.0 at 0d, 0.7 at 90d, 0.5 at 180d, 0.3 floor at 365+.
  - [ ] GIVEN conflict resolution (1.5) THEN composite confidence is multiplied by decay factor before comparison.
  - [ ] GIVEN an existing `profile_confidence_scores` row THEN decay factor recomputes on every extraction cycle (not stale-cached).
- Edge Cases:
  - None beyond standard date math.

### Story 1.9: New category `relationships` with named-person objects
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: none
- Review Cycles: 0
- User Problem: We know spouse's name and daughter's age but not their dynamic or why they matter. AI can't empathize without relational context.
- API Contract Preserved: `/v1/profile` retains `categories`; `relationships` appears as a new key alongside existing categories (additive). `basics.spouse` and `basics.children` remain in place. `completeness_pct` recomputes (expected).
- Architecture: New category on existing `profile_fields` schema (not a new table). `field_name = "{role}:{slug}"`. Reuses dedup/sources/confidence/UI generic render. Widen `chk_category_valid` via migration.
- Acceptance Criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS` gains `relationships` THEN `VALID_CATEGORIES` includes it and storage accepts writes.
  - [ ] GIVEN extraction runs on a memory describing a named person with a dynamic THEN LLM emits `{category: "relationships", field_name: "<role>:<slug>", field_value: {name, role, dynamic, why_matter, last_mentioned}}`.
  - [ ] GIVEN `basics.spouse` / `basics.children` exist THEN they are NOT migrated; `relationships` complements.
  - [ ] GIVEN `GET /v1/profile` AND the user has relationships data THEN `relationships` appears as additional key under `profile`; all frozen top-level keys remain.
- Edge Cases:
  - Same person in basics and relationships → allowed; different purposes.
  - Slug collision → disambiguator (`daughter:ava`, `daughter:ava_2`).

### Story 1.10: Present-tense fields — life_stage, current_inflection_point, active_stressors, recent_wins
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: none
- Review Cycles: 0
- User Problem: Profile captures goals and background but not where the user IS right now. No signal for "in the middle of a hard thing" vs "coasting." AI can't meet the user where they are.
- API Contract Preserved: `/v1/profile` retains all frozen top-level keys. New fields live under `profile.personality` (existing category). `completeness_pct` numeric value shifts (denominator grew); key itself unchanged.
- Acceptance Criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS['personality']` gains `life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins` THEN extraction prompt is extended to emit these when memories reference transitions / pressures / wins.
  - [ ] GIVEN extraction emits `personality.active_stressors` as array of strings AND `personality.recent_wins` as array of `{description, occurred_at}` THEN storage accepts both shapes via `value_type=list`.
  - [ ] GIVEN a `recent_wins` entry is >90 days old AND extraction runs THEN it's evicted (uniform decay — confirmed).
  - [ ] GIVEN `life_stage` overwrites on change THEN the previous value is captured in `profile_fields_history` so transitions are preserved.
  - [ ] GIVEN the four field names THEN they are enumerated verbatim in regression tests: `life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins`.
- Edge Cases:
  - LLM hallucinates a stressor not in the memory → enforce `source_memory_id` traceability; reject otherwise.

### Story 1.11: How-fields — decision_style, growth_edges, energy_recovery_patterns
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.10
- Review Cycles: 0
- User Problem: Profile captures what the user does, not how. Two "burned out" users need opposite interventions; AI can't tell them apart.
- API Contract Preserved: Same as 1.10 — frozen keys intact, new fields under `profile.personality`. `completeness_pct` recomputes on grown denominator.
- Acceptance Criteria:
  - [ ] GIVEN `EXPECTED_PROFILE_FIELDS['personality']` gains `decision_style`, `growth_edges`, `energy_recovery_patterns` THEN extraction prompt is extended to emit these.
  - [ ] GIVEN a stored `growth_edge` AND a later "I've gotten better at X" memory THEN edge is NOT auto-removed (explicit retirement or manual edit required).
  - [ ] GIVEN the three field names THEN they are enumerated verbatim in regression tests: `decision_style`, `growth_edges`, `energy_recovery_patterns`.
  - [ ] GIVEN `decision_style` is string, `growth_edges` is array of strings, `energy_recovery_patterns` is string THEN storage reflects those `value_type`s.
- Edge Cases:
  - Prompt diff coherence with 1.10 — land 1.10 first.

### Story 1.12: Enable inferred / soft-signal extraction
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.2
- Review Cycles: 0
- User Problem: LLM rarely uses `source_type: inferred` (12/421 sources). System refuses to form hypotheses — the whole value-add of a deep profile.
- API Contract Preserved: `/v1/profile` and `/v1/profile/{category}` response shapes unchanged. When `include_metadata=true` AND flag on AND a field is inferred, additive `source_type` key appears in metadata; clients ignoring unknown keys unaffected.
- Acceptance Criteria:
  - [ ] GIVEN flag `PROFILE_INFERRED_EXTRACTION=true` AND the extraction prompt THEN prompt explicitly encourages hypothesis formation with examples and caps inferred-field composite confidence at 75.
  - [ ] GIVEN an inferred extraction WHEN stored THEN `source_type='inferred'` is written; composite confidence capped at 75.
  - [ ] GIVEN the flag is off THEN extraction matches today's behavior.
  - [ ] GIVEN `GET /v1/profile?include_metadata=true` AND flag on AND inferred fields exist THEN metadata surfaces `source_type: "inferred"` for those fields; existing metadata keys unchanged.
- Edge Cases:
  - Metadata key is additive; existing clients ignoring unknown keys unaffected.

### Story 1.13: Destructive cleanup — `dietary_needs` vs `food_preferences`
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: 1.6
- Review Cycles: 0
- User Problem: `dietary_needs` currently carries preference data too, making it useless for "can this person eat this" queries. In v2 this becomes a destructive one-shot migration plus a manual-PUT input-validation guard.
- API Contract Preserved: `/v1/profile/health` retains all frozen top-level keys. `health.dietary_needs` still exists (cleaner); `preferences.food_preferences` still exists (more values). `completeness_pct` recomputes.
- Acceptance Criteria:
  - [ ] GIVEN a migration script AND existing `health.dietary_needs` values THEN preference markers (substrings after "Favorites:", "likes", "prefers", followed by food tokens) are stripped in place; `health.dietary_needs` rewritten with restriction content only.
  - [ ] GIVEN extracted favorites from the migration THEN they are merged into `preferences.food_preferences` — create the field if missing (`value_type=list`); append missing items if it exists; no duplicates.
  - [ ] GIVEN the migration is idempotent THEN running it twice produces no further change.
  - [ ] GIVEN a manual PUT to `health.dietary_needs` with preference-vocabulary tokens THEN the request is rejected with HTTP 400 and a message directing to `preferences.food_preferences`.
  - [ ] GIVEN the preference-vocabulary detector THEN it matches `favorites:`, `likes`, `prefers`, `loves to eat` and does NOT false-positive on restriction phrasing (`allergies: severe`, `avoids peanuts`).
  - [ ] GIVEN the migration runs THEN each changed field generates a `profile_fields_history` row with `change_type='migration'`.
- Edge Cases:
  - `health.dietary_needs` with no preference contamination → migration no-ops on that user; no history row.
  - Manual PUT to `preferences.food_preferences` is unaffected by the guard.

### Story 1.14: Destructive cleanup — `allergies: []` null-vs-empty
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.6
- Review Cycles: 0
- User Problem: `[]` ambiguously means "confirmed none" or "never extracted." In v2, migrate ambiguous rows to `null`; `[]` means affirmed-none going forward.
- API Contract Preserved: `/v1/profile/health` retains all frozen top-level keys. `allergies` may transition from `[]` to `null` for rows where it was never affirmatively confirmed; clients reading the field see a type shift (array → null) — acceptable per v2.
- Acceptance Criteria:
  - [ ] GIVEN a migration script AND each existing `health.allergies = []` row THEN if no `profile_sources` row exists for that field with an affirmative-confirmation marker, the value is rewritten to `null` (`value_type='none'` or equivalent sentinel).
  - [ ] GIVEN a `[]` row WHERE a source DOES affirmatively say "no known allergies" or equivalent THEN the value remains `[]`.
  - [ ] GIVEN the migration THEN each changed row produces a `profile_fields_history` entry with `change_type='migration'`.
  - [ ] GIVEN future manual PUT with body `{value: []}` THEN it is interpreted as "affirmed none" (explicit user intent).
  - [ ] GIVEN future extraction producing `allergies: []` THEN no value is written unless the extraction source contains affirmative markers.
- Edge Cases:
  - Pattern generalizes to other "confirmed-none-able" fields (e.g. `medications`); scope of THIS story is `allergies` only.

### Story 1.15: Destructive restructure — `health_conditions` string → object
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: 1.6
- Review Cycles: 0
- User Problem: Most-active health signal is a flat string with 10 sources. No triggers, severity, onset, or management captured. In v2 this is destructive: string → array of objects. No shadow field.
- API Contract Preserved: `/v1/profile/health` retains all frozen top-level keys. Field name `health.health_conditions` preserved; stored shape shifts from string to array of objects — acceptable per v2.
- Acceptance Criteria:
  - [ ] GIVEN a migration script AND existing `health.health_conditions` string values THEN each is rewritten as a single-element array `[{condition: "<old string>", triggers: [], severity: null, onset: null, management: [], status: "unknown"}]` with `value_type='list'`.
  - [ ] GIVEN the migration THEN each changed row produces a `profile_fields_history` entry with `change_type='migration'` and `previous_value` set to the old string.
  - [ ] GIVEN the extraction prompt is updated THEN subsequent extractions emit `health.health_conditions` as an array of objects, never as a flat string.
  - [ ] GIVEN a manual PUT with the old flat-string shape THEN the request is rejected with HTTP 400 and a message explaining the new object shape.
  - [ ] GIVEN an extraction refining an existing condition THEN the matching element is updated in place (match on `condition`, case-insensitive); a new element is appended if no match.
  - [ ] GIVEN `GET /v1/profile/health` THEN the field name `health_conditions` is preserved; only its stored shape changed.
- Edge Cases:
  - Empty string pre-migration → skip (leave unchanged).
  - LLM produces severity as free-form text → coerce to `{mild, moderate, severe, unknown}` with `unknown` fallback.

### Story 1.16: `GET /v1/profile/history` read endpoint
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.6
- Review Cycles: 0
- User Problem: History is write-only without a read endpoint; the self-correcting promise is vapor.
- API Contract Preserved: Net-new endpoint under `/v1/profile/*` namespace. All existing routes untouched.
- Acceptance Criteria:
  - [ ] GIVEN `GET /v1/profile/history?user_id=X&category=Y&field_name=Z&limit=N` THEN returns list ordered DESC by `changed_at`, each row with `{field_value, previous_value, change_type, source_memory_id, changed_at}`.
  - [ ] GIVEN category/field_name omitted THEN returns history across all fields, paginated (default 50).
  - [ ] GIVEN missing `user_id` THEN 400.
  - [ ] GIVEN limit above cap (500) THEN clamped silently.
- Edge Cases:
  - Unknown `user_id` → 200 with empty list.

### Story 1.17: `GET /v1/profile/conflicts` read endpoint
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.4
- Review Cycles: 0
- User Problem: Conflicts detected in 1.4/1.5 are unobservable without this endpoint.
- API Contract Preserved: Net-new endpoint; all existing routes untouched.
- Acceptance Criteria:
  - [ ] GIVEN `GET /v1/profile/conflicts?user_id=X&status=unresolved|all` AND flag `PROFILE_CONTRADICTION_DETECTION=true` THEN returns conflict rows with full diff context.
  - [ ] GIVEN the flag is off THEN 404.
  - [ ] GIVEN POST/PUT/DELETE on this path THEN 405 (resolution UX deferred to Epic 2).
- Edge Cases:
  - None substantive for read.

### Story 1.18: Profile.tsx refresh — depth, freshness, conflicts
- Status: drafted
- Assigned: unassigned
- Priority: P2
- Dependencies: 1.2, 1.7, 1.9, 1.10, 1.11, 1.15, 1.16, 1.17, 1.19
- Review Cycles: 0
- User Problem: New data (relationships, present-tense fields, freshness, conflicts, structured health_conditions, health.exercise) is invisible until the UI surfaces it. v2 removes the "additive tab only" constraint — redesign is allowed.
- API Contract Preserved: UI only; no backend contract touched. Frontend consumes existing endpoints plus `/v1/profile/history` and `/v1/profile/conflicts`.
- Acceptance Criteria:
  - [ ] GIVEN existing Profile.tsx category sections THEN each renders the updated shapes: `health.health_conditions` as structured condition cards, `health.exercise` as a new card, `relationships` as a named-person card list, new `personality` fields rendered with appropriate widgets.
  - [ ] GIVEN confidence metadata is available THEN each field displays a read-only confidence indicator.
  - [ ] GIVEN freshness data is available THEN each category header shows a freshness badge (green <30d, yellow 30-90d, red >90d).
  - [ ] GIVEN the user has open conflicts THEN a conflict count badge appears with a link to a modal/drawer listing them.
  - [ ] GIVEN a field of unknown shape arrives THEN the UI renders a generic key/value row, never crashes.
  - [ ] GIVEN the profile loads end-to-end THEN all frozen response keys (`user_id`, `profile`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `missing`, `last_updated`, `created_at`) are consumed as before; numeric `completeness_pct` may display a different number than pre-v2.
- Edge Cases:
  - Partial data: any subset of new fields may be present; render graceful empties.

### Story 1.19: Category re-assignment — exercise/fitness → `health.exercise`
- Status: drafted
- Assigned: unassigned
- Priority: P1
- Dependencies: 1.6
- Review Cycles: 0
- User Problem: Exercise/fitness lives under `interests.hobbies` ("barbell-based workouts"), where no consumer looking for health information would think to look. Categories aren't organized around user-intent queries; they're organized around whatever the LLM happened to emit first.
- API Contract Preserved: `/v1/profile` and `/v1/profile/{category}` retain all frozen top-level keys. `interests.hobbies` still exists (with exercise content removed); `health.exercise` is new. `completeness_pct` recomputes because `EXPECTED_PROFILE_FIELDS` gains `health.exercise`.
- Concrete moves:
  - `interests.hobbies` fitness items (vocabulary: `barbell`, `workout`, `gym`, `strength training`, `running`, `yoga`, `cardio`, `lifting`, `hiit`, `cycling`, `swimming`) → `health.exercise` (new dict: `{activities: [...], frequency: null, last_mentioned: <newest source ts>}`).
  - `preferences.sleep_schedule` → stays put (canonical home); doc-level cross-reference from health.
  - `health.dietary_needs` food favorites → `preferences.food_preferences` (handled by 1.13; referenced here for narrative completeness).
- Acceptance Criteria:
  - [ ] GIVEN a migration script AND each user's `interests.hobbies` value THEN items matching the documented fitness vocabulary list are extracted.
  - [ ] GIVEN extracted fitness items THEN they are written to `health.exercise` as `{activities: [...], frequency: null, last_mentioned: <latest source ts>}`; if `health.exercise` exists, activities merge without duplicates.
  - [ ] GIVEN the migration THEN `interests.hobbies` is rewritten with fitness items removed; if the resulting list is empty, the field is deleted.
  - [ ] GIVEN the migration THEN `EXPECTED_PROFILE_FIELDS['health']` includes `exercise`.
  - [ ] GIVEN the extraction prompt is updated THEN future extractions emit exercise content under `health.exercise`, not `interests.hobbies`; a prompt example makes this explicit.
  - [ ] GIVEN the migration runs THEN `profile_fields_history` records a `change_type='migration'` row for both source and destination rows.
  - [ ] GIVEN a manual PUT to `interests.hobbies` with a fitness-vocabulary value THEN the request is rejected with HTTP 400 and a message directing to `health.exercise`.
  - [ ] GIVEN `GET /v1/profile` AND `GET /v1/profile/health` post-migration THEN `health.exercise` appears with moved data; `interests.hobbies` appears without fitness items (or is absent if emptied); all frozen top-level response keys remain.
- Edge Cases:
  - Ambiguous item ("walking") — included in vocabulary list; rationale documented.
  - User with no fitness content in hobbies → migration no-ops.
  - Fitness item that's also social ("cycling with friends") → move to health anyway; `interests.social_preferences` captures social aspect separately.

## Team State
- Fenny: orchestrating
- Disha: Epic 1 v2 + 19 stories drafted; awaiting Parminder's v2 tech spec
- Parminder: rewriting tech spec for v2 in parallel
- David, Harpreet, Murat: on standby for implementation wave
