"""
Unit tests for Profile Completeness Tracking (Story 1.6)
Tests completeness calculation, gap identification, caching, and enhanced endpoint
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# Test EXPECTED_PROFILE_FIELDS constant
def test_expected_profile_fields_structure():
    """Test EXPECTED_PROFILE_FIELDS has correct structure (AC1)"""
    from src.services.profile_storage import EXPECTED_PROFILE_FIELDS, TOTAL_EXPECTED_FIELDS

    # Verify 8 categories
    assert len(EXPECTED_PROFILE_FIELDS) == 8
    assert set(EXPECTED_PROFILE_FIELDS.keys()) == {
        'basics', 'preferences', 'goals', 'interests', 'background', 'health', 'personality', 'values'
    }

    # Verify total is 27
    assert TOTAL_EXPECTED_FIELDS == 27


def test_expected_profile_fields_content():
    """Test EXPECTED_PROFILE_FIELDS contains correct field names (AC1)"""
    from src.services.profile_storage import EXPECTED_PROFILE_FIELDS

    # Verify basics fields
    assert 'name' in EXPECTED_PROFILE_FIELDS['basics']
    assert 'birthday' in EXPECTED_PROFILE_FIELDS['basics']
    assert 'location' in EXPECTED_PROFILE_FIELDS['basics']
    assert 'occupation' in EXPECTED_PROFILE_FIELDS['basics']
    assert 'family_status' in EXPECTED_PROFILE_FIELDS['basics']

    # Verify goals fields
    assert 'short_term' in EXPECTED_PROFILE_FIELDS['goals']
    assert 'long_term' in EXPECTED_PROFILE_FIELDS['goals']

    # Verify new categories exist
    assert 'allergies' in EXPECTED_PROFILE_FIELDS['health']
    assert 'personality_type' in EXPECTED_PROFILE_FIELDS['personality']


# Mock classes for testing
class _MockCursor:
    """Mock database cursor for completeness tests"""

    def __init__(self, results=None, fetchone_result=None):
        self.results = results or []
        self._fetchone_result = fetchone_result
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self._fetchone_result

    def fetchall(self):
        return self.results

    def close(self):
        pass


class _MockConnection:
    """Mock database connection"""

    def __init__(self, cursor=None):
        self._cursor = cursor or _MockCursor()

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass


# Test completeness calculation
def test_completeness_calculation_empty_profile():
    """Test completeness is 0% for empty profile (AC2)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    # Mock cursor with no profile fields
    mock_cursor = _MockCursor(
        fetchone_result=(0.0, 0, TOTAL_EXPECTED_FIELDS),  # profile exists but empty
        results=[]  # no fields
    )
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    assert result is not None
    assert result["overall_completeness_pct"] == 0.0
    assert result["populated_fields"] == 0
    assert result["total_fields"] == TOTAL_EXPECTED_FIELDS


def test_completeness_calculation_partial_profile():
    """Test completeness calculation with partial fields (AC1, AC2)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    # Mock profile with some fields populated (using new canonical field names)
    # 10 fields that match EXPECTED_PROFILE_FIELDS
    mock_cursor = _MockCursor(
        fetchone_result=(37.0, 10, TOTAL_EXPECTED_FIELDS),  # profile metadata
        results=[]
    )

    # We need to handle multiple fetchall calls
    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        if call_count[0] == 1:
            # profile_fields query - use fields from EXPECTED_PROFILE_FIELDS
            return [
                ('basics', 'name'),
                ('basics', 'birthday'),
                ('basics', 'location'),
                ('preferences', 'communication_style'),
                ('preferences', 'food_preferences'),
                ('goals', 'short_term'),
                ('interests', 'hobbies'),
                ('interests', 'learning_areas'),
                ('background', 'skills'),
                ('background', 'current_employer'),
            ]
        elif call_count[0] == 2:
            # confidence_scores query
            return []
        return []

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    assert result is not None
    # 10 fields / 27 total ≈ 37%
    assert abs(result["overall_completeness_pct"] - 37.0) < 1.0
    assert result["populated_fields"] == 10
    assert result["total_fields"] == TOTAL_EXPECTED_FIELDS

    # Verify per-category breakdown
    assert "categories" in result
    assert result["categories"]["basics"]["populated"] == 3
    assert result["categories"]["basics"]["total"] == 5
    assert result["categories"]["preferences"]["populated"] == 2


def test_completeness_category_breakdown():
    """Test per-category completeness breakdown (AC1)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    # Mock profile with full basics, empty goals
    mock_cursor = _MockCursor(fetchone_result=(21.7, 5, TOTAL_EXPECTED_FIELDS))

    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        if call_count[0] == 1:
            # All 5 basics fields from EXPECTED_PROFILE_FIELDS
            return [
                ('basics', 'name'),
                ('basics', 'birthday'),
                ('basics', 'location'),
                ('basics', 'occupation'),
                ('basics', 'family_status'),
            ]
        return []

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    assert result is not None

    # Basics should be 100%
    assert result["categories"]["basics"]["completeness_pct"] == 100.0
    assert result["categories"]["basics"]["missing"] == []

    # Goals should be 0% (3 expected fields in goals)
    assert result["categories"]["goals"]["completeness_pct"] == 0.0
    assert len(result["categories"]["goals"]["missing"]) == 3


