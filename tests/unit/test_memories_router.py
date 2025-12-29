"""
Unit tests for Memories Router API endpoints (Epic 10 - Direct Memory API)

Story 10.1: Direct memory store endpoint (ChromaDB)
Story 10.2: Typed table storage (episodic, emotional, procedural)

Tests cover:
- Direct memory storage with ChromaDB
- Typed table routing based on optional fields
- Helper functions for episodic, emotional, procedural storage
- Metadata flags tracking
- Response format with storage status per backend
- Error handling (best-effort for typed tables)
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# Mock database cursor and connection (consistent with test_portfolio_api.py)
class _MockCursor:
    """Mock database cursor for memories tests"""

    def __init__(self, results=None):
        self.results = results or []
        self.queries = []
        self.rowcount = 0  # Default rowcount for DELETE operations

    def execute(self, query, params=None):
        self.queries.append((query, params))
        # Simulate rowcount for DELETE queries
        if "DELETE" in query.upper():
            self.rowcount = 1

    def fetchall(self):
        return self.results

    def fetchone(self):
        return self.results[0] if self.results else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockConnection:
    """Mock database connection"""

    def __init__(self, cursor=None, should_fail=False):
        self._cursor = cursor or _MockCursor()
        self._committed = False
        self._rolled_back = False
        self._should_fail = should_fail

    def cursor(self):
        if self._should_fail:
            raise Exception("Database error")
        return self._cursor

    def commit(self):
        self._committed = True

    def rollback(self):
        self._rolled_back = True


# =============================================================================
# Story 10.1: Direct Memory Store Tests (ChromaDB)
# =============================================================================

def test_direct_store_success_basic(api_client, monkeypatch):
    """Test successful direct memory storage (AC1)"""
    # Mock embedding generation
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user-123",
                "content": "User enjoys hiking in the mountains"
            })

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["memory_id"] is not None
    assert data["memory_id"].startswith("mem_")
    assert data["message"] == "Memory stored successfully"
    assert data["storage"]["chromadb"] is True


def test_direct_store_with_all_fields(api_client, monkeypatch):
    """Test direct memory storage with all optional general fields (AC2)"""
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user-123",
                "content": "User prefers Python over JavaScript",
                "layer": "long-term",
                "type": "explicit",
                "importance": 0.9,
                "confidence": 0.95,
                "persona_tags": ["developer", "tech"],
                "metadata": {"source": "conversation"}
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_direct_store_embedding_failure(api_client, monkeypatch):
    """Test error handling when embedding generation fails (AC3)"""
    with patch("src.routers.memories.generate_embedding", side_effect=Exception("OpenAI error")):
        response = api_client.post("/v1/memories/direct", json={
            "user_id": "test-user-123",
            "content": "Test content"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "EMBEDDING_ERROR"
    assert data["memory_id"] is None


def test_direct_store_embedding_returns_none(api_client, monkeypatch):
    """Test error handling when embedding returns None (AC3)"""
    with patch("src.routers.memories.generate_embedding", return_value=None):
        response = api_client.post("/v1/memories/direct", json={
            "user_id": "test-user-123",
            "content": "Test content"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "EMBEDDING_ERROR"


def test_direct_store_chromadb_failure(api_client, monkeypatch):
    """Test error handling when ChromaDB storage fails (AC4)"""
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", side_effect=Exception("ChromaDB error")):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user-123",
                "content": "Test content"
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "STORAGE_ERROR"


def test_direct_store_chromadb_returns_empty(api_client, monkeypatch):
    """Test error handling when ChromaDB returns empty list (AC4)"""
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=[]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user-123",
                "content": "Test content"
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "STORAGE_ERROR"


def test_direct_store_missing_user_id(api_client):
    """Test validation error for missing user_id"""
    response = api_client.post("/v1/memories/direct", json={
        "content": "Test content"
    })

    assert response.status_code == 422


def test_direct_store_missing_content(api_client):
    """Test validation error for missing content"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user-123"
    })

    assert response.status_code == 422


