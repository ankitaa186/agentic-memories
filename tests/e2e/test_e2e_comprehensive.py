"""Comprehensive E2E tests using generated test data."""

import json
import time
import pytest
from pathlib import Path
from tests.evals.metrics import score_predictions


class TestE2EComprehensive:
    """Comprehensive E2E tests using generated test data."""

    @pytest.fixture
    def test_data(self):
        """Load test data from fixtures."""
        test_data_file = Path(__file__).parent / "fixtures" / "e2e_test_data_small.json"

        if not test_data_file.exists():
            # Generate test data if it doesn't exist
            from tests.e2e.fixtures.generate_test_data import E2ETestDataGenerator

            generator = E2ETestDataGenerator()
            test_data = generator.generate_test_suite(5)

            with open(test_data_file, "w") as f:
                json.dump(test_data, f, indent=2)
        else:
            with open(test_data_file, "r") as f:
                test_data = json.load(f)

        return test_data

    def test_store_all_conversations(self, api_client, e2e_config, test_data):
        """Test storing all conversations from test data."""
        conversations = test_data["conversations"]

        print(f"Storing {len(conversations)} conversations...")

        for i, conversation in enumerate(conversations):
            response = api_client.post(
                f"{e2e_config.api_base_url}/v1/store", json=conversation
            )
            assert response.status_code == 200, (
                f"Failed to store conversation {i}: {response.text}"
            )

            data = response.json()
            assert data["memories_created"] > 0, (
                f"No memories created for conversation {i}"
            )

            print(
                f"Conversation {i + 1}/{len(conversations)}: {data['memories_created']} memories created"
            )
            time.sleep(0.5)  # Small delay between stores

        print("All conversations stored successfully!")

    def test_retrieve_with_various_queries(self, api_client, e2e_config, test_data):
        """Test retrieving memories with various queries."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Test queries based on topics
        queries = [
            "sci-fi books",
            "Japan vacation",
            "Python programming",
            "running exercise",
            "work projects",
            "health fitness",
            "travel plans",
            "data analysis",
        ]

        for query in queries:
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={"query": query, "user_id": test_user_id, "limit": 10},
            )
            assert response.status_code == 200, (
                f"Failed to retrieve for query '{query}'"
            )

            data = response.json()
            print(f"Query '{query}': {len(data['results'])} results")

            # Check that we get some results for most queries
            if len(data["results"]) == 0:
                print(f"Warning: No results for query '{query}'")

    def test_memory_quality_evaluation(self, api_client, e2e_config, test_data):
        """Test memory quality against expected memories."""
        test_user_id = test_data["test_user_id"]
        expected_memories = test_data["expected_memories"]

        # Wait for indexing
        time.sleep(3)

        # Retrieve all memories
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user information", "user_id": test_user_id, "limit": 50},
        )
        assert response.status_code == 200

        data = response.json()
        predicted_memories = [result["content"] for result in data["results"]]

        # Calculate metrics
        metrics = score_predictions(expected_memories, predicted_memories)

        print("Memory Quality Metrics:")
        print(f"  Recall: {metrics['recall']:.3f}")
        print(f"  Precision: {metrics['precision']:.3f}")
        print(f"  F1 Score: {metrics['f1']:.3f}")

        # Assert quality thresholds
        assert metrics["recall"] >= 0.3, f"Recall too low: {metrics['recall']:.3f}"
        assert metrics["precision"] >= 0.3, (
            f"Precision too low: {metrics['precision']:.3f}"
        )
        assert metrics["f1"] >= 0.3, f"F1 score too low: {metrics['f1']:.3f}"

    def test_memory_normalization_quality(self, api_client, e2e_config, test_data):
        """Test memory normalization quality."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Retrieve memories
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user information", "user_id": test_user_id, "limit": 50},
        )
        assert response.status_code == 200

        data = response.json()
        results = data["results"]

        # Check normalization quality
        normalization_issues = []

        for result in results:
            content = result.get("content", "")

            # Check for proper normalization
            if not content.startswith("User "):
                normalization_issues.append(f"Doesn't start with 'User': {content}")

            if "I " in content or "I'm " in content:
                normalization_issues.append(f"Contains first person: {content}")

            if content.lower().startswith("the user "):
                normalization_issues.append(f"Starts with 'the user': {content}")

        print(f"Normalization issues found: {len(normalization_issues)}")
        for issue in normalization_issues[:5]:  # Show first 5 issues
            print(f"  - {issue}")

        # Allow some normalization issues but not too many
        assert len(normalization_issues) <= len(results) * 0.2, (
            f"Too many normalization issues: {len(normalization_issues)}"
        )

    def test_memory_categorization_quality(self, api_client, e2e_config, test_data):
        """Test memory categorization quality."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Retrieve memories
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user information", "user_id": test_user_id, "limit": 50},
        )
        assert response.status_code == 200

        data = response.json()
        results = data["results"]

        # Check categorization
        types_found = set(result.get("type", "") for result in results)
        layers_found = set(result.get("layer", "") for result in results)
        tags_found = set()

        for result in results:
            if "metadata" in result and "tags" in result["metadata"]:
                tags_found.update(result["metadata"]["tags"])

        print(f"Memory types found: {types_found}")
        print(f"Memory layers found: {layers_found}")
        print(f"Tags found: {list(tags_found)[:10]}...")  # Show first 10 tags

        # Check that we have different types of memories
        assert len(types_found) > 1, (
            f"Expected multiple memory types, got: {types_found}"
        )
        assert len(layers_found) > 1, (
            f"Expected multiple memory layers, got: {layers_found}"
        )

        # Check that explicit memories are properly categorized
        explicit_memories = [r for r in results if r.get("type") == "explicit"]
        assert len(explicit_memories) > 0, "Expected some explicit memories"

        # Check that implicit memories are properly categorized
        implicit_memories = [r for r in results if r.get("type") == "implicit"]
        assert len(implicit_memories) > 0, "Expected some implicit memories"

    def test_retrieval_relevance(self, api_client, e2e_config, test_data):
        """Test retrieval relevance for different queries."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Test different queries and check relevance
        query_tests = [
            ("sci-fi books", ["sci-fi", "fantasy", "books"]),
            ("Japan vacation", ["Japan", "vacation", "Tokyo", "Kyoto"]),
            ("Python programming", ["Python", "programming", "data", "analysis"]),
            ("running exercise", ["run", "exercise", "fitness", "health"]),
            ("work projects", ["work", "project", "Python", "data"]),
        ]

        for query, expected_keywords in query_tests:
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={"query": query, "user_id": test_user_id, "limit": 10},
            )
            assert response.status_code == 200

            data = response.json()
            results = data["results"]

            print(f"Query '{query}': {len(results)} results")

            if len(results) > 0:
                # Check that results contain expected keywords
                relevant_results = []
                for result in results:
                    content = result.get("content", "").lower()
                    if any(keyword.lower() in content for keyword in expected_keywords):
                        relevant_results.append(result)

                relevance_ratio = len(relevant_results) / len(results) if results else 0
                print(f"  Relevance ratio: {relevance_ratio:.2f}")

                # We expect at least some relevant results
                assert len(relevant_results) > 0, (
                    f"No relevant results for query '{query}': {results}"
                )

    def test_structured_retrieval(self, api_client, e2e_config, test_data):
        """Test structured retrieval endpoint."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Test structured retrieval
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve/structured",
            params={
                "query": "user preferences and activities",
                "user_id": test_user_id,
                "limit": 20,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "pagination" in data

        results = data["results"]
        print(f"Structured retrieval: {len(results)} results")

        # Check that results have structured fields
        for result in results:
            assert "content" in result
            assert "type" in result
            assert "layer" in result
            assert "confidence" in result

            # Check that confidence is a valid number
            assert isinstance(result["confidence"], (int, float))
            assert 0 <= result["confidence"] <= 1

    def test_pagination_consistency(self, api_client, e2e_config, test_data):
        """Test pagination consistency."""
        test_user_id = test_data["test_user_id"]

        # Wait for indexing
        time.sleep(3)

        # Test pagination
        page1_response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={
                "query": "user information",
                "user_id": test_user_id,
                "limit": 5,
                "offset": 0,
            },
        )
        assert page1_response.status_code == 200

        page2_response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={
                "query": "user information",
                "user_id": test_user_id,
                "limit": 5,
                "offset": 5,
            },
        )
        assert page2_response.status_code == 200

        page1_data = page1_response.json()
        page2_data = page2_response.json()

        # Check that pages are different
        page1_ids = set(result.get("id", "") for result in page1_data["results"])
        page2_ids = set(result.get("id", "") for result in page2_data["results"])

        # Pages should not overlap (assuming we have enough results)
        if len(page1_ids) > 0 and len(page2_ids) > 0:
            assert len(page1_ids.intersection(page2_ids)) == 0, "Page overlap detected"

        print(f"Page 1: {len(page1_data['results'])} results")
        print(f"Page 2: {len(page2_data['results'])} results")

    def test_error_handling_robustness(self, api_client, e2e_config):
        """Test error handling robustness."""
        # Test various error scenarios
        error_tests = [
            {
                "name": "Invalid JSON",
                "method": "POST",
                "url": f"{e2e_config.api_base_url}/v1/store",
                "data": "invalid json",
                "headers": {"Content-Type": "application/json"},
                "expected_status": 422,
            },
            {
                "name": "Missing required fields",
                "method": "POST",
                "url": f"{e2e_config.api_base_url}/v1/store",
                "data": {"user_id": "test_user_22"},  # Missing history
                "expected_status": 422,
            },
            {
                "name": "Empty query",
                "method": "GET",
                "url": f"{e2e_config.api_base_url}/v1/retrieve",
                "params": {"query": "", "user_id": "test_user_22"},
                "expected_status": 400,
            },
            {
                "name": "Invalid user ID",
                "method": "GET",
                "url": f"{e2e_config.api_base_url}/v1/retrieve",
                "params": {"query": "test", "user_id": ""},
                "expected_status": 200,  # Should handle empty user ID gracefully
            },
        ]

        for test in error_tests:
            print(f"Testing: {test['name']}")

            if test["method"] == "POST":
                response = api_client.post(
                    test["url"], json=test.get("data"), headers=test.get("headers", {})
                )
            else:
                response = api_client.get(test["url"], params=test.get("params", {}))

            assert response.status_code == test["expected_status"], (
                f"Expected status {test['expected_status']}, got {response.status_code} for {test['name']}"
            )

    def test_performance_under_load(self, api_client, e2e_config, test_data):
        """Test performance under load."""
        test_user_id = test_data["test_user_id"]

        # Test concurrent requests
        import threading

        results = []
        errors = []

        def make_request():
            try:
                response = api_client.get(
                    f"{e2e_config.api_base_url}/v1/retrieve",
                    params={
                        "query": "user information",
                        "user_id": test_user_id,
                        "limit": 10,
                    },
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print(f"Concurrent requests: {len(results)} successful, {len(errors)} errors")

        # Check that most requests succeeded
        success_rate = (
            len(results) / (len(results) + len(errors))
            if (len(results) + len(errors)) > 0
            else 0
        )
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2f}"

        # Check that all successful requests returned 200
        for status_code in results:
            assert status_code == 200, f"Unexpected status code: {status_code}"
