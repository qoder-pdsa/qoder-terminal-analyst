"""BL-06-2: the `get_capital_flow` tool, its stub-planner trigger, and the CF panel.

Written before the implementation (SDLC step 10001, TDD) and observed failing for business
reasons — see evidence/tdd-red.log. Amounts are asserted as the contract's exact decimal
strings so any float round-trip or reformatting fails the test.
"""

import re
from typing import Any

import httpx
import pytest

from qoder_analyst.analyst import Analyst
from qoder_analyst.llm import StubProvider
from qoder_analyst.tools import build_tools

ALL_TOOLS = ["get_quote", "search_news", "get_capital_flow"]

# tests/conftest.py CAPITAL_FLOWS["700.HK"]: three ascending points, the last one is the
# "last minute" the summary must quote, and the two earlier ones must not appear.
LAST_MINUTE_NET = "-1200000.0000"
LARGE_ORDER_NET = "900000.0000"
TENCENT_FLOW_LINE = (
    f"- **700.HK** capital flow last minute {LAST_MINUTE_NET}, "
    f"large-order net {LARGE_ORDER_NET} HKD"
)
TENCENT_QUOTE_LINE = "- **700.HK** last 388.2000 HKD, change 8.2000 (2.1578%)"

CAPITAL_FLOW_QUESTION = "What is the capital flow for 700.HK today?"


async def _events(question: str, data_client: httpx.AsyncClient) -> list[dict[str, Any]]:
    analyst = Analyst(StubProvider(), build_tools(data_client))
    return [event.model_dump() async for event in analyst.run(question)]


# --- A1: the tool itself -----------------------------------------------------------------


async def test_get_capital_flow_returns_the_contract_payload(
    data_client: httpx.AsyncClient,
) -> None:
    result = await build_tools(data_client)["get_capital_flow"].run({"symbol": "700.HK"})

    assert result["symbol"] == "700.HK"
    assert result["currency"] == "HKD"
    assert result["flow"][-1] == {"time": "2026-09-25T09:35:00Z", "inflow": LAST_MINUTE_NET}
    assert result["distribution"]["net"]["large"] == LARGE_ORDER_NET
    # decimals must survive as strings; parsing them anywhere would be a rule violation
    assert [type(point["inflow"]) for point in result["flow"]] == [str] * 3


def test_get_capital_flow_uses_the_same_symbol_schema(data_client: httpx.AsyncClient) -> None:
    tools = build_tools(data_client)

    assert tools["get_capital_flow"].parameters == tools["get_quote"].parameters
    assert tools["get_capital_flow"].parameters == tools["search_news"].parameters


async def test_capital_flow_404_raises_for_status(data_client: httpx.AsyncClient) -> None:
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await build_tools(data_client)["get_capital_flow"].run({"symbol": "8888.HK"})

    assert excinfo.value.response.status_code == 404


async def test_capital_flow_5xx_raises_for_status(data_client: httpx.AsyncClient) -> None:
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await build_tools(data_client)["get_capital_flow"].run({"symbol": "0005.HK"})

    assert excinfo.value.response.status_code == 500


# --- A1: failures surface as tool_result(ok=false) and the stream continues ---------------


async def test_capital_flow_404_fails_the_tool_result_but_not_the_stream(
    data_client: httpx.AsyncClient,
) -> None:
    events = await _events("What is the capital flow for 8888.HK today?", data_client)

    failed = [
        e
        for e in events
        if e["type"] == "tool_result" and e["tool"] == "get_capital_flow" and e["ok"] is False
    ]
    assert len(failed) == 1
    assert failed[0]["summary"] == "HTTP 404"
    assert events[-1]["type"] == "answer", "the stream must continue past a failed tool"


async def test_empty_flow_is_a_successful_observation_not_an_error(
    data_client: httpx.AsyncClient,
) -> None:
    """HUMAN decision, comment 10041: 200 with `flow: []` is a normal pre-market state.

    It must yield ok=true (so `analyst.py`'s error path stays untouched) and the summary
    line must say `no intraday flow yet`.
    """
    events = await _events("What is the capital flow into 9988.HK today?", data_client)

    result = next(
        e for e in events if e["type"] == "tool_result" and e["tool"] == "get_capital_flow"
    )
    assert result["ok"] is True
    assert events[-1]["type"] == "answer"
    assert "no intraday flow yet" in str(events[-1]["markdown"])