# =============================================================================
# Story 10.2: Typed Table Storage Tests
# =============================================================================

def test_episodic_storage_when_event_timestamp_provided(api_client, monkeypatch):
    """Test episodic table storage when event_timestamp is provided (AC #2)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "User attended daughter's graduation at Stanford",
                        "event_timestamp": "2025-06-15T14:00:00Z",
                        "location": "Stanford University, CA",
                        "participants": ["daughter Sarah", "wife Maria"],
                        "event_type": "family_milestone"
                    })

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["episodic"] is True
    # Should not have emotional or procedural keys
    assert "emotional" not in data["storage"]
    assert "procedural" not in data["storage"]


def test_emotional_storage_when_emotional_state_provided(api_client, monkeypatch):
    """Test emotional table storage when emotional_state is provided (AC #2)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "User expressed frustration about job search",
                        "emotional_state": "frustrated",
                        "valence": -0.6,
                        "arousal": 0.7,
                        "trigger_event": "Another job rejection email"
                    })

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["emotional"] is True
    assert "episodic" not in data["storage"]
    assert "procedural" not in data["storage"]


def test_procedural_storage_when_skill_name_provided(api_client, monkeypatch):
    """Test procedural table storage when skill_name is provided (AC #2)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "User demonstrated advanced Python skills",
                        "skill_name": "python_programming",
                        "proficiency_level": "advanced"
                    })

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["procedural"] is True
    assert "episodic" not in data["storage"]
    assert "emotional" not in data["storage"]


def test_multiple_typed_tables_simultaneously(api_client, monkeypatch):
    """Test storing in multiple typed tables when multiple fields provided (AC #2)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "User excitedly completed Python certification",
                        # Episodic fields
                        "event_timestamp": "2025-12-01T10:00:00Z",
                        "event_type": "achievement",
                        # Emotional fields
                        "emotional_state": "excited",
                        "valence": 0.9,
                        "arousal": 0.8,
                        # Procedural fields
                        "skill_name": "python_certification",
                        "proficiency_level": "expert"
                    })

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["episodic"] is True
    assert data["storage"]["emotional"] is True
    assert data["storage"]["procedural"] is True


def test_chromadb_always_stored_regardless_of_typed_fields(api_client, monkeypatch):
    """Test ChromaDB storage always occurs even when typed fields present (AC #2)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Track that ChromaDB storage was called
    chromadb_called = []

    def mock_upsert(user_id, memories):
        chromadb_called.append(True)
        return ["mem_test123456"]

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", side_effect=mock_upsert):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "Test with typed field",
                        "event_timestamp": "2025-01-01T00:00:00Z"
                    })

    assert response.status_code == 200
    assert len(chromadb_called) == 1  # ChromaDB was called


def test_typed_table_failure_logs_and_continues(api_client, monkeypatch):
    """Test typed table failure doesn't fail the overall request (AC #4 - best effort)"""
    mock_embedding = [0.1] * 1536

    # Mock that returns None for timescale connection (simulates connection failure)
    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=None):
                response = api_client.post("/v1/memories/direct", json={
                    "user_id": "test-user-123",
                    "content": "Test with typed field that will fail",
                    "event_timestamp": "2025-01-01T00:00:00Z"
                })

    assert response.status_code == 200
    data = response.json()

    # Overall status should be success (ChromaDB succeeded)
    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    # Episodic should be false (failed but didn't fail request)
    assert data["storage"]["episodic"] is False


