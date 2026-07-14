# Epic 1 — Deep Profile Tech Spec

**Author:** Parminder
**Status:** v2 — reframed after constraint relaxation
**Governing constraint:** API backward-compat only. Stored data, completeness math, internal services, extraction behavior, UI — all free to change.

---

## Version history

- **v1 (2026-04-20 00:42)** — initial tech spec under "don't change anything" constraint. Six feature flags, eight rollout slices, parallel `depth_completeness_pct` signal to protect the 27-field baseline, shadow fields for `health_conditions`, forward-only data flow (no rewrites of existing rows).
- **v2 (2026-04-20, this doc)** — user relaxed the constraint to "API backward-compat only" (bus [01:30]/[01:32]). Destructive data migrations now allowed; `EXPECTED_PROFILE_FIELDS` can grow and `completeness_pct` can recompute against the new denominator (existing user scores will shift — acceptable). Flag matrix collapses from 6 → 3 (`PROFILE_WRITE_CONFIDENCE`, `PROFILE_CONTRADICTION_DETECTION`, `PROFILE_INFERRED_EXTRACTION`). Rollout waves collapse from R1→R8 → R1→R4. New `Migration strategy` section covers four destructive data rewrites with idempotency + rollback per migration. New `API backward-compat guardrails` section spells out frozen keys per endpoint with a contract-test plan for Murat. Architectural calls from v1 are preserved verbatim.

What v2 deletes from v1:
- `PROFILE_LOG_HISTORY`, `PROFILE_ENABLE_RELATIONSHIPS`, `PROFILE_TEMPORAL_DECAY`, `PROFILE_NEW_FIELDS_COUNT` — dropped. History, relationships, decay, and new fields just ship. No shadow fields for `health_conditions`.
- Parallel `depth_completeness_pct` — retired per Fenny [01:32]. One number, `completeness_pct`, recomputed over the new expected set.
- R4/R5/R7/R8 as separate dark-launch slices — folded into R2/R3.

What v2 adds:
- Four destructive data migrations (`dietary_needs` split, `health_conditions` restructure, `allergies` null-vs-empty, category re-assignment) with idempotent up scripts, per-migration rollback plans, and before/after snippets against user `1169491032`'s real data.
- Per-endpoint frozen-key matrix + contract-test plan (golden responses; CI fails on frozen-key drift).
- Backfill order: schema migrations → data rewrites → confidence backfill → history seed.

What v2 confirms unchanged (architectural calls from v1 that survive):
1. **Confidence derived from `profile_sources`** — one source of truth. Formula `0.30·freq + 0.25·recency + 0.25·explicitness + 0.20·diversity`.
2. **Relationships as a new category on existing `profile_fields`** — `field_name = "{role}:{slug}"`, `value_type='dict'`. No new table.
3. **History written app-side** via `ProfileHistoryService` with `change_type ∈ {initial, refine, contradict, manual_override}`.

---

## 0. Summary of design calls (v2)

1. **Confidence from extraction** — unchanged from v1. `ProfileConfidenceService` invoked from `store_profile_extractions`, computes from `profile_sources`. Flag-gated (`PROFILE_WRITE_CONFIDENCE`) for shadow-launch only — not because the write is risky, but because we want to validate the scoring numbers against a real user's history before flipping on globally.
2. **History table** — unchanged from v1, but no longer flag-gated. Ships live. `profile_fields_history` is append-only; `ProfileHistoryService` owns the `change_type` classifier.
3. **Relationships** — unchanged from v1, but no longer flag-gated. Ships live. New category on `profile_fields`, `field_name = "{role}:{slug}"`.
4. **New flat fields** (`life_stage`, `current_inflection_point`, `active_stressors`, `recent_wins`, `growth_edges`, `decision_style`, `energy_recovery_patterns`) — ship live. Added to `EXPECTED_PROFILE_FIELDS`. `TOTAL_EXPECTED_FIELDS` grows; `completeness_pct` recomputes; user scores shift downward the day we ship, then climb as extraction populates the new fields. Accepted per user decision.
5. **Destructive data migrations (new in v2)** — `dietary_needs` de-conflation, `health_conditions` string→object restructure, `allergies` null-vs-empty cleanup, and a category re-assignment pass (exercise/fitness → `health`). All idempotent; all have a documented rollback stance.
6. **API contract is the only fence** — see §7 for per-endpoint frozen keys and contract tests.

---

## 1. Impact analysis

### Files that change

