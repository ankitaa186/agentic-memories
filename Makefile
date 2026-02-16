# Makefile for agentic-memories

.PHONY: help install .venv/bin/activate venv test test-unit test-integration test-e2e test-all test-fast test-intents test-intents-e2e test-memory test-profile test-coverage start stop clean clean-all lint format logs docker-logs docker-shell docker-test gh gh-read gh-diff gh-download gh-upload gh-write migrate requirements.txt

# Detect uv or fallback to pip
UV_AVAILABLE := $(shell command -v uv 2>/dev/null)
PYTHON_VERSION := 3.12

# Environment mode (dev or prod) - used for Docker commands
# Reads ENVIRONMENT from .env file, falls back to "dev" if not found
ENV ?= $(shell grep -E '^ENVIRONMENT=' .env 2>/dev/null | cut -d'=' -f2 || echo "dev")

# Compose file selection based on ENV
# In prod mode, use both base and production override files
COMPOSE_FILES = $(if $(filter prod,$(ENV)),-f docker-compose.yml -f docker-compose.prod.yml,)

# Default target
help: ## Show this help message
	@echo ""
	@echo "  Environment: Use ENV=prod for production mode (e.g., make start ENV=prod)"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "  Setup:"
	@grep -E '^(install|start|stop|clean|clean-all):.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Testing:"
	@grep -E '^test[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Code Quality:"
	@grep -E '^(lint|format):.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Docker:"
	@grep -E '^docker[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Database:"
	@grep -E '^migrate[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  GitHub (use ENV=prod for production):"
	@grep -E '^gh[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ============================================================
# SETUP
# ============================================================

install: venv ## Setup venv and install dependencies
	@echo "Dependencies installed in .venv/"

start: ## Start Docker containers (use ENV=prod for production)
	@ENV=$(ENV) ./scripts/run_docker.sh
	@echo "Application started at http://localhost:8080"

stop: ## Stop Docker containers (use ENV=prod for production)
	@echo "Stopping Agentic Memories services..."
	@docker compose $(COMPOSE_FILES) down

clean: ## Clean up logs, results, and volumes
	rm -rf tests/e2e/logs/ tests/e2e/results/
	@docker compose $(COMPOSE_FILES) down -v

clean-all: clean ## Clean everything including venv
	rm -rf .venv

# ============================================================
# TESTING - Simple Commands
# ============================================================

# Activate venv for all test commands
VENV := . .venv/bin/activate &&

requirements.txt:
	@uv export --no-dev --no-hashes --format requirements.txt --output-file requirements.txt

# Ensure venv exists and dependencies are installed
.venv/bin/activate:
ifdef UV_AVAILABLE
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment with uv (Python $(PYTHON_VERSION))..."; \
		uv venv --python $(PYTHON_VERSION); \
	fi
	@echo "Installing dependencies with uv..."
	@uv sync
else
	@echo "uv not found, using pip (install uv for faster installs: curl -LsSf https://astral.sh/uv/install.sh | sh)"
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		python$(PYTHON_VERSION) -m venv .venv || python3 -m venv .venv; \
	fi
	@echo "Installing dependencies..."
	@$(VENV) pip install --upgrade pip -q
	@$(VENV) pip install -q -r requirements.txt
endif
	@touch .venv/bin/activate

venv: .venv/bin/activate ## Setup venv and install dependencies

test: venv ## Run all tests (unit + integration, no e2e)
	$(VENV) pytest tests/unit tests/integration -v

test-fast: venv ## Run unit tests only (fastest)
	$(VENV) pytest tests/unit -q

test-unit: venv ## Run unit tests only
	$(VENV) pytest tests/unit -v $(PYTEST_ARGS)

test-integration: venv ## Run integration tests (mocked DB)
	$(VENV) pytest tests/integration -v $(PYTEST_ARGS)

test-e2e: venv ## Run E2E tests (requires Docker)
	@if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then \
		echo "Error: Docker container not running. Run 'make start' first."; \
		exit 1; \
	fi
	$(VENV) pytest tests/e2e -v

test-all: venv ## Run ALL tests including E2E (requires Docker)
	@if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then \
		echo "Error: Docker container not running. Run 'make start' first."; \
		exit 1; \
	fi
	$(VENV) pytest tests -v

# ============================================================
# TESTING - Specific Test Suites
# ============================================================

