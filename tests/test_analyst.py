import httpx

from qoder_analyst.analyst import Analyst
from qoder_analyst.llm import StubProvider
from qoder_analyst.tools import build_tools


async def _collect(analyst: Analyst, question: str) -> list[dict[str, object]]:
    return [event.model_dump() async for event in analyst.run(question)]


async def test_ask_emits_tool_calls_panels_and_answer(data_client: httpx.AsyncClient) -> None:
    analyst = Analyst(StubProvider(), build_tools(data_client))
    events = await _collect(analyst, "分析一下腾讯")

    types = [e["type"] for e in events]
    assert types[0] == "thinking"
    assert types.count("tool_call") == 2
    assert {"type": "open_panel", "command": "700.HK GP"} in events
    answer = events[-1]
    assert answer["type"] == "answer"
    assert "388.2000" in str(answer["markdown"])
    assert answer["citations"] == [{"title": "700.HK news", "url": "https://example.com/1"}]


async def test_tool_failure_does_not_break_stream(data_client: httpx.AsyncClient) -> None:
    analyst = Analyst(StubProvider(), build_tools(data_client))
    events = await _collect(analyst, "看看 0000.HK")

    failed = [e for e in events if e["type"] == "tool_result" and e["ok"] is False]
    assert failed, "404 from data service should surface as a failed tool_result"
    assert events[-1]["type"] == "answer"


async def test_failed_tool_result_reports_http_status(data_client: httpx.AsyncClient) -> None:
    analyst = Analyst(StubProvider(), build_tools(data_client))
    events = await _collect(analyst, "看看 0000.HK")

    failed = next(e for e in events if e["type"] == "tool_result" and e["ok"] is False)
    assert failed["summary"] == "HTTP 404"


def test_extract_symbols_supports_codes_and_chinese_names() -> None:
    from qoder_analyst.llm.stub import extract_symbols

    assert extract_symbols("对比腾讯和 9988.hk，再看看美团") == ["700.HK", "9988.HK", "3690.HK"]
    assert extract_symbols("0700.HK 怎么样") == ["700.HK"]
    assert extract_symbols("今天大盘如何") == []
