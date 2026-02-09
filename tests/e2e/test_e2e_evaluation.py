"""E2E evaluation tests for memory extraction quality."""

import time
import pytest
from tests.evals.metrics import score_predictions


class TestE2EEvaluation:
    """E2E evaluation tests for memory extraction quality."""

    @pytest.fixture
    def evaluation_dataset(self):
        """Evaluation dataset with ground truth."""
        return [
            {
                "conversation": {
                    "user_id": "test_user_22",
                    "history": [
                        {
                            "role": "user",
                            "content": "I love sci-fi books and fantasy novels.",
                        },
                        {
                            "role": "assistant",
                            "content": "That's great! What's your favorite author?",
                        },
                        {
                            "role": "user",
                            "content": "I really enjoy Isaac Asimov and J.R.R. Tolkien.",
                        },
                    ],
                },
                "expected_memories": [
                    "User loves sci-fi books and fantasy novels.",
                    "User enjoys Isaac Asimov and J.R.R. Tolkien.",
                ],
                "expected_tags": ["behavior", "personal", "preferences"],
            },
            {
                "conversation": {
                    "user_id": "test_user_22",
                    "history": [
                        {
                            "role": "user",
                            "content": "I'm planning a vacation to Japan next month.",
                        },
                        {
                            "role": "assistant",
                            "content": "That sounds exciting! What are you most looking forward to?",
                        },
                        {
                            "role": "user",
                            "content": "I want to visit Tokyo, Kyoto, and try authentic ramen.",
                        },
                    ],
                },
                "expected_memories": [
                    "User is planning a vacation to Japan next month.",
                    "User wants to visit Tokyo, Kyoto, and try authentic ramen.",
                ],
                "expected_tags": ["project", "travel", "planning"],
            },
            {
                "conversation": {
                    "user_id": "test_user_22",
                    "history": [
                        {
                            "role": "user",
                            "content": "I'm feeling anxious about work deadlines and running 3 times a week.",
                        },
                        {
                            "role": "assistant",
                            "content": "It sounds like you're managing stress well with exercise.",
                        },
                        {
                            "role": "user",
                            "content": "Yes, running helps me clear my mind and stay focused.",
                        },
                    ],
                },
                "expected_memories": [
                    "User is feeling anxious about work deadlines.",
                    "User runs 3 times a week.",
                    "Running helps User clear their mind and stay focused.",
                ],
                "expected_tags": ["emotion", "habits", "stress_management"],
            },
            {
                "conversation": {
                    "user_id": "test_user_22",
                    "history": [
                        {
                            "role": "user",
                            "content": "I'm working on a Python project for data analysis.",
                        },
                        {
                            "role": "assistant",
                            "content": "That's interesting! What kind of data are you analyzing?",
                        },
                        {
                            "role": "user",
                            "content": "I'm analyzing customer behavior data to improve our product.",
                        },
                    ],
                },
                "expected_memories": [
                    "User is working on a Python project for data analysis.",
                    "User is analyzing customer behavior data to improve their product.",
                ],
                "expected_tags": ["project", "technical", "work"],
            },
            {
                "conversation": {
                    "user_id": "test_user_22",
                    "history": [
                        {
                            "role": "user",
                            "content": "I have a meeting with my team tomorrow at 2 PM.",
                        },
                        {
                            "role": "assistant",
                            "content": "Good luck with your meeting!",
                        },
                        {
                            "role": "user",
                            "content": "Thanks, I need to prepare the quarterly report presentation.",
                        },
                    ],
                },
                "expected_memories": [
                    "User has a meeting with their team tomorrow at 2 PM.",
                    "User needs to prepare the quarterly report presentation.",
                ],
                "expected_tags": ["task", "work", "meeting"],
            },
        ]

    def test_memory_extraction_quality(
        self, api_client, e2e_config, evaluation_dataset
    ):
        """Test memory extraction quality against ground truth."""
        all_expected = []
        all_predicted = []

        for item in evaluation_dataset:
            # Store conversation
            response = api_client.post(
                f"{e2e_config.api_base_url}/v1/store", json=item["conversation"]
            )
            assert response.status_code == 200
            time.sleep(1)  # Allow processing time

            # Retrieve memories
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={
                    "query": "user information",
                    "user_id": item["conversation"]["user_id"],
                    "limit": 10,
                },
            )
            assert response.status_code == 200
            data = response.json()

            # Extract predicted memories
            predicted_memories = [result["content"] for result in data["results"]]

            # Add to evaluation sets
            all_expected.extend(item["expected_memories"])
            all_predicted.extend(predicted_memories)

        # Calculate metrics
        metrics = score_predictions(all_expected, all_predicted)

        # Assert quality thresholds
        assert metrics["recall"] >= 0.6, f"Recall too low: {metrics['recall']:.3f}"
        assert metrics["precision"] >= 0.5, (
            f"Precision too low: {metrics['precision']:.3f}"
        )
        assert metrics["f1"] >= 0.5, f"F1 score too low: {metrics['f1']:.3f}"

        print(f"E2E Evaluation Metrics: {metrics}")

    def test_memory_normalization_quality(self, api_client, e2e_config, test_user_id):
        """Test memory normalization quality."""
        # Store conversation with various patterns
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {"role": "user", "content": "I love sci-fi books."},
                {"role": "user", "content": "I'm planning a vacation to Japan."},
                {"role": "user", "content": "I prefer working from home."},
                {"role": "user", "content": "I'm anxious about deadlines."},
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

        # Retrieve memories
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user preferences", "user_id": test_user_id, "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()

        # Check normalization quality
        results = data["results"]
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

        assert len(normalization_issues) == 0, (
            f"Normalization issues: {normalization_issues}"
        )

    def test_memory_categorization_quality(self, api_client, e2e_config, test_user_id):
        """Test memory categorization quality."""
        # Store conversations with different types of content
        conversations = [
            {
                "user_id": test_user_id,
                "history": [
                    {"role": "user", "content": "I love sci-fi books."}
                ],  # Explicit preference
            },
            {
                "user_id": test_user_id,
                "history": [
                    {"role": "user", "content": "I'm feeling stressed about work."}
                ],  # Implicit emotion
            },
            {
                "user_id": test_user_id,
                "history": [
                    {"role": "user", "content": "I need to buy groceries tomorrow."}
                ],  # Short-term task
            },
            {
                "user_id": test_user_id,
                "history": [
                    {"role": "user", "content": "I'm learning Python programming."}
                ],  # Learning goal
            },
        ]

        for conv in conversations:
            response = api_client.post(f"{e2e_config.api_base_url}/v1/store", json=conv)
            assert response.status_code == 200
            time.sleep(0.5)

        # Retrieve and check categorization
        response = api_client.get(
            f"{e2e_config.api_base_url}/v1/retrieve",
            params={"query": "user information", "user_id": test_user_id, "limit": 20},
        )
        assert response.status_code == 200
        data = response.json()

        results = data["results"]

        # Check that we have different types of memories
        types_found = set(result.get("type", "") for result in results)
        layers_found = set(result.get("layer", "") for result in results)

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

    def test_memory_retrieval_relevance(self, api_client, e2e_config, test_user_id):
        """Test memory retrieval relevance."""
        # Store diverse conversations
        conversations = [
            {
                "user_id": test_user_id,
                "history": [
                    {
                        "role": "user",
                        "content": "I love sci-fi books and fantasy novels.",
                    }
                ],
            },
            {
                "user_id": test_user_id,
                "history": [
                    {
                        "role": "user",
                        "content": "I'm planning a vacation to Japan next month.",
                    }
                ],
            },
            {
                "user_id": test_user_id,
                "history": [
                    {"role": "user", "content": "I run 3 times a week to stay healthy."}
                ],
            },
            {
                "user_id": test_user_id,
                "history": [
                    {
                        "role": "user",
                        "content": "I'm working on a Python project for data analysis.",
                    }
                ],
            },
        ]

        for conv in conversations:
            response = api_client.post(f"{e2e_config.api_base_url}/v1/store", json=conv)
            assert response.status_code == 200
            time.sleep(0.5)

        # Test different queries and check relevance
        query_tests = [
            ("sci-fi books", ["sci-fi", "fantasy"]),
            ("Japan vacation", ["Japan", "vacation"]),
            ("running exercise", ["run", "exercise"]),
            ("Python programming", ["Python", "programming"]),
        ]

        for query, expected_keywords in query_tests:
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={"query": query, "user_id": test_user_id, "limit": 5},
            )
            assert response.status_code == 200
            data = response.json()

            results = data["results"]
            assert len(results) > 0, f"No results for query: {query}"

            # Check that results contain expected keywords
            relevant_results = []
            for result in results:
                content = result.get("content", "").lower()
                if any(keyword.lower() in content for keyword in expected_keywords):
                    relevant_results.append(result)

            assert len(relevant_results) > 0, (
                f"No relevant results for query '{query}': {results}"
            )

    def test_memory_persistence_and_consistency(
        self, api_client, e2e_config, test_user_id
    ):
        """Test memory persistence and consistency across retrievals."""
        # Store a conversation
        store_payload = {
            "user_id": test_user_id,
            "history": [
                {"role": "user", "content": "I love sci-fi books and fantasy novels."},
                {
                    "role": "user",
                    "content": "I'm planning a vacation to Japan next month.",
                },
            ],
        }

        response = api_client.post(
            f"{e2e_config.api_base_url}/v1/store", json=store_payload
        )
        assert response.status_code == 200
        time.sleep(2)

        # Retrieve multiple times and check consistency
        results_sets = []
        for i in range(3):
            response = api_client.get(
                f"{e2e_config.api_base_url}/v1/retrieve",
                params={
                    "query": "user preferences",
                    "user_id": test_user_id,
                    "limit": 10,
                },
            )
            assert response.status_code == 200
            data = response.json()
            results_sets.append(set(result["content"] for result in data["results"]))
            time.sleep(1)

        # Check that results are consistent across retrievals
        assert len(results_sets) == 3
        assert results_sets[0] == results_sets[1] == results_sets[2], (
            "Results inconsistent across retrievals"
        )

        # Check that we get the expected content
        all_results = results_sets[0]
        expected_content = [
            "User loves sci-fi books and fantasy novels.",
            "User is planning a vacation to Japan next month.",
        ]

        for expected in expected_content:
            assert any(expected in result for result in all_results), (
                f"Expected content not found: {expected}"
            )