def test_metadata_flags_stored_in_chromadb(api_client, monkeypatch):
    """Test metadata flags are stored correctly in ChromaDB (AC #3)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Capture the memory object passed to upsert_memories
    captured_memories = []

    def mock_upsert(user_id, memories):
        captured_memories.extend(memories)
        return ["mem_test123456"]

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", side_effect=mock_upsert):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user-123",
                        "content": "Test content",
                        "event_timestamp": "2025-01-01T00:00:00Z",
                        "emotional_state": "happy"
                    })

    assert response.status_code == 200
    assert len(captured_memories) == 1

    memory = captured_memories[0]
    metadata = memory.metadata

    # Verify metadata flags
    assert metadata["source"] == "direct_api"
    assert metadata["stored_in_episodic"] is True
    assert metadata["stored_in_emotional"] is True
    assert metadata["stored_in_procedural"] is False


def test_response_only_includes_attempted_typed_tables(api_client, monkeypatch):
    """Test response.storage only includes keys for attempted typed tables (AC #4)"""
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            # No typed fields - should only have chromadb in storage
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user-123",
                "content": "Simple memory without typed fields"
            })

    assert response.status_code == 200
    data = response.json()

    # Only chromadb should be in storage
    assert data["storage"] == {"chromadb": True}
    assert "episodic" not in data["storage"]
    assert "emotional" not in data["storage"]
    assert "procedural" not in data["storage"]


# =============================================================================
# Schema Validation Tests (AC #1)
# =============================================================================

def test_schema_accepts_episodic_fields(api_client, monkeypatch):
    """Test schema accepts all episodic fields (AC #1)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "event_timestamp": "2025-06-15T14:00:00Z",
                        "location": "San Francisco",
                        "participants": ["Alice", "Bob"],
                        "event_type": "meeting"
                    })

    assert response.status_code == 200


def test_schema_accepts_emotional_fields(api_client, monkeypatch):
    """Test schema accepts all emotional fields (AC #1)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "happy",
                        "valence": 0.8,
                        "arousal": 0.6,
                        "trigger_event": "Good news"
                    })

    assert response.status_code == 200


def test_schema_accepts_procedural_fields(api_client, monkeypatch):
    """Test schema accepts all procedural fields (AC #1)"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "skill_name": "coding",
                        "proficiency_level": "expert"
                    })

    assert response.status_code == 200


def test_valence_constraint_min(api_client):
    """Test valence must be >= -1.0 (AC #1)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "emotional_state": "test",
        "valence": -1.5  # Below minimum
    })

    assert response.status_code == 422


def test_valence_constraint_max(api_client):
    """Test valence must be <= 1.0 (AC #1)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "emotional_state": "test",
        "valence": 1.5  # Above maximum
    })

    assert response.status_code == 422


def test_arousal_constraint_min(api_client):
    """Test arousal must be >= 0.0 (AC #1)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "emotional_state": "test",
        "arousal": -0.5  # Below minimum
    })

    assert response.status_code == 422


def test_arousal_constraint_max(api_client):
    """Test arousal must be <= 1.0 (AC #1)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "emotional_state": "test",
        "arousal": 1.5  # Above maximum
    })

    assert response.status_code == 422


def test_default_valence_when_not_provided(api_client, monkeypatch):
    """Test default valence of 0.0 when not provided"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "neutral"
                        # No valence - should default to 0.0
                    })

    assert response.status_code == 200
    # Check that INSERT was called - valence should be 0.0
    assert len(mock_cursor.queries) > 0


def test_default_arousal_when_not_provided(api_client, monkeypatch):
    """Test default arousal of 0.5 when not provided"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "neutral"
                        # No arousal - should default to 0.5
                    })

    assert response.status_code == 200


def test_default_proficiency_level_when_not_provided(api_client, monkeypatch):
    """Test default proficiency_level of 'beginner' when not provided"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "skill_name": "cooking"
                        # No proficiency_level - should default to "beginner"
                    })

    assert response.status_code == 200


# =============================================================================
# Helper Function Unit Tests
# =============================================================================

