"""Integration test configuration.

This module provides shared fixtures for integration tests that use mocked
database connections and FastAPI's TestClient.

Note: E2E fixtures (real HTTP client, app_ready, etc.) are located in
tests/e2e/conftest.py for tests running against the deployed Docker container.
"""

import os

# Some integration tests do `from src.app import app` directly (bypassing the
# `api_client` fixture in `tests/conftest.py` that monkeypatches env). The app's
# startup hook fails fast with `RuntimeError: LLM not configured` if
# LLM_PROVIDER is unset — locally most devs have it set in their shell, but CI
# does not. Set sentinels here at conftest load time (before any test imports
# `src.app`) so the startup config check passes. These are stub values; no real
# API calls are made in test mode (Redis/Chroma fakes are wired by individual
# tests via `unittest.mock.patch`).
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key-integration-conftest")


# Integration-specific fixtures can be added here as needed.
# Currently, integration tests define their fixtures locally in test files.