test-intents: venv ## Run all intent-related tests
	$(VENV) pytest tests/unit/test_intent*.py tests/unit/test_next_check*.py tests/integration/test_intents*.py -v

test-intents-e2e: venv ## Run intent E2E tests (requires Docker)
	@if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then \
		echo "Error: Docker container not running. Run 'make start' first."; \
		exit 1; \
	fi
	$(VENV) pytest tests/e2e/test_intents_e2e.py -v

test-memory: venv ## Run memory-related tests
	$(VENV) pytest tests -k "memory or store or retrieve" -v --ignore=tests/e2e

test-profile: venv ## Run profile-related tests
	$(VENV) pytest tests -k "profile" -v --ignore=tests/e2e

test-coverage: venv ## Run tests with coverage report
	$(VENV) pytest tests/unit tests/integration --cov=src --cov-report=term-missing --cov-report=html

# ============================================================
# DOCKER
# ============================================================

logs: ## Tail logs (shorthand). Usage: make logs / make logs SERVICE=api
	@docker compose $(COMPOSE_FILES) logs -f --tail 100 $(SERVICE)

docker-logs: ## Show Docker container logs (use ENV=prod for production, SERVICE=name for specific)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Viewing logs from all services..."; \
		docker compose $(COMPOSE_FILES) logs -f; \
	else \
		echo "Viewing logs from $(SERVICE)..."; \
		docker compose $(COMPOSE_FILES) logs -f $(SERVICE); \
	fi

docker-shell: ## Open shell in Docker container (use SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Error: SERVICE variable is required"; \
		echo "Usage: make docker-shell SERVICE=api"; \
		exit 1; \
	fi
	@echo "Accessing $(SERVICE) shell..."
	@docker compose $(COMPOSE_FILES) exec $(SERVICE) /bin/bash || docker compose $(COMPOSE_FILES) exec $(SERVICE) /bin/sh

docker-test: ## Run tests inside Docker container
	docker compose $(COMPOSE_FILES) exec api pytest tests/unit tests/integration -v

docker-rebuild: ## Rebuild Docker containers (use ENV=prod for production)
	@echo "Rebuilding containers..."
	@docker compose $(COMPOSE_FILES) build --no-cache
	@echo "Containers rebuilt."

docker-health: ## Check service health (use ENV=prod for production)
	@echo "Checking service health..."
	@docker compose $(COMPOSE_FILES) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

check-loki: ## Verify Loki Docker plugin is installed
	@if docker plugin ls 2>/dev/null | grep -q "loki.*true"; then \
		echo "✓ Loki plugin installed and enabled"; \
	else \
		echo "✗ Loki plugin not installed"; \
		echo "Install with: docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions"; \
		exit 1; \
	fi

# ============================================================
# CODE QUALITY
# ============================================================

lint: venv ## Check linting (ruff). Use FIX=1 to auto-fix
	$(VENV) if ! command -v ruff >/dev/null 2>&1; then pip install -q "ruff~=0.15.0"; fi
ifdef FIX
	$(VENV) ruff check --fix .
else
	$(VENV) ruff check .
endif

format: venv ## Check formatting (ruff). Use FIX=1 to apply fixes
	$(VENV) if ! command -v ruff >/dev/null 2>&1; then pip install -q "ruff~=0.15.0"; fi
ifdef FIX
	$(VENV) ruff format .
else
	$(VENV) ruff format --check .
endif

# ============================================================
# GITHUB ENVIRONMENT MANAGEMENT
# ============================================================

gh: ## Interactive GitHub environment manager
	@python3 scripts/github_env.py

gh-read: ## Read GitHub environment variables/secrets
	@python3 scripts/github_env.py read --env $(ENV)

gh-diff: ## Show diff between local .env and GitHub
	@python3 scripts/github_env.py diff --env $(ENV)

gh-download: ## Download from GitHub to local .env (GitHub → local)
	@python3 scripts/github_env.py download --env $(ENV)

gh-upload: ## Upload local .env to GitHub (local → GitHub)
	@python3 scripts/github_env.py upload --env $(ENV)

gh-write: ## Write all .env values to GitHub (creates & overwrites)
	@python3 scripts/github_env.py write --env $(ENV)

# ============================================================
# DATABASE MIGRATIONS
# ============================================================

migrate: venv ## Run database migrations (interactive mode)
	$(VENV) ./migrations/migrate.sh