- `src/services/profile_storage.py` — `EXPECTED_PROFILE_FIELDS` expanded (see §3.4), stale `# 25` comment fixed to match new sum, `_identify_high_value_gaps` re-examined after field additions.
- `src/services/profile_confidence.py` — **new** service.
- `src/services/profile_history.py` — **new** service.
- `src/services/profile_extraction.py` — `PROFILE_EXTRACTION_PROMPT` grows with relationships + 7 new flat fields + guidance on `source_type='inferred'` (flag-gated via `PROFILE_INFERRED_EXTRACTION`). `FIELD_NAME_ALIASES` grows with the re-categorization aliases (e.g. `hobby:barbell` → redirect to `health.exercise`). `_validate_extractions` enforces that relationships carry `{name, role, ...}` and rejects relationships without a `role`.
- `src/routers/profile.py` — **no frozen-key changes** (see §7). Additive nested content only.
- `src/config.py` / `src/config/profile_flags.py` — 3 flags instead of 6.
- `src/services/unified_ingestion_graph.py` — `node_store_profile` invokes confidence + history services.
- `migrations/postgres/025` → `031` — schema + data migrations listed in §4.
- `scripts/backfill_confidence_scores.py` — **new**, idempotent.
- `scripts/backfill_profile_history_seed.py` — **new**, idempotent.
- `scripts/migrate_dietary_needs.py` — **new**, idempotent data rewrite.
- `scripts/migrate_health_conditions.py` — **new**, idempotent data rewrite.
- `scripts/migrate_allergies_null_semantics.py` — **new**, idempotent.
- `scripts/migrate_profile_categories.py` — **new**, idempotent category reassignment.
- `ui/src/pages/Profile.tsx` — extend `categoryIcons` + `categoryColors` for `relationships`, add relationship card renderer, display history drawer (calls new `GET /v1/profile/history`), display per-field confidence badges. UI freedom is full per Fenny [01:32].

### Modules that don't change (deliberately)

- `profile_sources` — schema untouched. This is the source of truth for confidence.
- `profile_confidence_scores` schema — already has all columns. We only change who writes to it.
- `user_profiles` schema — untouched. The math behind `completeness_pct` changes but the column doesn't.

### Consumers of the affected surface

- **REST clients** — response key structure for the frozen keys in §7 is preserved byte-for-byte. Values (e.g. the number inside `completeness_pct`, the contents of `categories`) can shift arbitrarily.
- **UI `Profile.tsx`** — free to change. We will change it.
- **LLM context builder** — reads `profile.profile` dict. New fields appear; no breakage because this is a consumer that already iterates whatever is there.

### Breaking-change audit

- **API surface:** zero breaking changes. Contract tests in §7 enforce.
- **Stored data:** breaking by design in four places (§4.2). Each has a documented before/after and a rollback stance.
- **Completeness scores:** existing user `completeness_pct` values WILL shift the day we ship. This is the documented acceptable cost of a single-number signal.

---

## 2. Dependency graph (v2)

```
          ┌──────────────────────────────────────────┐
          │ M1..M7: schema + data migrations (§4)   │
          │   idempotent; runnable in order          │
          └──────────────────┬───────────────────────┘
                             │
          ┌──────────────────▼───────────────────────┐
          │ S1: ProfileConfidenceService             │
          │ S2: ProfileHistoryService                │
          │ S3: Extraction prompt rewrite            │
          │     (relationships, 7 new flat fields,   │
          │      inferred guidance)                  │
          │ S4: EXPECTED_PROFILE_FIELDS expansion    │
          │     + completeness recompute             │
          │ S5: `_identify_high_value_gaps` refresh  │
          └──────────────────┬───────────────────────┘
                             │
          ┌──────────────────▼───────────────────────┐
          │ S6: Contradiction classifier + read API  │
          │     (/v1/profile/conflicts — new)        │
          │ S7: History read API                     │
          │     (/v1/profile/history — new)          │
          │ S8: Temporal decay multiplier on         │
          │     composite confidence                 │
          │ S9: UI — depth tab, history drawer,      │
          │     confidence badges, relationships     │
          └──────────────────────────────────────────┘
```

**Parallelizable:** S1..S5 after M1..M7. S6..S9 after S1..S5.

**Must serialize:**
- M1 (schema) → M2..M7 (data rewrites) — schema constraints must allow the destination shape before data moves.
- S2 (history service) → M7 (history seed) — the seed script uses `ProfileHistoryService`'s `change_type` classifier.
- S1 (confidence service) → confidence backfill — backfill reuses the service.

---

## 3. Schema strategy (unchanged from v1)

Preserved for reference. Only the flag gating and parallel-denominator story change in v2; the architectural calls are the same.

### 3.1 Writing `profile_confidence_scores` from the extraction path

**New service:** `src/services/profile_confidence.py`. Called from `ProfileStorageService.store_profile_extractions` **after** each `profile_fields` upsert and **after** the `profile_sources` insert.

