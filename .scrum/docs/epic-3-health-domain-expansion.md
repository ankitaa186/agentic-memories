# Epic 3: Health Domain Expansion — from gift-helper to self-model of the body

Owner: Disha (PM) — Design review: Parminder
Status: drafted (Wave A scoped)
Opened: 2026-05-17

---

## Why this epic exists

Today the `health` category is the weakest domain in the entire profile. It holds 7 qualitative fields — `allergies`, `dietary_needs`, `health_conditions`, `medications`, `clothing_sizes`, `sensory_preferences`, `vision_correction` — all extracted only from conversational text, all flat (string or short array), none time-aware. That set is barely enough to *not poison a gift purchase*; it is nowhere near enough for an "agentic memory" that genuinely understands the user's body.

Three structural gaps make the current state irrecoverable without a deliberate expansion:

1. **No quantitative time-series.** We already operate TimescaleDB hypertables for `episodic_memories`, `emotional_memories`, and `portfolio_snapshots`. We use none of that machinery for health. Weight, BP, HR, sleep, glucose, mood — none of these can be stored, queried, or trended. The infrastructure is here; the schema and pipeline are missing.
2. **No episode model.** Symptoms are events with onset, severity, duration, triggers, relief, and resolution. Today they land (if at all) inside `episodic_memories` as freeform text — unstructured, un-aggregable, invisible to pattern detection. There is no way to answer "how often do I get headaches" or "what triggered last week's flare."
3. **No baseline depth.** Even within qualitative-only territory we are missing fields any sensible consumer would expect: blood type, height/baseline-weight, biological sex, primary care provider, specialists, insurance, immunizations, last-physical date, family medical history, devices. The bar for a complete-enough health profile in 2026 (compare Apple Health, Whoop Advanced Labs, Function Health, Oura+Quest) has moved decisively past where we are.

The market context: in 2026 the wearables-plus-labs convergence is real. Apple Health embeds PHQ-9/GAD-7 since iOS 17. Whoop and Oura now ship blood-biomarker uploads. Function Health runs 160+ biomarkers per member twice a year. For an AI memory system that aspires to *know the user better than they know themselves*, having "ate eggs, allergic to penicillin" as the entirety of the body model is no longer defensible.

## Goal

Evolve the health domain from a 7-field gift-helper into a structured self-model of the body — capturing not just what the user *has* (conditions, meds, allergies) but how their body *behaves over time* (biometrics, episodes, patterns), with conversational ingest as the primary input and existing polyglot persistence as the substrate.

## Constraint frame

**The fence is API backward-compat on existing endpoints.** New endpoints are net-additive; existing `/v1/profile*` paths, methods, status codes, and response top-level keys remain frozen exactly as in Epic 1's v2 constraint.

### Frozen — breaking these is a regression
- `/v1/profile*` URL paths, HTTP methods, status codes
- Response top-level field names: `user_id`, `profile`, `completeness_pct`, `populated_fields`, `total_fields`, `categories`, `high_value_gaps`, `last_updated`, `created_at`
- Existing query parameter names and semantics

### Free to change — not regressions
- `EXPECTED_PROFILE_FIELDS["health"]` can grow and reshape; `completeness_pct` will recompute on a new denominator
- New endpoints under `/v1/health/*` for metrics and episodes (net-additive surface)
- New TimescaleDB hypertables (`health_metrics`, `health_episodes`)
- LLM extraction prompt can grow new output kinds beyond `profile_field` (specifically: `health_metric`, `health_episode_event`)

## Non-goals (Wave A)

- Wearable / external integrations (Apple Health export, Oura API, Whoop API, Dexcom). Deferred to Wave B.
- Medication dosing schedule + adherence tracking. Deferred to Wave B (Story 3.5).
- Family medical history as a structured per-relative table. Deferred to Wave B (Story 3.6) — for Wave A, a `family_medical_history_summary` text field is sufficient.
- Lab results / biomarker panels. Deferred to Wave C (Story 3.9).
- PHQ-9 / GAD-7 structured scales and daily mood logs. Deferred to Wave C (Story 3.8).
- Sleep ↔ mood correlation engine, anomaly detection, trend alerting. Deferred to Wave C (Story 3.10).
- Insights surfacing in `Profile.tsx` or chat retrieval — defer UX work until the data layer is proven; surfaces follow once data exists.
- Encryption-at-rest with a separate KMS key for `health_*` tables. Wave A persists health data in the same Postgres/TimescaleDB instances as everything else; cryptographic isolation is a deliberate Wave C decision after we've seen real usage.

## Success criteria (what "done" looks like for Wave A)

