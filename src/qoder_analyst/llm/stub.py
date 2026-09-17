"""确定性 stub provider：不调用任何模型，用于离线演示与测试。"""

import re
from typing import Any

from qoder_analyst.llm.base import Plan, PlannedCall

_SYMBOL = re.compile(r"\b(\d{1,5})\.HK\b", re.IGNORECASE)
_MAX_SYMBOLS = 3

# 常见港股中文名 → 代码，让 stub 也能理解“腾讯和阿里”这类自然语言
ALIASES: dict[str, str] = {
    "腾讯": "700.HK",
    "阿里": "9988.HK",
    "美团": "3690.HK",
    "小米": "1810.HK",
    "比亚迪": "1211.HK",
    "盈富": "2800.HK",
}


def extract_symbols(question: str) -> list[str]:
    """按出现顺序提取标的，去重，最多 _MAX_SYMBOLS 个。"""
    found: list[tuple[int, str]] = [
        (m.start(), f"{int(m.group(1))}.HK") for m in _SYMBOL.finditer(question)
    ]
    found += [(question.find(name), code) for name, code in ALIASES.items() if name in question]
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
            reasoning=f"识别到标的 {', '.join(symbols) or '无'}，获取报价与新闻。",
            calls=calls,
            panels=[f"{s} GP" for s in symbols],
        )

    async def summarize(self, question: str, observations: dict[str, Any]) -> str:
        lines = ["## 分析摘要（stub）", ""]
        for key, value in observations.items():
            if key.startswith("get_quote:") and isinstance(value, dict):
                lines.append(
                    f"- **{value['symbol']}** 现价 {value['price']} {value['currency']}，"
                    f"涨跌 {value['change']}（{value['changePercent']}%）"
                )
        if len(lines) == 2:
            lines.append("- 未识别到可分析的标的，请包含股票代码（如 700.HK）或公司名（如 腾讯）。")
        return "\n".join(lines)
