# qoder-terminal-analyst — Agent Guide

Python 3.12 + FastAPI, dependencies managed with `uv`. **This repo owns `api/openapi.yaml` and `api/agent-event.schema.json`**;
downstream `qoder-terminal-web` depends on them. The upstream data contract is `qoder-terminal-data/api/openapi.yaml`.

## Architecture
- `app.py` — HTTP layer that encodes `Analyst` events as SSE
- `analyst.py` — agent loop: LLM planning → tool execution → `AgentEvent` output
- `events.py` — event models that **must match `api/agent-event.schema.json`** (guarded by `tests/test_contract.py`)
- `tools.py` — tool registry (name + description + parameter schema + async function)
- `llm/` — the `LLMProvider` protocol; `stub` must always work so offline demos never break

## Rules
- Contract first: change the JSON Schema before the models when changing the event format; the contract test must pass.
- Symbol format is `700.HK`; add new company-name aliases to `llm/stub.py::ALIASES`.
- All I/O is async; HTTP clients are injected, tests use `httpx.MockTransport`, and **tests never hit the real network**.
- Service-to-service clients must use `trust_env=False` (a local proxy would route localhost requests out and return 502).
- A failing tool emits `tool_result(ok=false)` and the stream continues; never abort the whole stream.
- API keys come only from environment variables; fail fast with a clear error at startup when missing.
- mypy strict and ruff must pass.

## Commands
- `make test` / `make lint` / `make dev`