**Scoring formula** (matches migration 011's column comment):

```
overall = 0.30 * frequency
        + 0.25 * recency
        + 0.25 * explicitness
        + 0.20 * source_diversity
```

**Component calculations** (all pulled from `profile_sources` for `(user_id, category, field_name)`):

| Component | Formula | Cap |
|---|---|---|
| `frequency_score` | `min(100, 10 * count(*))` | 100 at 10 mentions |
| `recency_score` | `max(0, 100 - (days_since_latest / 30 * 100))` | 0 after 30d |
| `explicitness_score` | `weighted_avg(source_type)` where explicit=100, implicit=70, inferred=40 | 0–100 |
| `source_diversity_score` | `min(100, 20 * count(distinct source_memory_id))` | 100 at 5 unique sources |
| `mention_count` | `count(*)` over `profile_sources` | — |
| `last_mentioned` | `max(extracted_at)` | — |

**Why derive from `profile_sources`?** One source of truth. Survives backfill and concurrent ingestions because the formula is deterministic over the source set.

**Upsert semantics** — `ON CONFLICT (user_id, category, field_name) DO UPDATE SET ...` over all component scores + `mention_count` + `last_mentioned` + `last_updated=NOW()`.

**Manual PUT path** — unchanged for Epic 1 (confidence=100, `is_manual_override=true` derivable at read). Revisit in Epic 2.

### 3.2 `profile_fields_history` table (migration 025)

```sql
CREATE TABLE IF NOT EXISTS profile_fields_history (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
  category VARCHAR(50) NOT NULL,
  field_name VARCHAR(100) NOT NULL,
  old_value TEXT,
  new_value TEXT NOT NULL,
  old_value_type VARCHAR(20),
  new_value_type VARCHAR(20) NOT NULL,
  change_type VARCHAR(30) NOT NULL,
  old_confidence DECIMAL(5,2),
  new_confidence DECIMAL(5,2),
  source_memory_id VARCHAR(255),
  source_type VARCHAR(50),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pfh_user_field ON profile_fields_history (user_id, category, field_name, changed_at DESC);
CREATE INDEX idx_pfh_changed_at ON profile_fields_history (changed_at DESC);
CREATE INDEX idx_pfh_contradict ON profile_fields_history (user_id, change_type) WHERE change_type = 'contradict';
```

**Trigger vs app-side:** app-side. Reasons unchanged from v1 — contradiction classification needs Python semantics, trigger would fire on admin scripts, and we want ingestion-flow observability in one place.

**Retention:** keep forever (user decision).

**Change-type classifier** (same as v1):
- `initial` — no prior row in `profile_fields`
- `manual_override` — source is PUT endpoint
- `contradict` — string/scalar field where normalized old != normalized new AND old confidence ≥ 60
- `refine` — everything else

### 3.3 Relationships category

**Decision: new category `relationships` on existing `profile_fields`.** Reasoning unchanged from v1 — consistency with generic render loop, reuses dedup/sources/confidence, no parallel code path.

**Field-name convention:** `{role}:{slugified_name}` — `daughter:ava`, `cofounder:priya`. Slug is stable; display name lives in the JSON.

**`field_value` JSON** (`value_type='dict'`):

```json
{
  "name": "Ava",
  "role": "daughter",
  "dynamic": "anchor; source of present-tense joy",
  "why_matter": "identity-forming relationship",
  "age_or_dob": "3",
  "notes": ["loves dinosaurs", "father-daughter Sunday tradition"]
}
```

Migration 026 widens `chk_category_valid` (same pattern as 023).

### 3.4 Life-stage / inflection / stressors / wins / how-fields

All flat fields on `profile_fields`. Category assignment:

| Field | Category | value_type |
|---|---|---|
| `life_stage` | `basics` | `string` |
| `current_inflection_point` | `basics` | `string` |
| `active_stressors` | `personality` | `list` |
| `recent_wins` | `personality` | `list` |
| `growth_edges` | `personality` | `list` |
| `decision_style` | `personality` | `string` |
| `energy_recovery_patterns` | `personality` | `string` or `list` |
| `exercise` *(new, split out during recategorization)* | `health` | `dict` |

All are added to `EXPECTED_PROFILE_FIELDS`. New denominator: 27 + 8 = **35** fields (see §4.3 for per-category map). User `1169491032`'s completeness drops from ~70% to a lower floor immediately after ship, then climbs as extraction populates.

---

## 4. Migration strategy (expanded in v2)

### 4.1 Ordered migrations

| # | Migration | Kind | Destructive? | Depends on |
|---|---|---|---|---|
| 025 | `profile_fields_history.up.sql` | Schema | No | — |
| 026 | `add_relationships_category.up.sql` | Schema (widens constraint) | No | — |
| 027 | `migrate_dietary_needs.up.sql` + data script | **Destructive data** | Yes (rewrites rows) | 025, 026 |
| 028 | `migrate_health_conditions.up.sql` + data script | **Destructive data** | Yes | 025, 026 |
| 029 | `migrate_allergies_null_semantics.up.sql` + data script | **Destructive data** | Yes | 025 |
| 030 | `recategorize_profile_fields.up.sql` + data script | **Destructive data** | Yes (moves rows between categories) | 025, 026 |
| 031 | `seed_profile_fields_history.up.sql` + data script | Data seed | No (inserts only) | 025, 027–030 |

**Backfill order (required):**

```
(1) schema migrations: 025, 026
(2) data rewrites:     027, 028, 029, 030
(3) confidence backfill: scripts/backfill_confidence_scores.py
(4) history seed:      031 (runs scripts/backfill_profile_history_seed.py)
```

Why this order:
- Schema must admit the destination shape before data moves. 026 in particular must land before 030 tries to write rows in the new `relationships` category or any recategorized rows that invoke the widened constraint.
- Confidence backfill aggregates from `profile_sources`, which is not touched by 027–030. Running it after data rewrites is purely so history seed (step 4) can snapshot post-rewrite confidence alongside the field values.
- History seed runs last because it writes `initial` rows referencing the *current* (post-rewrite) state. We deliberately do NOT seed history rows for the destructive rewrites themselves — we do not want synthetic `refine` rows manufactured by the migration. The rewrite is a schema-level operation, not a user-observable change event.

### 4.2 Idempotency contract (applies to every migration)

Every data-rewrite script must be re-runnable safely. The contract:

1. **Detect already-migrated rows before rewriting.** Use a shape/content check, not a flag column. Example: `dietary_needs` migration checks whether the string contains "Favorites:" before splitting.
2. **Use `ON CONFLICT` semantics for target rows.** `food_preferences` merge in `dietary_needs` migration must MERGE with any existing `preferences.food_preferences` row, not overwrite.
3. **Log per-row outcome** — `migrated | already_migrated | skipped_unexpected_shape`. Counts published to stdout so operators can diff runs.
4. **Dry-run mode** — `--dry-run` prints the proposed rewrites without executing. Required for review before the destructive run.
5. **Transactional per user_id.** Each user's rewrite is wrapped in a transaction. A failure on user X doesn't leave user X half-migrated; it rolls back and the script continues to user X+1 with the failure logged.

### 4.3 Destructive migration 027: `dietary_needs` de-conflation

**Problem (from audit):** `dietary_needs: "Vegetarian (eats eggs). Favorites: Pizza, Noodles, Indian food."` conflates a medical requirement with food preferences. Duplicates `preferences.food_preferences`.

**Strategy:** parse the stored string. The "requirement" clause (before "Favorites:" or equivalent marker) stays in `health.dietary_needs`. The "favorites" clause migrates into `preferences.food_preferences`, merging with existing values if any.

**Preference markers (regex, case-insensitive):** `\b(favorites?|likes?|prefers?|loves?|enjoys?)\b\s*[:-]`.

**Idempotency check:** if `health.dietary_needs` value matches the "requirement-only" shape (no preference marker), treat as already migrated — no-op.

**Acceptance criteria — before/after for user `1169491032`:**

```
BEFORE (from audit):
  profile_fields row:
    (user_id='1169491032', category='health', field_name='dietary_needs',
     field_value='Vegetarian (eats eggs). Favorites: Pizza, Noodles, Indian food.',
     value_type='string')

AFTER migration 027:
  profile_fields row (UPDATED):
    (user_id='1169491032', category='health', field_name='dietary_needs',
     field_value='Vegetarian (eats eggs)',
     value_type='string')

  profile_fields row (INSERTED or MERGED):
    (user_id='1169491032', category='preferences', field_name='food_preferences',
     field_value=<merged list including 'Pizza', 'Noodles', 'Indian food'>,
     value_type='list')
```

If `preferences.food_preferences` already exists, union the new items into the existing list (case-insensitive dedup). If it does not exist, create it.

**Rollback plan:** the down migration reconstructs the original conflated string from the two post-migration rows. Captured in `027_migrate_dietary_needs.down.sql` as documented intent — the script is commented "manual recovery only; do not run without inspection" because we cannot reliably tell which items in `food_preferences` came from this migration vs. were authored separately. Operator-driven.

### 4.4 Destructive migration 028: `health_conditions` string → object

**Problem (from audit):** `health_conditions: "stomach uneasiness"` carried 10 sources (most-active signal) but stored as a flat string. Missing triggers, severity trajectory, management strategies.

**Strategy:** rewrite `health.health_conditions` from `value_type='string'` to `value_type='list'` of condition objects. Existing flat strings become shell objects with `status='unknown'`.

**Target schema (per item in the list):**

```json
{
  "condition": "<old string>",
  "triggers": [],
  "severity": null,
  "onset": null,
  "management": [],
  "status": "unknown"
}
```

**Idempotency check:** if the current `value_type` is already `list` and the first item has a `condition` key, no-op.

**Acceptance criteria — before/after for user `1169491032`:**

```
BEFORE:
  (user_id='1169491032', category='health', field_name='health_conditions',
   field_value='stomach uneasiness',
   value_type='string')

AFTER migration 028:
  (user_id='1169491032', category='health', field_name='health_conditions',
   field_value='[{"condition":"stomach uneasiness","triggers":[],"severity":null,"onset":null,"management":[],"status":"unknown"}]',
   value_type='list')
```

Forward extractions will then enrich the object with triggers/severity/management as new memories arrive.

**Rollback plan:** `028.down.sql` reduces the list back to a comma-joined string of `condition` values, drops the structure. Documented in the down script; operator runs explicitly.

### 4.5 Destructive migration 029: `allergies` null-vs-empty semantics

**Problem (from audit):** `allergies: []` is ambiguous — confirmed none vs. never extracted.

**Strategy:** set `field_value=NULL` (by deleting the row entirely) on all `health.allergies` rows that currently hold `[]` AND whose `profile_sources` contains zero explicit affirmations like "no known allergies" / "I don't have any allergies". If explicit confirmation exists in sources, preserve `[]` and mark `confirmed_none=true` (a new column added in 029 schema portion).

**Schema piece of 029:**

```sql
ALTER TABLE profile_fields
  ADD COLUMN IF NOT EXISTS confirmed_none BOOLEAN DEFAULT FALSE;
```

**Source-scan regex (case-insensitive):** `\b(no|don'?t have|no known)\s+(?:food\s+)?(allergi|allergies)\b`, matched against `profile_sources.source_content` for the target field.

**Idempotency check:** existing rows with `confirmed_none=TRUE` are skipped. Rows absent from the table (already null) are skipped.

**Acceptance criteria — before/after for user `1169491032`:**

```
BEFORE:
  (user_id='1169491032', category='health', field_name='allergies',
   field_value='[]', value_type='list', confirmed_none=FALSE [new default])

  profile_sources for this field: no explicit "no allergies" affirmation
  (per audit — allergies is flagged as "never extracted affirmatively").

AFTER migration 029:
  profile_fields row DELETED (field_value became unknown → null semantics).
  Subsequent extractions or a manual PUT can re-populate.
```

If a different user's sources did contain an explicit affirmation, they retain the `[]` row with `confirmed_none=TRUE`.

**Rollback plan:** non-reversible (deleted rows can be restored from the backup, but we do not reconstruct them from migration state). `029.down.sql` drops the `confirmed_none` column; deleted field rows stay deleted. Operator runs a point-in-time restore if needed.

### 4.6 Destructive migration 030: category re-assignment pass

**Problem (from audit and bus [01:32]):** `interests.hobbies` contains fitness/exercise items that belong in `health`. `preferences.food_preferences` and `health.dietary_needs` have implicit cross-reference. After 027, food preferences are cleanly in preferences; 030 handles exercise.

**Strategy:** move exercise/fitness items out of `interests.hobbies` into a new `health.exercise` dict field. Extraction prompt (S3) will thereafter write to `health.exercise` directly.

**Target shape for `health.exercise` (`value_type='dict'`):**

```json
{
  "modalities": ["barbell training", "running"],
  "frequency": null,
  "goals": [],
  "notes": []
}
```

**Detection heuristic:** items in the `interests.hobbies` list matching fitness vocabulary (`barbell`, `weight`, `strength training`, `running`, `gym`, `yoga`, `crossfit`, `cycling`, `swimming`, `climbing`, `pilates`). Seed list; refinement during review.

**Idempotency check:** if `health.exercise` already exists for the user and has the same `modalities` set, no-op. Otherwise merge (union) before writing.

**Acceptance criteria — before/after for user `1169491032`:**

```
BEFORE (illustrative, based on audit note "exercise specifics orphaned in `interests`"):
  (user_id='1169491032', category='interests', field_name='hobbies',
   field_value='["barbell-based workouts", "reading", "tennis"]',
   value_type='list')

AFTER migration 030:
  (user_id='1169491032', category='interests', field_name='hobbies',
   field_value='["reading", "tennis"]',
   value_type='list')

  (user_id='1169491032', category='health', field_name='exercise',
   field_value='{"modalities":["barbell-based workouts"],"frequency":null,"goals":[],"notes":[]}',
   value_type='dict')
```

`profile_sources` rows are NOT moved — they keep their original `(category, field_name)` as historical record of where the signal was first captured. New sources from future extractions will land in the new category.

**Rollback plan:** `030.down.sql` merges `health.exercise.modalities` back into `interests.hobbies`, deletes the `health.exercise` row. Reversible but lossy on the `frequency`/`goals`/`notes` sub-fields (which were null at migration time anyway). Documented.

### 4.7 Non-destructive migrations: 025, 026, 031

- **025** (`profile_fields_history`): additive. `.down.sql` drops the table; safe.
- **026** (widen `chk_category_valid`): relaxes a CHECK constraint. `.down.sql` requires deleting rows in newly-added categories first (documented in down file with a warning comment — operator decides).
- **031** (seed `profile_fields_history`): inserts `initial` rows only. `.down.sql` is `DELETE FROM profile_fields_history WHERE source_memory_id = 'backfill'`. Clean.

### 4.8 Confidence backfill (`scripts/backfill_confidence_scores.py`)

Iterates every `(user_id, category, field_name)` in `profile_fields`, aggregates from `profile_sources`, upserts a `profile_confidence_scores` row. Idempotent — the upsert itself is the idempotency boundary. Safe to re-run. Do NOT re-run LLM extraction on historical memories — `profile_sources` rows are the authoritative aggregation, and re-extraction risks the LLM overwriting human-curated fields.

### 4.9 History seed (`scripts/backfill_profile_history_seed.py`)

Seeds one row per existing `profile_fields` row: `old_value=NULL`, `new_value=<current>`, `change_type='initial'`, `source_memory_id='backfill'`, `changed_at=profile_fields.last_updated`. One-shot; idempotent via a pre-check `WHERE NOT EXISTS (SELECT 1 FROM profile_fields_history WHERE ...)`.

---

## 5. Feature flags — shrunk to 3

### 5.1 Active flags

| Flag | Env var | Guards | Shadow-launch rationale |
|---|---|---|---|
| `PROFILE_WRITE_CONFIDENCE` | `PROFILE_WRITE_CONFIDENCE` | Calls into `ProfileConfidenceService` from `store_profile_extractions`. | Keeps flag during scoring-formula validation. We want to run the backfill, spot-check scores against user `1169491032`'s source counts, then flip. Low-risk but the flag is cheap insurance against a formula bug tanking trust in the number. |
| `PROFILE_CONTRADICTION_DETECTION` | `PROFILE_CONTRADICTION_DETECTION` | `change_type='contradict'` classification surfacing + `/v1/profile/conflicts` endpoint behavior. History rows still log regardless — this flag only controls observe-vs-resolve and API surfacing. | Detection is correct long before resolution UX is. We want to watch contradiction volume for a couple of days before turning on the endpoint (and later, the resolution logic in Story 1.5). |
| `PROFILE_INFERRED_EXTRACTION` | `PROFILE_INFERRED_EXTRACTION` | Prompt section encouraging `source_type='inferred'` hypothesis formation + the 75-confidence cap on inferred extractions. | Genuinely new LLM behavior. Current production rarely uses `inferred` (12/421 sources per audit). Flipping extraction to encourage it has prompt-regression risk on *other* fields. Dark-launch so we can compare a day's worth of flag-on ingestions to a day's flag-off baseline. |

### 5.2 Retired flags (v1 → v2)

| Retired flag | Why retired |
|---|---|
| `PROFILE_LOG_HISTORY` | History logging is harmless and the default. No user-visible behavior change until the read endpoint is live, which gates itself on data presence. Just ship it. |
| `PROFILE_ENABLE_RELATIONSHIPS` | Relationships is a new category that stores writes correctly whether or not the UI surfaces them. Migration 026 widens the constraint; prompt additions are safe to ship because the LLM will only emit relationships when the memory describes them. No dark-launch value. |
| `PROFILE_TEMPORAL_DECAY` | Decay is a multiplier on composite confidence. Since confidence itself is gated by `PROFILE_WRITE_CONFIDENCE`, decay piggybacks — no second flag needed. If the multiplier introduces a bug, we roll back the commit, not toggle a flag. |
| `PROFILE_NEW_FIELDS_COUNT` (v1's parallel-denominator defense) | Constraint relaxed [01:32]. Completeness denominator grows; existing scores shift. One signal, one number. |

### 5.3 Flag plumbing

Flags live in `src/config/profile_flags.py`. Single module, each flag exposed as `flag_<name>()` function (callable, not constant) so tests can monkey-patch. `GET /v1/profile/_flags` returns the current flag state — additive, under a new path, not in the §7 frozen-keys list.

---

## 6. Rollout sequence — collapsed to R1..R4

v1 had R1..R8. v2 has R1..R4 because the retired flags collapse previously-separate slices.

| Slice | Ships | What flips | Parallelizable? |
|---|---|---|---|
| R1 | **Schema + data migrations** (025–031) + backfill scripts. `EXPECTED_PROFILE_FIELDS` expansion + stale-comment fix ships together with the recategorization migration so the denominator and the data move in lockstep. | `completeness_pct` recomputes on the next ingestion for every user. Shift is visible immediately. | — |
| R2 | **Backend services**: `ProfileConfidenceService`, `ProfileHistoryService`, contradiction classifier (logs to history; endpoint gated), extraction prompt rewrite (new flat fields + relationships always on; inferred section flag-gated). | `PROFILE_WRITE_CONFIDENCE=true` once confidence backfill is reviewed. `PROFILE_INFERRED_EXTRACTION=true` after dark-launch day compares reasonable. | R2 independent of R3/R4 after R1. |
| R3 | **Read endpoints**: `GET /v1/profile/history`, `GET /v1/profile/conflicts`. `PROFILE_CONTRADICTION_DETECTION=true` turns on the conflicts endpoint. | Flag flip above. | Parallel with R4. |
| R4 | **UI**: Profile.tsx additions — relationships card, Depth tab, confidence badges, history drawer. | No flag — UI reads what the API returns and degrades gracefully for absent data. | — |

Verification gates between slices:
- R1 → R2: schema applied cleanly in staging, destructive data migrations re-run without error (idempotency proof), user `1169491032`'s transformed rows match the acceptance snippets in §4.3–§4.6.
- R2 → R3: confidence spot-check for user `1169491032` — `health.health_conditions` should score ≥ 80 overall (10 sources, recent); `health.vision_correction` should score substantially lower (single source, 99 days stale).
- R3 → R4: smoke test the two new read endpoints with flag off (returns 404) and flag on (returns list).

---

## 7. API backward-compat guardrails

### 7.1 Frozen per endpoint

These keys cannot change name or JSON type under Epic 1. Values inside them (numbers, nested structures under `profile` / `categories` / `field_metadata`) are free to evolve.

#### `GET /v1/profile?user_id=X`

| Frozen key | Type | Notes |
|---|---|---|
| `user_id` | string | |
| `profile` | `dict[str, dict[str, Any]]` | Outer keys are categories; adding new categories (e.g. `relationships`) is allowed — additive. Inner values free to change shape. |
| `completeness_pct` | number | Value will shift with denominator recompute; key + type frozen. |
| `populated_fields` | integer | |
| `total_fields` | integer | Will increase to the new `TOTAL_EXPECTED_FIELDS`. |
| `last_updated` | string or absent | ISO8601 when present. |
| `created_at` | string or absent | ISO8601 when present. |

Allowed additive: `field_metadata` (already exists, `include_metadata=true`), new top-level keys under opt-in query params only (e.g. a future `?include_confidence=true` adds a `confidence` block).

#### `GET /v1/profile/{category}?user_id=X`

| Frozen key | Type |
|---|---|
| `user_id` | string |
| `category` | string |
| `fields` | `dict[str, Any]` |
| `field_metadata` | `dict[str, dict]` or absent |

Values inside `fields` change shape freely (e.g. `health_conditions` becomes a list of objects after migration 028). That's a downstream consumer concern, not a contract break — the key and its container type are unchanged.

#### `GET /v1/profile/completeness?user_id=X&details=bool`

**Simple mode (`details=false`):**

| Frozen key | Type |
|---|---|
| `user_id` | string |
| `overall_completeness_pct` | number |
| `populated_fields` | integer |
| `total_fields` | integer |

**Detailed mode (`details=true`):**

| Frozen key | Type |
|---|---|
| `user_id` | string |
| `overall_completeness_pct` | number |
| `populated_fields` | integer |
| `total_fields` | integer |
| `categories` | `dict[str, CategoryCompleteness]` |
| `categories[*].completeness_pct` | number |
| `categories[*].populated` | integer |
| `categories[*].total` | integer |
| `categories[*].missing` | `list[string]` |
| `high_value_gaps` | `list[string]` |

Task spec mentions a top-level `missing` key. In the current code it lives at `categories[*].missing`, not at the top level. Treating the nested location as the canonical frozen shape per the live response model. (If the intent was a top-level alias, call out as a contract question — see §10.)

#### `PUT /v1/profile/{category}/{field_name}`

**Request body (frozen):**

```json
{ "user_id": "...", "value": <any>, "source": "manual" }
```

**Response (frozen):**

| Frozen key | Type |
|---|---|
| `user_id` | string |
| `category` | string |
| `field_name` | string |
| `value` | any |
| `confidence` | number |
| `last_updated` | string |

**Status codes frozen:** 200 OK, 400 on null value with the existing error message, 404 on unknown user (existing behavior).

#### `DELETE /v1/profile/{category}/{field_name}?user_id=X`

**Response (frozen):** `{ deleted: bool, user_id, category, field_name }`.

#### `DELETE /v1/profile?user_id=X&confirmation=DELETE`

**Response (frozen):** `{ deleted: bool, user_id }`. `confirmation=DELETE` query param is frozen.

### 7.2 Free to add / evolve

- New top-level keys gated behind opt-in query params (`?include_confidence=true`, `?include_freshness=true`).
- New nested shapes under `profile.<category>.<field_name>` (e.g. `health.health_conditions` becoming a list of objects).
- New category keys under `profile` (e.g. `relationships`).
- New endpoints under `/v1/profile/*` (e.g. `/v1/profile/history`, `/v1/profile/conflicts`, `/v1/profile/_flags`) — these add to the surface; they do not change frozen contracts.
- Anything inside `field_metadata`.
- The numeric value of `completeness_pct` for a given user.

### 7.3 Contract test plan (for Murat)

**Goal:** CI fails if any frozen key drops, changes type, or is renamed.

**Test fixtures** (in `tests/contract/fixtures/`):
- `fixture_empty_user.json` — no profile.
- `fixture_user_1169491032_post_migration.json` — snapshot of user `1169491032` after migrations R1 has run. Handcrafted; does not require a real DB connection.
- `fixture_user_with_relationships.json` — includes at least one `relationships.daughter:ava` row.
- `fixture_user_with_completeness_50pct.json` — exercises detailed completeness including `high_value_gaps` population.

**Golden-response tests** (in `tests/contract/test_profile_api_contract.py`):

For each endpoint and each fixture:

1. Invoke the endpoint via FastAPI `TestClient`.
2. Assert the response JSON matches a golden file (`tests/contract/golden/<endpoint>_<fixture>.json`) **on frozen keys only** — comparison uses a custom assertion that walks only the keys listed in §7.1 and asserts each exists with the declared JSON type. Values are not pinned.
3. Additionally assert: no frozen key missing, no frozen key type-changed, and the set of frozen keys is a subset of the actual response keys (additive is allowed).

**CI integration:** `pytest tests/contract/` runs in CI before deploy. A golden-file diff is required for any intentional change to the frozen matrix; reviewers see the matrix move in PR.

**When golden files update:** only if §7.1 changes. Otherwise the goldens are stable across Epic 1.

**Mutation tests to write:**
- Accidentally rename `completeness_pct` → `completeness_percent`. Expect: test fails.
- Change `total_fields` type from int to string. Expect: test fails.
- Drop `categories[*].missing`. Expect: test fails.
- Add a new top-level key `health_check`. Expect: test passes (additive).

---

## 8. Confirmed architectural calls (unchanged from v1)

### 8.1 Confidence is derived, not maintained

`ProfileConfidenceService.compute_and_upsert(user_id, category, field_name)`:
1. Read all `profile_sources` rows for the tuple.
2. Compute the four components (see §3.1).
3. Compute `overall = 0.30·freq + 0.25·recency + 0.25·explicitness + 0.20·diversity`.
4. `ON CONFLICT` upsert into `profile_confidence_scores`.

No incremented counters, no drift risk, no special-casing concurrent ingestions. Two parallel ingestions racing on this for the same user converge because the formula is pure over the source set.

### 8.2 Relationships reuses `profile_fields`

One row per relation. `field_name = "{role}:{slug}"`. `value_type='dict'`. Dedup, sources, confidence, and history all work for free — same code paths as every other field. The UI render path is the only place relationships need special handling (a dedicated card vs. generic key/value). Not a backend concern.

### 8.3 History is app-side with `change_type` classification

`ProfileHistoryService.record_change(old, new, source_memory_id, source_type)` classifies and appends. Reasons (unchanged from v1):

- Classification needs Python semantics (normalization, JSON compare, list-set compare).
- DB triggers would fire during admin migration backfills — unwanted.
- Keeping the logic in one place simplifies observability and rollout.

### 8.4 Manual PUT semantics unchanged for Epic 1

Confidence stays at 100 for manual PUT. `is_manual_override` is derivable at read time from `profile_sources` (last source is `source_memory_id='manual'` with no subsequent extraction source). Revisit in Epic 2 per user decision [01:30].

---

## 9. Risks

1. **Destructive migration on production data.** By design; mitigation is the idempotency contract + dry-run mode + per-user transactional wrap. Recommend taking a point-in-time backup before first prod run — standard operations hygiene.
2. **Completeness score visibly drops the day R1 ships.** User decision to accept. Worth a release note so any consumer watching the number doesn't interpret it as a regression.
3. **Prompt regression from adding relationships + 7 fields + inferred guidance.** Murat should write a per-field extraction regression suite (sample memories → expected field emissions) before R2 flips on. Flagged as a companion story to Disha's draft.
4. **Concurrency on confidence recomputation.** Tolerable — formula is deterministic over sources, converges on next run. `SELECT ... FOR UPDATE` not needed for Epic 1.
5. **`migrations/migrate.sh` PG_PORT drift** — project-wide gotcha noted in CLAUDE.md (defaults to 5433, new setup uses 5432, stale `.dbconfig` can linger). Migrations 025–031 inherit this — verify the migrate harness is pointed at the right port before running destructive data migrations. Pre-flight check for David/operator.

---

## 10. Open questions / contract clarifications

1. **Top-level `missing` key.** Task spec lists `missing` as a frozen top-level key on `/v1/profile/completeness`. The live response model puts it at `categories[*].missing`, not top-level. I'm encoding the nested location as canonical. If a top-level alias was the intent, raise and we'll add it as an additive top-level mirror — cheap, non-breaking. **No blocker; flagging for acknowledgement.**
2. **Contract test golden files for user `1169491032`.** Do we want goldens pinned against real DB snapshots post-migration, or handcrafted fixtures? Handcrafted is cleaner for CI reproducibility. Recommending handcrafted.
3. **`exercise` field under `health` — does it count toward the new denominator?** Yes in this spec — it's added to `EXPECTED_PROFILE_FIELDS["health"]`. Confirm with Disha that her story 1.13/1.19 aligns.

---

## 11. Verification strategy

### 11.1 Per-slice acceptance

- **R1 (migrations + backfills):**
  - Schema migrations apply + rollback cleanly on a scratch DB.
  - Each data-rewrite script is run twice; second run emits `already_migrated` for every row.
  - Dry-run mode prints proposed rewrites without touching the DB.
  - User `1169491032`'s post-migration rows match the snippets in §4.3–§4.6 byte-exact.
  - `TOTAL_EXPECTED_FIELDS` equals the new sum (35 after §3.4 expansion); unit test asserts `TOTAL_EXPECTED_FIELDS == sum(len(v) for v in EXPECTED_PROFILE_FIELDS.values())`.
- **R2 (services):**
  - Ingest a test memory; assert `profile_confidence_scores` row with all 4 components populated.
  - Ingest same memory twice; assert two `profile_fields_history` rows (`initial`, then `refine`).
  - Ingest a contradicting memory; assert `change_type='contradict'`.
  - Flag-off parity: with all three flags false, response bytes for `/v1/profile*` match a baseline captured before R2 ships.
- **R3 (endpoints):**
  - `/v1/profile/history` returns DESC-ordered rows.
  - `/v1/profile/conflicts` returns conflict rows when flag on, 404 when off.
  - Both new endpoints pass the §7.3 contract guard — frozen keys on the *existing* endpoints unchanged.
- **R4 (UI):**
  - Profile.tsx renders `relationships` with a dedicated card.
  - Confidence badge visible on every populated field.
  - History drawer opens and loads.
  - Graceful degradation when any flag is off.

### 11.2 End-to-end success criterion

After R1..R4 ship with all flags ON, user `1169491032`'s profile should show:
1. Live `profile_confidence_scores` populated for every extracted field (~73 rows).
2. `health.health_conditions` as a list with one shell object for "stomach uneasiness".
3. `health.dietary_needs` = "Vegetarian (eats eggs)" (de-conflated).
4. `preferences.food_preferences` includes "Pizza", "Noodles", "Indian food" (merged from the old conflated string).
5. `health.exercise` populated with `modalities: ["barbell-based workouts"]`.
6. `health.allergies` either absent (null — no affirmation in sources) or present with `confirmed_none=true` (if affirmation found).
7. At least one `relationships.daughter:ava` row with `{name, role, dynamic, why_matter}`.
8. `profile_fields_history` seeded with one `initial` row per existing field.
9. A detected contradiction between `fears: "leaving stable job"` and `long_term: "quit Intuit for entrepreneurship"` surfaced via `/v1/profile/conflicts`.
10. `completeness_pct` recomputed against the new 35-field denominator, visibly different from pre-migration but mathematically coherent with the field count.

That's Epic 1 done.