def test_store_episodic_success():
    """Test _store_episodic helper function success case"""
    from src.routers.memories import _store_episodic
    from src.schemas import DirectMemoryRequest
    from datetime import datetime, timezone

    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test episodic memory",
        event_timestamp=datetime.now(timezone.utc),
        event_type="test",
        location="Test location",
        participants=["Alice"]
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _store_episodic("mem_test123456", body)

    assert result is True
    assert mock_conn._committed is True
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert "INSERT INTO episodic_memories" in query


def test_store_episodic_connection_unavailable():
    """Test _store_episodic returns False when connection unavailable"""
    from src.routers.memories import _store_episodic
    from src.schemas import DirectMemoryRequest
    from datetime import datetime, timezone

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test",
        event_timestamp=datetime.now(timezone.utc)
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _store_episodic("mem_test123456", body)

    assert result is False


def test_store_emotional_success():
    """Test _store_emotional helper function success case"""
    from src.routers.memories import _store_emotional
    from src.schemas import DirectMemoryRequest

    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test emotional memory",
        emotional_state="happy",
        valence=0.8,
        arousal=0.6
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _store_emotional("mem_test123456", body)

    assert result is True
    assert mock_conn._committed is True
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert "INSERT INTO emotional_memories" in query


def test_store_emotional_connection_unavailable():
    """Test _store_emotional returns False when connection unavailable"""
    from src.routers.memories import _store_emotional
    from src.schemas import DirectMemoryRequest

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test",
        emotional_state="happy"
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _store_emotional("mem_test123456", body)

    assert result is False


def test_store_procedural_success():
    """Test _store_procedural helper function success case"""
    from src.routers.memories import _store_procedural
    from src.schemas import DirectMemoryRequest

    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test procedural memory",
        skill_name="python",
        proficiency_level="advanced"
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _store_procedural("mem_test123456", body)

    assert result is True
    assert mock_conn._committed is True
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert "INSERT INTO procedural_memories" in query
    assert "ON CONFLICT" in query  # UPSERT logic


def test_store_procedural_connection_unavailable():
    """Test _store_procedural returns False when connection unavailable"""
    from src.routers.memories import _store_procedural
    from src.schemas import DirectMemoryRequest

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test",
        skill_name="python"
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _store_procedural("mem_test123456", body)

    assert result is False


def test_store_episodic_database_error_rollback():
    """Test _store_episodic rollback on database error"""
    from src.routers.memories import _store_episodic
    from src.schemas import DirectMemoryRequest
    from datetime import datetime, timezone

    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor, should_fail=True)

    body = DirectMemoryRequest(
        user_id="test-user",
        content="Test",
        event_timestamp=datetime.now(timezone.utc)
    )

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _store_episodic("mem_test123456", body)

    assert result is False
    assert mock_conn._rolled_back is True


# =============================================================================
# Story 10.3: Delete Memory Tests (AC #2)
# =============================================================================

class _MockChromaCollection:
    """Mock ChromaDB collection for delete tests"""

    def __init__(self, ids=None, metadatas=None, get_raises=False, delete_raises=False):
        self._ids = ids or []
        self._metadatas = metadatas or []
        self._get_raises = get_raises
        self._delete_raises = delete_raises
        self._deleted_ids = []

    def get(self, ids, include=None):
        if self._get_raises:
            raise Exception("ChromaDB get error")
        # Return only matching ids
        result_ids = [id for id in ids if id in self._ids]
        result_metadatas = [
            self._metadatas[self._ids.index(id)]
            for id in result_ids
            if id in self._ids
        ]
        return {"ids": result_ids, "metadatas": result_metadatas}

    def delete(self, ids):
        if self._delete_raises:
            raise Exception("ChromaDB delete error")
        self._deleted_ids.extend(ids)


class _MockChromaClient:
    """Mock ChromaDB client for delete tests"""

    def __init__(self, collection=None, get_collection_raises=False):
        self._collection = collection
        self._get_collection_raises = get_collection_raises

    def get_collection(self, name):
        if self._get_collection_raises:
            raise Exception("Collection error")
        return self._collection


