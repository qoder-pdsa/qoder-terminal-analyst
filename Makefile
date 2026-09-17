.PHONY: install dev test lint lint-api
install:
	uv sync
dev:
	uv run uvicorn qoder_analyst.app:app --port 8082 --reload
test:
	uv run pytest -q
lint: lint-api
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
lint-api:
	npx --yes @redocly/cli@1 lint --config api/redocly.yaml api/openapi.yaml
