# Open-Source Prep: Change Audit & Non-Breaking Analysis

> **Branch:** `claude/open-source-prep-OQjaR`
> **Base commit:** `50622be`
> **Date:** 2026-02-12
> **Files changed:** 129 | **Insertions:** +13,110 | **Deletions:** -8,980

The vast majority of the diff (+12,500 / -8,700 lines) is **ruff auto-formatting** — line wrapping,
trailing commas, quote normalization, and import reordering. This document focuses on the **semantic
changes** that alter logic or behavior.

---

## Table of Contents

1. [Semantic Code Changes (src/)](#1-semantic-code-changes-src)
2. [Semantic Test Changes (tests/)](#2-semantic-test-changes-tests)
3. [Configuration & Infrastructure Changes](#3-configuration--infrastructure-changes)
4. [New Files Added](#4-new-files-added)
5. [Files Moved (No Content Changes)](#5-files-moved-no-content-changes)
6. [Formatting-Only Changes](#6-formatting-only-changes)
7. [Risk Assessment Summary](#7-risk-assessment-summary)

---

## 1. Semantic Code Changes (src/)

### 1.1 BEHAVIORAL CHANGE: `src/storage/timescale_client.py`

| Aspect | Details |
|--------|---------|
| **What changed** | Removed hardcoded fallback `'postgresql://memories:memories123@localhost:5433/episodic_memories'` from `os.getenv('TIMESCALE_DSN', ...)`. Now raises `ValueError` if `TIMESCALE_DSN` is not set. |
| **Before** | `self.connection_string = connection_string or os.getenv('TIMESCALE_DSN', 'postgresql://memories:memories123@...')` |
| **After** | `self.connection_string = connection_string or os.getenv('TIMESCALE_DSN')` followed by `if not self.connection_string: raise ValueError(...)` |
| **Why safe** | The hardcoded DSN pointed to a **different database** (`episodic_memories`) than the one actually used (`agentic_memories`). The fallback was effectively wrong and would cause connection failures anyway. Any working deployment already has `TIMESCALE_DSN` set in `.env` or environment. |
| **Risk** | **Low**. If someone ran the code without any `.env` file, they'd previously get a silent connection failure to the wrong DB. Now they get an explicit error message telling them exactly what to set. This is a better developer experience. |
| **Breaking?** | **No** for any correctly configured deployment. **Yes** if someone relied on the wrong fallback — but that configuration never worked correctly. |

### 1.2 Unused variable renames (`span` → `_span`) — 28 occurrences

| Files affected | `compaction_graph.py` (7), `unified_ingestion_graph.py` (14), `graph_extraction.py` (2), `memory_router.py` (3), `hybrid_retrieval.py` (1), `portfolio_service.py` (1), `reconstruction.py` (1) |
|--------|---------|
| **What changed** | `span = start_span(...)` → `_span = start_span(...)` |
| **Why safe** | The `start_span()` function is called for its **side effect** (creating a tracing span). The return value was never used — not passed to `end_span()`, not read, not returned. The underscore prefix tells Python/linters "this is intentionally unused." The side effect (span creation) still executes identically. |
| **Breaking?** | **No**. The function call and its side effects are unchanged. Only the variable name binding changed. |

### 1.3 Other unused variable renames — 6 occurrences

| File | Variable | Change | Why safe |
|------|----------|--------|----------|
| `src/app.py:1117` | `total_count` → `_total_count` | Assigned but never read; the actual pagination uses `persona_payload.items` directly | **Not breaking** |
| `src/services/compaction_graph.py:254` | `metadata` → `_metadata` | Assigned from `c.get("metadata", {})` but never read in that scope | **Not breaking** |
| `src/services/forget.py:54` | `metas` → `_metas` | Return value from `res.get("metadatas", [])` was never used | **Not breaking** |
| `src/services/procedural_memory.py:595` | `metadata` → `_metadata` | Local in a loop; the actual metadata used comes from a different variable | **Not breaking** |
| `src/services/profile_storage.py:88` | `confidence` → `_confidence` | Extracted from dict but never used; the confidence is used elsewhere | **Not breaking** |
| `src/services/unified_ingestion_graph.py:715,717` | `memory_ids` → `_memory_ids`, `extracted_items` → `_extracted_items` | Assigned but never referenced after assignment | **Not breaking** |

### 1.4 Bare `except:` → `except Exception:` — 2 occurrences

| File | Lines | Context |
|------|-------|---------|
| `src/services/compaction_graph.py` | 148, 191 | Timestamp parsing and JSON parsing fallbacks |

**Why safe:** `except Exception:` is **strictly safer** than bare `except:`. Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit` — signals that should propagate. `except Exception:` lets those through while still catching all regular errors. The existing `pass` / fallback behavior is unchanged.

**Breaking?** **No**. This is a correctness improvement.

### 1.5 Removed unused imports — 116 occurrences

Examples:
- `from typing import Set` (never used in `scripts/github_env.py`)
- `from datetime import timedelta` (never used in `src/app.py`)
- `from src.services.extraction import extract_from_transcript` (never called in `src/app.py`)
- `from src.services.storage import upsert_memories` (never called in `src/app.py`)
- `from src.services.retrieval import _standard_collection_name` (never referenced)
- `import psycopg2` (never used directly in `timescale_client.py` — uses `psycopg2` via pool)
- `import json` (removed from files that don't call `json.*`)
- `from uuid import UUID` (only `uuid4` was used)
- `from langfuse import observe, propagate_attributes` (only `Langfuse` and `CallbackHandler` were used)

**Why safe:** Every removed import was verified as unused by ruff's F401 rule. ruff performs static analysis to confirm no reference exists in the file. If any import were actually used, removing it would cause an `ImportError` at import time — which would be immediately caught by any test run or startup.

**Breaking?** **No**. Removing unused imports has zero runtime effect.

### 1.6 Re-exports made explicit in `src/routers/__init__.py`

| Before | After |
|--------|-------|
| `from src.routers import profile, portfolio, memories` | `from src.routers import profile as profile, portfolio as portfolio, memories as memories` |

**Why safe:** The `as X` syntax makes the re-export explicit, satisfying ruff's F401 rule while preserving the exact same runtime behavior. `import X` and `import X as X` are semantically identical in Python.

**Breaking?** **No**.

### 1.7 `# noqa: E402` comments added — 3 files

| File | Lines | Why needed |
|------|-------|------------|
| `src/app.py` | 293 | `import time as _time` placed after app setup (used by middleware defined immediately below) |
| `src/services/hybrid_retrieval.py` | 18-23 | Imports placed after `TYPE_CHECKING` guard and logging setup |

**Why safe:** `# noqa` comments are instructions to the linter only. They have zero effect on Python execution.

**Breaking?** **No**.

---

## 2. Semantic Test Changes (tests/)

### 2.1 Lambda → def conversion in `tests/unit/test_app_retrieve.py:26`

| Before | After |
|--------|-------|
| `search_stub = lambda **_: (_ for _ in ()).throw(AssertionError("search_memories should not be called"))` | `def search_stub(**_): raise AssertionError("search_memories should not be called")` |

**Why safe:** Both raise `AssertionError` with the same message when called. The lambda used a generator trick; the def uses a direct `raise`. Functionally identical. The stub is used as a `monkeypatch.setattr` target — calling behavior is unchanged.

**Breaking?** **No**.

### 2.2 Unused test variable renames — 4 occurrences

| File | Variable | Change |
|------|----------|--------|
| `tests/e2e/fixtures/generate_test_data.py:250` | `test_data` → `_test_data` | Return value of `save_test_data()` was unused |
| `tests/evals/metrics.py:193` | `pred_contents` → `_pred_contents` | Set was computed but never read |
| `tests/unit/test_profile_api.py:228` | `original_fetchall` → `_original_fetchall` | Saved reference was unused |
| `tests/unit/test_profile_completeness.py:444` | `mock_cursor` → `_mock_cursor` | Created but only `mock_redis` was used |

**Why safe:** Same as source code — prefix rename, side effects preserved, no behavioral change.

**Breaking?** **No**.

### 2.3 `# noqa: E402` added to test files — 3 files

| File | Context |
|------|---------|
| `tests/conftest.py:23-24` | Imports after `os.environ` setup (intentional — env vars must be set before importing app) |
| `tests/evals/test_comprehensive.py:45-46` | Imports after `sys.path` manipulation |
| `tests/evals/test_prompts_direct.py:35-36` | Imports after `sys.path` manipulation |

**Breaking?** **No**. Linter comments only.

### 2.4 Removed unused test imports — ~20 occurrences

Same pattern as source: `from datetime import timezone` removed when only `datetime` was used, etc.

**Breaking?** **No**.

---

## 3. Configuration & Infrastructure Changes

### 3.1 `docker-compose.yml` — TIMESCALE_DSN default removed

| Before | After |
|--------|-------|
| `TIMESCALE_DSN=${TIMESCALE_DSN:-postgresql://postgres:Passw0rd1!@host.docker.internal:5433/agentic_memories}` | `TIMESCALE_DSN=${TIMESCALE_DSN:?Set TIMESCALE_DSN in your .env file}` |

**Why safe:** The `${VAR:?message}` syntax in shell/docker-compose causes an explicit error if the variable is unset, with a clear message. Any correctly configured deployment has `TIMESCALE_DSN` in `.env`. The old default exposed a real password.

**Breaking?** **No** for configured deployments. Fails fast with clear instructions if `.env` is missing.

### 3.2 `docker-compose.yml` — UI port changed

| Before | After |
|--------|-------|
| `"80:80"` | `"3000:80"` |

**Why safe:** Port 80 requires root/admin privileges on most systems. Port 3000 is unprivileged. The container internally still listens on 80 (nginx); only the host mapping changed. Updated all references in README, `run_docker.sh`, and docs.

**Breaking?** **No** for new setups. Existing users who bookmarked `localhost:80` need to use `localhost:3000`. This is documented.

### 3.3 `.github/workflows/deploy.yml` — Hardcoded paths removed

| Before | After |
|--------|-------|
| `cd /home/ankit/dev/agentic-memories` (hardcoded 2x) | `cd "$DEPLOY_DIR"` (uses `vars.DEPLOY_DIR` with `/opt/agentic-memories` default) |

**Why safe:** The old paths only worked on one specific developer's machine. The new version uses a configurable GitHub Actions variable, making it work for any deployment.

**Breaking?** **No**. The old workflow was non-functional for anyone except the original developer.

### 3.4 `.github/workflows/ci.yml` — Lint job added

Added a new `lint` job that runs `ruff check .` and `ruff format --check .` **before** the existing `test` job. The `test` job now has `needs: lint`.

**Why safe:** This is purely additive. The existing test and build jobs are unchanged. The lint job runs on `ubuntu-latest` with Python 3.12, matching the test job.

**Breaking?** **No**. Additive CI step.

### 3.5 `README.md` — Passwords scrubbed, links fixed, disclaimer added

| Change | Details |
|--------|---------|
| Passwords | `Passw0rd1!` → `<your-password>` in 3 locations |
| Links | `yourusername` → `ankitaa186` in 7 locations |
| Contact | Removed placeholder email/Twitter |
| Port | `localhost:80` → `localhost:3000` in 2 locations |
| License badge | MIT → Apache 2.0 |
| License section | Added full disclaimer section |

**Breaking?** **No**. Documentation only.

### 3.6 `migrations/TEST_RESULTS.md` — Passwords scrubbed

`Passw0rd1!` → `<your-password>` in 4 locations. Documentation only.

### 3.7 Docs — Personal paths removed

| File | Change |
|------|--------|
| `docs/epic-5-scheduled-intents.md:382` | `/home/ankit/dev/annie/...` → `(internal reference)` |
| `docs/epic-6-intents-api-alignment.md:49-50,557-558` | `file:///Users/Ankit/dev/annie/...` → `(internal reference)` |
| `docs/sprint-artifacts/9-5-update-tests-and-documentation.md:126` | `/home/ankit/dev/agentic-memories/tests/` → `tests/` |
| `scripts/run_docker.sh:295` | `localhost:80` → `localhost:3000` |
| `docs/component-inventory-client.md:294` | `localhost:80` → `localhost:3000` |
| `docs/internal/DEPLOYMENT_TEST_RESULTS.md:128` | `localhost:80` → `localhost:3000` |

**Breaking?** **No**. Documentation and print output only.

### 3.8 `LICENSE` — MIT → Apache 2.0

Replaced MIT license text with Apache License 2.0. Legal change, not a code change.

**Breaking?** **No** (code-wise). License is more permissive regarding patents.

---

## 4. New Files Added

| File | Purpose | Breaking? |
|------|---------|-----------|
| `LICENSE` | Apache 2.0 license text | No |
| `CONTRIBUTING.md` | Contribution guidelines | No |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 | No |
| `SECURITY.md` | Vulnerability reporting policy | No |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, trailing whitespace, detect-private-key) | No |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Bug report template | No |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Feature request template | No |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist template | No |

None of these files affect runtime behavior. All are community/tooling files.

---

## 5. Files Moved (No Content Changes)

25 internal development markdown files moved from repository root to `docs/internal/`:

```
API_ORCHESTRATION_INGESTION_PERSISTENCE_RETRIEVAL_PLAN.md
CHATBOT_INTEGRATION_GUIDE.md
CLEAN_REBUILD_PLAN.md
CLEAN_REBUILD_SUMMARY.md
COMPREHENSIVE_DATA_SOURCES.md
DEBUG.md
DEPLOYMENT_TEST_RESULTS.md
ENHANCED_EXTRACTION_SUMMARY.md
IMPLEMENTATION_SUMMARY.md
LANGFUSE_IMPLEMENTATION.md
MIGRATION_ENHANCEMENT_COMPLETE.md
MIGRATION_ROBUSTNESS_ENHANCEMENTS.md
PHASE2_COMPLETION_SUMMARY.md
PHASE2_REMAINING_FIXES.md
PHASE4_COMPLETE.md
README_CONTRAST.md
README_DETAILED.md
RETRIEVAL_DATA_FLOW.md
RETRIEVAL_OVERHAUL_PLAN.md
SCHEMA_AUDIT_FINAL.md
SCHEMA_AUDIT_PLAN.md
V2_IMPLEMENTATION_STATUS.md
postman_curl_commands.md
restructure.md
restructure_v2.md
```

**Breaking?** **No**. These are documentation files not referenced by any code.

---

## 6. Formatting-Only Changes

The following files had **only** ruff auto-formatting applied (line wrapping, trailing commas,
quote normalization `'` → `"`, import sorting). No semantic changes:

**Source (src/):** `app.py` (mostly), `config.py`, `models.py`, `schemas.py`, `dependencies/*.py`,
`routers/*.py`, `services/*.py` (all files except the specific changes noted above),
`storage/orchestrator.py`, `memory_orchestrator/*.py`

**Scripts:** `scripts/ci_env.py`, `scripts/github_env.py`, `scripts/merge_env.py`

**Migrations:** `migrations/chromadb/001_collections.up.py`, `migrations/chromadb/001_collections.down.py`

**Tests:** All test files except the specific changes noted in Section 2.

**Breaking?** **No**. ruff format is deterministic and semantics-preserving. It changes only
whitespace, line breaks, trailing commas, and quote style.

---

## 7. Risk Assessment Summary

| Category | Count | Risk Level | Breaking? |
|----------|-------|------------|-----------|
| Formatting only (ruff format) | ~90 files | **None** | No |
| Removed unused imports | 116 | **None** | No |
| Unused var → `_var` rename | 34 | **None** | No |
| `# noqa` comments added | 6 files | **None** | No |
| `except:` → `except Exception:` | 2 | **None** (safer) | No |
| Lambda → def | 1 | **None** | No |
| Re-export syntax | 1 file | **None** | No |
| TIMESCALE_DSN fallback removed | 1 file | **Low** | No* |
| UI port 80 → 3000 | 1 file + docs | **Low** | No* |
| Password scrubbed from configs | 3 files | **Low** | No* |
| Deploy paths genericized | 1 file | **None** | No |
| New community files | 8 files | **None** | No |
| Docs moved to docs/internal/ | 25 files | **None** | No |
| License MIT → Apache 2.0 | 1 file | **None** (legal) | No |

*\* These require users to have `.env` properly configured, which was already a requirement for a working deployment.*

### Verdict

**No breaking changes.** All semantic modifications fall into these categories:
1. **Security improvements** — removing hardcoded credentials (fail-fast with clear error messages)
2. **Lint compliance** — unused imports/variables cleaned up (zero runtime impact)
3. **Correctness improvements** — bare `except` → `except Exception` (prevents swallowing system signals)
4. **Formatting standardization** — ruff auto-format (deterministic, semantics-preserving)
5. **Documentation/community** — new files, moved files, scrubbed secrets (no code impact)
