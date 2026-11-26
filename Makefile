.DEFAULT_GOAL := help
.PHONY: help install run down logs lint format typecheck test check migrate

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install: ## Install dependencies (creates/updates uv.lock)
	uv sync

run: ## Start app, PostgreSQL and Redis with Docker Compose
	docker compose up --build

down: ## Stop Docker Compose services
	docker compose down

logs: ## Follow app logs
	docker compose logs -f app

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint issues and format code
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Static type check (mypy --strict)
	uv run mypy

test: ## Run tests with coverage
	uv run pytest

check: lint typecheck test ## Everything CI runs

migrate: ## Apply database migrations (available from roadmap step 2)
	@echo "Migrations arrive in roadmap step 2."
