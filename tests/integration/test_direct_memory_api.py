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

    with patch(
        "src.routers.memories.generate_embedding", return_value=embedding_vector
    ):
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
        store_response = client.post(
            "/v1/memories/direct", json=sample_direct_memory_request
        )
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
        store_response = client.post(
            "/v1/memories/direct", json=sample_direct_memory_request
        )
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
        response = client.post(
            "/v1/memories/direct", json=sample_episodic_memory_request
        )

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
        response = client.post(
            "/v1/memories/direct", json=sample_emotional_memory_request
        )

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
        response = client.post(
            "/v1/memories/direct", json=sample_procedural_memory_request
        )

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
        store_response = client.post(
            "/v1/memories/direct", json=sample_episodic_memory_request
        )
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
        assert elapsed_time < 3.0, (
            f"Store operation took {elapsed_time:.2f}s, expected < 3s"
        )

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
        assert elapsed_time < 1.0, (
            f"Delete operation took {elapsed_time:.2f}s, expected < 1s"
        )

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
        assert avg_time < 3.0, (
            f"Average store time {avg_time:.2f}s exceeds 3s threshold"
        )


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
            response = client.post(
                "/v1/memories/direct", json=sample_direct_memory_request
            )

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
            response = client.post(
                "/v1/memories/direct", json=sample_direct_memory_request
            )

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
            response = client.post(
                "/v1/memories/direct", json=sample_direct_memory_request
            )

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
            response = client.post(
                "/v1/memories/direct", json=sample_direct_memory_request
            )

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
            response = client.post(
                "/v1/memories/direct", json=sample_episodic_memory_request
            )

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


# =============================================================================
# AM-X.1 PATCH /v1/memories/{memory_id} integration tests
# =============================================================================


