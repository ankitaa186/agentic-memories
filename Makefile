# Makefile for agentic-memories

.PHONY: help install venv test test-unit test-integration test-e2e test-all test-fast test-intents test-intents-e2e test-memory test-profile start stop clean docker-logs docker-shell docker-test

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@echo ""
	@echo "  Setup:"
	@grep -E '^(install|start|stop|clean):.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Testing:"
	@grep -E '^test[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Docker:"
	@grep -E '^docker[a-zA-Z0-9_-]*:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ============================================================
# SETUP
# ============================================================

install: venv ## Setup venv and install dependencies
	@echo "Dependencies installed in .venv/"

start: ## Start Docker containers
	./run_docker.sh
	@echo "Application started at http://localhost:8080"

stop: ## Stop Docker containers
	docker-compose down

clean: ## Clean up logs, results, and volumes
	rm -rf tests/e2e/logs/ tests/e2e/results/
	docker-compose down -v

# ============================================================
# TESTING - Simple Commands
# ============================================================

# Activate venv for all test commands
VENV := . .venv/bin/activate &&

# Ensure venv exists and dependencies are installed
.venv/bin/activate: requirements.txt
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv .venv; \
	fi
	@echo "Installing dependencies..."
	@$(VENV) pip install -q -r requirements.txt
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

# ============================================================
# DOCKER
# ============================================================

docker-logs: ## Show Docker container logs
	docker-compose logs -f app

docker-shell: ## Open shell in Docker container
	docker exec -it agentic-memories-app-1 /bin/bash

docker-test: ## Run tests inside Docker container
	docker exec -it agentic-memories-app-1 pytest tests/unit tests/integration -v