def test_completeness_missing_fields():
    """Test missing fields are correctly identified (AC1)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    mock_cursor = _MockCursor(fetchone_result=(4.3, 1, TOTAL_EXPECTED_FIELDS))

    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        if call_count[0] == 1:
            return [('basics', 'name')]
        return []

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    # Check missing basics fields (using new canonical names)
    basics_missing = result["categories"]["basics"]["missing"]
    assert "birthday" in basics_missing
    assert "location" in basics_missing
    assert "occupation" in basics_missing
    assert "family_status" in basics_missing
    assert "name" not in basics_missing  # name is populated


# Test high-value gap identification
def test_high_value_gaps_basics_priority():
    """Test basics fields have highest priority in gaps (AC3)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    mock_cursor = _MockCursor(fetchone_result=(0.0, 0, TOTAL_EXPECTED_FIELDS))

    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        return []  # No fields populated

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    gaps = result["high_value_gaps"]

    # First 5 gaps should be basics fields (using new canonical names)
    basics_fields = {'name', 'birthday', 'location', 'occupation', 'family_status'}
    first_five = set(gaps[:5])
    assert first_five == basics_fields, f"First 5 gaps should be basics fields, got {first_five}"


def test_high_value_gaps_limit():
    """Test high-value gaps are limited to 10 items (AC3)"""
    from src.services.profile_storage import ProfileStorageService, TOTAL_EXPECTED_FIELDS

    service = ProfileStorageService()

    mock_cursor = _MockCursor(fetchone_result=(0.0, 0, TOTAL_EXPECTED_FIELDS))

    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        return []

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=None):
                result = service.get_completeness_details("test-user")

    # Should be limited to 10
    assert len(result["high_value_gaps"]) <= 10


# Test Redis caching
def test_completeness_cache_hit():
    """Test completeness data is returned from cache (AC4)"""
    from src.services.profile_storage import ProfileStorageService

    service = ProfileStorageService()

    cached_data = {
        "overall_completeness_pct": 60.0,
        "populated_fields": 15,
        "total_fields": 25,
        "categories": {},
        "high_value_gaps": ["education"],
        "cached_at": "2025-12-14T10:00:00Z"
    }

    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(cached_data)

    with patch("src.services.profile_storage.get_redis_client", return_value=mock_redis):
        result = service.get_completeness_details("test-user")

    assert result is not None
    assert result["overall_completeness_pct"] == 60.0
    mock_redis.get.assert_called_once()


def test_completeness_cache_miss():
    """Test completeness is calculated on cache miss (AC4)"""
    from src.services.profile_storage import ProfileStorageService

    service = ProfileStorageService()

    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # Cache miss

    mock_cursor = _MockCursor(fetchone_result=(20.0, 5, 25))

    call_count = [0]

    def mock_fetchall():
        call_count[0] += 1
        if call_count[0] == 1:
            return [('basics', 'name')]
        return []

    mock_cursor.fetchall = mock_fetchall
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.services.profile_storage.get_timescale_conn", return_value=mock_conn):
        with patch("src.services.profile_storage.release_timescale_conn"):
            with patch("src.services.profile_storage.get_redis_client", return_value=mock_redis):
                result = service.get_completeness_details("test-user")

    assert result is not None
    # Should have cached the result
    mock_redis.setex.assert_called_once()


