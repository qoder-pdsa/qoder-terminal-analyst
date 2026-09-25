# qoder-terminal-analyst

The **AI analyst** (Python) for Qoder Terminal — the product's own AI brain.
API contracts: [`api/openapi.yaml`](api/openapi.yaml) and the event format [`api/agent-event.schema.json`](api/agent-event.schema.json).

```bash
make dev    # :8082, LLM_PROVIDER=stub by default (offline, deterministic)
make test
curl -N -X POST localhost:8082/v1/ask -H 'content-type: application/json' \
  -d '{"question":"Compare Tencent and Alibaba recently"}'
```

## Features
| Feature | Status |
|---|---|
| `ASK` analyst: plan → call data tools → open panels → cited conclusion (SSE stream) | ✅ stub planner |
| Recognizes Hong Kong codes (`700.HK`) and company names (Tencent, Alibaba, …) | ✅ |
| Real LLM (OpenAI-compatible API such as Alibaba Cloud Model Studio Qwen) | 🚧 backlog |
| Capital flow tool (`get_capital_flow`) and the `<symbol> CF` panel | ✅ stub planner |
| Tools over MCP, indicator tools | 🚧 backlog |
| Watch agent and opening briefing | 🚧 backlog |

## Environment variables
| Variable | Default | Notes |
|---|---|---|
| `DATA_BASE_URL` | `http://localhost:8081` | qoder-terminal-data address |
| `LLM_PROVIDER` | `stub` | |
