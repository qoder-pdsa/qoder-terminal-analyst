"""Tools the analyst can call.

Currently calls qoder-terminal-data REST directly; will move to MCP (see backlog).
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

ToolFn = Callable[[dict[str, Any]], Awaitable[Any]]

_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: ToolFn


def _symbol_path(symbol: str) -> str:
    """The single place a symbol enters a URL path, so it can never leave its endpoint."""
    return quote(symbol, safe="")


def validate_tool_args(schema: dict[str, Any], args: dict[str, Any]) -> str | None:
    """Return why `args` violates `schema`, or None when they satisfy it.

    Enforces the keywords the registry declares — `required`, `properties`, `type` and
    `pattern`. Arguments the schema does not declare are accepted, so a tool may take
    extras such as `limit`. The reason names the argument but never echoes its value,
    which is model-chosen and would end up in the event stream.
    """
    for name in schema.get("required", []):
        if name not in args:
            return f"missing required '{name}'"
    for name, rules in schema.get("properties", {}).items():
        if name not in args:
            continue
        value = args[name]
        expected = rules.get("type")
        if expected is not None and not _matches_type(value, expected):
            return f"'{name}' must be of type '{expected}'"
        pattern = rules.get("pattern")
        # fullmatch, not search: a `$`-anchored pattern still admits "700.HK\n" under search
        if pattern is not None and isinstance(value, str) and not re.fullmatch(pattern, value):
            return f"'{name}' does not match the required pattern"
    return None


def _matches_type(value: Any, expected: str) -> bool:
    types = _JSON_TYPES.get(expected)
    if types is None:
        return True
    if isinstance(value, bool):  # bool is a subclass of int, so it must not satisfy "integer"
        return expected == "boolean"
    return isinstance(value, types)


def build_tools(data: httpx.AsyncClient) -> dict[str, Tool]:
    """Build the tool registry. The base_url of `data` must point to qoder-terminal-data."""

    async def get_quote(args: dict[str, Any]) -> Any:
        resp = await data.get(f"/v1/quotes/{_symbol_path(args['symbol'])}")
        resp.raise_for_status()
        return resp.json()

    async def search_news(args: dict[str, Any]) -> Any:
        params = {"symbol": args["symbol"], "limit": args.get("limit", 3)}
        resp = await data.get("/v1/news", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_capital_flow(args: dict[str, Any]) -> Any:
        resp = await data.get(f"/v1/capital-flow/{_symbol_path(args['symbol'])}")
        resp.raise_for_status()
        return resp.json()

    symbol_schema = {
        "type": "object",
        "required": ["symbol"],
        "properties": {"symbol": {"type": "string", "pattern": r"^[0-9A-Z]{1,20}\.(HK|US|SH|SZ)$"}},
    }
    tools = [
        Tool("get_quote", "Get the latest quote for a symbol", symbol_schema, get_quote),
        Tool("search_news", "Search the latest news for a symbol", symbol_schema, search_news),
        Tool(
            "get_capital_flow",
            "Get today's capital flow for a symbol: net inflow per minute and the "
            "large/medium/small order distribution",
            symbol_schema,
            get_capital_flow,
        ),
    ]
    return {t.name: t for t in tools}
