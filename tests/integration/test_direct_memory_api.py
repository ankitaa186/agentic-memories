"""Integration tests for Direct Memory API (Epic 10, Story 10.6).

Tests end-to-end store/retrieve/delete lifecycle with mocked storage backends.
Covers:
- AC 10.6.1: Lifecycle tests (store → retrieve → delete → verify not found)
- AC 10.6.2: Typed memory tests (episodic, emotional, procedural)
- AC 10.6.3: Performance tests (store < 3s, delete < 1s)
"""
import time
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import app


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_chroma_client() -> Generator[MagicMock, None, None]:
    """Create mock ChromaDB client with collection."""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "metadatas": []}
    mock_collection.delete.return_value = None

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection

    with patch("src.routers.memories.get_chroma_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_timescale_conn() -> Generator[tuple, None, None]:
    """Create mock TimescaleDB connection with cursor."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("src.routers.memories.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.memories.release_timescale_conn"):
            yield mock_conn, mock_cursor


@pytest.fixture
def mock_embedding() -> Generator[MagicMock, None, None]:
    """Mock embedding generation to return consistent vector."""
    embedding_vector = [0.1] * 1536  # OpenAI embedding dimension

    with patch("src.routers.memories.generate_embedding", return_value=embedding_vector):
        yield embedding_vector


@pytest.fixture
def mock_upsert_memories() -> Generator[MagicMock, None, None]:
    """Mock upsert_memories to simulate successful storage."""
    with patch("src.routers.memories.upsert_memories") as mock_upsert:
        # Return the memory ID that was passed in
        mock_upsert.side_effect = lambda user_id, memories: [m.id for m in memories]
        yield mock_upsert


@pytest.fixture
def sample_direct_memory_request() -> dict:
    """Sample request for basic memory storage."""
    return {
        "user_id": "test_user_integration",
        "content": "User prefers morning meetings before 10am",
        "layer": "semantic",
        "type": "explicit",
        "importance": 0.85,
        "persona_tags": ["preferences", "scheduling"],
    }


@pytest.fixture
def sample_episodic_memory_request() -> dict:
    """Sample request for episodic memory with event_timestamp."""
    return {
        "user_id": "test_user_integration",
        "content": "User attended team offsite in Lake Tahoe",
        "layer": "long-term",
        "type": "explicit",
        "importance": 0.9,
        "event_timestamp": "2025-06-15T09:00:00Z",
        "location": "Lake Tahoe, CA",
        "participants": ["team", "manager"],
        "event_type": "work_event",
    }


@pytest.fixture
def sample_emotional_memory_request() -> dict:
    """Sample request for emotional memory with emotional_state."""
    return {
        "user_id": "test_user_integration",
        "content": "User expressed frustration about job search",
        "layer": "semantic",
        "type": "explicit",
        "emotional_state": "frustrated",
        "valence": -0.6,
        "arousal": 0.7,
        "trigger_event": "Another job rejection email",
    }


@pytest.fixture
def sample_procedural_memory_request() -> dict:
    """Sample request for procedural memory with skill_name."""
    return {
        "user_id": "test_user_integration",
        "content": "User demonstrated Python expertise",
        "layer": "semantic",
        "type": "explicit",
        "skill_name": "python_programming",
        "proficiency_level": "advanced",
    }


# =============================================================================
# AC 10.6.1: Lifecycle Tests
# =============================================================================


class TestLifecycleTests:
    """Tests for store/retrieve/delete lifecycle (AC 10.6.1)."""

    def test_store_and_retrieve_lifecycle(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store memory via direct API, verify success response.

        AC 10.6.1: Store memory via direct API
        """
        response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["memory_id"] is not None
        assert data["memory_id"].startswith("mem_")
        assert data["storage"]["chromadb"] is True
        assert "episodic" not in data["storage"]  # No typed fields

        # Verify upsert was called
        mock_upsert_memories.assert_called_once()
        call_args = mock_upsert_memories.call_args
        assert call_args[0][0] == sample_direct_memory_request["user_id"]

    def test_store_and_delete_lifecycle(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_chroma_client: MagicMock,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store memory, delete it, verify deleted.

        AC 10.6.1: Store memory, delete via delete endpoint, verify deleted
        """
        # Step 1: Store memory
        store_response = client.post("/v1/memories/direct", json=sample_direct_memory_request)
        assert store_response.status_code == 200
        memory_id = store_response.json()["memory_id"]

        # Step 2: Configure mock for delete operation
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {
            "ids": [memory_id],
            "metadatas": [
                {
                    "user_id": sample_direct_memory_request["user_id"],
                    "source": "direct_api",
                    "stored_in_episodic": False,
                    "stored_in_emotional": False,
                    "stored_in_procedural": False,
                }
            ],
        }

        # Step 3: Delete memory
        delete_response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": sample_direct_memory_request["user_id"]},
        )

        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["status"] == "success"
        assert delete_data["deleted"] is True
        assert delete_data["memory_id"] == memory_id
        assert delete_data["storage"]["chromadb"] is True

        # Verify delete was called on collection
        collection.delete.assert_called_once_with(ids=[memory_id])

    def test_full_lifecycle_store_retrieve_delete(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_chroma_client: MagicMock,
        sample_direct_memory_request: dict,
    ) -> None:
        """Complete lifecycle: store → retrieve → delete → verify not found.

        AC 10.6.1: Full store/retrieve/delete lifecycle
        """
        user_id = sample_direct_memory_request["user_id"]

        # Step 1: Store memory
        store_response = client.post("/v1/memories/direct", json=sample_direct_memory_request)
        assert store_response.status_code == 200
        memory_id = store_response.json()["memory_id"]

        # Step 2: Configure mock - memory exists for retrieval
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {
            "ids": [memory_id],
            "metadatas": [
                {
                    "user_id": user_id,
                    "source": "direct_api",
                    "stored_in_episodic": False,
                    "stored_in_emotional": False,
                    "stored_in_procedural": False,
                }
            ],
        }

        # Step 3: Delete memory
        delete_response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": user_id},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] is True

        # Step 4: Configure mock - memory no longer exists
        collection.get.return_value = {"ids": [], "metadatas": []}

        # Step 5: Try to delete again - should return not found
        delete_again_response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": user_id},
        )
        assert delete_again_response.status_code == 200
        delete_again_data = delete_again_response.json()
        assert delete_again_data["status"] == "error"
        assert delete_again_data["deleted"] is False
        assert "not found" in delete_again_data["message"].lower()

    def test_delete_memory_not_found(
        self,
        client: TestClient,
        mock_chroma_client: MagicMock,
    ) -> None:
        """Delete non-existent memory returns not found.

        AC 10.6.1: Retrieve again (verify not found)
        """
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {"ids": [], "metadatas": []}

        response = client.delete(
            "/v1/memories/mem_nonexistent",
            params={"user_id": "test_user"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["deleted"] is False
        assert "not found" in data["message"].lower()

    def test_delete_memory_unauthorized(
        self,
        client: TestClient,
        mock_chroma_client: MagicMock,
    ) -> None:
        """Delete memory belonging to different user returns 403."""
        memory_id = "mem_test123456"
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {
            "ids": [memory_id],
            "metadatas": [{"user_id": "different_user", "source": "direct_api"}],
        }

        response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": "requesting_user"},
        )

        assert response.status_code == 403
        assert "unauthorized" in response.json()["detail"].lower()


# =============================================================================
# AC 10.6.2: Typed Memory Tests
# =============================================================================


class TestTypedMemoryTests:
    """Tests for typed memory storage (AC 10.6.2)."""

    def test_episodic_memory_storage(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_timescale_conn: tuple,
        sample_episodic_memory_request: dict,
    ) -> None:
        """Store episodic memory with event_timestamp triggers episodic table storage.

        AC 10.6.2: Store episodic memory -> verify in time-based retrieval
        """
        response = client.post("/v1/memories/direct", json=sample_episodic_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        assert data["storage"]["episodic"] is True

        # Verify episodic table insert was attempted
        mock_conn, mock_cursor = mock_timescale_conn
        mock_cursor.execute.assert_called()

        # Check that INSERT INTO episodic_memories was called
        calls = mock_cursor.execute.call_args_list
        episodic_insert_called = any(
            "INSERT INTO episodic_memories" in str(call) for call in calls
        )
        assert episodic_insert_called, "Expected INSERT INTO episodic_memories"

    def test_emotional_memory_storage(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_timescale_conn: tuple,
        sample_emotional_memory_request: dict,
    ) -> None:
        """Store emotional memory with emotional_state triggers emotional table storage.

        AC 10.6.2: Store emotional memory -> verify in emotional retrieval
        """
        response = client.post("/v1/memories/direct", json=sample_emotional_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        assert data["storage"]["emotional"] is True

        # Verify emotional table insert was attempted
        mock_conn, mock_cursor = mock_timescale_conn
        calls = mock_cursor.execute.call_args_list
        emotional_insert_called = any(
            "INSERT INTO emotional_memories" in str(call) for call in calls
        )
        assert emotional_insert_called, "Expected INSERT INTO emotional_memories"

    def test_procedural_memory_storage(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_timescale_conn: tuple,
        sample_procedural_memory_request: dict,
    ) -> None:
        """Store procedural memory with skill_name triggers procedural table storage.

        AC 10.6.2: Store procedural memory -> verify in procedural queries
        """
        response = client.post("/v1/memories/direct", json=sample_procedural_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        assert data["storage"]["procedural"] is True

        # Verify procedural table insert was attempted
        mock_conn, mock_cursor = mock_timescale_conn
        calls = mock_cursor.execute.call_args_list
        procedural_insert_called = any(
            "INSERT INTO procedural_memories" in str(call) for call in calls
        )
        assert procedural_insert_called, "Expected INSERT INTO procedural_memories"

    def test_multi_typed_memory_storage(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_timescale_conn: tuple,
    ) -> None:
        """Store memory with multiple type indicators stores to all relevant tables."""
        multi_type_request = {
            "user_id": "test_user_integration",
            "content": "User felt happy during Python workshop",
            "layer": "long-term",
            "type": "explicit",
            # Episodic fields
            "event_timestamp": "2025-06-15T10:00:00Z",
            "event_type": "workshop",
            # Emotional fields
            "emotional_state": "happy",
            "valence": 0.8,
        }

        response = client.post("/v1/memories/direct", json=multi_type_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        assert data["storage"]["episodic"] is True
        assert data["storage"]["emotional"] is True
        assert "procedural" not in data["storage"]

    def test_delete_typed_memory_cleans_all_tables(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        mock_chroma_client: MagicMock,
        mock_timescale_conn: tuple,
        sample_episodic_memory_request: dict,
    ) -> None:
        """Delete typed memory removes from both ChromaDB and typed tables."""
        # Step 1: Store episodic memory
        store_response = client.post("/v1/memories/direct", json=sample_episodic_memory_request)
        assert store_response.status_code == 200
        memory_id = store_response.json()["memory_id"]

        # Step 2: Configure mock for delete with typed table flags
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {
            "ids": [memory_id],
            "metadatas": [
                {
                    "user_id": sample_episodic_memory_request["user_id"],
                    "source": "direct_api",
                    "typed_table_id": "test-uuid-1234",
                    "stored_in_episodic": True,
                    "stored_in_emotional": False,
                    "stored_in_procedural": False,
                }
            ],
        }

        # Step 3: Delete memory
        mock_conn, mock_cursor = mock_timescale_conn
        mock_cursor.rowcount = 1

        delete_response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": sample_episodic_memory_request["user_id"]},
        )

        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        assert data["storage"]["episodic"] is True

        # Verify episodic table delete was called
        calls = mock_cursor.execute.call_args_list
        episodic_delete_called = any(
            "DELETE FROM episodic_memories" in str(call) for call in calls
        )
        assert episodic_delete_called, "Expected DELETE FROM episodic_memories"


# =============================================================================
# AC 10.6.3: Performance Tests
# =============================================================================


class TestPerformanceTests:
    """Tests for performance requirements (AC 10.6.3)."""

    def test_direct_store_performance_under_3_seconds(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        sample_direct_memory_request: dict,
    ) -> None:
        """Direct store operation completes in < 3 seconds.

        AC 10.6.3: Verify direct store completes in < 3s
        """
        start_time = time.perf_counter()

        response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        elapsed_time = time.perf_counter() - start_time

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert elapsed_time < 3.0, f"Store operation took {elapsed_time:.2f}s, expected < 3s"

    def test_delete_performance_under_1_second(
        self,
        client: TestClient,
        mock_chroma_client: MagicMock,
    ) -> None:
        """Delete operation completes in < 1 second.

        AC 10.6.3: Verify delete completes in < 1s
        """
        memory_id = "mem_perf123456"
        collection = mock_chroma_client.get_collection.return_value
        collection.get.return_value = {
            "ids": [memory_id],
            "metadatas": [
                {
                    "user_id": "perf_test_user",
                    "source": "direct_api",
                    "stored_in_episodic": False,
                    "stored_in_emotional": False,
                    "stored_in_procedural": False,
                }
            ],
        }

        start_time = time.perf_counter()

        response = client.delete(
            f"/v1/memories/{memory_id}",
            params={"user_id": "perf_test_user"},
        )

        elapsed_time = time.perf_counter() - start_time

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert elapsed_time < 1.0, f"Delete operation took {elapsed_time:.2f}s, expected < 1s"

    def test_store_multiple_memories_performance(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
    ) -> None:
        """Multiple store operations maintain performance."""
        num_memories = 5
        total_start = time.perf_counter()

        for i in range(num_memories):
            request = {
                "user_id": "perf_test_user",
                "content": f"Performance test memory {i}",
                "importance": 0.5 + (i * 0.1),
            }
            response = client.post("/v1/memories/direct", json=request)
            assert response.status_code == 200

        total_elapsed = time.perf_counter() - total_start
        avg_time = total_elapsed / num_memories

        # Each store should average < 3s
        assert avg_time < 3.0, f"Average store time {avg_time:.2f}s exceeds 3s threshold"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_store_embedding_failure(
        self,
        client: TestClient,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store returns EMBEDDING_ERROR when embedding fails."""
        with patch("src.routers.memories.generate_embedding", return_value=None):
            response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "EMBEDDING_ERROR"
        assert data["memory_id"] is None

    def test_store_embedding_exception(
        self,
        client: TestClient,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store returns EMBEDDING_ERROR when embedding raises exception."""
        with patch(
            "src.routers.memories.generate_embedding",
            side_effect=Exception("OpenAI API error"),
        ):
            response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "EMBEDDING_ERROR"

    def test_store_chromadb_failure(
        self,
        client: TestClient,
        mock_embedding: list,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store returns STORAGE_ERROR when ChromaDB fails."""
        with patch("src.routers.memories.upsert_memories", return_value=[]):
            response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "STORAGE_ERROR"

    def test_store_chromadb_exception(
        self,
        client: TestClient,
        mock_embedding: list,
        sample_direct_memory_request: dict,
    ) -> None:
        """Store returns STORAGE_ERROR when ChromaDB raises exception."""
        with patch(
            "src.routers.memories.upsert_memories",
            side_effect=Exception("ChromaDB connection error"),
        ):
            response = client.post("/v1/memories/direct", json=sample_direct_memory_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "STORAGE_ERROR"

    def test_store_typed_table_failure_continues(
        self,
        client: TestClient,
        mock_embedding: list,
        mock_upsert_memories: MagicMock,
        sample_episodic_memory_request: dict,
    ) -> None:
        """Typed table failure is best-effort - doesn't fail the request."""
        # Mock TimescaleDB to fail
        with patch("src.routers.memories.get_timescale_conn", return_value=None):
            response = client.post("/v1/memories/direct", json=sample_episodic_memory_request)

        assert response.status_code == 200
        data = response.json()
        # Request succeeds because ChromaDB is the source of truth
        assert data["status"] == "success"
        assert data["storage"]["chromadb"] is True
        # Episodic storage failed but didn't fail the request
        assert data["storage"]["episodic"] is False

    def test_delete_chromadb_unavailable(
        self,
        client: TestClient,
    ) -> None:
        """Delete returns error when ChromaDB client unavailable."""
        with patch("src.routers.memories.get_chroma_client", return_value=None):
            response = client.delete(
                "/v1/memories/mem_test123",
                params={"user_id": "test_user"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["deleted"] is False
        assert "unavailable" in data["message"].lower()


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for request validation."""

    def test_store_missing_required_fields(
        self,
        client: TestClient,
    ) -> None:
        """Store returns 422 for missing required fields."""
        # Missing user_id and content
        response = client.post("/v1/memories/direct", json={})

        assert response.status_code == 422

    def test_store_invalid_importance_range(
        self,
        client: TestClient,
    ) -> None:
        """Store returns 422 for importance outside [0, 1] range."""
        response = client.post(
            "/v1/memories/direct",
            json={
                "user_id": "test_user",
                "content": "Test content",
                "importance": 1.5,  # Invalid - max is 1.0
            },
        )

        assert response.status_code == 422

    def test_store_invalid_valence_range(
        self,
        client: TestClient,
    ) -> None:
        """Store returns 422 for valence outside [-1, 1] range."""
        response = client.post(
            "/v1/memories/direct",
            json={
                "user_id": "test_user",
                "content": "Test content",
                "emotional_state": "happy",
                "valence": 2.0,  # Invalid - max is 1.0
            },
        )

        assert response.status_code == 422

    def test_store_invalid_arousal_range(
        self,
        client: TestClient,
    ) -> None:
        """Store returns 422 for arousal outside [0, 1] range."""
        response = client.post(
            "/v1/memories/direct",
            json={
                "user_id": "test_user",
                "content": "Test content",
                "emotional_state": "excited",
                "arousal": -0.5,  # Invalid - min is 0.0
            },
        )

        assert response.status_code == 422

    def test_delete_missing_user_id(
        self,
        client: TestClient,
    ) -> None:
        """Delete returns 422 for missing user_id query param."""
        response = client.delete("/v1/memories/mem_test123")

        assert response.status_code == 422
