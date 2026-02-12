"""E2E test configuration for deployed application testing."""

import time
import requests
import pytest
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class E2ETestConfig:
    """Configuration for E2E tests."""

    api_base_url: str = "http://localhost:8080"
    test_user_id: str = "test_user_22"
    timeout: int = 30


@pytest.fixture(scope="session")
def e2e_config():
    """E2E test configuration fixture."""
    return E2ETestConfig()


@pytest.fixture(scope="session")
def app_ready(e2e_config):
    """Wait for deployed application to be ready."""
    print("Waiting for deployed application to be ready...")

    max_retries = 60
    for i in range(max_retries):
        try:
            response = requests.get(f"{e2e_config.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                print("Application is ready!")
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    else:
        raise Exception("Application failed to start within timeout")

    yield e2e_config


@pytest.fixture
def api_client(app_ready):
    """API client for E2E testing."""
    return requests.Session()


@pytest.fixture
def test_user_id():
    """Consistent test user ID for all E2E tests."""
    return "test_user_22"


@pytest.fixture
def sample_conversations():
    """Sample conversations for E2E testing."""
    return [
        {
            "user_id": "test_user_22",
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
            "expected_memories": [
                "User loves sci-fi books and fantasy novels.",
                "User enjoys Isaac Asimov and J.R.R. Tolkien.",
            ],
        },
        {
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
            "expected_memories": [
                "User is planning a vacation to Japan next month.",
                "User wants to visit Tokyo, Kyoto, and try authentic ramen.",
            ],
        },
        {
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
            "expected_memories": [
                "User is feeling anxious about work deadlines.",
                "User runs 3 times a week.",
                "Running helps User clear their mind and stay focused.",
            ],
        },
    ]


def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for service to be ready."""
    for i in range(timeout):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return False


@pytest.fixture
def real_api_client(app_ready):
    """Real API client for E2E testing (alias for api_client)."""
    return requests.Session()


@pytest.fixture
def unique_user_id():
    """Generate a unique user ID for test isolation."""
    return f"e2e_test_{uuid4().hex[:8]}"
