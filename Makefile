# Makefile for agentic-memories

.PHONY: help install venv test test-unit test-integration test-e2e test-all test-fast test-intents test-intents-e2e test-memory test-profile test-coverage start stop clean clean-all lint format docker-logs docker-shell docker-test gh gh-read gh-diff gh-download gh-upload gh-write migrate

# Detect uv or fallback to pip
UV_AVAILABLE := $(shell command -v uv 2>/dev/null)
PYTHON_VERSION := 3.12

# Default target
help: ## Show this help message
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

start: ## Start Docker containers
	./scripts/run_docker.sh
	@echo "Application started at http://localhost:8080"

stop: ## Stop Docker containers
	docker-compose down

clean: ## Clean up logs, results, and volumes
	rm -rf tests/e2e/logs/ tests/e2e/results/
	docker-compose down -v

clean-all: clean ## Clean everything including venv
	rm -rf .venv

# ============================================================
# TESTING - Simple Commands
# ============================================================

# Activate venv for all test commands
VENV := . .venv/bin/activate &&

# Ensure venv exists and dependencies are installed
.venv/bin/activate: requirements.txt
ifdef UV_AVAILABLE
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment with uv (Python $(PYTHON_VERSION))..."; \
		uv venv --python $(PYTHON_VERSION); \
	fi
	@echo "Installing dependencies with uv..."
	@uv pip install -q -r requirements.txt
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

docker-logs: ## Show Docker container logs
	docker-compose logs -f app

docker-shell: ## Open shell in Docker container
	docker exec -it agentic-memories-app-1 /bin/bash

docker-test: ## Run tests inside Docker container
	docker exec -it agentic-memories-app-1 pytest tests/unit tests/integration -v

# ============================================================
# CODE QUALITY
# ============================================================

lint: venv ## Check linting (ruff). Use FIX=1 to auto-fix
	$(VENV) pip install -q ruff
ifdef FIX
	$(VENV) ruff check --fix .
else
	$(VENV) ruff check .
endif

format: venv ## Check formatting (ruff). Use FIX=1 to apply fixes
	$(VENV) pip install -q ruff
ifdef FIX
	$(VENV) ruff format .
else
	$(VENV) ruff format --check .
endif

# ============================================================
# GITHUB ENVIRONMENT MANAGEMENT
# ============================================================

# Default environment is dev
ENV ?= dev

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
