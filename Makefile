# Developer entry points. Run `make help` for the list.

BACKEND  := backend
FRONTEND := frontend
COMPOSE  := docker compose -f compose/compose.yml
# pyproject pins requires-python to >=3.12,<3.13. uv fetches that interpreter
# instead of trusting whatever `python3` happens to be on PATH.
PY_VER   ?= 3.12
# Electron's dev sidecar spawns `process.env.PYTHON || 'python3'`, so it needs an
# absolute path to the backend venv — a bare `python3` picks up whatever the shell
# happens to have active.
VENV_PY  := $(abspath $(BACKEND)/.venv/bin/python)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Setup -------------------------------------------------------------------

.PHONY: setup
setup: setup-backend setup-frontend ## Install all dependencies

.PHONY: setup-backend
setup-backend: ## Create the backend venv and install it editable
	cd $(BACKEND) && uv venv --python $(PY_VER) && \
		uv pip install --python .venv/bin/python -e ".[dev]"

.PHONY: setup-frontend
setup-frontend: ## Install frontend dependencies
	npm --prefix $(FRONTEND) install

# --- Quality -----------------------------------------------------------------

.PHONY: check
check: lint typecheck test ## Run every check (what CI runs)

.PHONY: lint
lint: ## Lint and format-check the backend, type-check the frontend
	cd $(BACKEND) && .venv/bin/ruff check src tests
	cd $(BACKEND) && .venv/bin/ruff format --check src tests
	npm --prefix $(FRONTEND) run lint

.PHONY: format
format: ## Auto-format and auto-fix the backend
	cd $(BACKEND) && .venv/bin/ruff check --fix src tests
	cd $(BACKEND) && .venv/bin/ruff format src tests

.PHONY: typecheck
typecheck: ## Type-check the backend
	cd $(BACKEND) && .venv/bin/mypy

.PHONY: test
test: backend-test ## Run the test suite

.PHONY: backend-test
backend-test: ## Run backend tests
	cd $(BACKEND) && .venv/bin/pytest

.PHONY: backend-cov
backend-cov: ## Run backend tests with a coverage report
	cd $(BACKEND) && .venv/bin/pytest --cov=rag_backend --cov-report=term-missing

# --- Run ---------------------------------------------------------------------

.PHONY: backend-run
backend-run: ## Run the backend API locally
	cd $(BACKEND) && .venv/bin/python -m rag_backend

.PHONY: frontend-run
frontend-run: ## Run the Next.js dev server
	npm --prefix $(FRONTEND) run dev

.PHONY: desktop
desktop: ## Run the Electron desktop shell against a dev server
	PYTHON="$(VENV_PY)" npm --prefix $(FRONTEND) run electron:dev

.PHONY: dist
dist: ## Build the packaged desktop application
	# package-backend.js otherwise falls back to a bare python3, which may be the
	# wrong version and will not have the backend dependencies installed.
	PYTHON="$(VENV_PY)" npm --prefix $(FRONTEND) run dist

# --- Compose stacks ----------------------------------------------------------

.PHONY: up
up: ## Start the dev stack
	$(COMPOSE) -f compose/compose.dev.yml up --build

.PHONY: up-prod
up-prod: ## Start the production stack detached
	$(COMPOSE) -f compose/compose.prod.yml up -d --build

.PHONY: up-airflow
up-airflow: ## Start the dev stack plus Airflow orchestration
	$(COMPOSE) -f compose/compose.dev.yml -f compose/compose.airflow.yml up --build

.PHONY: down
down: ## Stop all stacks
	$(COMPOSE) -f compose/compose.dev.yml -f compose/compose.prod.yml \
		-f compose/compose.airflow.yml down --remove-orphans

.PHONY: logs
logs: ## Tail logs from the running stack
	$(COMPOSE) logs -f --tail=100

.PHONY: config
config: ## Render and validate the merged dev compose configuration
	$(COMPOSE) -f compose/compose.dev.yml config

# --- Housekeeping ------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/build $(BACKEND)/dist
	rm -rf $(FRONTEND)/.next $(FRONTEND)/out $(FRONTEND)/dist