def test_completeness_cache_ttl():
    """Test completeness cache uses correct TTL (AC4)"""
    from src.services.profile_storage import ProfileStorageService, COMPLETENESS_CACHE_TTL

    assert COMPLETENESS_CACHE_TTL == 3600  # 1 hour


def test_completeness_cache_key_pattern():
    """Test completeness cache key follows pattern (AC4)"""
    from src.services.profile_storage import COMPLETENESS_CACHE_KEY

    key = COMPLETENESS_CACHE_KEY.format(user_id="test-123")
    assert key == "profile_completeness:test-123"


# Test enhanced endpoint
def test_get_completeness_simple_mode(api_client):
    """Test GET /v1/profile/completeness without details (AC5 backward compat)"""
    mock_cursor = _MockCursor(fetchone_result=(75.0, 15, 25))
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.profile.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.profile.release_timescale_conn"):
            response = api_client.get("/v1/profile/completeness?user_id=test-user")

    assert response.status_code == 200
    data = response.json()

    # Simple mode should NOT have categories or high_value_gaps
    assert "overall_completeness_pct" in data
    assert "populated_fields" in data
    assert "total_fields" in data
    assert "categories" not in data
    assert "high_value_gaps" not in data


def test_get_completeness_detailed_mode(api_client):
    """Test GET /v1/profile/completeness with details=true (AC5)"""
    from src.services.profile_storage import ProfileStorageService

    mock_service = MagicMock(spec=ProfileStorageService)
    mock_service.get_completeness_details.return_value = {
        "overall_completeness_pct": 60.0,
        "populated_fields": 15,
        "total_fields": 25,
        "categories": {
            "basics": {"completeness_pct": 80.0, "populated": 4, "total": 5, "missing": ["education"]},
            "preferences": {"completeness_pct": 60.0, "populated": 3, "total": 5, "missing": ["favorites", "style"]},
            "goals": {"completeness_pct": 40.0, "populated": 2, "total": 5, "missing": ["aspirations", "plans", "targets"]},
            "interests": {"completeness_pct": 60.0, "populated": 3, "total": 5, "missing": ["passions", "learning"]},
            "background": {"completeness_pct": 60.0, "populated": 3, "total": 5, "missing": ["achievements", "journey"]},
        },
        "high_value_gaps": ["education", "aspirations", "skills"]
    }

    with patch("src.routers.profile._profile_service", mock_service):
        response = api_client.get("/v1/profile/completeness?user_id=test-user&details=true")

    assert response.status_code == 200
    data = response.json()

    # Detailed mode should have categories and high_value_gaps
    assert data["overall_completeness_pct"] == 60.0
    assert "categories" in data
    assert "basics" in data["categories"]
    assert data["categories"]["basics"]["completeness_pct"] == 80.0
    assert "missing" in data["categories"]["basics"]
    assert "high_value_gaps" in data
    assert "education" in data["high_value_gaps"]


def test_get_completeness_detailed_not_found(api_client):
    """Test details=true returns 404 for missing profile (AC5)"""
    from src.services.profile_storage import ProfileStorageService

    mock_service = MagicMock(spec=ProfileStorageService)
    mock_service.get_completeness_details.return_value = None

    with patch("src.routers.profile._profile_service", mock_service):
        response = api_client.get("/v1/profile/completeness?user_id=nonexistent&details=true")

    assert response.status_code == 404


# Test cache invalidation
def test_cache_invalidation_on_profile_update():
    """Test cache is invalidated when profile is updated (AC4)"""
    mock_cursor = _MockCursor()

    mock_redis = MagicMock()

    # The _invalidate_completeness_cache function imports get_redis_client internally
    with patch("src.dependencies.redis_client.get_redis_client", return_value=mock_redis):
        # Import after patching
        from src.routers.profile import _invalidate_completeness_cache
        _invalidate_completeness_cache("test-user")

    # Should have called delete on Redis
    mock_redis.delete.assert_called_once()
    call_args = mock_redis.delete.call_args[0][0]
    assert "profile_completeness:test-user" in call_args
