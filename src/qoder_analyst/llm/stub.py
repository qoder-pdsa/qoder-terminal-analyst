"""Deterministic stub provider: calls no model, used for offline demos and tests."""

import re
from typing import Any

from qoder_analyst.llm.base import Plan, PlannedCall

_SYMBOL = re.compile(r"\b(\d{1,5})\.HK\b", re.IGNORECASE)
_MAX_SYMBOLS = 3

# Common Hong Kong company names → symbols, so the stub understands "Tencent vs Alibaba"
ALIASES: dict[str, str] = {
    "tencent": "700.HK",
    "alibaba": "9988.HK",
    "meituan": "3690.HK",
    "xiaomi": "1810.HK",
    "byd": "1211.HK",
    "tracker fund": "2800.HK",
}


def extract_symbols(question: str) -> list[str]:
    """Extract symbols in order of appearance, de-duplicated, at most _MAX_SYMBOLS."""
    found: list[tuple[int, str]] = [
        (m.start(), f"{int(m.group(1))}.HK") for m in _SYMBOL.finditer(question)
    ]
    for name, code in ALIASES.items():
        match = re.search(rf"\b{re.escape(name)}\b", question, re.IGNORECASE)
        if match:
            found.append((match.start(), code))
    ordered = [code for _, code in sorted(found)]
    return list(dict.fromkeys(ordered))[:_MAX_SYMBOLS]


class StubProvider:
    async def plan(self, question: str, tool_names: list[str]) -> Plan:
        symbols = extract_symbols(question)
        calls = [
            PlannedCall(tool, {"symbol": s})
            for s in symbols
            for tool in ("get_quote", "search_news")
            if tool in tool_names
        ]
        return Plan(
            reasoning=(
                f"Identified symbols: {', '.join(symbols) or 'none'}. Fetching quotes and news."
            ),
            calls=calls,
            panels=[f"{s} GP" for s in symbols],
        )

    async def summarize(self, question: str, observations: dict[str, Any]) -> str:
        lines = ["## Analysis Summary (stub)", ""]
        for key, value in observations.items():
            if key.startswith("get_quote:") and isinstance(value, dict):
                lines.append(
                    f"- **{value['symbol']}** last {value['price']} {value['currency']}, "
                    f"change {value['change']} ({value['changePercent']}%)"
                )
        if len(lines) == 2:
            lines.append(
                "- No symbols recognized. Include a stock code (e.g. 700.HK) "
                "or a company name (e.g. Tencent)."
            )
        return "\n".join(lines)
