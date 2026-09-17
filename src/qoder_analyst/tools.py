"""Tools the analyst can call.

Currently calls qoder-terminal-data REST directly; will move to MCP (see backlog).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

ToolFn = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: ToolFn


def build_tools(data: httpx.AsyncClient) -> dict[str, Tool]:
    """Build the tool registry. The base_url of `data` must point to qoder-terminal-data."""

    async def get_quote(args: dict[str, Any]) -> Any:
        resp = await data.get(f"/v1/quotes/{args['symbol']}")
        resp.raise_for_status()
        return resp.json()

    async def search_news(args: dict[str, Any]) -> Any:
        params = {"symbol": args["symbol"], "limit": args.get("limit", 3)}
        resp = await data.get("/v1/news", params=params)
        resp.raise_for_status()
        return resp.json()

    symbol_schema = {
        "type": "object",
        "required": ["symbol"],
        "properties": {"symbol": {"type": "string", "pattern": r"^[0-9A-Z]{1,6}\.(HK|US|SH|SZ)$"}},
    }
    tools = [
        Tool("get_quote", "Get the latest quote for a symbol", symbol_schema, get_quote),
        Tool("search_news", "Search the latest news for a symbol", symbol_schema, search_news),
    ]
    return {t.name: t for t in tools}
