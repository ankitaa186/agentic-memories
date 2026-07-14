# Sprint Status — agentic-memories

Last Updated: 2026-07-13

## Active Epics
**Epic 1: Deep Profile — from resume to self-model** (drafted v2 by Disha, design-reviewed v1 by Parminder — parallel v2 tech-spec rewrite in flight) — on user-hold
**Epic 2: Observability** (opened 2026-04-25) — operational; parallel to Epic 1; doc at `.claude/scrum/docs/epic-2-observability.md`
**Epic 3: Health Domain Expansion** (opened 2026-05-18) — Wave A scoped (Stories 3.1, 3.2, 3.3); doc at `.scrum/docs/epic-3-health-domain-expansion.md`. Pending Parminder design review before stories transition to `ready`.

## Epic 1 Detail
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

## Epic 2 Backlog (Observability)

### Story 2.1: Wrap non-graph embedding entry points in Langfuse parent spans
- Status: in-progress
- Assigned: david
- Priority: P1
- Dependencies: none
- Review Cycles: 1
- User Problem: OpenAI embedding calls invoked outside `unified_ingestion_graph.run_unified_ingestion` show up in Langfuse as standalone top-level traces — one trace per embedding, with no parent context. The user can't tell which request, retrieval, compaction, or background job produced any given embedding observation. Net effect: the Langfuse view becomes high-noise and operationally useless for everything except the unified ingestion path.
- Diagnosis reference: Parminder, bus 2026-04-25 [22:25] and [22:05]. The `langfuse.openai` wrapper uses OTEL context propagation and auto-attaches to whatever Langfuse span is currently active. Only `unified_ingestion_graph.run_unified_ingestion` (line 1428) wraps work in `start_as_current_observation`. Every other embedding call site runs with no active span, so each embedding becomes its own root trace.
- Pattern to mirror: `src/services/unified_ingestion_graph.py:1428-1452` — `langfuse_client.start_as_current_observation(as_type="span", name=..., trace_context={...}, input=..., metadata={...}) as root_span: ...`. Span name should describe the entry point; `trace_context` carries `user_id` (and `session_id` where the call site has one); body of the wrapper is the existing handler logic; `root_span.update(output=...)` on success.
- Parminder review notes (2026-04-25):
  - **Open Q1 (compaction_graph 116/306): CONFIRMED** — both call sites are inside the same `run_compaction_graph` invocation. Line 116 is in `_cluster_memories` (called from `node_consolidate` at `compaction_graph.py:646`) and line 306 is in `_consolidate_cluster` (called from `node_consolidate` at `compaction_graph.py:664`). One parent span `compaction_run` covers both. NOTE: `run_compaction_graph` ALREADY calls `start_trace("compaction_job", ...)` at `compaction_graph.py:964` — the wrap target is the existing trace; rename it to `compaction_run` and ensure it actually closes (the existing code calls `trace.update(output=...)` at :993 but never `end_trace()` — that's a leak; this story now also fixes that by switching to a `with langfuse_client.start_as_current_observation(...)` context manager).
  - **Open Q2 (episodic_memory 119/236): CONFIRMED two distinct paths, but Disha's labels are SWAPPED.** Line 119 is inside `_store_in_chroma` (write path) → span name `episodic_store`. Line 236 is inside `_semantic_search` (read path) → span name `episodic_query`. ACs below are corrected.
  - **Reference correction — `forget.py:66` is dead code.** That line is inside `forget.simple_deduplicate` (line 45), which has no callers. The live forget entry is `forget.run_compaction_for_user` at `forget.py:101`, which delegates to `run_compaction_graph` and is therefore covered by the `compaction_run` span. The standalone `forget_memory` AC is dropped — there is no separate non-graph embedding path in `forget.py`.
  - **Reference correction — `compaction_ops.py:81` is in a docstring.** The actual `generate_embedding` call inside `compaction_ops.simple_deduplicate` is at line 137. The function is called only from `compaction_graph.py:557` (inside `node_dedup`), so it always runs nested inside `compaction_run`. There is no standalone `compaction_ops` entry point today, but the nested-detection guard is still required (in case a future caller invokes it directly). AC kept but reframed as a defensive guard.
  - **Reference correction — wrap target is the enclosing public method, not the literal `generate_embedding(...)` line.** For retrieval, that's `search_memories` (`retrieval.py:70`). For hybrid_retrieval, that's `retrieve_memories` (`hybrid_retrieval.py:97`). For episodic, that's `store_memory` (`episodic_memory.py:44`) and `_semantic_search` (`episodic_memory.py:225`). For emotional, that's `_store_in_chroma` (`emotional_memory.py:184`). David should wrap at the function entry, not at the embedding line.
  - **SDK correction — nested-detection mechanism.** The API to detect a currently-active span in `langfuse-python==3.14.2` is `langfuse_client.get_current_trace_id()` (returns `Optional[str]`, `None` when no span is active) — verified at `.venv/.../langfuse/_client/client.py:2328`. There is NO `get_current_span()` method. ACs updated.
  - **SDK note — sync only.** `start_as_current_observation` is a sync context manager. None of the wrap targets in this story are `async def` (`store_memory_direct` at `routers/memories.py:321` is sync `def`; all service methods are sync), so `with` (not `async with`) is correct everywhere. If any future caller is async, that's a separate story.
  - **Existing partial instrumentation stays.** `hybrid_retrieval.retrieve_memories` already calls `tracing.start_span(...)` at line 109; `compaction_graph.node_*` nodes also use `start_span` (lines 509, 550, 620, 776, 821). Both rely on `_current_root_span` being set via `start_trace(...)` first — and TODAY that root only exists in `unified_ingestion_graph` (and the half-broken `compaction_graph.run_compaction_graph` trace). Once the root span exists at the OUTERMOST entry points (added by this story), those nested `start_span` calls become real children. The only `start_span → start_as_current_observation` rewrite required is at `hybrid_retrieval.retrieve_memories:109` (because that one IS the outermost wrap for that entry point).
  - **Backward-compat for existing instrumentation.** The existing `unified_ingestion_graph.py:1428-1452` `start_as_current_observation` block must NOT be removed, modified, or renamed. New wraps follow the same shape but live in their own files. Encoded as an explicit AC below.
  - **Route path correction.** The direct-ingest endpoint is `POST /v1/memories/direct` (router prefix `/v1/memories` + route `/direct`), not `POST /v1/memories`. AC updated.
  - **`user_id` availability at every call site.** Verified — every wrap target has `user_id` directly available: `store_memory_direct(body)` has `body.user_id`; `search_memories(user_id, ...)`, `HybridRetrievalService.retrieve_memories(query)` (with `query.user_id`), `EpisodicMemoryService.store_memory(memory)` (with `memory.user_id`), `_semantic_search(self, user_id, ...)`, `EmotionalMemoryService._store_in_chroma(memory)` (with `memory.user_id`), `run_compaction_graph(user_id, ...)`. No fallback needed.
- API Contract Preserved: Not applicable — this is observability-only. No request/response shapes, no status codes, no headers, no behavior visible to API clients change. Wrapping must be transparent to all consumers; if tracing is unavailable (ImportError, Langfuse client failure) the underlying call still executes.
- Acceptance Criteria:
  - [ ] GIVEN a POST to `/v1/memories/direct` (direct ingest, handler `store_memory_direct` at `src/routers/memories.py:321`, embedding call at `:363`) WHEN the request is processed THEN the embedding observation in Langfuse is a child of a single parent span named `memory_create_direct` whose `trace_context` carries the request's `body.user_id`. The span starts at handler entry and closes after the response is built (or after exception unwind). The HTTP response shape is unchanged.
  - [ ] GIVEN a retrieval call through `search_memories` (`src/services/retrieval.py:70`, embedding at `:139`) WHEN it issues an embedding for a non-empty query THEN that observation is a child of a parent span named `retrieval` carrying the `user_id` (and `query` text — truncated to 200 chars — in metadata). When `query` is empty/whitespace (the metadata-only branch), no embedding is generated; wrap is still opened so the metadata-fetch latency is visible.
  - [ ] GIVEN a hybrid retrieval call through `HybridRetrievalService.retrieve_memories` (`src/services/hybrid_retrieval.py:97`, embedding at `:173`) WHEN it issues an embedding THEN that observation is a child of a parent span named `hybrid_retrieval` carrying the `user_id` and `query` metadata. NOTE: this method already calls `tracing.start_span(...)` at line 109 — rewrite that call to use `langfuse_client.start_as_current_observation(...)` directly (mirror the unified-graph pattern) so it works as a true root when no upstream trace exists.
  - [ ] GIVEN a compaction graph run through `run_compaction_graph` (`src/services/compaction_graph.py:944`) WHEN embeddings are issued by `_cluster_memories` (line 116) and `_consolidate_cluster` (line 306) THEN both are children of a single parent span named `compaction_run` covering the entire run; `user_id` is on `trace_context`. The existing `start_trace("compaction_job", ...)` at line 964 is rewritten in-place to use `with langfuse_client.start_as_current_observation(as_type="span", name="compaction_run", trace_context={...}, ...) as root_span:` wrapping `graph.compile().invoke(initial)` and updating `root_span` on exit. The current code's leak (no `end_trace()` call after `trace.update(...)` at :993) is fixed as part of this AC.
  - [ ] GIVEN a compaction-ops call through `compaction_ops.simple_deduplicate` (`src/services/compaction_ops.py:74`, embedding at `:137`) WHEN invoked AND a parent span is already active (i.e., `langfuse_client.get_current_trace_id() is not None`) THEN the function does NOT open a new span and lets the embedding nest under the existing parent. WHEN invoked with no active parent (defensive — no live caller does this today, but `simple_deduplicate` is module-level public and could be called directly), it opens a parent span named `compaction_ops`. Same defensive guard applies to `compaction_ops.deduplicate_episodic` (`:216`) and `compaction_ops.deduplicate_emotional` (`:291`) which take the same call path.
  - [ ] GIVEN an episodic-memory write through `EpisodicMemoryService.store_memory` (`src/services/episodic_memory.py:44`, embedding at `:119` inside `_store_in_chroma`) WHEN invoked AND no parent span is active THEN that observation is a child of a parent span named `episodic_store` carrying the `memory.user_id` and `memory.id`. WHEN invoked from inside the unified ingestion graph (`unified_ingestion_graph.py:834`), the nested-detection guard skips wrapping and the embedding nests under `unified_memory_ingestion`.
  - [ ] GIVEN an episodic-memory read through `EpisodicMemoryService.retrieve_memories` → `_semantic_search` (`src/services/episodic_memory.py:225`, embedding at `:236`) WHEN invoked AND no parent span is active THEN that observation is a child of a parent span named `episodic_query` carrying the `user_id`. Same nested-detection guard as above.
  - [ ] GIVEN an emotional-memory write through `EmotionalMemoryService._store_in_chroma` (`src/services/emotional_memory.py:184`, embedding at `:196`) WHEN invoked AND no parent span is active THEN that observation is a child of a parent span named `emotional_store` carrying the `memory.user_id`. Same nested-detection guard. (NOTE: Disha's original AC named this `emotional_query`, but the call site at line 196 is in `_store_in_chroma` — write path. There is no separate read-path embedding in `emotional_memory.py`; semantic emotional search runs through `hybrid_retrieval`. Renamed to `emotional_store`.)
  - [ ] GIVEN any of the wrapped entry points completes successfully THEN the parent span is closed with `output={...}` containing at minimum a result-shape summary (count of items returned, ids written — whatever the call site already logs).
  - [ ] GIVEN any of the wrapped entry points raises THEN the parent span closes cleanly with the exception recorded (level=ERROR, status_message set); the original exception propagates unchanged to the caller; no orphan/open spans remain.
  - [ ] GIVEN Langfuse is unavailable (`is_langfuse_enabled()` returns false, ImportError on `langfuse`, client init failure, or runtime error inside the wrapper) THEN the wrapped function still executes and returns its normal result; the failure is logged at `warning` level (mirror the fallback pattern at `unified_ingestion_graph.py:1468-1480`).
  - [ ] GIVEN the existing `unified_ingestion_graph.py:1428-1452` `start_as_current_observation` block THEN it is NOT modified, NOT removed, and NOT renamed by this story. It remains the canonical reference pattern and the root span for `/v1/store` requests. Any consolidation of the two-Langfuse-clients smell (singleton vs in-graph instantiation) is a separate story.
  - [ ] GIVEN a Langfuse session covering one direct ingest + one retrieval + one compaction run THEN the Langfuse UI shows three top-level traces (`memory_create_direct`, `retrieval`, `compaction_run`) and zero unparented `OpenAI-embedding` observations.
- Edge Cases:
  - **Sync only — no async wrap targets in scope.** All wrap targets in this story are sync `def`. `start_as_current_observation` is a sync context manager. Use `with`, not `async with`. If a future async caller appears, it gets its own story.
  - **Exception propagation.** The span MUST close on exceptions (`__exit__` semantics) and the original exception MUST propagate unchanged — no re-wrapping, no swallowing. Murat will assert this with a call site that raises.
  - **Nested calls — do NOT double-wrap.** Detection mechanism: `langfuse_client.get_current_trace_id() is not None` (verified API for `langfuse-python==3.14.2`). When already inside a parent (`unified_memory_ingestion`, `compaction_run`, etc.), the new wrappers skip opening a child root and let the embedding nest under the existing OTEL context. This matters for `episodic_store`/`episodic_query`/`emotional_store` (called from inside `unified_ingestion_graph`) and `compaction_ops` (callable from inside `compaction_run`).
  - **`/v1/memories/direct` interplay with the unified graph.** This story wraps the *direct* POST handler only. The `/v1/store` path through `unified_ingestion_graph` is already wrapped at `unified_ingestion_graph.py:1428-1452` — do NOT touch it (see backward-compat AC above).
  - **Per-process Langfuse client lifecycle.** All entry points should reuse the same singleton `get_langfuse_client()` from `src/dependencies/langfuse_client.py:18`. Do NOT instantiate fresh `Langfuse(...)` clients per call. NOTE: `unified_ingestion_graph.py:1402` currently instantiates a second client — that's a known smell flagged in Parminder's memory but out of scope for this story.
  - **Span output payload.** Keep `output` summaries small (counts, ids, latency) — do not dump full embedding vectors or full retrieval result bodies into the span output.
  - **`trace_context` keys.** Mirror the unified-graph shape: `{trace_id, user_id, session_id?}`. `trace_id` is generated via `langfuse_client.create_trace_id()` at the wrap site. If a call site has no natural `session_id`, omit it rather than fabricate one.
  - **Existing nested `start_span` usage stays.** `hybrid_retrieval.retrieve_memories` (line 109), `compaction_graph.node_ttl/node_dedup/node_consolidate/node_load/node_reextract/node_apply` (lines 509, 550, 620, 776, 821, etc.) all call `tracing.start_span(...)` for nested spans. Once the root span exists (added by this story for the outermost entry points), those nested spans become real children. Only the OUTERMOST wrap is new work.
  - **Test surface for Murat.** The "zero unparented embedding observations" AC needs a way to assert programmatically — mock the `Langfuse` client and inspect the captured span tree, OR query Langfuse via SDK after a synthetic run. Implementation choice is David's; Murat should be able to write one integration-level test per entry point asserting (a) parent span exists with expected name, (b) embedding observation is a child of it, (c) on exception the span closes with `level=ERROR` and the exception still propagates.

### Story 2.2: Narrow exception handling in `_call_llm_json` retry loop to avoid silent duplicate LLM calls
- Status: ready
- Assigned: unassigned
- Priority: P1
- Dependencies: none
- Review Cycles: 1
- User Problem: Every LLM-backed pipeline in this system — worthiness gating, extraction, sentiment, profile_extraction, graph_extraction, compaction, reconstruction, and the `app.py:1476` call site — routes through a single helper, `_call_llm_json` in `src/services/extract_utils.py`. That helper's retry loop catches `except Exception` and continues, which means *any* error — a transient network blip, an `IndexError` on an empty `choices` list, a JSON-decode hiccup, even a bug in `_parse_json_from_text` — silently triggers a brand-new SDK call. Each retry doubles latency and doubles cost. The user-visible symptom that surfaced this (two back-to-back ~3s `OpenAI-generation` observations on a single worthiness check) was the smallest, cheapest call in the system; the same defect is silently inflating spend across every non-worthy ingestion path and every JSON-parse hiccup anywhere in the stack. Fix narrows the inner except clause so only genuinely-retryable errors (timeouts, connection drops, 5xx, rate-limits) trigger a retry. Expected outcome: a measurable drop in overall LLM spend and disappearance of mystery duplicate observations across all pipelines, not just worthiness.
- Diagnosis reference: Parminder, bus 2026-04-25 [22:55]. Root cause is `extract_utils.py:117-146` (OpenAI branch) and `:164-193` (xAI branch). `EXTRACTION_RETRIES` defaults to 1 (`config.py:191-196`), so today the loop runs up to 2 attempts on any exception. Auto-generated `OpenAI-generation` observation name confirms both calls came from the SDK wrapper, not deliberate code paths.
- Parminder review notes (2026-04-25):
  - **Verified exception classes against `openai==1.40.0` (uv.lock).** Read `.venv/.../openai/_exceptions.py`. All six classes Disha named exist in the right module paths: `openai.APIConnectionError`, `openai.APITimeoutError` (which is a subclass of `APIConnectionError`), `openai.RateLimitError`, `openai.InternalServerError` are exported from `openai`. `httpx.TimeoutException` and `httpx.ConnectError` are exported from `httpx`. The narrow tuple compiles and behaves as Disha specified.
  - **`openai-python` wraps `httpx` errors.** In normal `chat.completions.create` flow, raw `httpx.TimeoutException` / `httpx.ConnectError` get wrapped into `openai.APITimeoutError` / `openai.APIConnectionError` before they exit the SDK. So listing the `httpx.*` parents in the narrow tuple is technically redundant for the happy SDK path, but it's defensive (e.g., if a future SDK regression leaks a raw httpx error, or if the request interceptor / custom http_client raises pre-wrap, we still retry rather than crashing). Keep the `httpx.*` entries — cost is one tuple element, value is non-zero.
  - **Did NOT add `openai.UnprocessableEntityError` (422).** That's a non-retryable client error (we sent a malformed payload). Retrying it just burns another call.
  - **Did NOT add `openai.APIError`** (the base class). That would re-introduce the broad-except problem — `APIError` covers `BadRequestError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `UnprocessableEntityError`, all of which are deterministic client errors that retry won't fix.
  - **xAI uses the `openai`-compatible client.** `extract_utils.py:163` constructs `OpenAI(api_key=..., base_url=get_xai_base_url())`, same SDK, same exception classes. Identical narrow tuple is correct.
  - **CRITICAL CORRECTION — non-retryable errors do NOT propagate to callers.** Disha's framing (Edge Cases line 1, AC line 5, Test Plan case 1) said "after the fix they propagate." That's wrong. There is a **second** `try/except Exception` at `extract_utils.py:97-220` that wraps the entire function body, logs a full traceback via `logger.exception(...)`, calls `trace_error(...)`, and **returns `None`**. The narrow inner-except change only fixes the retry-loop double-call bug; it does NOT change the function's external return contract. Non-retryable errors that reach the loop body now SKIP the inner except (no second SDK call — the bug fix), propagate out of the `for` loop, and get caught by the outer except → return `None`. AC, Test Plan, and Edge Cases corrected below.
  - **Caller-tolerance audit (re-done after correction above).** Because the outer except still swallows, no caller needs to change behavior. For the record, here is what each caller does today and continues to do after this fix:
    - `unified_ingestion_graph.py:155, :200` (worthiness, extract): `resp or default` pattern — handles `None` cleanly. No change needed.
    - `unified_ingestion_graph.py:1255` (sentiment, via `_analyze_sentiment_llm`): wrapped in try/except locally — handles `None` cleanly.
    - `profile_extraction.py:325`: wrapped in try/except locally — handles `None` cleanly.
    - `graph_extraction.py:29, :61`: same `resp or default` pattern.
    - `compaction_graph.py:259`: wrapped in try, checks `if not response: return {...}`.
    - `reconstruction.py:153`: type-checks `if not isinstance(resp, dict): resp = {default}`.
    - `app.py:1476`: type-checks `if not isinstance(resp, dict): resp = {}`.
    - Verdict: no caller is fragile to `None` return; the only thing changing for callers is they get `None` *faster* (one SDK call instead of two on non-retryable errors) and with better diagnostics (warning log on retries; outer `logger.exception` already gives traceback on swallowed errors).
  - **No companion story needed.** This story stays single, scoped to `extract_utils.py`. The outer except is also a smell (silent-return-None is a debugging-debt pattern) but tightening it would force every caller to grow new error handling — that's a separate, larger refactor and is NOT this story's bug.
  - **Smell flagged for the future, NOT this story:** the outer `except Exception → return None` swallow at `extract_utils.py:200-220` is the second silent-failure layer. It IS useful for traceback logging + Langfuse `trace_error` breadcrumb today, but the "return None on any unexpected failure" contract makes pipeline failures invisible. Reconsider once Story 2.1 lands and we can see error spans natively in Langfuse — at that point the outer except's value drops and we may want to let exceptions propagate. Track as a future Epic 2 candidate, NOT a blocker for 2.2.
  - **Worthiness/extraction node behavior on the bug-fix path.** Today, when worthiness throws an `IndexError`, the outer except catches → returns `None` → `bool(None and None.get("worthy"))` → `worthy=False` → ingestion short-circuits. After the fix, EXACT same behavior — the outer except still swallows. The only delta is the second SDK call disappears. So the worthiness node will continue to silently mark unworthy on parse failures (which is itself a smell — a parse failure isn't the same signal as "user says hi"), but that's pre-existing and not in scope for 2.2.
- API Contract Preserved: Not applicable — this is a change to an internal helper. The function signature of `_call_llm_json` is unchanged. The return contract (parsed JSON object/list on success, `None` default on exhausted retries OR on any unexpected error caught by the outer except — whatever the helper returns today) is unchanged. `EXTRACTION_RETRIES` semantics are unchanged. No HTTP route, request shape, or response shape is touched. Stating explicitly: there is no API surface to preserve; the contract being preserved is the *internal* one between the helper and its callers.
- Acceptance Criteria:
  - [ ] GIVEN `src/services/extract_utils.py:117-146` (OpenAI branch) WHEN the retry loop catches an exception THEN the inner `except Exception` clause is replaced with a narrow tuple: `(httpx.TimeoutException, httpx.ConnectError, openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError)`. (Note: `APITimeoutError` is a subclass of `APIConnectionError` per `openai==1.40.0`; listed explicitly for readability/intent.)
  - [ ] GIVEN `src/services/extract_utils.py:164-193` (xAI branch) WHEN the retry loop catches an exception THEN it uses the IDENTICAL narrow tuple as the OpenAI branch (do not drift between provider branches).
  - [ ] GIVEN any retryable exception is caught in either branch WHEN the loop continues THEN a `logger.warning(...)` is emitted inside the except, named identically across both branches (e.g. `_call_llm_json` retry warning with provider, attempt number, and exception class), so future incidents surface in our own logs without requiring a Langfuse round-trip.
  - [ ] GIVEN the function signature of `_call_llm_json` and its return contract THEN both are unchanged. `EXTRACTION_RETRIES` continues to mean "additional attempts after the first" with default 1 (i.e. up to 2 total calls). The outer `try/except Exception` block at `extract_utils.py:200-220` (which logs a traceback, calls `trace_error`, and returns `None`) is NOT modified by this story.
  - [ ] GIVEN a non-retryable error inside the LLM call path (e.g. `IndexError` on `response.choices[0]`, `KeyError`, JSON-decode error from `_parse_json_from_text`, prompt-validation `ValueError`) WHEN it is raised THEN it skips the inner `except` (no second SDK call — this IS the bug fix), propagates out of the `for` loop, gets caught by the outer `except Exception`, is logged via `logger.exception(...)` with traceback, sent through `trace_error(...)`, and the function returns `None` — i.e. EXACTLY today's external return contract, but with one LLM call instead of two.
  - [ ] GIVEN the helper change is purely internal AND no caller signature/return-handling changes are needed THEN a grep of every caller confirms no call-site edits are required: verified callers are `unified_ingestion_graph.py:155, :200, :1255` (worthiness, extract, sentiment), `profile_extraction.py:325`, `graph_extraction.py:29, :61`, `compaction_graph.py:259`, `reconstruction.py:153`, `app.py:1476`. (Per Parminder's caller-tolerance audit above, every caller already handles `None` gracefully — the bug fix preserves that path; no caller-side edits are needed in this story.)
- Test Plan:
  1. **Non-retryable error → exactly one call, returns None.** Monkeypatch `client.chat.completions.create` to raise `IndexError("simulated parse error")`. Wrap the patched function in a call counter. Invoke `_call_llm_json`. Assert (a) the helper returns `None` (the outer except's contract), (b) **exactly one** SDK call was made (no silent retry — this is the bug being fixed), (c) `logger.exception(...)` was called once with the IndexError traceback, (d) `trace_error(...)` was called once.
  2. **Single retryable error → success after exactly two calls.** Monkeypatch `client.chat.completions.create` to raise `openai.APITimeoutError` on first invocation, then return a valid response on the second. Wrap in a call counter. Invoke `_call_llm_json`. Assert the helper returns the parsed JSON AFTER **exactly two** SDK calls. `logger.warning(...)` should have been emitted once with `{provider, attempt=1, total_attempts=2, exception_class="APITimeoutError"}`.
  3. **Persistent retryable error → returns None after exactly two calls.** Same as (2) but raise `openai.APITimeoutError` on BOTH attempts. Assert the helper returns `None` AFTER exactly two SDK calls; no third call is made. `logger.warning` emitted twice. The outer except catches the re-raised `last_exc` and returns `None`.
  4. **Retries disabled → exactly one call regardless of retryability.** Set `EXTRACTION_RETRIES=0`. Monkeypatch the SDK call to raise `openai.APITimeoutError`. Assert the helper returns `None` AFTER exactly one SDK call (no retry attempt because retries are off). `logger.warning` emitted once.
  5. **Mixed-class regression — non-retryable openai error short-circuits.** Monkeypatch `client.chat.completions.create` to raise `openai.BadRequestError` (a 4xx, NOT in the narrow tuple, NOT a base-class `APIError` masquerade). Assert exactly one SDK call, return value `None`, `logger.exception` traceback present, `logger.warning` (the retry log) NOT emitted. Confirms we don't accidentally retry on client errors.
  - Test cases (1)-(5) MUST be parameterized over both provider branches (OpenAI and xAI) — running only against one branch is insufficient because the whole point of the AC is that the two branches stay in lockstep.
- Edge Cases:
  - **No external behavior change for callers.** The retry-loop fix is internal: same return value (`None` on any failure, parsed JSON on success), same outer error logging. The ONLY observable differences are (a) one SDK call instead of two on non-retryable errors (the bug fix), (b) a new `logger.warning(...)` line on retries, (c) measurable LLM cost/latency drop in production. **Caller-tolerance audit done at review (see Parminder review notes above) — every caller already handles `None` gracefully; no caller-side edits are needed.** This corrects Disha's draft Edge Case which claimed errors would propagate to callers — they don't, because the outer `except Exception → return None` block at `extract_utils.py:200-220` is unchanged.
  - **xAI branch parity is non-negotiable.** The two provider branches share semantic responsibility; if they drift, future incidents in xAI go invisible because everyone debugs the OpenAI branch first. Tests run against both branches (see Test Plan).
  - **Don't accidentally narrow too far.** `httpx.ReadTimeout` and `httpx.WriteTimeout` are subclasses of `httpx.TimeoutException`, so listing the parent class covers them. Verify this assumption holds in the version of `httpx` we ship — if a future bump changes the hierarchy, the narrow tuple may need to grow. Note in PR description.
  - **`httpx.*` entries are belt-and-suspenders.** `openai-python` normally wraps raw httpx errors into `openai.APIConnectionError` / `openai.APITimeoutError` before they exit the SDK, so the `httpx.*` entries in the narrow tuple are mostly defensive. Keep them — they cover the case where a future SDK regression leaks a raw httpx error or where a custom http_client raises pre-wrap.
  - **`openai.RateLimitError` is retryable as a class but may need backoff.** Today the loop has no backoff; `EXTRACTION_RETRIES=1` means at most one immediate retry. Including `RateLimitError` in the narrow tuple preserves today's behavior (immediate single retry on a rate limit). If we later want exponential backoff on rate limits, that's a follow-up story — DO NOT scope-creep it into this fix.
  - **Logger naming and structured fields.** The `logger.warning(...)` should include at least `{provider, attempt, total_attempts, exception_class}` so future grep/aggregation works without needing the trace context. Do not embed the prompt or response in the warning (PII / log volume).
  - **Do NOT add `APIError` or `UnprocessableEntityError` to the tuple.** `APIError` is the base class for ALL openai-emitted errors (including 4xx client errors); catching it re-introduces the broad-except problem. `UnprocessableEntityError` (422) is a deterministic client error — retry won't fix it.
  - **Imports at top of file.** `extract_utils.py` currently does NOT import `openai` or `httpx` at module scope (the `openai` import is local inside `_call_llm_json` for the Langfuse-vs-vanilla branch selection at lines 110-114, 157-161). David must add `import httpx` and `import openai` at the top of the file (or do narrow imports in the except clause if he prefers), so the narrow tuple is in scope. Note: `openai` is always available as a transitive dep — we can import it unconditionally even when `is_langfuse_enabled()` is false.

## Epic 3 Detail
Goal: Evolve the health domain from a 7-field gift-helper into a structured self-model of the body — quantitative time-series (`health_metrics` hypertable), bounded episodes with lifecycle (`health_episodes` hypertable), and ~25-field health profile depth, all fed by conversational ingest.
Constraint: API backward-compat on existing `/v1/profile*` endpoints; new endpoints under `/v1/health/*` are net-additive. Same fence as Epic 1 v2.
Full epic doc: `.claude/scrum/docs/epic-3-health-domain-expansion.md`
Wave A scope: Stories 3.1 (profile expansion, no DDL), 3.2 (`health_metrics` hypertable + new extraction kind), 3.3 (`health_episodes` hypertable + start/update/close lifecycle). Linear sequencing — each story unblocks the next.
Cross-cutting decisions (per epic doc): D1 single LLM call w/ multiple output kinds; D2 upfront opt-in for sensitive fields; D3 unit normalization at ingest; D4 per-kind confidence thresholds (profile 80, metric 70, episode 75); D5 idempotency via unique index on metrics + explicit action verb on episodes; D6 no backfill in Wave A; D7 all DDL via migrate scripts.
Sensitive-field surface (Story 3.1 plumbing reused by 3.3): `mental_health_history`, `surgical_history`, `hospitalizations`, `substances_baseline`, `reproductive_status`, `gender_identity` (profile, 3.1); `mental_health_episode` type (episodes, 3.3). All gated by `user_profiles.health_sensitive_opt_in`.
New migrations introduced: `migrations/postgres/025_user_profiles_sensitive_opt_in.up.sql` (3.1), `migrations/timescaledb/004_health_metrics.up.sql` (3.2), `migrations/timescaledb/005_health_episodes.up.sql` (3.3).
Waves B and C are listed in the epic doc for context but NOT drafted — they earn their own epic-level review once Wave A lands.
Pending: Parminder design review of Wave A schemas (specifically the metric catalog in 3.2 and the open-episode partial-index strategy in 3.3) before stories transition from `drafted` to `ready`.

## Epic 3 Backlog (Wave A)

### Story 3.1: Health profile expansion (7 → ~25 structured fields)
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: none
- Review Cycles: 0
- User Problem: The current `health` category captures 7 flat fields, mostly for gifting and dietary safety. Anyone asking "who is my doctor, when was my last physical, what are my immunizations, what's my family medical history" gets nothing. The bar for a usable health profile in 2026 is dozens of fields, not seven.
- API Contract Preserved: `/v1/profile` and `/v1/profile/health` retain all frozen top-level keys. New fields appear under `profile.health` (existing category). `completeness_pct` numeric value will shift because denominator grows; key itself unchanged. New endpoints `POST/GET /v1/profile/health/sensitive_opt_in` are net-additive.
- Tier 1 fields (16 new, count toward completeness): `blood_type`, `height_cm`, `weight_baseline_kg`, `biological_sex`, `primary_care_provider`, `specialists`, `insurance`, `immunizations`, `last_physical_date`, `dental_care_last`, `eye_care_last`, `fitness_baseline`, `sleep_baseline`, `devices`, `family_medical_history_summary`, plus inherited from Epic 1 (`health.exercise` from 1.19, restructured `health_conditions` from 1.15).
- Tier 2 fields (6, sensitive, opt-in only, NOT counted toward completeness): `mental_health_history`, `surgical_history`, `hospitalizations`, `substances_baseline`, `reproductive_status`, `gender_identity`.
- Acceptance Criteria:
  - [ ] GIVEN `src/services/profile_storage.py:20` WHEN `EXPECTED_PROFILE_FIELDS["health"]` is updated THEN it contains exactly the Tier 1 catalog (16 new fields plus 7 existing). Tier 2 fields are NOT in `EXPECTED_PROFILE_FIELDS`.
  - [ ] GIVEN `src/services/profile_extraction.py` WHEN the prompt is regenerated THEN the `**health**` section enumerates the full Tier 1 catalog with type hints AND includes ≥6 worked examples (provider, immunization-with-date, family history, sensitive-when-opted-out, sensitive-when-opted-in, height/weight numeric).
  - [ ] GIVEN migration `025_user_profiles_sensitive_opt_in.up.sql` THEN `user_profiles` gains nullable `health_sensitive_opt_in BOOLEAN DEFAULT FALSE`; matching `.down.sql` drops the column.
  - [ ] GIVEN module-level `SENSITIVE_HEALTH_FIELDS` constant (single source of truth) listing the 6 Tier 2 field names THEN `store_profile_extractions()` checks the user's `health_sensitive_opt_in` and silently drops Tier 2 extractions (logged at debug with `extraction_skipped_reason="sensitive_opt_out"`) when false.
  - [ ] GIVEN `POST /v1/profile/health/sensitive_opt_in {user_id, opt_in: bool}` THEN it upserts the flag and returns the new value; matching `GET` returns current value.
  - [ ] GIVEN shape validators THEN `POST /v1/profile/field` rejects malformed values with HTTP 400 and a field-specific error: invalid `blood_type` enum, non-numeric `height_cm`, malformed date in `last_physical_date`, malformed object shape in `primary_care_provider`.
  - [ ] GIVEN `scripts/recompute_completeness.py` THEN running it refreshes `completeness_pct`/`total_fields`/`populated_fields` for every `user_profiles` row against the new baseline; existing users' completeness values WILL change, documented in PR description.
  - [ ] GIVEN extraction emits a Tier 1 health field with confidence ≥80 THEN it persists to `profile_fields`; below threshold → logged to new `extraction_review_log` table (additive — created by this story) for offline eval, not persisted.
  - [ ] GIVEN `GET /v1/profile/health` after a Tier 1 extraction lands THEN the new field appears under `fields`; all frozen top-level response keys remain.
- Edge Cases:
  - Existing `medications` stays as flat array of strings in Wave A; restructured in Story 3.5. Validators accept flat-array shape.
  - LLM emits Tier 2 field while opted-out → drop silently at debug. Do NOT 4xx; the field name shouldn't leak via error messages per-utterance.
  - LLM emits structured object with extra keys (e.g., `primary_care_provider: {..., fax}`) → open schema accepts additional keys but doesn't use them in completeness math.
  - `family_medical_history_summary` is freeform text; flag in prompt comment as deprecated-by-3.6 so no consumer treats it as canonical.
  - Sequencing with Epic 1 stories 1.15 and 1.19 (both touch `health.*`): if Epic 1 lands first, 3.1 inherits as-is; if 3.1 lands first, no further field-catalog change needed in Epic 1. Decided at sprint planning.

### Story 3.2: Biometric time-series hypertable (`health_metrics`)
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: 3.1
- Review Cycles: 0
- User Problem: Quantitative health signals (weight, BP, HR, sleep, glucose, mood-1-to-10) have nowhere to live. The user says "I weighed 168 today" and the system either drops it, persists it as one-off episodic prose, or stuffs a single point into a profile field that overwrites on next mention. None of those forms support trend queries, anomaly detection, or correlation with episodes.
- API Contract Preserved: Net-additive endpoints under `/v1/health/metric*`. No `/v1/profile*` change. No existing TimescaleDB hypertable touched.
- Schema: New hypertable `health_metrics(id, user_id, ts, metric, value_numeric, value_text, unit, source, confidence, source_memory_id, metadata, created_at)`. Hypertable on `ts`. Unique index `(user_id, ts, metric, source)`. Partial index on `(user_id, metric, ts DESC)`. Check constraints on confidence range and value presence. Chunk interval 7d. Compression after 30d, segmentby `(user_id, metric)`.
- Metric catalog (v1, ~24 metrics): `weight` (kg), `body_fat_pct` (%), `bp_systolic`/`bp_diastolic` (mmHg, paired via `metadata.correlation_id`), `hr_resting`/`hr_walking` (bpm), `hrv_sdnn_ms` (ms), `vo2max` (ml/kg/min), `body_temp` (°C), `spo2` (%), `glucose` (mg/dL), `sleep_duration` (h), `sleep_efficiency` (%), `sleep_deep`/`sleep_rem` (min), `steps` (count), `exercise_minutes` (min), `active_kcal` (kcal), `water_ml` (ml), `caffeine_mg` (mg), `mood_self`/`stress_self`/`energy_self` (scale_1_10), `pain_self` (scale_0_10 + location in metadata).
- Acceptance Criteria:
  - [ ] GIVEN migration `004_health_metrics.up.sql` + `.down.sql` THEN they apply cleanly through `migrate.sh`; up creates hypertable + indexes + constraints + chunk interval + compression policy; down drops the table.
  - [ ] GIVEN `src/services/health_metrics.py` THEN it exposes `HealthMetricsService` with `record_metric()`, `record_batch()`, `query_range()`, `latest()`, `trend_summary()`.
  - [ ] GIVEN `ALLOWED_METRICS` constant (single source of truth) THEN `record_metric()` rejects (HTTP 400) on (a) unknown metric, (b) unit mismatch with canonical, (c) value outside documented sanity range (e.g., `weight` > 500kg, `bp_systolic` < 50 or > 280).
  - [ ] GIVEN repeat insertion of same `(user_id, ts, metric, source)` THEN the row is UPDATEd via the unique index (UPSERT), not duplicated.
  - [ ] GIVEN new router `src/routers/health.py` registered in `src/app.py` THEN it exposes `POST /v1/health/metric`, `POST /v1/health/metrics/batch` (≤1000 rows), `GET /v1/health/metric?user_id=&metric=&start=&end=&agg=` (raw/daily_avg/daily_min/daily_max/weekly_avg), `GET /v1/health/metric/latest?user_id=&metric=`.
  - [ ] GIVEN LLM extraction prompt is extended THEN it emits new top-level array `health_metrics: [{metric, value, unit, ts?, confidence, source_memory_id}, ...]` for quantitative utterances; ≥12 worked examples covering numeric + unit-converted + self-rated + paired-BP.
  - [ ] GIVEN unit-conversion prompt rule THEN LLM converts to canonical unit at extraction (lb→kg, °F→°C, oz→ml); the service-layer unit validator catches mis-conversions and routes to `extraction_review_log`.
  - [ ] GIVEN `run_unified_ingestion()` THEN after profile extraction the new `health_metrics` extractions are dispatched to `record_batch()`; per-row failures log + skip without aborting the ingestion run.
  - [ ] GIVEN `record_metric()` for `weight` or `height` THEN a downstream hook refreshes `weight_baseline_kg` / `height_cm` on `profile_fields` to the latest point. One-way sync: metrics → profile baseline (never reverse).
  - [ ] GIVEN paired BP "BP was 122/78" THEN extraction emits TWO rows (`bp_systolic`, `bp_diastolic`) with identical `ts` AND identical `metadata.correlation_id` (UUID). Canonical pattern for future paired metrics.
  - [ ] GIVEN extraction confidence < 70 THEN it is NOT persisted; appended to `extraction_review_log` for offline eval.
  - [ ] GIVEN no parent Langfuse span is active AND `record_batch()` writes THEN upstream extraction observations remain correctly nested under the existing `unified_memory_ingestion` root span (Epic 2 invariant — do NOT regress).
  - [ ] GIVEN integration tests THEN they cover roundtrip insert/query, idempotency, unit-validator rejection, paired-BP correlation_id, lb→kg / oz→ml / °F→°C conversion, low-confidence routing to review log, GET range queries with each `agg` value, sensitive opt-out interaction (none of v1 metrics are sensitive — confirm no Tier 2 metric leaks).
- Edge Cases:
  - "I weighed 168" with no unit → LLM assumes lb in 80-400 range, kg in 35-200 range, lb in 80-200 overlap (US default); documented in prompt and tested.
  - "I slept 6 hours last night" → `ts` is morning-of-mention's 06:00 local time; documented in prompt.
  - "Heart rate is normally around 60" → narrative baseline, routes to `fitness_baseline.resting_hr` on profile, NOT to `health_metrics`. Prompt example covers this.
  - "Feeling pretty energetic" → no number, no `health_metric`. "Energy is like 7 out of 10" → `energy_self=7`.
  - Backfill from historical memories is OUT of scope (Decision D6).
  - `metric` column is free-form TEXT — adding metrics is a constant + prompt update, no DB migration. Trade-off accepted.

### Story 3.3: Symptom & episode logs (`health_episodes`)
- Status: drafted
- Assigned: unassigned
- Priority: P0
- Dependencies: 3.2
- Review Cycles: 0
- User Problem: Symptoms are events with onset, severity, location, duration, triggers, relief, resolution. Today they disappear or land in `episodic_memories` as unstructured prose. No way to answer "how often do I get headaches," "what triggers my back flares," "have I had this stomach pain before." Pre-doctor-visit summary "here's what I've experienced" is impossible.
- API Contract Preserved: Net-additive endpoints under `/v1/health/episode*`. No `/v1/profile*` or existing `/v1/health/metric*` change. No existing hypertable touched.
- Schema: New hypertable `health_episodes(id, user_id, started_at, ended_at, episode_type, subtype, severity_max, severity_current, body_location[], triggers[], relief_attempts JSONB, related_metric_ids[], source_memory_ids[], notes, metadata, created_at, updated_at)`. Hypertable on `started_at`. Partial index `WHERE ended_at IS NULL` for open-episode reconciliation. Check constraints on severity ranges and time order. Chunk 30d. Compression after 90d, segmentby `user_id`.
- Episode types (locked enum): `symptom`, `illness`, `injury`, `allergic_reaction`, `chronic_flare`, `mental_health_episode` (gated by `health_sensitive_opt_in`). Subtypes are free-form text normalized in app code via `SUBTYPE_NORMALIZATION` lookup.
- Acceptance Criteria:
  - [ ] GIVEN migration `005_health_episodes.up.sql` + `.down.sql` THEN they apply cleanly; up creates hypertable + partial index on open episodes + check constraints + chunk + compression; down drops the table.
  - [ ] GIVEN `src/services/health_episodes.py` THEN it exposes `HealthEpisodesService` with `start_episode()`, `update_episode()`, `close_episode()`, `find_open_episode()`, `list_episodes()`, `pattern_summary()`.
  - [ ] GIVEN `find_open_episode()` THEN it uses the partial index `idx_health_episodes_open` and returns most recent open episode for `(user_id, episode_type, subtype)` within `window_hours`. Defaults: 72h symptom, 14d chronic_flare, 48h allergic_reaction, 30d illness, 30d injury. Encoded in `WINDOW_DEFAULTS` constant.
  - [ ] GIVEN `update_episode()` THEN it appends to `source_memory_ids[]`, updates `severity_current`, bumps `severity_max` if exceeded, merges `body_location[]`/`triggers[]` de-duplicated, appends to `relief_attempts[]` JSONB, sets `updated_at`.
  - [ ] GIVEN `close_episode()` THEN it sets `ended_at` and `updated_at`; partial index reflects closure immediately (test asserts `find_open_episode()` no longer returns it).
  - [ ] GIVEN extended router THEN it exposes `POST /v1/health/episode`, `PATCH /v1/health/episode/{id}`, `GET /v1/health/episode?user_id=&status=open|closed|all&type=&since=&limit=`, `GET /v1/health/episode/patterns?user_id=&type=&subtype=&lookback_days=`.
  - [ ] GIVEN LLM extraction prompt is extended THEN it emits `health_episode_events: [{action: "start"|"update"|"close"|"none", episode_id?, episode_type, subtype, severity?, severity_current?, body_location?, triggers?, relief_attempt?, ended_at?, source_memory_id}, ...]`; ≥10 worked examples (start, update-severity, close, relief, ambiguous-skip, metaphor-skip, mental_health while opted-out, multi-open disambig).
  - [ ] GIVEN dispatch from `run_unified_ingestion()` THEN: `action=start` → `start_episode()`; `action=update|close` with explicit `episode_id` → operate on that ID (404 → log + skip); `action=update|close` without episode_id → `find_open_episode()` first, then operate (none found → log + skip, do not auto-create); `action=none` → no-op.
  - [ ] GIVEN LLM prompt receives recent open episodes (last 7d, max 10) as context THEN it can return explicit `episode_id` for disambiguation; the implementation MUST pass this context.
  - [ ] GIVEN multiple open episodes match `(type, subtype)` within window THEN `find_open_episode()` returns the most recent; sets `ambiguous_match=true` in the action result; logs at warning. Action still applies (most-recent wins).
  - [ ] GIVEN `pattern_summary()` THEN it returns: `count`, `count_by_day_of_week`, `count_by_hour_of_day`, `top_triggers` (5), `top_relief_actions` (5, where `worked=true`), `avg_duration_hours`, `avg_severity_max`, `co_occurrence_with_metrics` (per-metric percentage of episodes where a low/high reading occurred within ±24h).
  - [ ] GIVEN `episode_type=mental_health_episode` AND `health_sensitive_opt_in=false` THEN extraction silently drops the event (debug log); row is NEVER written.
  - [ ] GIVEN open episode >14d with no updates THEN a daily auto-close cron (`scripts/auto_close_stale_episodes.py` or maintenance-graph node) sets `ended_at`, `metadata.auto_closed=true` — distinguishable from user-confirmed close.
  - [ ] GIVEN false-positive guard examples in prompt ("headache scene in the movie", "this meeting gave me a headache") THEN eval set includes them with `action=none` as expected.
  - [ ] GIVEN integration tests THEN they cover: start → update → close lifecycle; two-of-same-type → update ambiguous → warning logged; close non-existent episode_id → logged-and-skipped no 5xx; sensitive opt-out drop; `pattern_summary()` with ≥10 seeded episodes across 60d; auto-close cron behavior.
- Edge Cases:
  - "Headache since this morning" with different headache closed 5h ago → `action=start` (new), `metadata.previous_episode_id=<closed-one>` for clustering.
  - "It's getting worse" with headache + back pain both open → LLM ideally returns explicit `episode_id`; otherwise service applies most-recent-wins AND logs `ambiguous_match=true`. Never auto-create "general worsening" episode.
  - Relief attempt without open episode ("took some ibuprofen") → `action=none`. Do NOT auto-create.
  - "Headache scene in the movie" → `action=none`. Verified by eval.
  - Unknown subtype ("cluster headache") → lands in table as-is; `SUBTYPE_NORMALIZATION` adds it in follow-up code change.
  - Severity emitted as text → coerced to 0-10 per prompt: vague intensifiers → 6-7, mild → 3, moderate → 5, severe → 8, "10/10" literal.
  - `related_metric_ids[]` populated by co-occurrence pass at close time (within ±24h of start..end); for open episodes, populated at `pattern_summary()` query time only (avoids write-amplification on every metric insert).
  - Compression policy 90d (vs metrics' 30d) because open-episode reconciliation needs the partial index hot.

## Team State
- Fenny: orchestrating
- Disha: Epic 1 v2 + 19 stories drafted (on user-hold); Epic 2 opened (Stories 2.1 + 2.2 ready); Epic 3 opened with Wave A drafted (Stories 3.1, 3.2, 3.3 drafted, pending Parminder design review)
- Parminder: 2.1 reviewed and transitioned to `ready` (both open Qs answered, ACs corrected); 2.2 reviewed and transitioned to `ready` (caller-tolerance audit done; corrected the "errors propagate to caller" framing — outer `except Exception → return None` at extract_utils.py:200-220 still swallows; bug-fix delta is just "no second SDK call"); v2 tech spec for Epic 1 in parallel; Epic 3 Wave A schemas queued for design review
- David, Harpreet, Murat: on standby for implementation wave

## Epic H: PG Connection-Leak Incident Hotfix (opened 2026-07-13)
Context: prod incident 2026-07-12 ~20:00 — TimescaleDB saturated at max_connections=100 for ~24h. RCA verified by Aria (bus 2026-07-13 [21:05]). APScheduler theory rejected.

### Story H-1: Connection-leak hotfix (Fixes 1+2+3 + pool stats + tests)
- Status: done
- Assigned: dave
- Priority: P0
- Dependencies: none
- Review Cycles: 0
- Branch: story/H-1-conn-leak-hotfix (commit 7d414c6)
- Test gate (tess, 2026-07-13): PASS. Full unit suite 540 passed / 1 pre-existing skip / 9.09s; hotfix suite 5 passed / 0.57s; hermetic integration test_retrieve_filters 6 passed / 0.84s. App-based integration (forget/intents/direct_memory/chroma_wrapper) DEFERRED — TestClient(app) runs the real lifespan which does a live prod-Chroma read and starts the TTL sweeper (SCHEDULED_MAINTENANCE_ENABLED defaults true → delete risk on the live old-image prod stack). Ship-ready pending user deploy decision. Post-deploy verification (real /health/full pool stats + pool exhaustion/recovery under concurrent /v1/narrative) is story H-5.
- Acceptance Criteria:
  - [x] _temporal_retrieval releases its pooled conn on every path (try/finally)
  - [x] release_timescale_conn always putconns even when rollback raises
  - [x] _store_in_timescale releases via try/finally
  - [x] /health/full exposes pool.get_stats()
  - [x] Unit test: rollback raises → putconn still called (fails on pre-fix code)
  - [x] Spy tests: release called exactly once on happy+error paths (both fixed functions)
  - [x] make lint clean; targeted tests green
  - [x] Zero happy-path behavioral change

### Story H-2: Pool max_size 10→5 (separate revertable PR) — backlog, P1
### Story H-3: Non-superuser DB role for app DSN — backlog, P1 (own story; GRANT risk)
### Story H-4: Hygiene — single-worker scheduler, dedupe log handlers, /health/full try-finally, delete dead StorageOrchestrator — backlog, P2
### Story H-5: Incident-repro integration test (/v1/narrative loop vs small pool) — backlog, P1, owner tess