def test_delete_memory_success(api_client, monkeypatch):
    """Test successful memory deletion (AC #2 - successful deletion)"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{"user_id": "test-user-123", "stored_in_episodic": False}]
    )
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["deleted"] is True
    assert data["memory_id"] == "mem_test123456"
    assert data["storage"]["chromadb"] is True
    assert "mem_test123456" in mock_collection._deleted_ids


def test_delete_memory_not_found(api_client, monkeypatch):
    """Test memory not found returns appropriate error (AC #2 - not found)"""
    mock_collection = _MockChromaCollection(ids=[], metadatas=[])
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_nonexistent?user_id=test-user-123")

    assert response.status_code == 200  # Returns error in response body
    data = response.json()

    assert data["status"] == "error"
    assert data["deleted"] is False
    assert data["memory_id"] == "mem_nonexistent"
    assert "not found" in data["message"].lower()


def test_delete_memory_unauthorized(api_client, monkeypatch):
    """Test unauthorized deletion returns 403 (AC #2 - unauthorized)"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{"user_id": "other-user-456"}]  # Different user owns this memory
    )
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 403
    data = response.json()
    assert "unauthorized" in data["detail"].lower()


def test_delete_memory_cross_storage_episodic(api_client, monkeypatch):
    """Test cross-storage deletion includes episodic table (AC #2 - cross-storage)"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{
            "user_id": "test-user-123",
            "stored_in_episodic": True,
            "stored_in_emotional": False,
            "stored_in_procedural": False
        }]
    )
    mock_client = _MockChromaClient(collection=mock_collection)
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["deleted"] is True
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["episodic"] is True
    # Verify episodic DELETE was executed
    assert any("DELETE FROM episodic_memories" in q[0] for q in mock_cursor.queries)


def test_delete_memory_cross_storage_emotional(api_client, monkeypatch):
    """Test cross-storage deletion includes emotional table"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{
            "user_id": "test-user-123",
            "stored_in_episodic": False,
            "stored_in_emotional": True,
            "stored_in_procedural": False
        }]
    )
    mock_client = _MockChromaClient(collection=mock_collection)
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["emotional"] is True


def test_delete_memory_cross_storage_procedural(api_client, monkeypatch):
    """Test cross-storage deletion includes procedural table"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{
            "user_id": "test-user-123",
            "stored_in_episodic": False,
            "stored_in_emotional": False,
            "stored_in_procedural": True
        }]
    )
    mock_client = _MockChromaClient(collection=mock_collection)
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["procedural"] is True


def test_delete_memory_cross_storage_all_tables(api_client, monkeypatch):
    """Test cross-storage deletion from all typed tables simultaneously"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{
            "user_id": "test-user-123",
            "stored_in_episodic": True,
            "stored_in_emotional": True,
            "stored_in_procedural": True
        }]
    )
    mock_client = _MockChromaClient(collection=mock_collection)
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["storage"]["chromadb"] is True
    assert data["storage"]["episodic"] is True
    assert data["storage"]["emotional"] is True
    assert data["storage"]["procedural"] is True


def test_delete_memory_chromadb_client_unavailable(api_client, monkeypatch):
    """Test error handling when ChromaDB client is unavailable"""
    with patch("src.routers.memories.get_chroma_client", return_value=None):
        response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["deleted"] is False
    assert "unavailable" in data["message"].lower()


def test_delete_memory_collection_error(api_client, monkeypatch):
    """Test error handling when collection access fails"""
    mock_client = _MockChromaClient(get_collection_raises=True)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["deleted"] is False
    assert "collection" in data["message"].lower()


def test_delete_memory_get_metadata_error(api_client, monkeypatch):
    """Test error handling when getting metadata fails"""
    mock_collection = _MockChromaCollection(get_raises=True)
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["deleted"] is False
    assert "metadata" in data["message"].lower()


def test_delete_memory_chromadb_delete_error(api_client, monkeypatch):
    """Test error handling when ChromaDB deletion fails"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{"user_id": "test-user-123"}],
        delete_raises=True
    )
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["deleted"] is False
    assert data["storage"]["chromadb"] is False


