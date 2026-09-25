"""Characterization tests pinning the legacy behaviour BL-06-2 touches.

Written and executed on the UNCHANGED tree at 92a0018 before any edit, as SDLC step 10000
requires. Every assertion records what the code does today; the pre-change values are also
captured in evidence/baseline-characterization.log.

Assertions marked AMEND are the only ones a human decision authorizes changing. The rest
must stay byte-identical after BL-06-2 lands (acceptance criterion A4).
"""

from typing import Any

import httpx

from qoder_analyst.analyst import Analyst, _citations, _summarize
from qoder_analyst.llm import StubProvider
from qoder_analyst.tools import build_tools

# Legacy quote payload, same values as tests/conftest.py QUOTES["700.HK"].
QUOTE: dict[str, Any] = {
    "symbol": "700.HK",
    "price": "388.2000",
    "change": "8.2000",
    "changePercent": "2.1578",
    "currency": "HKD",
    "asOf": "2026-09-17T00:00:00Z",
}

# Shape of GET /v1/capital-flow/{symbol} per qoder-terminal-data/api/openapi.yaml:261
# (CapitalFlow): required [symbol, currency, asOf, flow, distribution], flow[] items
# {time, inflow}, distribution.{in,out,net} are CapitalBuckets{large,medium,small}.
CAPITAL_FLOW: dict[str, Any] = {
    "symbol": "700.HK",
    "currency": "HKD",
    "asOf": "2026-09-25T09:35:00Z",
    "flow": [
        {"time": "2026-09-25T09:31:00Z", "inflow": "-1200000.0000"},
        {"time": "2026-09-25T09:32:00Z", "inflow": "340000.5000"},
    ],
    "distribution": {
        "in": {"large": "5000000.0000", "medium": "1200000.0000", "small": "300000.0000"},
        "out": {"large": "4100000.0000", "medium": "1000000.0000", "small": "250000.0000"},
        "net": {"large": "900000.0000", "medium": "200000.0000", "small": "50000.0000"},
    },
}

CAPITAL_FLOW_QUESTION = "Is main capital flowing out of Tencent today?"


def test_registry_keeps_the_legacy_tools_and_their_shared_schema(
    data_client: httpx.AsyncClient,
) -> None:
    """AMEND authorized by acceptance criterion A1 — BL-06-2 adds a third tool.

    Pre-change value: `sorted(build_tools(...)) == ["get_quote", "search_news"]`, recorded in
    evidence/baseline-characterization.log. What must survive is the two legacy entries and
    the single symbol schema object every tool shares.
    """
    tools = build_tools(data_client)
    assert {"get_quote", "search_news"} <= set(tools)
    assert tools["get_quote"].parameters is tools["search_news"].parameters
    assert tools["get_capital_flow"].parameters is tools["get_quote"].parameters


def test_symbol_pattern_was_widened_for_every_tool(data_client: httpx.AsyncClient) -> None:
    """AMEND authorized by HUMAN comment 10041 decision 2 (acceptance criterion A7).

    Pre-change value: `^[0-9A-Z]{1,6}\\.(HK|US|SH|SZ)$`, which rejected real option symbols
    such as MSFT261016P420000.US (17 characters before the dot); recorded in
    evidence/baseline-characterization.log. Pinned here only as "one shared schema, widened
    for all tools" — the boundary cases live in tests/test_capital_flow.py.
    """
    patterns = {
        tool.parameters["properties"]["symbol"]["pattern"]
        for tool in build_tools(data_client).values()
    }
    assert patterns == {r"^[0-9A-Z]{1,20}\.(HK|US|SH|SZ)$"}


async def test_plan_for_a_plain_question_is_unchanged() -> None:
    plan = await StubProvider().plan("Analyze Tencent", ["get_quote", "search_news"])
    assert plan.reasoning == "Identified symbols: 700.HK. Fetching quotes and news."
    assert [(c.tool, c.args) for c in plan.calls] == [
        ("get_quote", {"symbol": "700.HK"}),
        ("search_news", {"symbol": "700.HK"}),
    ]
    assert plan.panels == ["700.HK GP"]


async def test_capital_flow_wording_keeps_the_legacy_half_of_the_plan() -> None:
    """AMEND authorized by acceptance criterion A2 — trigger words now plan capital flow.

    Pre-change value: `[c.tool for c in plan.calls] == ["get_quote", "search_news"]`,
    `plan.panels == ["700.HK GP"]` and no panel ending in "CF", recorded in
    evidence/baseline-characterization.log. What must survive is the legacy half of that
    plan — same two calls in the same order, same GP panel first, same reasoning text.
    The added CF call and CF panel are asserted in tests/test_capital_flow.py.
    """
    plan = await StubProvider().plan(
        CAPITAL_FLOW_QUESTION, ["get_quote", "search_news", "get_capital_flow"]
    )
    assert [(c.tool, c.args) for c in plan.calls][:2] == [
        ("get_quote", {"symbol": "700.HK"}),
        ("search_news", {"symbol": "700.HK"}),
    ]
    assert plan.panels[0] == "700.HK GP"
    assert plan.reasoning == "Identified symbols: 700.HK. Fetching quotes and news."


async def test_summarize_renders_only_quote_observations() -> None:
    text = await StubProvider().summarize(
        "Analyze Tencent",
        {"get_quote:700.HK": QUOTE, "search_news:700.HK": [{"id": "1"}]},
    )
    assert text.splitlines() == [
        "## Analysis Summary (stub)",
        "",
        "- **700.HK** last 388.2000 HKD, change 8.2000 (2.1578%)",
    ]


async def test_summarize_falls_back_when_nothing_was_recognized() -> None:
    text = await StubProvider().summarize("How is the market today?", {})
    assert text == (
        "## Analysis Summary (stub)\n"
        "\n"
        "- No symbols recognized. Include a stock code (e.g. 700.HK) "
        "or a company name (e.g. Tencent)."
    )


async def test_summarize_fallback_is_driven_by_the_len_lines_sentinel() -> None:
    """Highest-risk legacy detail: stub.py:60 gates the fallback on `len(lines) == 2`.

    A recognized symbol whose only observation is not a get_quote dict still renders the
    "No symbols recognized" fallback, because no line was appended. Any new observation
    kind that appends a line silently suppresses it, so this is pinned before the change.
    """
    text = await StubProvider().summarize("700.HK news", {"search_news:700.HK": [{"id": "1"}]})
    assert "No symbols recognized" in text


def test_tool_result_summary_is_empty_for_a_capital_flow_payload() -> None:
    assert _summarize(CAPITAL_FLOW) == ""
    assert _summarize(CAPITAL_FLOW["flow"]) == "2 items"
    assert _summarize(QUOTE) == "price 388.2000"


def test_citations_ignore_non_news_observations() -> None:
    citations = _citations(
        {
            "search_news:700.HK": [{"headline": "700.HK news", "url": "https://example.com/1"}],
            "get_capital_flow:700.HK": CAPITAL_FLOW,
        }
    )
    assert [(c.title, c.url) for c in citations] == [("700.HK news", "https://example.com/1")]


async def test_legacy_event_sequence_for_a_plain_question(
    data_client: httpx.AsyncClient,
) -> None:
    analyst = Analyst(StubProvider(), build_tools(data_client))
    events = [e.model_dump() async for e in analyst.run("Analyze Tencent")]
    assert [e["type"] for e in events] == [
        "thinking",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "open_panel",
        "answer",
    ]
    assert events[2]["ok"] is True
    assert events[2]["summary"] == "price 388.2000"
    assert events[4]["summary"] == "1 items"
    assert events[5]["command"] == "700.HK GP"
