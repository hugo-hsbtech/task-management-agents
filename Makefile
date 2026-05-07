SHELL := /usr/bin/env bash

.DEFAULT_GOAL := help

.PHONY: help build up run down logs shell auth-linear ps restart clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image
	@./scripts/build.sh

up: ## Start the service in detached mode
	@./scripts/up.sh

run: ## Run the service in foreground (logs stream, exits when container exits)
	@./scripts/run.sh

down: ## Stop and remove the service container + network
	@./scripts/down.sh

logs: ## Tail service logs
	@./scripts/logs.sh

shell: ## Open a bash shell inside a fresh container
	@./scripts/shell.sh

auth-linear: ## Run mcp-remote to complete Linear OAuth (one-time, persists in named volume)
	@./scripts/auth-linear.sh

ps: ## Show service status
	@./scripts/ps.sh

restart: down up ## Restart the service

clean: ## Stop service and remove volumes + locally-built image
	@./scripts/clean.sh
