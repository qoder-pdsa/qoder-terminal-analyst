# qoder-terminal-analyst — Agent 指南

Python 3.12 + FastAPI，`uv` 管理依赖。**本 repo 维护 `api/openapi.yaml` 与 `api/agent-event.schema.json`**，
下游 `qoder-terminal-web` 依赖它们；上游数据契约见 `qoder-terminal-data/api/openapi.yaml`。

## 架构
- `app.py` — HTTP 层，把 `Analyst` 事件编码为 SSE
- `analyst.py` — agent 循环：LLM 规划 → 执行工具 → 产出 `AgentEvent`
- `events.py` — 事件模型，**必须与 `api/agent-event.schema.json` 一致**（`tests/test_contract.py` 守护）
- `tools.py` — 工具注册表（名称 + 描述 + 参数 schema + async 执行函数）
- `llm/` — `LLMProvider` 协议；`stub` 必须始终可用，保证离线演示

## 规则
- 契约先行：改事件格式先改 JSON Schema，再改模型，契约测试必须通过。
- 标的格式 `700.HK`；新增中文别名放在 `llm/stub.py::ALIASES`。
- 所有 IO 用 async；HTTP 客户端依赖注入，测试用 `httpx.MockTransport`，**禁止真实网络**。
- 服务间客户端必须 `trust_env=False`（本机代理会把 localhost 请求转发出去返回 502）。
- 工具失败产出 `tool_result(ok=false)` 并继续，不得中断整个流。
- API key 只从环境变量读取，缺失时启动失败并给出明确错误。
- mypy strict + ruff 必须通过。

## 命令
- `make test` / `make lint` / `make dev`
