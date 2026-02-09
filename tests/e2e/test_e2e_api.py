"""End-to-end API tests running in Docker container."""

import json
import time


class TestE2EAPI:
    """E2E API tests with real Docker services."""

    def test_health_endpoints(self, api_client, e2e_config):
        """Test health endpoints are working."""
        # Test basic health
        response = api_client.get(f"{e2e_config.api_base_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Test full health
        response = api_client.get(f"{e2e_config.api_base_url}/health/full")
        assert response.status_code == 200
        health_data = response.json()
        assert "status" in health_data
        assert "checks" in health_data
        assert health_data["status"] == "ok"

    def test_store_and_retrieve_basic(self, api_client, e2e_config, test_user_id):
        """Test basic store and retrieve functionality."""
        # Store a conversation
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {"role": "user", "content": "I love sci-fi books and fantasy novels."},
                {
                    "role": "assistant",
                    "content": "That's great! What's your favorite author?",
                },
                {
                    "role": "user",
                    "content": "I really enjoy Isaac Asimov and J.R.R. Tolkien.",
                },
            ],
        }

        store_response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store", json=store_payload
        )
        assert store_response.status_code == 200
        store_data = store_response.json()
        assert "memories_created" in store_data
        assert "ids" in store_data
        assert store_data["memories_created"] > 0
        assert len(store_data["ids"]) == store_data["memories_created"]

        # Wait a moment for indexing
        time.sleep(2)

        # Retrieve memories
        retrieve_response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "sci-fi books", "user_id": test_user_id, "limit": 10},
        )
        assert retrieve_response.status_code == 200
        retrieve_data = retrieve_response.json()
        assert "results" in retrieve_data
        assert "pagination" in retrieve_data
        assert len(retrieve_data["results"]) > 0

        # Verify content quality
        results = retrieve_data["results"]
        content_found = any(
            "sci-fi" in result.get("content", "").lower() for result in results
        )
        assert content_found, f"Expected sci-fi content in results: {results}"

    def test_store_and_retrieve_multiple_conversations(
        self, api_client, e2e_config, sample_conversations
    ):
        """Test storing and retrieving multiple conversations."""
        user_id = sample_conversations[0]["user_id"]

        # Store all conversations
        for conv in sample_conversations:
            response = api_client.post(f"{e2e_config.api_base_url}/v1/store", json=conv)
            assert response.status_code == 200
            time.sleep(1)  # Small delay between stores

        # Test different queries
        queries = [
            ("sci-fi books", "sci-fi"),
            ("Japan vacation", "Japan"),
            ("running exercise", "running"),
            ("work deadlines", "deadlines"),
        ]

        for query, expected_keyword in queries:
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={"query": query, "user_id": user_id, "limit": 10},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) > 0

            # Verify relevant content
            results = data["results"]
            content_found = any(
                expected_keyword.lower() in result.get("content", "").lower()
                for result in results
            )
            assert content_found, (
                f"Expected '{expected_keyword}' in results for query '{query}': {results}"
            )

    def test_retrieve_with_filters(self, api_client, e2e_config, test_user_id):
        """Test retrieve with different filters."""
        # First store some data
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {"role": "user", "content": "I love sci-fi books and fantasy novels."},
                {
                    "role": "user",
                    "content": "I'm planning a vacation to Japan next month.",
                },
                {"role": "user", "content": "I run 3 times a week to stay healthy."},
            ],
        }

        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store", json=store_payload
        )
        assert response.status_code == 200
        time.sleep(2)

        # Test different filters
        filters_to_test = [
            {"layer": "semantic"},
            {"type": "explicit"},
            {"tags": ["behavior"]},
        ]

        for filters in filters_to_test:
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={
                    "query": "user preferences",
                    "user_id": test_user_id,
                    "filters": json.dumps(filters),
                    "limit": 10,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_retrieve_pagination(self, api_client, e2e_config, test_user_id):
        """Test retrieve pagination."""
        # Store multiple conversations to create pagination
        for i in range(5):
            store_payload = {
                "user_id": test_user_id,
                "history": [
                    {
                        "role": "user",
                        "content": f"I love topic {i} and enjoy learning about it.",
                    }
                ],
            }
            response = api_client.post(
                f"{e2e_config.api_base_url}/v1/store", json=store_payload
            )
            assert response.status_code == 200
            time.sleep(0.5)

        # Test pagination
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={
                "query": "user preferences",
                "user_id": test_user_id,
                "limit": 2,
                "offset": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 2
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["offset"] == 0

        # Test second page
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={
                "query": "user preferences",
                "user_id": test_user_id,
                "limit": 2,
                "offset": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 2
        assert data["pagination"]["offset"] == 2

    def test_error_handling(self, api_client, e2e_config):
        """Test error handling scenarios."""
        # Test invalid JSON
        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

        # Test missing required fields
        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store",
            json={"user_id": "test_user_22"},  # Missing history
        )
        assert response.status_code == 422

        # Test invalid query parameters
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "", "user_id": "test_user_22"},  # Empty query
        )
        assert response.status_code == 400

    def test_memory_quality_and_normalization(
        self, api_client, e2e_config, test_user_id
    ):
        """Test memory quality and normalization."""
        # Store conversation with various patterns
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {"role": "user", "content": "I love sci-fi books."},
                {"role": "user", "content": "I'm planning a vacation to Japan."},
                {"role": "user", "content": "I prefer working from home."},
                {"role": "user", "content": "I'm anxious about deadlines."},
            ],
        }

        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store", json=store_payload
        )
        assert response.status_code == 200
        time.sleep(2)

        # Retrieve and check normalization
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user preferences", "user_id": test_user_id, "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()

        # Check that memories are properly normalized
        results = data["results"]
        for result in results:
            content = result.get("content", "")
            # Should start with "User" (normalized)
            assert content.startswith("User"), f"Memory not normalized: {content}"
            # Should not contain first person pronouns
            assert "I " not in content, f"Memory contains first person: {content}"
            assert "I'm " not in content, f"Memory contains first person: {content}"

    def test_structured_retrieval(self, api_client, e2e_config, test_user_id):
        """Test structured retrieval endpoint."""
        # Store some structured data
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {
                    "role": "user",
                    "content": "I'm working on a Python project for data analysis.",
                },
                {
                    "role": "user",
                    "content": "I have a meeting with my team tomorrow at 2 PM.",
                },
                {
                    "role": "user",
                    "content": "I need to buy groceries: milk, bread, and eggs.",
                },
            ],
        }

        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store", json=store_payload
        )
        assert response.status_code == 200
        time.sleep(2)

        # Test structured retrieval
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve/structured",
            params={
                "query": "user tasks and projects",
                "user_id": test_user_id,
                "limit": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "pagination" in data

        # Check that results have structured fields
        results = data["results"]
        for result in results:
            assert "content" in result
            assert "type" in result
            assert "layer" in result
            assert "confidence" in result