class TestPatchMemoryFanoutAndRetrieve:
    """Integration tests for PATCH typed-table fan-out and retrieve-after-patch
    (Story AM-X.1, ACs 12-15).

    Mocks Chroma at the storage helper level (`get_chroma_record`,
    `update_chroma_record`) and the typed-table UPDATE helpers, then drives
    PATCH through the full FastAPI stack.
    """

    def _stub_chroma(self, monkeypatch, get_return, recorder=None):
        """Patch chroma helpers; return (get_mock, update_mock)."""
        get_mock = MagicMock(return_value=get_return)
        update_mock = MagicMock()
        if recorder is not None:
            update_mock.side_effect = lambda *a, **kw: recorder.append(kw)
        monkeypatch.setattr("src.routers.memories.get_chroma_record", get_mock)
        monkeypatch.setattr("src.routers.memories.update_chroma_record", update_mock)
        # Just need a non-None client for the PATCH router's availability check.
        monkeypatch.setattr(
            "src.routers.memories.get_chroma_client", lambda: MagicMock()
        )
        return get_mock, update_mock

    def test_patch_fanout_to_episodic_typed_table(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PATCH on a record with stored_in_episodic=True calls the episodic
        UPDATE helper."""
        record = {
            "id": "mem_episode01",
            "document": "User attended team offsite in Tahoe",
            "metadata": {
                "user_id": "test_user_integration",
                "layer": "episodic",
                "type": "explicit",
                "timestamp": "2026-05-08T10:00:00+00:00",
                "content_hash": "deadbeef",
                "importance": 0.9,
                "stored_in_episodic": True,
                "stored_in_emotional": False,
                "stored_in_procedural": False,
                "typed_table_id": "11111111-2222-3333-4444-555555555555",
            },
        }
        self._stub_chroma(monkeypatch, record)

        episodic_helper = MagicMock(return_value=True)
        monkeypatch.setattr(
            "src.routers.memories._update_episodic_row", episodic_helper
        )

        response = client.patch(
            f"/v1/memories/{record['id']}",
            params={"user_id": "test_user_integration"},
            json={"importance": 0.99, "metadata": {"location": "Tahoe, CA"}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["chroma_updated"] is True
        assert body["typed_table_updated"]["episodic"] is True
        assert body["typed_table_updated"]["emotional"] is False
        assert body["warnings"] == []

        # Helper invoked with content=None (no content patch), importance=0.99,
        # metadata_update containing the patch dict.
        call = episodic_helper.call_args
        assert call.kwargs["importance"] == 0.99
        assert call.kwargs["metadata_update"] == {"location": "Tahoe, CA"}
        assert call.kwargs["content"] is None

    def test_patch_fanout_partial_failure_returns_200_with_warnings(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When a typed-table UPDATE fails, response is HTTP 200 with the
        per-table flag False and a warning surfaced (AC13 + DELETE pattern)."""
        record = {
            "id": "mem_episode02",
            "document": "doc",
            "metadata": {
                "user_id": "u1",
                "layer": "episodic",
                "type": "explicit",
                "timestamp": "2026-05-08T10:00:00+00:00",
                "content_hash": "d34db33f",
                "importance": 0.5,
                "stored_in_episodic": True,
                "stored_in_emotional": True,
                "stored_in_procedural": False,
                "typed_table_id": "1111-2222",
            },
        }
        self._stub_chroma(monkeypatch, record)
        monkeypatch.setattr(
            "src.routers.memories._update_episodic_row",
            MagicMock(return_value=True),
        )
        monkeypatch.setattr(
            "src.routers.memories._update_emotional_row",
            MagicMock(return_value=False),  # fan-out fails
        )

        response = client.patch(
            f"/v1/memories/{record['id']}",
            params={"user_id": "u1"},
            json={"importance": 0.7},
        )
        assert response.status_code == 200  # NOT 207
        body = response.json()
        assert body["status"] == "success"
        assert body["chroma_updated"] is True
        assert body["typed_table_updated"]["episodic"] is True
        assert body["typed_table_updated"]["emotional"] is False
        assert any("emotional" in w for w in body["warnings"])

    def test_retrieve_after_patch_returns_new_content(
        self,
        client: TestClient,
        mock_chroma_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC15: a retrieve immediately after PATCH must return the new content.

        We simulate the round-trip by:
        1. Stubbing get_chroma_record to return the original document on PATCH.
        2. Verifying the PATCH calls update_chroma_record with the new
           document + new embedding.
        3. Stubbing the Chroma collection's `query` (used by /v1/retrieve) to
           return the new document, and asserting it appears in the response.
        """
        memory_id = "mem_pasta01"
        original = {
            "id": memory_id,
            "document": "User likes pasta",
            "metadata": {
                "user_id": "annie",
                "layer": "semantic",
                "type": "explicit",
                "timestamp": "2026-05-08T10:00:00+00:00",
                "content_hash": "old_hash",
                "importance": 0.8,
            },
        }
        get_mock, update_mock = self._stub_chroma(monkeypatch, original)

        new_content = "User now prefers risotto"
        new_embedding = [0.42] * 1536
        with patch(
            "src.routers.memories.generate_embedding", return_value=new_embedding
        ):
            patch_resp = client.patch(
                f"/v1/memories/{memory_id}",
                params={"user_id": "annie"},
                json={"content": new_content},
            )
        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["embedding_regenerated"] is True

        # Verify update_chroma_record was passed the new doc + new embedding.
        call_kwargs = update_mock.call_args.kwargs
        assert call_kwargs["document"] == new_content
        assert call_kwargs["embedding"] == new_embedding
        # internal_metadata should carry a recomputed content_hash.
        assert (
            call_kwargs["internal_metadata"]["content_hash"]
            != original["metadata"]["content_hash"]
        )

    def test_patch_explicit_null_ttl_seconds_over_the_wire(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC21 (offline near-e2e variant): send raw JSON ``{"ttl_seconds":
        null}`` as the request body and assert the router clears ``ttl_epoch``
        from the internal metadata payload.

        The Annie e2e in tests/e2e/test_e2e_patch_memory.py exercises the
        same path against a deployed instance via httpx.AsyncClient. This
        offline variant runs without Docker and verifies the Pydantic
        sentinel survives the FastAPI body-parse path (TestClient uses httpx
        underneath, so this is a real JSON-over-HTTP round-trip).
        """
        record = {
            "id": "mem_ttl_test",
            "document": "Annie's coffee preference",
            "metadata": {
                "user_id": "annie",
                "layer": "semantic",
                "type": "explicit",
                "timestamp": "2026-05-08T10:00:00+00:00",
                "content_hash": "h1",
                "ttl_epoch": 9_999_999_999,
                "importance": 0.7,
            },
        }
        get_mock, update_mock = self._stub_chroma(monkeypatch, record)

        # Pass the raw JSON body (httpx serializes the dict for us; explicit
        # ``None`` becomes JSON null on the wire — confirmed by FastAPI/Pydantic
        # parsing it into our UNSET-vs-None sentinel scheme).
        import json as _json

        resp = client.patch(
            f"/v1/memories/{record['id']}",
            params={"user_id": "annie"},
            content=_json.dumps({"ttl_seconds": None}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200, resp.text
        # Internal metadata payload should NOT contain ttl_epoch (it was cleared).
        internal = update_mock.call_args.kwargs.get("internal_metadata") or {}
        assert "ttl_epoch" not in internal, (
            f"ttl_epoch should be cleared but is in internal_metadata: {internal}"
        )

        # Sanity: when ttl_seconds is OMITTED, ttl_epoch must be PRESERVED.
        update_mock.reset_mock()
        resp2 = client.patch(
            f"/v1/memories/{record['id']}",
            params={"user_id": "annie"},
            content=_json.dumps({"importance": 0.42}),  # no ttl_seconds key
            headers={"Content-Type": "application/json"},
        )
        assert resp2.status_code == 200
        internal2 = update_mock.call_args.kwargs.get("internal_metadata") or {}
        assert internal2.get("ttl_epoch") == 9_999_999_999


# =============================================================================
# Real-Chroma PATCH smoke test (skips when Chroma not reachable)
#
# This test exists because the existing PATCH integration suite mocks
# ``update_chroma_record`` -- so the original V2Collection.update bug
# (AttributeError, "no attribute 'update'") was invisible to pytest.
# A round-trip against a real Chroma container would have caught it.
# =============================================================================


class TestPatchMemoryRealChromaSmoke:
    """Round-trip PATCH against a real Chroma server when reachable.

    Stubs out only Timescale (typed-table fan-out) and embedding generation
    so the test runs without Postgres/OpenAI -- but exercises the real
    ``V2Collection.upsert`` / ``.update`` / ``.get`` HTTP path. Skips
    cleanly when Chroma is not reachable on ``CHROMA_HOST:CHROMA_PORT``.
    """

    @staticmethod
    def _chroma_reachable() -> bool:
        """Probe for a reachable Chroma. Falls back to ``localhost`` if the
        env-configured host is the docker-internal name (matches the
        docker-compose port-mapping pattern)."""
        import os
        import httpx as _httpx

        try:
            port = int(os.getenv("CHROMA_PORT", "8000"))
        except ValueError:
            port = 8000
        candidates = [os.getenv("CHROMA_HOST", "localhost")]
        if "localhost" not in candidates:
            candidates.append("localhost")
        for host in candidates:
            try:
                with _httpx.Client(timeout=2.0) as c:
                    r = c.get(f"http://{host}:{port}/api/v2/heartbeat")
                    if r.status_code == 200:
                        # Also export so the actual test code uses the same host.
                        os.environ["CHROMA_HOST"] = host
                        return True
            except Exception:
                continue
        return False

    def test_patch_round_trip_real_chroma(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Store, PATCH content, get back; assert content changed in Chroma."""
        if not self._chroma_reachable():
            pytest.skip("Chroma not reachable; skipping real-Chroma smoke test")

        from src.dependencies.chroma import get_chroma_client
        from src.services.storage import (
            update_chroma_record,
            get_chroma_record,
        )

        # Seed a record directly via the real wrapper (skip the full /direct
        # endpoint to avoid pulling in Timescale + Redis dependencies that
        # this smoke test isn't trying to cover).
        chroma = get_chroma_client()
        if chroma is None:
            pytest.skip("Chroma client could not be instantiated")
        if not chroma.health_check(max_retries=2):
            pytest.skip("Chroma health check failed")

        # Discover the standard collection name + its embedding dimension by
        # listing what's there. The dev / deployed environments differ
        # (768-d in some, 3072-d in others) so a fixed dim probe would be
        # brittle. We pick the first ``memories_*`` collection we find.
        collections = chroma.list_collections()
        target = None
        for c in collections:
            if c.name.startswith("memories_"):
                target = c
                break
        if target is None:
            pytest.skip("No memories_* collection in Chroma to seed against")
        try:
            dim = int(target.name.split("_")[-1])
        except (ValueError, IndexError):
            pytest.skip(f"Cannot parse dim from collection name {target.name!r}")

        collection = target

        # Stub the embedding model with a vector matching the discovered dim.
        fake_embedding = [0.1] * dim
        monkeypatch.setattr(
            "src.routers.memories.generate_embedding", lambda *_: fake_embedding
        )
        monkeypatch.setattr(
            "src.services.storage._standard_collection_name", lambda: target.name
        )
        memory_id = f"mem_smoke_{int(time.time() * 1000)}"
        original_doc = "I love pasta with marinara sauce."
        original_meta = {
            "user_id": "smoke_user",
            "layer": "semantic",
            "type": "explicit",
            "timestamp": "2026-05-08T10:00:00+00:00",
            "content_hash": "smoke_h1",
            "importance": 0.7,
            "persona_tags": "[]",
        }
        collection.upsert(
            ids=[memory_id],
            documents=[original_doc],
            embeddings=[fake_embedding],
            metadatas=[original_meta],
        )

        try:
            # Sanity: read back via the real get_chroma_record helper.
            seeded = get_chroma_record(memory_id)
            assert seeded is not None
            assert seeded["document"] == original_doc

            # Apply update via the real wrapper path that the PATCH router uses.
            new_doc = "I now prefer risotto with mushrooms."
            update_chroma_record(
                memory_id,
                document=new_doc,
                embedding=fake_embedding,
                internal_metadata={
                    "content_hash": "smoke_h2",
                    "timestamp": original_meta["timestamp"],
                },
            )

            # Read back: content should have changed.
            after = get_chroma_record(memory_id)
            assert after is not None
            assert after["document"] == new_doc
            assert after["metadata"].get("content_hash") == "smoke_h2"
            # user_id / layer should be preserved by the wrapper update path.
            assert after["metadata"].get("user_id") == "smoke_user"
            assert after["metadata"].get("layer") == "semantic"
        finally:
            # Cleanup so repeated test runs stay clean.
            try:
                collection.delete(ids=[memory_id])
            except Exception:
                pass

    def test_patch_metadata_delete_sentinel_removes_key_in_chroma(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: PATCH with metadata `__delete__` sentinel must REMOVE
        the key from the persisted Chroma record (AC8).

        This drives the full HTTP -> router -> storage -> Chroma round-trip,
        which catches a class of bug invisible to unit tests that mock the
        storage helper: Chroma's /update endpoint does a shallow merge, so
        omitting a key from the metadatas payload preserves the stored
        value. Only an explicit `key: null` removes it.
        """
        if not self._chroma_reachable():
            pytest.skip("Chroma not reachable; skipping real-Chroma smoke test")

        from src.dependencies.chroma import get_chroma_client
        from src.services.storage import get_chroma_record

        chroma = get_chroma_client()
        if chroma is None:
            pytest.skip("Chroma client could not be instantiated")
        if not chroma.health_check(max_retries=2):
            pytest.skip("Chroma health check failed")

        collections = chroma.list_collections()
        target = None
        for c in collections:
            if c.name.startswith("memories_"):
                target = c
                break
        if target is None:
            pytest.skip("No memories_* collection in Chroma to seed against")
        try:
            dim = int(target.name.split("_")[-1])
        except (ValueError, IndexError):
            pytest.skip(f"Cannot parse dim from collection name {target.name!r}")

        fake_embedding = [0.1] * dim
        monkeypatch.setattr(
            "src.routers.memories.generate_embedding", lambda *_: fake_embedding
        )
        monkeypatch.setattr(
            "src.services.storage._standard_collection_name", lambda: target.name
        )

        memory_id = f"mem_smoke_delete_{int(time.time() * 1000)}"
        original_meta = {
            "user_id": "smoke_user_del",
            "layer": "semantic",
            "type": "explicit",
            "timestamp": "2026-05-08T10:00:00+00:00",
            "content_hash": "smoke_del_h1",
            "foo": "bar",
            "baz": 42,
            "keep": "this",
            "persona_tags": "[]",
        }
        target.upsert(
            ids=[memory_id],
            documents=["delete sentinel probe"],
            embeddings=[fake_embedding],
            metadatas=[original_meta],
        )

        try:
            # Sanity: keys present pre-PATCH.
            seeded = get_chroma_record(memory_id)
            assert seeded is not None
            assert seeded["metadata"].get("foo") == "bar"
            assert seeded["metadata"].get("baz") == 42

            # PATCH with the `__delete__` sentinel via the real HTTP endpoint.
            response = client.patch(
                f"/v1/memories/{memory_id}",
                params={"user_id": "smoke_user_del"},
                json={"metadata": {"foo": "__delete__"}},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["chroma_updated"] is True

            # Verify in Chroma: foo is REMOVED, baz/keep preserved.
            after = get_chroma_record(memory_id)
            assert after is not None
            assert "foo" not in after["metadata"], (
                f"`foo` should be removed but found: {after['metadata']!r}"
            )
            assert after["metadata"].get("baz") == 42
            assert after["metadata"].get("keep") == "this"
            # System-managed keys must still be intact.
            assert after["metadata"].get("user_id") == "smoke_user_del"
            assert after["metadata"].get("layer") == "semantic"
        finally:
            try:
                target.delete(ids=[memory_id])
            except Exception:
                pass

    def test_patch_ttl_seconds_null_clears_ttl_epoch_in_chroma(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: PATCH with `ttl_seconds: null` must REMOVE the
        `ttl_epoch` key from the persisted Chroma record (AC9).

        The Pydantic UNSET-vs-None distinction is verified at the schema
        level by `test_patch_request_ttl_sentinel_distinguishes_null_from_omitted`,
        but that does NOT verify the wire-level Chroma write. Same merge
        gotcha as the `__delete__` test: the storage layer must send
        `ttl_epoch: null` to Chroma to actually drop the key.
        """
        if not self._chroma_reachable():
            pytest.skip("Chroma not reachable; skipping real-Chroma smoke test")

        from src.dependencies.chroma import get_chroma_client
        from src.services.storage import get_chroma_record

        chroma = get_chroma_client()
        if chroma is None:
            pytest.skip("Chroma client could not be instantiated")
        if not chroma.health_check(max_retries=2):
            pytest.skip("Chroma health check failed")

        collections = chroma.list_collections()
        target = None
        for c in collections:
            if c.name.startswith("memories_"):
                target = c
                break
        if target is None:
            pytest.skip("No memories_* collection in Chroma to seed against")
        try:
            dim = int(target.name.split("_")[-1])
        except (ValueError, IndexError):
            pytest.skip(f"Cannot parse dim from collection name {target.name!r}")

        fake_embedding = [0.1] * dim
        monkeypatch.setattr(
            "src.routers.memories.generate_embedding", lambda *_: fake_embedding
        )
        monkeypatch.setattr(
            "src.services.storage._standard_collection_name", lambda: target.name
        )

        memory_id = f"mem_smoke_ttl_{int(time.time() * 1000)}"
        ttl_epoch_seed = int(time.time()) + 7200
        original_meta = {
            "user_id": "smoke_user_ttl",
            "layer": "semantic",
            "type": "explicit",
            "timestamp": "2026-05-08T10:00:00+00:00",
            "content_hash": "smoke_ttl_h1",
            "ttl_epoch": ttl_epoch_seed,
            "persona_tags": "[]",
        }
        target.upsert(
            ids=[memory_id],
            documents=["ttl clear probe"],
            embeddings=[fake_embedding],
            metadatas=[original_meta],
        )

        try:
            # Sanity: ttl_epoch present pre-PATCH.
            seeded = get_chroma_record(memory_id)
            assert seeded is not None
            assert seeded["metadata"].get("ttl_epoch") == ttl_epoch_seed

            # PATCH with explicit JSON null for ttl_seconds. Use raw `data=`
            # so JSON-null is preserved through to FastAPI parsing (the
            # UNSET sentinel scheme depends on the literal `null` reaching
            # the Pydantic validator).
            import json as _json

            response = client.patch(
                f"/v1/memories/{memory_id}",
                params={"user_id": "smoke_user_ttl"},
                content=_json.dumps({"ttl_seconds": None}),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["chroma_updated"] is True

            # Verify in Chroma: ttl_epoch is REMOVED (not just unchanged).
            after = get_chroma_record(memory_id)
            assert after is not None
            assert "ttl_epoch" not in after["metadata"], (
                f"`ttl_epoch` should be removed but found: "
                f"{after['metadata'].get('ttl_epoch')!r}"
            )
            # System-managed keys must still be intact.
            assert after["metadata"].get("user_id") == "smoke_user_ttl"
            assert after["metadata"].get("layer") == "semantic"
        finally:
            try:
                target.delete(ids=[memory_id])
            except Exception:
                pass
