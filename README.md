# qoder-terminal-analyst

Qoder Terminal 的 **AI 分析师**（Python）—— 产品本身的 AI 大脑。
接口契约：[`api/openapi.yaml`](api/openapi.yaml)、事件格式 [`api/agent-event.schema.json`](api/agent-event.schema.json)。

```bash
make dev    # :8082，默认 LLM_PROVIDER=stub（离线、确定性）
make test
curl -N -X POST localhost:8082/v1/ask -H 'content-type: application/json' \
  -d '{"question":"对比腾讯和阿里最近表现"}'
```

## 功能
| 功能 | 状态 |
|---|---|
| `ASK` 分析师：规划 → 调数据工具 → 打开面板 → 带引用的结论（SSE 流式） | ✅ stub planner |
| 识别港股代码（`700.HK`）与中文公司名（腾讯、阿里…） | ✅ |
| 真实 LLM（OpenAI 兼容接口，如百炼 Qwen） | 🚧 backlog |
| 工具改走 MCP、接入资金流向 / 指标 | 🚧 backlog |
| 盯盘 agent、开盘简报 | 🚧 backlog |

## 环境变量
| 变量 | 默认 | 说明 |
|---|---|---|
| `DATA_BASE_URL` | `http://localhost:8081` | qoder-terminal-data 地址 |
| `LLM_PROVIDER` | `stub` | |
