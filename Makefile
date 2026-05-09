SHELL := /usr/bin/env bash

.DEFAULT_GOAL := help

# ── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Service ───────────────────────────────────────────────────────────────────

.PHONY: build
build: ## Build the Docker image
	@./scripts/build.sh

.PHONY: up
up: ## Start the service in detached mode
	@./scripts/up.sh

.PHONY: run
run: ## Run the service in foreground (logs stream, exits when container exits)
	@./scripts/run.sh

.PHONY: down
down: ## Stop and remove the service container + network
	@./scripts/down.sh

.PHONY: restart
restart: down up ## Restart the service

.PHONY: logs
logs: ## Tail service logs
	@./scripts/logs.sh

.PHONY: ps
ps: ## Show service status
	@./scripts/ps.sh

.PHONY: shell
shell: ## Open a bash shell inside a fresh container
	@./scripts/shell.sh

.PHONY: auth-linear
auth-linear: ## Run mcp-remote to complete Linear OAuth (one-time, persists in named volume)
	@./scripts/auth-linear.sh

.PHONY: kill-stale
kill-stale: ## Remove any lingering hsb-agents containers
	@./scripts/kill-stale.sh

.PHONY: clean
clean: ## Stop service and remove volumes + locally-built image
	@./scripts/clean.sh

# ── Quality ───────────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Lint source files
	uv run ruff check src/ tests/

.PHONY: fmt
fmt: ## Format source files
	uv run ruff format src/ tests/

.PHONY: fmt-check
fmt-check: ## Check formatting without writing
	uv run ruff format --check src/ tests/

.PHONY: typecheck
typecheck: ## Run type checker
	uv run mypy src/

.PHONY: test
test: ## Run test suite
	uv run pytest tests/
