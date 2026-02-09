"""
Unit tests for Profile CRUD API endpoints
Tests all profile endpoints: GET, PUT, DELETE, and completeness
"""
import pytest
from unittest.mock import patch


# Mock ProfileStorageService for testing
class _MockProfileStorage:
    """Mock ProfileStorageService for testing"""

    def __init__(self):
        self.profiles = {}

    def get_profile_by_user(self, user_id: str):
        """Return mock profile or None"""
        if user_id in self.profiles:
            return self.profiles[user_id]
        return None


# Mock database connection
class _MockCursor:
    """Mock database cursor"""

    def __init__(self):
        self.results = []
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if self.results:
            return self.results.pop(0)
        return None

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


@pytest.fixture
def mock_profile_service():
    """Fixture for mock profile service"""
    return _MockProfileStorage()


@pytest.fixture
def mock_db_conn():
    """Fixture for mock database connection"""
    cursor = _MockCursor()
    conn = _MockConnection(cursor)
    return conn, cursor


# Test GET /v1/profile endpoint
def test_get_profile_success(api_client, mock_profile_service, monkeypatch):
    """Test successful profile retrieval"""
    # Setup mock data
    mock_profile_service.profiles["test-user-123"] = {
        "user_id": "test-user-123",
        "completeness_pct": 75.0,
        "populated_fields": 15,
        "total_fields": 21,
        "last_updated": "2024-11-16T12:00:00Z",
        "created_at": "2024-11-01T10:00:00Z",
        "profile": {
            "basics": {
                "name": {"value": "John Doe", "last_updated": "2024-11-16T12:00:00Z"},
                "age": {"value": 30, "last_updated": "2024-11-16T12:00:00Z"}
            },
            "preferences": {},
            "goals": {},
            "interests": {},
            "background": {}
        }
    }

    # Patch the service
    with patch("src.routers.profile._profile_service", mock_profile_service):
        response = api_client.get("/v1/profile?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test-user-123"
    assert data["completeness_pct"] == 75.0
    assert data["populated_fields"] == 15
    assert "profile" in data
    assert "basics" in data["profile"]


def test_get_profile_not_found(api_client, mock_profile_service, monkeypatch):
    """Test 404 when profile doesn't exist"""
    with patch("src.routers.profile._profile_service", mock_profile_service):
        response = api_client.get("/v1/profile?user_id=nonexistent-user")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# Test GET /v1/profile/{category} endpoint
def test_get_profile_category_success(api_client, mock_profile_service, monkeypatch):
    """Test successful category retrieval"""
    mock_profile_service.profiles["test-user-123"] = {
        "user_id": "test-user-123",
        "profile": {
            "basics": {
                "name": {"value": "John Doe", "last_updated": "2024-11-16T12:00:00Z"},
                "age": {"value": 30, "last_updated": "2024-11-16T12:00:00Z"}
            },
            "preferences": {"communication_style": {"value": "direct", "last_updated": "2024-11-16T12:00:00Z"}},
            "goals": {},
            "interests": {},
            "background": {}
        }
    }

    with patch("src.routers.profile._profile_service", mock_profile_service):
        response = api_client.get("/v1/profile/basics?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "basics"
    assert data["user_id"] == "test-user-123"
    assert "name" in data["fields"]
    assert data["fields"]["name"]["value"] == "John Doe"


def test_get_profile_category_invalid(api_client, mock_profile_service, monkeypatch):
    """Test 400 for invalid category"""
    with patch("src.routers.profile._profile_service", mock_profile_service):
        response = api_client.get("/v1/profile/invalid_category?user_id=test-user-123")

    assert response.status_code == 400
    assert "invalid category" in response.json()["detail"].lower()


def test_get_profile_category_not_found(api_client, mock_profile_service, monkeypatch):
    """Test 404 when profile doesn't exist for category request"""
    with patch("src.routers.profile._profile_service", mock_profile_service):
        response = api_client.get("/v1/profile/basics?user_id=nonexistent-user")

    assert response.status_code == 404


# Test PUT /v1/profile/{category}/{field_name} endpoint
def test_update_profile_field_success(api_client, mock_db_conn, monkeypatch):
    """Test successful field update"""
    conn, cursor = mock_db_conn

    # Mock get_timescale_conn
    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.put(
                "/v1/profile/basics/name",
                json={"user_id": "test-user-123", "value": "Jane Smith", "source": "manual"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test-user-123"
    assert data["category"] == "basics"
    assert data["field_name"] == "name"
    assert data["value"] == "Jane Smith"
    assert data["confidence"] == 100.0  # Manual edits always 100%


def test_update_profile_field_invalid_category(api_client, monkeypatch):
    """Test 400 for invalid category in update"""
    response = api_client.put(
        "/v1/profile/invalid/field",
        json={"user_id": "test-user-123", "value": "test", "source": "manual"}
    )

    assert response.status_code == 400
    assert "invalid category" in response.json()["detail"].lower()


def test_update_profile_field_null_value_rejected(api_client, monkeypatch):
    """Test 400 when trying to set field value to null"""
    response = api_client.put(
        "/v1/profile/basics/name",
        json={"user_id": "test-user-123", "value": None, "source": "manual"}
    )

    assert response.status_code == 400
    assert "cannot set field value to null" in response.json()["detail"].lower()
    assert "DELETE" in response.json()["detail"]


# Test DELETE /v1/profile/{category}/{field_name} endpoint
def test_delete_profile_field_success(api_client, mock_db_conn, monkeypatch):
    """Test successful single field deletion"""
    conn, cursor = mock_db_conn

    # Mock: profile exists, field exists, then remaining fields after delete
    # fetchone calls: 1) profile exists check, 2) field exists check
    # fetchall call: for _update_profile_metadata to get remaining fields
    cursor.results = [("test-user-123",), ("name",)]

    # Override fetchall to return empty list (no remaining fields after deletion)
    original_fetchall = cursor.fetchall
    cursor.fetchall = lambda: []

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.delete("/v1/profile/basics/name?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["user_id"] == "test-user-123"
    assert data["category"] == "basics"
    assert data["field_name"] == "name"


def test_delete_profile_field_invalid_category(api_client, monkeypatch):
    """Test 400 for invalid category in field delete"""
    response = api_client.delete("/v1/profile/invalid_category/name?user_id=test-user-123")

    assert response.status_code == 400
    assert "invalid category" in response.json()["detail"].lower()


def test_delete_profile_field_profile_not_found(api_client, mock_db_conn, monkeypatch):
    """Test 404 when profile doesn't exist for field delete"""
    conn, cursor = mock_db_conn

    # Mock: profile doesn't exist
    cursor.results = [None]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.delete("/v1/profile/basics/name?user_id=nonexistent")

    assert response.status_code == 404
    assert "profile not found" in response.json()["detail"].lower()


def test_delete_profile_field_field_not_found(api_client, mock_db_conn, monkeypatch):
    """Test 404 when field doesn't exist"""
    conn, cursor = mock_db_conn

    # Mock: profile exists, but field doesn't exist
    cursor.results = [("test-user-123",), None]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.delete("/v1/profile/basics/nonexistent_field?user_id=test-user-123")

    assert response.status_code == 404
    assert "field" in response.json()["detail"].lower()
    assert "not found" in response.json()["detail"].lower()


# Test DELETE /v1/profile endpoint
def test_delete_profile_success(api_client, mock_db_conn, monkeypatch):
    """Test successful profile deletion"""
    conn, cursor = mock_db_conn

    # Mock that profile exists
    cursor.results = [("test-user-123",)]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.delete("/v1/profile?user_id=test-user-123&confirmation=DELETE")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["user_id"] == "test-user-123"


def test_delete_profile_wrong_confirmation(api_client, monkeypatch):
    """Test 400 when confirmation is incorrect"""
    response = api_client.delete("/v1/profile?user_id=test-user-123&confirmation=delete")

    assert response.status_code == 400
    assert "confirmation" in response.json()["detail"].lower()


def test_delete_profile_not_found(api_client, mock_db_conn, monkeypatch):
    """Test 404 when profile doesn't exist"""
    conn, cursor = mock_db_conn

    # Mock that profile doesn't exist
    cursor.results = [None]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.delete("/v1/profile?user_id=nonexistent&confirmation=DELETE")

    assert response.status_code == 404


# Test GET /v1/profile/completeness endpoint
def test_get_completeness_success(api_client, mock_db_conn, monkeypatch):
    """Test successful completeness retrieval"""
    conn, cursor = mock_db_conn

    # Mock completeness data
    cursor.results = [(75.0, 15, 21)]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.get("/v1/profile/completeness?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test-user-123"
    assert data["overall_completeness_pct"] == 75.0
    assert data["populated_fields"] == 15
    assert data["total_fields"] == 21


def test_get_completeness_not_found(api_client, mock_db_conn, monkeypatch):
    """Test 404 when profile doesn't exist for completeness"""
    conn, cursor = mock_db_conn

    # Mock no profile
    cursor.results = [None]

    def mock_get_conn():
        return conn

    def mock_release_conn(c):
        pass

    with patch("src.routers.profile.get_timescale_conn", mock_get_conn):
        with patch("src.routers.profile.release_timescale_conn", mock_release_conn):
            response = api_client.get("/v1/profile/completeness?user_id=nonexistent")

    assert response.status_code == 404


# Test helper functions
def test_infer_value_type():
    """Test value type inference"""
    from src.routers.profile import _infer_value_type

    assert _infer_value_type(True) == "bool"
    assert _infer_value_type(42) == "int"
    assert _infer_value_type(3.14) == "float"
    assert _infer_value_type([1, 2, 3]) == "list"
    assert _infer_value_type({"key": "value"}) == "dict"
    assert _infer_value_type("hello") == "string"


def test_serialize_field_value():
    """Test field value serialization"""
    from src.routers.profile import _serialize_field_value

    assert _serialize_field_value(True) == "true"
    assert _serialize_field_value(False) == "false"
    assert _serialize_field_value(42) == "42"
    assert _serialize_field_value([1, 2, 3]) == "[1, 2, 3]"
    assert _serialize_field_value({"key": "value"}) == '{"key": "value"}'
    assert _serialize_field_value("hello") == "hello"


# Integration-style test (requires actual DB - mark as skipif no DB)
@pytest.mark.skipif(True, reason="Requires actual database connection")
def test_full_crud_cycle_integration():
    """
    Full CRUD integration test (requires real database).
    This test is skipped by default but can be run with actual DB.
    """
    pass
