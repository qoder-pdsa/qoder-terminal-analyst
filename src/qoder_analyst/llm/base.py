"""LLMProvider 协议：负责把问题规划成工具调用，并基于结果写结论。"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PlannedCall:
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Plan:
    reasoning: str
    calls: list[PlannedCall] = field(default_factory=list)
    panels: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    async def plan(self, question: str, tool_names: list[str]) -> Plan: ...

    async def summarize(self, question: str, observations: dict[str, Any]) -> str: ...