- **Depth captured (profile)** — For the target user, at least 12 of the new Tier-1 health profile fields are populated after one backfill / extraction cycle. (Today's count: 0 of the new fields.)
- **Quantitative signal captured** — After one ingestion cycle covering conversations that mention numbers ("I weighed 168", "BP 122/78", "slept 6 hours"), the corresponding rows exist in `health_metrics` with correct unit normalization (lb→kg, °F→°C, oz→ml).
- **Episode lifecycle captured** — At least one start → update → close lifecycle for a `symptom` episode survives a real ingestion sequence: utterance "headache since 3pm" → row in `health_episodes` with `ended_at IS NULL`; utterance "feeling better now" → same row patched with `ended_at` set.
- **Pattern surfacing wired** — `GET /v1/health/episode/patterns?type=symptom&subtype=headache` returns a non-empty aggregation (counts by day-of-week / hour-of-day / top triggers) after seeding ≥3 episodes of the same subtype.
- **Sensitivity gating respected** — Sensitive fields (`mental_health_history`, `surgical_history`, `hospitalizations`, `substances_baseline`, `reproductive_status`, `gender_identity`) are NOT written when `user_profiles.health_sensitive_opt_in = false`; an integration test enforces this for each of the six.
- **API contract intact** — All frozen response keys still return for every existing `/v1/profile*` endpoint; existing integration tests pass; only `completeness_pct` numeric value is expected to shift (denominator grew); Murat's golden-response contract tests are the gate.
- **No regressions in existing extraction** — Profile / episodic / emotional extraction quality holds; specifically, the worthiness call from Epic 2 is not duplicated, episodic-write traces still nest correctly under their root span.

---

## Wave structure & scope

Epic 3 is planned as three waves. Only **Wave A (Stories 3.1, 3.2, 3.3)** is in scope of this epic doc as drafted. Waves B and C are listed for context — they are NOT drafted as stories here and will earn their own epic-level review once Wave A lands.

```
Wave A — Foundation (this epic)
  3.1 Health profile expansion        (~1.5 weeks)
  3.2 Biometric time-series hypertable (~3 weeks)
  3.3 Symptom & episode logs           (~2.5 weeks)

Wave B — Integration (future)
  3.4 Healthcare events log
  3.5 Medication adherence
  3.6 Family medical history (structured)
  3.7 Wearable & app ingestion adapters

Wave C — Insight & sensitivity (future)
  3.8 Mental wellbeing structured (PHQ-9, GAD-7, mood)
  3.9 Lab results & biomarkers
  3.10 Insights & correlations engine
  3.11 Privacy / consent / encryption layer
  3.12 Health-aware retrieval enhancements
```

Wave A is sequenced linearly:

```
3.1 (profile expansion, no DDL) → 3.2 (health_metrics hypertable + new extraction kind) → 3.3 (health_episodes, builds on 3.2's extraction layer)
```

3.1 is a low-risk, code-only change to the profile-field catalog and LLM prompt; it unblocks UX wins immediately. 3.2 is the load-bearing schema decision — it introduces the new extraction output kind that 3.3 reuses. 3.3 closes the loop with the most behaviorally complex piece (open-episode reconciliation).

---

## Cross-cutting architectural decisions

These apply across all three Wave A stories and are called out here so they are not re-litigated per story.

### D1. LLM extraction strategy: one call, multiple output kinds

**Decision:** extend the existing `run_unified_ingestion()` pipeline's LLM call to emit additional top-level arrays (`health_metrics`, `health_episode_events`) alongside the existing extraction kinds (profile fields, episodic, emotional, etc.) — NOT a separate parallel LLM call.

**Rationale:** the same utterance "I have a headache since 3pm, took ibuprofen, BP was 140/90" contains profile-irrelevant content, a metric, and an episode start. Forcing the model to make those decisions in one pass keeps reasoning coherent and avoids the cost/latency penalty of a second LLM round-trip. Risk: more complex JSON schema → higher malformed-output probability. Mitigation: explicit per-kind validators; reject-and-log on schema violation; eval set covering all kinds.

**Known pitfall to avoid:** Pydantic silently drops dict keys that don't match schema field names (memory/CLAUDE.md). Each new extraction kind ships with named Pydantic models, not dict-typed shims.

### D2. Sensitivity gating: upfront opt-in, not per-mention

**Decision:** sensitive health categories (`mental_health_history`, `surgical_history`, `hospitalizations`, `substances_baseline`, `reproductive_status`, `gender_identity`) require a one-time explicit opt-in stored as `user_profiles.health_sensitive_opt_in BOOLEAN DEFAULT FALSE`. Extractions for these fields are silently dropped (logged at debug) when the flag is false.

**Rationale:** Apple Health's pattern (and the GDPR-adjacent thinking we should adopt even when not legally required) is upfront opt-in for clinical-grade categories. Per-mention prompts (à la "do you want me to remember this?") would be intrusive and would not survive batch ingestion of historical conversations.

**Out of scope for Wave A:** crisis policy (what to do when PHQ-9 ≥ 20 or ideation is expressed). That's a Wave C decision; Wave A's `mental_health_history` field is biographical / historical only, not clinical screening.

### D3. Unit normalization at ingestion, not query

**Decision:** all numeric metrics are normalized to canonical SI / metric units at extraction time (`kg`, `°C`, `ml`, `bpm`, `mmHg`, `mg/dL`, `ms`, `%`, `min`, `kcal`, `mg`). The LLM does the conversion per a prompt rule; the `unit` column on `health_metrics` always holds the canonical unit.

**Rationale:** convert-at-query forces every consumer (briefing, retrieval, UI) to know the conversion table. Convert-at-ingest is a one-time cost and yields a homogeneous time-series.

**Risk:** LLM mis-conversion (especially lb ↔ kg). Mitigation: a dedicated eval bucket covers all unit-conversion cases; confidence drops below threshold for ambiguous units route to a review log instead of auto-persist.

### D4. Confidence-based persistence threshold

**Decision:** auto-persist thresholds differ by kind. Profile fields: composite confidence ≥ 80. Health metrics: ≥ 70. Health episodes: ≥ 75. Below threshold → log to a review queue, do not write.

**Rationale:** the cost of a wrong metric is higher than the cost of a wrong profile field (because metrics are aggregated and trended), so the bar is higher. Episodes sit between because misclassified episodes only matter once pattern detection runs.

**Open question:** these are gut numbers; refine after the first ingestion cycle's eval. Tracked in story-level open questions.

### D5. Idempotency keys

- `health_metrics`: `UNIQUE (user_id, ts, metric, source)` — same metric/timestamp/source upserts in place.
- `health_episodes`: no natural unique key; instead, the LLM extraction emits an explicit `action: start | update | close | none` plus an optional `episode_id` (when available from prior context). Storage-side reconciliation matches `update`/`close` to the most-recent open episode of the same `(episode_type, subtype)` within a configurable window (default 72h for symptom, longer for chronic flare). Ambiguous matches (≥2 candidate open episodes) → log + ask, do not silently guess.

### D6. Backfill policy

**Decision:** NO backfill of historical conversations during Wave A. Once the new extraction pipeline has run live for ≥2 weeks and we trust the eval numbers, run a one-shot backfill over historical `memories` to populate `health_metrics` and `health_episodes` from past utterances. This is explicitly a Wave A → Wave B transition activity, not a Wave A deliverable.

### D7. Migrations follow the existing rule

Per the standing project rule (and `migrations/README.md`): every DDL change in Wave A goes through `migrations/postgres/` or `migrations/timescaledb/`, never ad-hoc from app code. New migrations introduced by Wave A:

- `migrations/postgres/025_user_profiles_sensitive_opt_in.up.sql` (Story 3.1)
- `migrations/timescaledb/004_health_metrics.up.sql` (Story 3.2)
- `migrations/timescaledb/005_health_episodes.up.sql` (Story 3.3)

Each with a matching `.down.sql`. Story 3.1's profile-catalog change requires NO DDL (the existing `profile_fields(user_id, category, field_name, field_value JSONB, value_type, last_updated)` table already accepts arbitrary `field_name`s).

---

## Stories

### Story 3.1: Health profile expansion (7 → ~25 structured fields)

- Priority: P0
- Estimate: ~1.5 weeks
- Dependencies: none

**User problem.** The current `health` category captures 7 flat fields, mostly for gifting and dietary safety. Anyone asking the system "who is my doctor, when was my last physical, what are my immunizations, what's my family medical history" gets nothing. The bar for a usable health profile in 2026 is dozens of fields, not seven.

**API contract preserved.** `/v1/profile` and `/v1/profile/health` retain all frozen top-level keys. New fields appear under `profile.health` (existing category). `completeness_pct` numeric value will shift because the denominator grows; key itself unchanged.

**Field catalog (Tier 1 — non-sensitive, counts toward completeness):**

| Field | Type | Example |
|------|------|---------|
| `allergies` *(existing)* | array | `["penicillin", "bees"]` |
| `dietary_needs` *(existing)* | array | `["gluten-free"]` |
| `health_conditions` *(existing — note Epic 1 Story 1.15 destructively restructures this to array-of-objects)* | array of objects | `[{condition, triggers[], severity, onset, management[], status}]` |
| `medications` *(existing — flat array of strings in Wave A; restructured in Story 3.5)* | array | `["ibuprofen", "metformin"]` |
| `clothing_sizes` *(existing)* | object | `{"shirt": "M", "shoe": "10"}` |
| `sensory_preferences` *(existing)* | object | `{"temperature": "cool"}` |
| `vision_correction` *(existing)* | object | `{"type": "myopia", "rx": "-2.5"}` |
| `blood_type` | enum | `"O+"` (one of `A+/A-/B+/B-/AB+/AB-/O+/O-/unknown`) |
| `height_cm` | number | `175` |
| `weight_baseline_kg` | number | `76` *(point-in-time; series goes to 3.2)* |
| `biological_sex` | enum | `"male" / "female" / "intersex" / "prefer_not_to_say"` |
| `primary_care_provider` | object | `{"name": "Dr. Patel", "clinic": "..."}` |
| `specialists` | array of objects | `[{"specialty": "cardiologist", "name": "..."}]` |
| `insurance` | object | `{"provider": "Aetna", "plan": "PPO"}` |
| `immunizations` | array of objects | `[{"vaccine": "MMR", "date": "1985"}, {"vaccine": "COVID", "date": "2025-09"}]` |
| `last_physical_date` | date | `"2025-10-14"` |
| `dental_care_last` | date | `"2026-01-22"` |
| `eye_care_last` | date | `"2025-06-03"` |
| `fitness_baseline` | object | `{"resting_hr": 58, "vo2max": 42, "activity_level": "moderate"}` |
| `sleep_baseline` | object | `{"typical_duration_hr": 7.5, "typical_bedtime": "23:30"}` |
| `devices` | array of objects | `[{"type": "CPAP", "model": "ResMed AirSense 10"}]` |
| `family_medical_history_summary` | text | "Father: heart attack at 55. Mother: T2D at 60." *(structured per-relative goes to Story 3.6)* |
| `exercise` *(introduced by Epic 1 Story 1.19)* | object | `{activities: [...], frequency: ..., last_mentioned: ...}` |

**Field catalog (Tier 2 — sensitive, opt-in only, NOT counted toward completeness):**

| Field | Type |
|------|------|
| `mental_health_history` | array of objects |
| `surgical_history` | array of objects |
| `hospitalizations` | array of objects |
| `substances_baseline` | object — `{alcohol_per_week, caffeine_mg_per_day, tobacco, recreational}` |
| `reproductive_status` | object — pregnancy / menopause / fertility plans |
| `gender_identity` | string |

**Acceptance criteria:**
- [ ] GIVEN `src/services/profile_storage.py:20` WHEN `EXPECTED_PROFILE_FIELDS["health"]` is updated THEN it contains exactly the Tier 1 catalog above (16 *new* fields plus the 7 existing). Tier 2 fields are NOT in `EXPECTED_PROFILE_FIELDS`.
- [ ] GIVEN `src/services/profile_extraction.py` WHEN the prompt is regenerated THEN the `**health**` section enumerates the full Tier 1 field catalog with type hints AND includes at least 6 worked examples (provider, immunization-with-date, family history, sensitive-when-opted-out, sensitive-when-opted-in, height/weight numeric).
- [ ] GIVEN a migration `025_user_profiles_sensitive_opt_in.up.sql` THEN `user_profiles` gains a nullable column `health_sensitive_opt_in BOOLEAN DEFAULT FALSE`. A matching `.down.sql` drops the column.
- [ ] GIVEN a new module-level constant `SENSITIVE_HEALTH_FIELDS` (single source of truth) listing the six Tier 2 field names THEN `store_profile_extractions()` checks the user's `health_sensitive_opt_in` flag and silently drops Tier 2 extractions (logged at `debug` with `extraction_skipped_reason="sensitive_opt_out"`) when the flag is false.
- [ ] GIVEN a new endpoint `POST /v1/profile/health/sensitive_opt_in` accepting `{user_id, opt_in: bool}` THEN it upserts the flag on `user_profiles` and returns the new value. A matching `GET` returns the current value.
- [ ] GIVEN shape validators on the structured fields THEN `POST /v1/profile/field` rejects malformed values with HTTP 400 and a field-specific error: invalid `blood_type` enum, non-numeric `height_cm`, malformed date in `last_physical_date`, malformed object shape in `primary_care_provider`.
- [ ] GIVEN a one-shot script `scripts/recompute_completeness.py` THEN running it iterates every row in `user_profiles` and refreshes `completeness_pct`, `total_fields`, `populated_fields` against the new `EXPECTED_PROFILE_FIELDS["health"]` baseline; existing users' completeness values WILL change and that is documented in the PR description.
- [ ] GIVEN extraction emits a Tier 1 health field with confidence ≥80 THEN it is persisted to `profile_fields`. Below threshold → logged to a new `extraction_review_log` table (additive — added by this story) for offline eval; not persisted to `profile_fields`.
- [ ] GIVEN `GET /v1/profile/health` after a Tier 1 extraction lands THEN the new field appears under `fields` in the response; all frozen top-level response keys remain.

**Edge cases:**
- Existing user has `medications` as a flat array of strings; this story does NOT restructure it (3.5 does). Validators accept the flat-array shape.
- LLM emits a Tier 2 field while the user is opted-out → drop silently, log at debug. Do NOT 4xx or surface to user; the field name itself shouldn't leak via error messages on a per-utterance basis.
- LLM emits a structured object with extra keys (e.g., `primary_care_provider: {name, clinic, phone, fax}`) → validator allows additional keys (object schema is open) but does NOT use them in completeness math.
- `family_medical_history_summary` is a freeform text field; it MUST be marked for deprecation in the field's prompt comment so 3.6 can supersede it cleanly without anyone treating it as canonical.
- `EXPECTED_PROFILE_FIELDS["health"]` collision with Epic 1 Story 1.19's `health.exercise` and Story 1.15's restructured `health.health_conditions` — both are listed as existing in the Tier 1 table above. If Epic 1 lands first, this story inherits both as-is. If Epic 3.1 lands first, this story includes them; Epic 1 then needs no further field-catalog change for those two fields. Sequencing is decided at sprint planning.

**Open questions:**
- How do we communicate the completeness-pct drop to existing users? Release notes? An additive metadata field on `/v1/profile/completeness` describing the baseline shift? Disha to propose at sprint planning.

---

### Story 3.2: Biometric time-series hypertable (`health_metrics`)

- Priority: P0
- Estimate: ~3 weeks
- Dependencies: 3.1 (specifically: the sensitive-opt-in plumbing and the extraction-pipeline conventions)

**User problem.** Quantitative health signals (weight, BP, HR, sleep duration, glucose, mood-1-to-10) currently have nowhere to live. The user says "I weighed 168 today" and the system either drops it on the floor, persists it as a one-off episodic memory ("user said they weighed 168"), or stuffs a single point into a profile field that gets overwritten on the next mention. None of those forms support trend queries, anomaly detection, or correlation with episodes.

**API contract preserved.** This story adds net-new endpoints under `/v1/health/metric*`. No existing `/v1/profile*` endpoint changes. Existing TimescaleDB hypertables (`episodic_memories`, `emotional_memories`, `portfolio_snapshots`) are untouched.

**Schema (full DDL in `migrations/timescaledb/004_health_metrics.up.sql`):**

```sql
CREATE TABLE IF NOT EXISTS health_metrics (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    metric TEXT NOT NULL,             -- weight, hr_resting, mood_self, ...
    value_numeric DOUBLE PRECISION,   -- scalar metrics
    value_text TEXT,                  -- categorical (e.g., pain location)
    unit TEXT NOT NULL,               -- kg, mmHg, bpm, ... (canonical / SI)
    source TEXT NOT NULL,             -- manual, apple_health, oura, whoop, dexcom, inferred
    confidence SMALLINT,              -- 0-100; null for manual
    source_memory_id UUID,            -- link back to the memory that produced this
    metadata JSONB,                   -- {location:"lower back", arm:"left", correlation_id:"..."}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('health_metrics', 'ts', if_not_exists => TRUE);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_health_metric
    ON health_metrics (user_id, ts, metric, source);

CREATE INDEX IF NOT EXISTS idx_health_metrics_user_metric_ts
    ON health_metrics (user_id, metric, ts DESC);

ALTER TABLE health_metrics
    ADD CONSTRAINT chk_confidence_range
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 100),
    ADD CONSTRAINT chk_value_present
        CHECK (value_numeric IS NOT NULL OR value_text IS NOT NULL);

SELECT set_chunk_time_interval('health_metrics', INTERVAL '7 days');

ALTER TABLE health_metrics
    SET (timescaledb.compress,
         timescaledb.compress_orderby = 'ts DESC',
         timescaledb.compress_segmentby = 'user_id, metric');

SELECT add_compression_policy('health_metrics', INTERVAL '30 days');
```

**Metric catalog (v1) — application-layer enum, NOT a DB constraint:**

| Metric | Canonical unit | Notes |
|--------|----------------|-------|
| `weight` | kg | LLM converts lb → kg at ingest |
| `body_fat_pct` | % | |
| `bp_systolic` | mmHg | paired with `bp_diastolic` via `metadata.correlation_id` |
| `bp_diastolic` | mmHg | |
| `hr_resting` | bpm | |
| `hr_walking` | bpm | |
| `hrv_sdnn_ms` | ms | |
| `vo2max` | ml/kg/min | |
| `body_temp` | °C | LLM converts °F → °C |
| `spo2` | % | |
| `glucose` | mg/dL | |
| `sleep_duration` | hours | |
| `sleep_efficiency` | % | |
| `sleep_deep` | minutes | |
| `sleep_rem` | minutes | |
| `steps` | count | |
| `exercise_minutes` | minutes | |
| `active_kcal` | kcal | |
| `water_ml` | ml | LLM converts oz → ml |
| `caffeine_mg` | mg | |
| `mood_self` | 1–10 | unit string `"scale_1_10"` |
| `stress_self` | 1–10 | unit string `"scale_1_10"` |
| `energy_self` | 1–10 | unit string `"scale_1_10"` |
| `pain_self` | 0–10 | unit string `"scale_0_10"`; location in metadata |

(Locked at the application layer in a new `src/services/health_metrics.py::ALLOWED_METRICS` constant — DB column stays free-form `TEXT` so we can add metrics without a migration.)

**Acceptance criteria:**
- [ ] GIVEN migration `004_health_metrics.up.sql` + `.down.sql` THEN they apply cleanly through `migrate.sh`; the up creates the hypertable, indexes, constraints, chunk interval, and compression policy as specified above; the down drops the table.
- [ ] GIVEN a new module `src/services/health_metrics.py` THEN it exposes a `HealthMetricsService` with methods: `record_metric(user_id, ts, metric, value, unit, source, confidence?, source_memory_id?, metadata?)`, `record_batch(rows)`, `query_range(user_id, metric, start, end, agg?)`, `latest(user_id, metric)`, `trend_summary(user_id, metric, window_days)`.
- [ ] GIVEN `ALLOWED_METRICS` constant (single source of truth) THEN `record_metric()` rejects (HTTP 400 / `ValueError`) on (a) unknown metric name, (b) unit mismatch with the canonical unit, (c) value outside the documented sanity range (e.g., `weight` > 500 kg, `bp_systolic` < 50 or > 280 mmHg).
- [ ] GIVEN repeat insertion of the same `(user_id, ts, metric, source)` THEN the row is UPDATEd in place (UPSERT semantics on the unique index), not duplicated.
- [ ] GIVEN a new router `src/routers/health.py` registered in `src/app.py` THEN it exposes: `POST /v1/health/metric` (single), `POST /v1/health/metrics/batch` (≤1000 rows), `GET /v1/health/metric?user_id=&metric=&start=&end=&agg=` (returns time-series; `agg` ∈ {`raw`, `daily_avg`, `daily_min`, `daily_max`, `weekly_avg`}), `GET /v1/health/metric/latest?user_id=&metric=`.
- [ ] GIVEN the LLM extraction prompt is extended (`src/services/profile_extraction.py` or a new `src/services/health_extraction.py`) THEN it emits a new top-level array `health_metrics` containing objects `{metric, value, unit, ts?, confidence, source_memory_id}` for quantitative health utterances. The prompt MUST include 12 worked examples covering each metric class (numeric + unit-converted + self-rated + paired-BP).
- [ ] GIVEN unit conversion in the prompt THEN the LLM is instructed to convert at extraction time to the canonical unit; the response's `unit` field always matches the canonical for that metric. Mis-conversions are caught by the service-layer unit-validator AC above (rejected with HTTP 400 / logged to `extraction_review_log`).
- [ ] GIVEN `run_unified_ingestion()` in `src/memory_orchestrator/ingestion.py:80` THEN after profile extraction completes, the new `health_metrics` extractions are dispatched to `HealthMetricsService.record_batch()`. Failures on individual rows (validator rejection) log + skip; they do NOT abort the ingestion run.
- [ ] GIVEN `record_metric()` for `weight` or `height` (when emitted as a metric, not a profile field) THEN a downstream hook calls `profile_storage` to refresh `weight_baseline_kg` / `height_cm` on `profile_fields` to the **latest** point. (One-way sync: metrics → profile baseline. The profile baseline never writes back to metrics.)
- [ ] GIVEN paired BP utterance "BP was 122/78" THEN extraction emits TWO `health_metrics` rows (`bp_systolic`, `bp_diastolic`) with identical `ts` AND identical `metadata.correlation_id` (UUID). Documented as the canonical pattern for any future paired/multi-component metric.
- [ ] GIVEN a metric extraction with `confidence < 70` THEN it is NOT persisted to `health_metrics`; it is appended to `extraction_review_log` (the table introduced in Story 3.1) for offline eval.
- [ ] GIVEN no parent Langfuse span is active AND `record_batch()` writes to the hypertable THEN the embedding/LLM observations in the upstream extraction call remain correctly nested under the existing `unified_memory_ingestion` root span (Epic 2 invariant — do NOT regress).
- [ ] GIVEN Murat's regression suite THEN integration tests cover: roundtrip insert/query, idempotency on repeated `(user, ts, metric, source)`, unit-validator rejection paths, paired-BP correlation_id presence, lb→kg conversion via extraction, oz→ml conversion via extraction, °F→°C conversion via extraction, low-confidence routing to review log, `/v1/health/metric` GET range queries with each `agg` value, sensitive-opt-out interaction (none of the v1 metrics are sensitive — confirm no Tier 2 metric leaks).

**Edge cases:**
- "I weighed 168" — ambiguous unit (lb? kg?). LLM prompt MUST instruct: assume lb when value is between 80 and 400 with no unit; assume kg when value is between 35 and 200 with no unit; ambiguous overlap (80–200) → assume lb in the US context (configurable per user later, but the global default is documented and tested).
- "I slept 6 hours last night" — timestamp policy. LLM emits `ts` as the morning-of-mention's 06:00 local time. Documented in the prompt.
- "BP was 122/78 at the doctor today" — extraction emits BOTH rows with the SAME `correlation_id`. Test asserts this.
- "Heart rate is normally around 60" — narrative baseline, not a point-in-time measurement. Extraction should route this to `fitness_baseline.resting_hr` on `profile_fields`, NOT to `health_metrics`. Prompt examples must cover this disambiguation.
- "Feeling pretty energetic today" — qualitative, no number. Do NOT emit a `health_metric`. If the user explicitly says "energy is like 7 out of 10," then emit `energy_self=7`.
- Backfill from historical memories is OUT of scope per D6.
- The metric column is free-form TEXT at the DB layer (per architectural intent) — adding new metrics is a constant-update + prompt-update, no DB migration. Trade-off accepted.

**Open questions:**
- Should `value_text` be used for any v1 metric, or is it purely future-proofing? Pain location goes in `metadata`, not `value_text`. Recommend leaving the column in the schema as future-proofing but documenting "no v1 metric uses `value_text`."
- Sanity-range bounds: who owns the table of `(metric, min, max)`? Proposal: lives in `ALLOWED_METRICS` as a Pydantic spec. David to confirm at implementation.

---

### Story 3.3: Symptom & episode logs (`health_episodes`)

- Priority: P0
- Estimate: ~2.5 weeks
- Dependencies: 3.2 (shares the LLM extraction extension and the new-router convention)

**User problem.** Symptoms are events with onset, severity, location, duration, triggers, relief attempts, and resolution. Today they either disappear or land in `episodic_memories` as unstructured prose. No way to answer "how often do I get headaches," "what triggers my back flares," "have I had this stomach pain before." Pattern detection is impossible. Pre-doctor-visit summary "here's what I've experienced since I last saw you" is impossible.

**API contract preserved.** Net-new endpoints under `/v1/health/episode*`. No existing `/v1/profile*` or `/v1/health/metric*` (from 3.2) endpoint changes. No existing TimescaleDB hypertable changes.

**Schema (full DDL in `migrations/timescaledb/005_health_episodes.up.sql`):**

```sql
CREATE TABLE IF NOT EXISTS health_episodes (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,                     -- NULL = still open
    episode_type TEXT NOT NULL,               -- symptom, illness, injury, allergic_reaction, chronic_flare, mental_health_episode
    subtype TEXT,                             -- "headache", "migraine", "cold", ... (free-form; normalized in code)
    severity_max SMALLINT,                    -- 0-10, observed maximum
    severity_current SMALLINT,                -- 0-10, mutable while open
    body_location TEXT[],                     -- ["lower back", "left side"]
    triggers TEXT[],                          -- ["stress", "dehydration"]
    relief_attempts JSONB,                    -- [{"action":"ibuprofen","ts":"...","worked":true}, ...]
    related_metric_ids UUID[],                -- references health_metrics(id) co-occurring in window
    source_memory_ids UUID[],                 -- multiple memories can extend an episode
    notes TEXT,
    metadata JSONB,                           -- {auto_closed: bool, previous_episode_id: uuid, ...}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('health_episodes', 'started_at', if_not_exists => TRUE);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_health_episodes_id
    ON health_episodes (id, started_at DESC);

-- Critical index for open-episode matching during update/close reconciliation
CREATE INDEX IF NOT EXISTS idx_health_episodes_open
    ON health_episodes (user_id, episode_type, subtype, started_at DESC)
    WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_health_episodes_user_time
    ON health_episodes (user_id, started_at DESC);

ALTER TABLE health_episodes
    ADD CONSTRAINT chk_severity_max
        CHECK (severity_max IS NULL OR severity_max BETWEEN 0 AND 10),
    ADD CONSTRAINT chk_severity_current
        CHECK (severity_current IS NULL OR severity_current BETWEEN 0 AND 10),
    ADD CONSTRAINT chk_episode_time_order
        CHECK (ended_at IS NULL OR ended_at >= started_at);

SELECT set_chunk_time_interval('health_episodes', INTERVAL '30 days');

ALTER TABLE health_episodes
    SET (timescaledb.compress,
         timescaledb.compress_orderby = 'started_at DESC',
         timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('health_episodes', INTERVAL '90 days');
```

**Episode types (locked enum, v1):**
- `symptom` (headache, fatigue, nausea, dizziness, abdominal pain, ...)
- `illness` (cold, flu, COVID, food poisoning)
- `injury` (sprain, cut, fall)
- `allergic_reaction`
- `chronic_flare` (for users with chronic conditions — migraine, IBS, eczema flare)
- `mental_health_episode` (anxiety attack, depressive episode) — **gated by `health_sensitive_opt_in`** (Story 3.1's plumbing)

**Subtypes are FREE-FORM TEXT, normalized in application code** via a maintained lookup table in `src/services/health_episodes.py::SUBTYPE_NORMALIZATION` (e.g., "headache" / "head pain" / "head ache" → `"headache"`). This avoids the LLM-emits-everything-slightly-different fragmentation pitfall.

**Acceptance criteria:**
- [ ] GIVEN migration `005_health_episodes.up.sql` + `.down.sql` THEN they apply cleanly through `migrate.sh`; the up creates the hypertable, two indexes (including the partial index on open episodes), check constraints, chunk interval, and compression policy as specified.
- [ ] GIVEN a new module `src/services/health_episodes.py` THEN it exposes a `HealthEpisodesService` with methods: `start_episode(user_id, started_at, episode_type, subtype, severity?, body_location?, triggers?, source_memory_id?)`, `update_episode(episode_id, severity_current?, body_location?, triggers?, relief_attempts?, source_memory_id?)`, `close_episode(episode_id, ended_at, source_memory_id?)`, `find_open_episode(user_id, episode_type, subtype, window_hours)`, `list_episodes(user_id, status?, episode_type?, since?, limit?)`, `pattern_summary(user_id, episode_type, subtype, lookback_days)`.
- [ ] GIVEN `find_open_episode()` THEN it queries the partial index `idx_health_episodes_open` and returns the most recent open episode matching `(user_id, episode_type, subtype)` started within `window_hours`. Default windows: 72h for `symptom`, 14 days for `chronic_flare`, 48h for `allergic_reaction`, 30 days for `illness`, 30 days for `injury`. Encoded in a `WINDOW_DEFAULTS` constant.
- [ ] GIVEN `update_episode()` THEN it appends to `source_memory_ids[]`, updates `severity_current`, updates `severity_max` if exceeded, merges `body_location[]` and `triggers[]` (de-duplicated), appends to `relief_attempts[]` JSONB array, and sets `updated_at`.
- [ ] GIVEN `close_episode()` THEN it sets `ended_at` and `updated_at`; the partial index `idx_health_episodes_open` reflects the closure immediately (test asserts `find_open_episode()` no longer returns it).
- [ ] GIVEN a new router (extending `src/routers/health.py` from 3.2) THEN it exposes: `POST /v1/health/episode`, `PATCH /v1/health/episode/{id}` (partial update; closes when `ended_at` provided), `GET /v1/health/episode?user_id=&status=open|closed|all&type=&since=&limit=`, `GET /v1/health/episode/patterns?user_id=&type=&subtype=&lookback_days=`.
- [ ] GIVEN the LLM extraction prompt is extended THEN it emits a new top-level array `health_episode_events` containing objects `{action: "start" | "update" | "close" | "none", episode_id?, episode_type, subtype, severity?, severity_current?, body_location?, triggers?, relief_attempt?, ended_at?, source_memory_id}`. The prompt includes ≥10 worked examples (start, update with severity bump, close, relief attempt, ambiguous-skip, false-positive-skip-metaphor, mental_health_episode while opted-out, multiple-open-episode disambiguation).
- [ ] GIVEN `run_unified_ingestion()` dispatches `health_episode_events` THEN: `action=start` → `start_episode()`; `action=update|close` with an explicit `episode_id` → operate on that ID (404 → log + skip); `action=update|close` without `episode_id` → `find_open_episode()` first, then operate on the result (none found → log + skip, do not silently auto-create); `action=none` → no-op.
- [ ] GIVEN the LLM prompt receives **recent open episodes** as context (last 7 days, max 10 episodes) THEN it can return explicit `episode_id` references in `update`/`close` actions to disambiguate. The prompt MUST document this and the implementation MUST pass the context.
- [ ] GIVEN multiple open episodes match `(episode_type, subtype)` within window THEN `find_open_episode()` returns the most recent; an `ambiguous_match=true` flag is set in the action result and the situation is logged at `warning`. The action still applies (most-recent wins) — but the warning surfaces the case for human review.
- [ ] GIVEN `pattern_summary()` THEN it returns: `count`, `count_by_day_of_week`, `count_by_hour_of_day`, `top_triggers` (top 5 from `triggers[]`), `top_relief_actions` (top 5 from `relief_attempts[].action` where `worked=true`), `avg_duration_hours`, `avg_severity_max`, `co_occurrence_with_metrics` (for each metric in `ALLOWED_METRICS`, percentage of episodes where a low/high reading of that metric occurred within ±24h — e.g., "of 7 headaches, 6 happened on days with sleep_duration < 6h").
- [ ] GIVEN `episode_type=mental_health_episode` AND the user's `health_sensitive_opt_in = false` THEN extraction silently drops the event (logged at debug); the row is NEVER written.
- [ ] GIVEN an episode is open for >14 days with no updates THEN a daily cron job (`scripts/auto_close_stale_episodes.py` or a node in a maintenance graph — implementation choice) sets `ended_at = updated_at + window`, `metadata.auto_closed = true`. Documented as the canonical pattern; the auto-close marker distinguishes it from a user-confirmed close.
- [ ] GIVEN false-positive guard examples in the extraction prompt ("the headache scene in the movie", "this meeting gave me a headache" — metaphorical) THEN Murat's eval set includes them with `action=none` as the expected output.
- [ ] GIVEN integration tests THEN they cover: start → update → close lifecycle for a single episode; start two-of-same-type → update with ambiguous match → warning logged; close non-existent episode_id → logged-and-skipped, no 5xx; sensitive opt-out drop; pattern_summary with seeded fixtures (≥10 episodes across 60 days); auto-close cron behavior.

**Edge cases:**
- "I've had a headache since this morning" while a different headache was closed 5 hours ago → `action=start` (new episode), `metadata.previous_episode_id = <closed-one>` for clustering. Confirm in test fixtures.
- "It's getting worse" with two open episodes (headache + back pain) → LLM ideally returns explicit `episode_id`; if it cannot, the service applies most-recent-wins AND logs `ambiguous_match=true`. We do NOT auto-create a "general worsening" episode.
- Relief attempt without an open episode ("took some ibuprofen") → `action=none`. Do NOT auto-create an episode just because a relief verb was mentioned.
- "Headache scene in the movie was intense" → `action=none`. Verified by eval.
- LLM emits an unknown subtype ("cluster headache") → it lands in the table as-is; `SUBTYPE_NORMALIZATION` adds it to the canonical list in a follow-up code change (subtype taxonomy is intentionally low-friction to grow).
- Severity emitted as text ("a really bad headache") → coerce to a 0-10 number per prompt instruction: vague intensifiers map to 6-7, "mild" → 3, "moderate" → 5, "severe" → 8, "10/10" preserved literally. Documented in prompt.
- `related_metric_ids[]` correlation — populated by a co-occurrence pass at episode-close time (within ±24h of `started_at`..`ended_at`). For open episodes, populated at `pattern_summary()` query time only. (Avoids the write-amplification cost on every metric insert.)
- Compression policy on `health_episodes` is 90 days vs `health_metrics`'s 30 days because episodes are accessed more recently (open-episode reconciliation needs the partial index to stay performant).

**Open questions:**
- Should `chronic_flare` be a distinct top-level `episode_type` or a subtype of `symptom`? Today's modeling keeps it as a distinct type because the matching window differs (14 days vs 72h). Parminder to confirm at design review.
- Auto-close window — fixed 14 days, or configurable per subtype? Recommend fixed for v1; add per-subtype configuration once we see real data.
- Relationship to `emotional_memories`: a `mental_health_episode` close-cousins with the emotional layer. Today they stay separate (emotional_memories tracks valence/arousal of conversational moments; mental_health_episodes track bounded clinical episodes). Cross-linking is a Wave C enhancement.

---

## Sequencing & dependency map

```
Story 3.1 (P0, ~1.5w, no deps)
   │
   │ unblocks: sensitive opt-in plumbing, EXPECTED_PROFILE_FIELDS expansion conventions
   ▼
Story 3.2 (P0, ~3w, depends on 3.1)
   │
   │ unblocks: shared LLM extraction extension pattern, new /v1/health/* router, hypertable migration template
   ▼
Story 3.3 (P0, ~2.5w, depends on 3.2)
   │
   ▼ Wave A complete
```

Linear sequencing is deliberate — each story introduces a load-bearing pattern reused by the next. Parallelization would force premature consolidation of the LLM extraction extension and double the review cost. Wave A ships in ~7 weeks of focused work + ~1 week of cross-story eval and polish.

## Known risks

- **Completeness shock** — `completeness_pct` numeric value will shift for every user when Story 3.1 lands (16 new Tier 1 fields, recomputed denominator). Same risk profile as Epic 1 v2; mitigated by release-notes communication.
- **LLM extraction quality drift** — the prompt grows by ~3 new sections (Tier 1 health, health_metric kind, health_episode_event kind). Adding too many output kinds in one ingestion call risks degrading the *existing* extractions. Mitigation: a pre/post eval bucket of the existing extraction kinds (profile, episodic, emotional) MUST hold its numbers; if it regresses by >5pp on the eval set, the prompt change is rolled back and we revisit Decision D1 (single call vs parallel calls).
- **Unit-conversion errors** — pound/kilogram and Fahrenheit/Celsius conversions are the most likely LLM mistake. The validator catches gross errors; the eval set must cover both directions.
- **Open-episode reconciliation ambiguity** — multi-open-episodes case is rare but ugly. The "most-recent wins + log warning" policy is intentionally conservative; iterate based on real frequency.
- **Sensitivity drift** — `mental_health_episode` is the only Tier 2 surface in 3.3 (Tier 2 profile fields in 3.1, no Tier 2 metrics in 3.2). The opt-in check must be tested at every entry point — extraction-side AND service-side (defense in depth).
- **Schema growth in metric/subtype taxonomy** — both `metric` (in `health_metrics`) and `subtype` (in `health_episodes`) are free-form TEXT columns governed by application-layer constants. Avoid silent enum drift by including a unit test that asserts every value the LLM is allowed to emit appears in `ALLOWED_METRICS` / `SUBTYPE_NORMALIZATION`.
- **Backfill temptation** — once 3.2 and 3.3 are live, it will be tempting to backfill metrics/episodes from historical `episodic_memories`. Per Decision D6, defer this to the Wave A → Wave B transition. Premature backfill amplifies extraction errors at scale.

## Out of scope (explicitly deferred from Wave A — for clarity, not a comprehensive list)

- Wearable / external-source integrations (Apple Health, Oura, Whoop, Dexcom, Garmin) — Wave B Story 3.7.
- Medication dosing schedule + adherence tracking + reminder integration with `scheduled_intents` — Wave B Story 3.5.
- Structured family medical history per-relative — Wave B Story 3.6.
- Healthcare events log (appointments, procedures, hospitalizations, vaccinations as events not profile state) — Wave B Story 3.4.
- Lab results / biomarker panels with reference ranges — Wave C Story 3.9.
- PHQ-9 / GAD-7 / WHO-5 structured scales + daily mood logs — Wave C Story 3.8.
- Sleep ↔ mood correlation engine, anomaly detection, trend alerts — Wave C Story 3.10.
- Encryption-at-rest with separate KMS key for `health_*` tables, audit log of read access, export-all / delete-all endpoints — Wave C Story 3.11.
- Health-aware retrieval (auto-pulling recent sleep + activity when user says "I'm feeling tired", auto-pulling vaccinations when user mentions travel) — Wave C Story 3.12.
- UI surfacing of new health data in `Profile.tsx` — defer to post-Wave-A UX pass; not blocked by Wave A but not in scope.