def test_delete_memory_typed_table_failure_continues(api_client, monkeypatch):
    """Test typed table deletion failure doesn't fail overall deletion (best-effort)"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{
            "user_id": "test-user-123",
            "stored_in_episodic": True,
            "stored_in_emotional": False,
            "stored_in_procedural": False
        }]
    )
    mock_client = _MockChromaClient(collection=mock_collection)

    # Return None for timescale connection (simulates connection failure)
    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            with patch("src.routers.memories.get_timescale_conn", return_value=None):
                response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    # Overall deletion succeeded (ChromaDB succeeded)
    assert data["status"] == "success"
    assert data["deleted"] is True
    assert data["storage"]["chromadb"] is True
    # Episodic deletion failed but didn't fail the request
    assert data["storage"]["episodic"] is False


def test_delete_memory_missing_user_id(api_client):
    """Test missing user_id query parameter returns 422"""
    response = api_client.delete("/v1/memories/mem_test123456")

    assert response.status_code == 422


def test_delete_memory_no_user_id_in_metadata(api_client, monkeypatch):
    """Test deletion succeeds when metadata has no user_id (legacy memory)"""
    mock_collection = _MockChromaCollection(
        ids=["mem_test123456"],
        metadatas=[{"stored_in_episodic": False}]  # No user_id in metadata
    )
    mock_client = _MockChromaClient(collection=mock_collection)

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        with patch("src.routers.memories._standard_collection_name", return_value="test_collection"):
            response = api_client.delete("/v1/memories/mem_test123456?user_id=test-user-123")

    # Should succeed since no user_id means no auth check
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


# =============================================================================
# Delete Helper Function Tests
# =============================================================================

def test_delete_from_episodic_success():
    """Test _delete_from_episodic helper function success case"""
    from src.routers.memories import _delete_from_episodic

    mock_cursor = _MockCursor()
    mock_cursor.rowcount = 1
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _delete_from_episodic("mem_test123456", "test-user")

    assert result is True
    assert mock_conn._committed is True
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert "DELETE FROM episodic_memories" in query


def test_delete_from_episodic_connection_unavailable():
    """Test _delete_from_episodic returns False when connection unavailable"""
    from src.routers.memories import _delete_from_episodic

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _delete_from_episodic("mem_test123456", "test-user")

    assert result is False


def test_delete_from_emotional_success():
    """Test _delete_from_emotional helper function success case"""
    from src.routers.memories import _delete_from_emotional

    mock_cursor = _MockCursor()
    mock_cursor.rowcount = 1
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _delete_from_emotional("mem_test123456", "test-user")

    assert result is True
    assert mock_conn._committed is True
    query, params = mock_cursor.queries[0]
    assert "DELETE FROM emotional_memories" in query


def test_delete_from_emotional_connection_unavailable():
    """Test _delete_from_emotional returns False when connection unavailable"""
    from src.routers.memories import _delete_from_emotional

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _delete_from_emotional("mem_test123456", "test-user")

    assert result is False


def test_delete_from_procedural_success():
    """Test _delete_from_procedural helper function success case"""
    from src.routers.memories import _delete_from_procedural

    mock_cursor = _MockCursor()
    mock_cursor.rowcount = 1
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _delete_from_procedural("mem_test123456", "test-user")

    assert result is True
    assert mock_conn._committed is True
    query, params = mock_cursor.queries[0]
    assert "DELETE FROM procedural_memories" in query


def test_delete_from_procedural_connection_unavailable():
    """Test _delete_from_procedural returns False when connection unavailable"""
    from src.routers.memories import _delete_from_procedural

    with patch("src.routers.memories.get_timescale_conn", return_value=None):
        result = _delete_from_procedural("mem_test123456", "test-user")

    assert result is False


def test_delete_from_episodic_database_error_rollback():
    """Test _delete_from_episodic rollback on database error"""
    from src.routers.memories import _delete_from_episodic

    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor, should_fail=True)

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            result = _delete_from_episodic("mem_test123456", "test-user")

    assert result is False
    assert mock_conn._rolled_back is True


# =============================================================================
# Story 10.5: Additional Validation Tests (AC #3)
# =============================================================================

def test_validation_importance_below_min(api_client):
    """Test importance must be >= 0.0 (AC #3)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "importance": -0.1  # Below minimum
    })

    assert response.status_code == 422


