"""AgentEvent models mirroring api/agent-event.schema.json.

The contract test lives in tests/test_contract.py.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class Thinking(BaseModel):
    type: Literal["thinking"] = "thinking"
    text: str


class ToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    args: dict[str, Any]


class ToolResult(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool: str
    ok: bool
    summary: str | None = None


class OpenPanel(BaseModel):
    type: Literal["open_panel"] = "open_panel"
    command: str


class Citation(BaseModel):
    title: str
    url: str


class Answer(BaseModel):
    type: Literal["answer"] = "answer"
    markdown: str
    citations: list[Citation] = Field(default_factory=list)


class Error(BaseModel):
    type: Literal["error"] = "error"
    message: str


AgentEvent = Annotated[
    Thinking | ToolCall | ToolResult | OpenPanel | Answer | Error,
    Field(discriminator="type"),
]