# --- A2: the stub planner ----------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Show me the capital flow for Tencent",
        "What is the inflow into 700.HK?",
        "Any outflow from 700.HK today?",
        "700.HK 的资金流向如何？",
        "主力在买 700.HK 吗？",
        "700.HK 今天的流入情况",
        "700.HK 今天的流出情况",
    ],
)
async def test_planner_triggers_on_every_capital_flow_wording(question: str) -> None:
    plan = await StubProvider().plan(question, ALL_TOOLS)

    assert any(c.tool == "get_capital_flow" for c in plan.calls)
    assert "700.HK CF" in plan.panels


@pytest.mark.parametrize(
    "question",
    ["Analyze Tencent", "How is 700.HK doing?", "Compare Tencent with 9988.HK"],
)
async def test_planner_without_trigger_words_plans_no_capital_flow(question: str) -> None:
    plan = await StubProvider().plan(question, ALL_TOOLS)

    assert not any(c.tool == "get_capital_flow" for c in plan.calls)
    assert not any(p.endswith(" CF") for p in plan.panels)


async def test_capital_flow_call_is_appended_after_the_legacy_calls() -> None:
    plan = await StubProvider().plan(CAPITAL_FLOW_QUESTION, ALL_TOOLS)

    assert [(c.tool, c.args) for c in plan.calls] == [
        ("get_quote", {"symbol": "700.HK"}),
        ("search_news", {"symbol": "700.HK"}),
        ("get_capital_flow", {"symbol": "700.HK"}),
    ]


async def test_each_identified_symbol_gets_its_own_cf_panel() -> None:
    plan = await StubProvider().plan("Compare the capital flow of Tencent and 9988.HK", ALL_TOOLS)

    assert plan.panels == ["700.HK GP", "9988.HK GP", "700.HK CF", "9988.HK CF"]


async def test_planner_skips_the_call_when_the_tool_is_not_registered() -> None:
    """Panels follow the legacy GP rule and do not depend on the registry; calls do."""
    plan = await StubProvider().plan(CAPITAL_FLOW_QUESTION, ["get_quote", "search_news"])

    assert [c.tool for c in plan.calls] == ["get_quote", "search_news"]
    assert plan.panels == ["700.HK GP", "700.HK CF"]


# --- A3: the summary carries the contract's decimal strings ------------------------------


async def test_summary_carries_the_decimal_strings_verbatim(
    data_client: httpx.AsyncClient,
) -> None:
    markdown = str((await _events(CAPITAL_FLOW_QUESTION, data_client))[-1]["markdown"])

    assert TENCENT_FLOW_LINE in markdown
    # "last minute" means the final ascending point, not an aggregate of the earlier ones
    assert "4800000.0000" not in markdown
    assert "-2600000.5000" not in markdown
    # the legacy quote line for the same symbol is untouched
    assert TENCENT_QUOTE_LINE in markdown


async def test_summary_before_the_open_reports_no_intraday_flow_yet(
    data_client: httpx.AsyncClient,
) -> None:
    """A1 as amended by HUMAN comment 10041: an empty flow is a valid observation."""
    markdown = str(
        (await _events("What is the capital flow into 9988.HK today?", data_client))[-1]["markdown"]
    )

    assert "- **9988.HK** no intraday flow yet, large-order net 0.0000 HKD" in markdown
    # A line was appended, so the `len(lines) == 2` no-symbols fallback must not fire.
    assert "No symbols recognized" not in markdown


# --- A7: symbol regex widened to the contract's 20 characters ----------------------------


def test_symbol_pattern_accepts_twenty_char_option_symbols(
    data_client: httpx.AsyncClient,
) -> None:
    """A7 boundary: the local part is 1..20 characters, per HUMAN comment 10041 decision 2."""
    tools = build_tools(data_client)
    pattern: str = tools["get_capital_flow"].parameters["properties"]["symbol"]["pattern"]

    assert pattern == r"^[0-9A-Z]{1,20}\.(HK|US|SH|SZ)$"
    # The width bounds the part before the dot, so the boundary cases are built from it.
    # MSFT261016P420000.US is a real watchlist option symbol (17 chars before the dot) that
    # the legacy {1,6} pattern rejected.
    assert re.fullmatch(pattern, "MSFT261016P420000.US"), "real option symbol must be admitted"
    assert re.fullmatch(pattern, "A" * 20 + ".US")
    assert re.fullmatch(pattern, "700.HK")
    assert re.fullmatch(pattern, "600519.SH")
    assert re.fullmatch(pattern, "A" * 21 + ".US") is None, "21 chars must be rejected"
    assert re.fullmatch(pattern, "700.hk") is None
    assert re.fullmatch(pattern, "700") is None
