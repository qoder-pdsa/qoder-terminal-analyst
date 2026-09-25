"""ASK analyst agent loop."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from qoder_analyst.events import (
    AgentEvent,
    Answer,
    Citation,
    Error,
    OpenPanel,
    Thinking,
    ToolCall,
    ToolResult,
)
from qoder_analyst.llm import LLMProvider
from qoder_analyst.tools import Tool, validate_tool_args


class Analyst:
    def __init__(self, llm: LLMProvider, tools: dict[str, Tool]) -> None:
        self._llm = llm
        self._tools = tools

    async def run(self, question: str) -> AsyncIterator[AgentEvent]:
        plan = await self._llm.plan(question, list(self._tools))
        yield Thinking(text=plan.reasoning)

        observations: dict[str, Any] = {}
        for call in plan.calls:
            tool = self._tools.get(call.tool)
            yield ToolCall(tool=call.tool, args=call.args)
            if tool is None:
                yield ToolResult(tool=call.tool, ok=False, summary="unknown tool")
                continue
            violation = validate_tool_args(tool.parameters, call.args)
            if violation is not None:
                summary = f"invalid arguments: {violation}"
                yield ToolResult(tool=call.tool, ok=False, summary=summary)
                continue
            try:
                result = await tool.run(call.args)
            except httpx.HTTPStatusError as exc:
                summary = f"HTTP {exc.response.status_code}"
                yield ToolResult(tool=call.tool, ok=False, summary=summary)
                continue
            except httpx.HTTPError as exc:
                yield ToolResult(tool=call.tool, ok=False, summary=type(exc).__name__)
                continue
            observations[f"{call.tool}:{call.args.get('symbol', '')}"] = result
            yield ToolResult(tool=call.tool, ok=True, summary=_summarize(result))

        for command in plan.panels:
            yield OpenPanel(command=command)

        try:
            markdown = await self._llm.summarize(question, observations)
        except Exception as exc:  # providers vary, so fall back to an error event
            yield Error(message=f"summarize failed: {type(exc).__name__}")
            return
        yield Answer(markdown=markdown, citations=_citations(observations))


def _summarize(result: Any) -> str:
    if isinstance(result, list):
        return f"{len(result)} items"
    if isinstance(result, dict) and "price" in result:
        return f"price {result['price']}"
    return ""


def _citations(observations: dict[str, Any]) -> list[Citation]:
    return [
        Citation(title=item["headline"], url=item["url"])
        for key, items in observations.items()
        if key.startswith("search_news:") and isinstance(items, list)
        for item in items
    ]
