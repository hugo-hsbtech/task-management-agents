.PHONY: lint fmt fmt-check typecheck test

lint:
	uv run ruff check src/ tests/

fmt:
	uv run ruff format src/ tests/

fmt-check:
	uv run ruff format --check src/ tests/

typecheck:
	uv run mypy src/

test:
	uv run pytest tests/