def test_validation_importance_above_max(api_client):
    """Test importance must be <= 1.0 (AC #3)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "importance": 1.5  # Above maximum
    })

    assert response.status_code == 422


def test_validation_confidence_below_min(api_client):
    """Test confidence must be >= 0.0 (AC #3)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "confidence": -0.1  # Below minimum
    })

    assert response.status_code == 422


def test_validation_confidence_above_max(api_client):
    """Test confidence must be <= 1.0 (AC #3)"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "confidence": 1.5  # Above maximum
    })

    assert response.status_code == 422


def test_validation_content_max_length(api_client):
    """Test content max_length constraint (5000 chars) (AC #3)"""
    # Create content with more than 5000 characters
    long_content = "x" * 5001

    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": long_content
    })

    assert response.status_code == 422


def test_validation_content_at_max_length(api_client, monkeypatch):
    """Test content at exactly max_length is accepted"""
    mock_embedding = [0.1] * 1536

    # Create content with exactly 5000 characters
    max_content = "x" * 5000

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user",
                "content": max_content
            })

    assert response.status_code == 200


def test_validation_empty_content(api_client, monkeypatch):
    """Test empty content handling - embedding still attempted"""
    # Note: Schema doesn't have min_length on content, so empty string is accepted
    # but will likely fail on embedding generation
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "test-user",
                "content": ""
            })

    # Schema accepts empty string (no min_length constraint)
    assert response.status_code == 200


def test_validation_empty_user_id(api_client, monkeypatch):
    """Test empty user_id handling - storage will work but user_id is empty"""
    # Note: Schema doesn't have min_length on user_id, so empty string is accepted
    mock_embedding = [0.1] * 1536

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            response = api_client.post("/v1/memories/direct", json={
                "user_id": "",
                "content": "Test content"
            })

    # Schema accepts empty string (no min_length constraint)
    assert response.status_code == 200


def test_validation_invalid_layer(api_client):
    """Test invalid layer value is rejected"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "layer": "invalid-layer"
    })

    assert response.status_code == 422


def test_validation_invalid_type(api_client):
    """Test invalid type value is rejected"""
    response = api_client.post("/v1/memories/direct", json={
        "user_id": "test-user",
        "content": "Test",
        "type": "invalid-type"
    })

    assert response.status_code == 422


def test_validation_valence_at_boundaries(api_client, monkeypatch):
    """Test valence at exact boundaries is accepted"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Test at -1.0 (min)
    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "sad",
                        "valence": -1.0
                    })

    assert response.status_code == 200

    # Test at 1.0 (max)
    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "happy",
                        "valence": 1.0
                    })

    assert response.status_code == 200


def test_validation_arousal_at_boundaries(api_client, monkeypatch):
    """Test arousal at exact boundaries is accepted"""
    mock_embedding = [0.1] * 1536
    mock_cursor = _MockCursor()
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Test at 0.0 (min)
    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "calm",
                        "arousal": 0.0
                    })

    assert response.status_code == 200

    # Test at 1.0 (max)
    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", return_value=["mem_test123456"]):
            with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
                with patch("src.routers.memories.release_timescale_conn"):
                    response = api_client.post("/v1/memories/direct", json={
                        "user_id": "test-user",
                        "content": "Test",
                        "emotional_state": "excited",
                        "arousal": 1.0
                    })

    assert response.status_code == 200
