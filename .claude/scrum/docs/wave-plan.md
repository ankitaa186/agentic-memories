# Epic 1 — Wave Plan (v2, 19 stories)

Maps Parminder's R1→R4 rollout into concrete wave assignments. A "wave" is a batch of stories that can start together. A wave kicks off when its entry dependencies are `done`.

## Reading this doc
- **Wave N** starts when all stories from preceding waves (that it depends on) are `done`.
- **Parallel group** = stories spawned together in one `Agent` batch; no shared-file conflicts.
- **Sequential chain** = stories that touch the same file (usually `PROFILE_EXTRACTION_PROMPT`); merge conflicts force serialization even when business logic is independent.

## Summary table

| Wave | Stories | Parallel | Sequential chain | Deps cleared |
|---|---|---|---|---|
| **1 — Foundations** | 1.1, 1.3, 1.6 | all 3 parallel | — | none |
| **2 — Pipeline + migrations** | 1.2, 1.4, 1.7, 1.14, 1.16 (parallel) + 1.9, 1.10, 1.13, 1.15, 1.19 (sequential prompt chain) | 5 parallel + 5 sequential | prompt chain | Wave 1 |
| **3 — Stacked logic + remaining prompt edits** | 1.5, 1.8, 1.17 (parallel) + 1.11, 1.12 (sequential prompt chain, extends Wave 2's chain) | 3 parallel + 2 sequential | prompt chain continues | Wave 2 |
| **4 — UI** | 1.18 | solo | — | Wave 3 |

**Total: 19 stories across 4 waves.** Wave 1 is small and fast (unblocks everything). Wave 2 is the widest (10 stories, 5 parallel + 5 sequential). Wave 3 resolves the stacked-logic stories. Wave 4 is UI cleanup.

---

## Wave 1 — Foundations (3 stories, fully parallel)

Nothing depends on anything outside the wave. All three can spawn together.

| Story | Title | Why it's Wave 1 | Files touched |
|---|---|---|---|
| **1.1** | Stale `TOTAL_EXPECTED_FIELDS` comment | No deps, trivial, pays off all v2 denominator math | `src/services/profile_storage.py`, new test |
| **1.3** | Three-flag harness | Unblocks every flag-gated story (1.2, 1.4, 1.12) | new `src/config/profile_flags.py`, router mount |
| **1.6** | `profile_fields_history` + `ProfileHistoryService` + backfill | Unblocks all 4 destructive migrations (1.13, 1.14, 1.15, 1.19) and 1.16 read endpoint | new migration, new service, backfill script |

**Spawn strategy:** one `Agent` batch with David-1.1, David-1.3, David-1.6.
**Wait condition:** all three reach `done` (review + test passed).

---

## Wave 2 — Pipeline observability + destructive data migrations (10 stories)

Kicks off after Wave 1 done. Two sub-groups because five of these stories touch the same file.

### Wave 2-parallel (5 stories, spawn in one batch)

No shared-file conflicts. All independent business logic.

| Story | Title | Deps | Shared file risk |
|---|---|---|---|
| **1.2** | Wire extraction → `profile_confidence_scores` | 1.3 | new `ProfileConfidenceService`; edits `profile_storage.py` (add call after source insert) |
| **1.4** | Contradiction detection on extraction | 1.3 | new `profile_field_conflicts` table; edits `profile_storage.py` (add pre-upsert diff) |
| **1.7** | Per-category freshness in `/completeness` | none | edits `profile_storage.py::get_completeness_details`, `profile.py` response |
| **1.14** | Allergies null-vs-empty migration | 1.6 | new migration script; no code changes |
| **1.16** | `GET /v1/profile/history` endpoint | 1.6 | adds endpoint to `profile.py` (non-conflicting) |

Note: 1.2, 1.4, 1.7 all edit `src/services/profile_storage.py`. Risk is lower than prompt edits because changes land in different functions. **Coordination**: Davids must pull latest before each function-scope edit. If conflicts arise, harpreet can rebase at review time.

### Wave 2-sequential (5 stories, single chain)

All touch `PROFILE_EXTRACTION_PROMPT` in `src/services/profile_extraction.py`. Parallel spawning would cause last-write-wins overwrite.

Order (grouped by prompt section affected so each David knows exactly what block they own):

```
1.9  (relationships)         → adds new category block to prompt
1.10 (present-tense fields)  → extends personality category block
1.13 (dietary guard)         → refines health.dietary_needs wording + food_preferences cross-ref
1.15 (health_conditions)     → changes health_conditions schema in prompt
1.19 (exercise recategorization) → moves fitness vocab from interests to health.exercise, adds example
```

**Spawn strategy:** one David at a time in this order. Each David is told: "1.9 is merged at commit SHA X; you are editing against that base." Prevents merge-conflict churn.

**Why this order:**
- 1.9 first: adds a whole new category; biggest structural change; reviewer can assess the template.
- 1.10 second: adds fields to existing category; extends a pattern.
- 1.13 third: narrows wording — easier to land after 1.10 clarifies personality vs preferences.
- 1.15 fourth: reshapes a single field's schema; isolated edit.
- 1.19 last: cross-cuts interests + health, depends on the health section already being stable from 1.15.

---

## Wave 3 — Stacked logic + remaining prompt edits (5 stories)

Depends on Wave 2 outputs (confidence service, contradiction table, flag harness).

### Wave 3-parallel (3 stories)

| Story | Title | Deps | Touches |
|---|---|---|---|
| **1.5** | Confidence-weighted conflict resolution | 1.2, 1.4 | `profile_storage.py` upsert path; `profile_field_conflicts` resolution_status |
| **1.8** | Temporal decay factor in composite confidence | 1.2, 1.7 | `ProfileConfidenceService` formula + new column `temporal_decay_factor` on `profile_confidence_scores` |
| **1.17** | `GET /v1/profile/conflicts` endpoint | 1.4 | `profile.py` new endpoint |

### Wave 3-sequential (2 stories, extends Wave 2's prompt chain)

| Story | Title | Deps | Extends chain from |
|---|---|---|---|
| **1.11** | How-fields (`decision_style`, `growth_edges`, `energy_recovery_patterns`) | 1.10 | Wave 2's prompt chain (needs 1.10 merged) |
| **1.12** | Inferred extraction | 1.2 | Prompt posture shift; lands after 1.11 for coherence |

**Spawn strategy:** 1.5, 1.8, 1.17 parallel; 1.11 sequential (after Wave 2 chain fully merged); 1.12 after 1.11.

---

## Wave 4 — UI (1 story)

Depends on Wave 3 because Profile.tsx consumes new endpoints (`/history`, `/conflicts`) and renders new data (relationships, structured health_conditions, confidence metadata, freshness badges).

| Story | Title | Deps | Touches |
|---|---|---|---|
| **1.18** | Profile.tsx refresh — depth, freshness, conflicts | 1.2, 1.7, 1.9, 1.10, 1.11, 1.15, 1.16, 1.17, 1.19 | `ui/src/pages/Profile.tsx`, possibly new components |

**Spawn strategy:** one David, solo. Frontend-only; no merge conflicts to manage.

---

## Dependency graph (visual)

```
Wave 1 (foundations)
├── 1.1 ──────────────────────────────────────────────────┐
├── 1.3 ─┬─ 1.2 ─┬─ 1.5  (Wave 3)                         │
│        │       ├─ 1.8  (Wave 3, needs 1.7 too)          │
│        │       └─ 1.12 (Wave 3, prompt chain)           │
│        └─ 1.4 ─┬─ 1.5  (Wave 3)                         │
│                └─ 1.17 (Wave 3)                         │
├── 1.6 ─┬─ 1.13 ─┐                                       │
│        ├─ 1.14 ─┤                                       │
│        ├─ 1.15 ─┼─ all → 1.18 (Wave 4, UI)              │
│        ├─ 1.19 ─┤                                       │
│        └─ 1.16 ─┘                                       │
├── 1.7 ─── 1.8 (Wave 3)                                  │
├── 1.9 ────────── 1.18                                   │
└── 1.10 ─ 1.11 ── 1.18                                   │
                                                          │
All Wave 3 outputs ───────────────────────────────────────┤
                                                          ▼
                                                       1.18
```

---

## Coordination notes

1. **Prompt edit sequencing is non-negotiable.** `PROFILE_EXTRACTION_PROMPT` is a long single string in `profile_extraction.py`. Parallel edits will stomp each other. Plan: assign the prompt chain to a single David across multiple serial turns, OR use different Davids per story but serialize their spawns (wait for prior to merge before starting next).

2. **Migration ordering within Wave 2.** Even though 1.13/1.14/1.15/1.19 are "parallel", they each write to `profile_fields_history` with `change_type='migration'`. They should be run against the DB sequentially (after code merge) to keep history timeline clean. Code implementation can be parallel; migration execution must be serial.

3. **Harpreet review bandwidth.** 10 Wave 2 stories will pile up at review. Expect to spawn Harpreet in batches of 3–4. Murat similar for testing.

4. **Completeness number shift.** Ships visibly at Wave 2 when `EXPECTED_PROFILE_FIELDS` grows (1.9, 1.10, 1.19 each add). Release-note at Wave 2 close, not at Epic close.

5. **Rollback boundary.** If anything goes sideways mid-epic, Wave 1 is safe to leave in place (flag harness at default-off = no behavior change; history table empty = no harm; comment fix is cosmetic). First "point of no easy return" is Wave 2's destructive migrations (1.13/1.14/1.15/1.19). Before starting Wave 2, take a DB snapshot.

---

## Gate check before each wave starts

| Gate | Check |
|---|---|
| Wave 1 → Wave 2 | All 3 Wave 1 stories `done`. DB snapshot taken. Flag matrix defaults off. |
| Wave 2 → Wave 3 | All 10 Wave 2 stories `done`. Migrations executed in order. `completeness_pct` numbers on sample users sanity-checked (expected to have shifted). |
| Wave 3 → Wave 4 | All 5 Wave 3 stories `done`. `/history` and `/conflicts` endpoints smoke-tested. |
| Wave 4 → Epic close | 1.18 `done`. E2E user flow verified in the UI. Release notes drafted (completeness % change, new fields, new UI). |
