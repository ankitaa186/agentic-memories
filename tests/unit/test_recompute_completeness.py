"""
Unit tests for scripts/recompute_completeness.py pure helpers.

Covers:
- The N+1 fix: bulk loader groups (user_id, category, field) correctly.
- The math: _compute_from_populated returns the right (count, pct) for
  empty / partial / fully-populated input.
"""

from scripts.recompute_completeness import (
    _compute_from_populated,
    _load_all_populated_fields,
)
from src.services.profile_storage import (
    EXPECTED_PROFILE_FIELDS,
    TOTAL_EXPECTED_FIELDS,
)


class _MockCursor:
    """Minimal cursor stub returning a fixed result set."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        return list(self._rows)


# --- _compute_from_populated ---------------------------------------------


def test_compute_from_populated_empty_returns_zero():
    empty = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
    count, pct = _compute_from_populated(empty)
    assert count == 0
    assert pct == 0.0


def test_compute_from_populated_full_returns_one_hundred():
    full = {cat: set(fields) for cat, fields in EXPECTED_PROFILE_FIELDS.items()}
    count, pct = _compute_from_populated(full)
    assert count == TOTAL_EXPECTED_FIELDS
    assert pct == 100.0


def test_compute_from_populated_ignores_fields_outside_baseline():
    """Fields not in EXPECTED_PROFILE_FIELDS must not inflate the count."""
    populated = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
    populated["basics"] = {"name", "birthday", "not_a_baseline_field"}
    populated["health"] = {"allergies", "another_unknown"}
    count, pct = _compute_from_populated(populated)
    # 2 (basics: name, birthday) + 1 (health: allergies) = 3
    assert count == 3
    assert abs(pct - (3 / TOTAL_EXPECTED_FIELDS) * 100) < 0.001


def test_compute_from_populated_health_tier1_partial():
    populated = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
    populated["health"] = {
        "allergies",
        "blood_type",
        "height_cm",
        "primary_care_provider",
    }
    count, pct = _compute_from_populated(populated)
    assert count == 4
    assert abs(pct - (4 / TOTAL_EXPECTED_FIELDS) * 100) < 0.001


# --- _load_all_populated_fields (N+1 fix) --------------------------------


def test_load_all_populated_fields_groups_by_user_tuple_rows():
    cursor = _MockCursor(
        [
            ("user-a", "basics", "name"),
            ("user-a", "basics", "birthday"),
            ("user-a", "health", "blood_type"),
            ("user-b", "basics", "name"),
            ("user-b", "preferences", "love_language"),
        ]
    )
    result = _load_all_populated_fields(cursor)

    # One bulk query, not one-per-user.
    assert len(cursor.queries) == 1
    assert "WHERE user_id" not in cursor.queries[0][0]

    assert set(result.keys()) == {"user-a", "user-b"}
    assert result["user-a"]["basics"] == {"name", "birthday"}
    assert result["user-a"]["health"] == {"blood_type"}
    assert result["user-b"]["basics"] == {"name"}
    assert result["user-b"]["preferences"] == {"love_language"}


def test_load_all_populated_fields_groups_by_user_dict_rows():
    cursor = _MockCursor(
        [
            {"user_id": "alice", "category": "basics", "field_name": "name"},
            {"user_id": "alice", "category": "goals", "field_name": "short_term"},
            {"user_id": "bob", "category": "health", "field_name": "allergies"},
        ]
    )
    result = _load_all_populated_fields(cursor)
    assert result["alice"]["basics"] == {"name"}
    assert result["alice"]["goals"] == {"short_term"}
    assert result["bob"]["health"] == {"allergies"}


def test_load_all_populated_fields_skips_unknown_categories():
    """Stale categories from old migrations should be silently dropped."""
    cursor = _MockCursor(
        [
            ("user-a", "basics", "name"),
            ("user-a", "obsolete_category", "ghost"),
        ]
    )
    result = _load_all_populated_fields(cursor)
    assert "obsolete_category" not in result["user-a"]
    assert result["user-a"]["basics"] == {"name"}


def test_load_all_populated_fields_empty_table():
    cursor = _MockCursor([])
    result = _load_all_populated_fields(cursor)
    assert result == {}
    assert len(cursor.queries) == 1
