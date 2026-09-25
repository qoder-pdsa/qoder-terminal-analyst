"""Characterization tests pinning the legacy tool-argument behaviour TD-01 changes.

Written and executed on the UNCHANGED tree at 9722407 before any production edit, as SDLC
step 10000 requires; the real run is evidence/baseline-characterization-td01.log and the
pre-change event streams / request URLs are dumped in evidence/baseline-legacy-probe.log.

Assertions marked AMEND record a defect that work item 10017 authorizes fixing, with the
pre-change value in the docstring so step 10002 can name the exact difference. Everything
not marked AMEND must stay byte-identical after TD-01 lands.

Step 10001 flipped every AMEND assertion to its post-change value. Four of them also moved
from the tool level (`Tool.run` called directly) to the agent loop, because A1 puts the
validation in the loop: at the tool level a hostile symbol is now merely percent-encoded
(A2, pinned in tests/test_tool_arg_validation.py), while the loop rejects it with 0
requests. The pre-change tool-level URLs stay in the docstrings and the baseline logs.

Deliberately unpinned (documented exemption): the `summary` *text* of a validation failure.
Acceptance criterion A1 requires `tool_result(ok=false)` plus a continuing stream, not a
wording, and the event schema is out of scope for TD-01. Only `ok`, the event sequence and
the request counts are pinned, so choosing the wording in step 10001 is not a
characterization difference. Today's wording for every path stays in the baseline logs.
"""

from collections.abc import Callable, Sequence
from typing import Any

import httpx
import pytest

from qoder_analyst.analyst import Analyst
from qoder_analyst.llm import PlannedCall, StubProvider
from qoder_analyst.tools import build_tools

VALID_QUOTE_URL = "http://data/v1/quotes/700.HK"
VALID_NEWS_URL = "http://data/v1/news?symbol=700.HK&limit=3"
VALID_CAPITAL_FLOW_URL = "http://data/v1/capital-flow/700.HK"
WIDEST_LEGAL_SYMBOL = "MSFT261016P420000.US"

ScriptedAnalyst = Callable[[Sequence[PlannedCall]], Analyst]


async def _events(analyst: Analyst, question: str = "scripted") -> list[dict[str, Any]]:
    return [event.model_dump() async for event in analyst.run(question)]


def _urls(recorded_requests: list[httpx.Request]) -> list[str]:
    return [str(request.url) for request in recorded_requests]


# --- AMEND: TD-01 now validates the arguments before they can reach a URL ----------------


async def test_a_traversal_symbol_never_reaches_the_upstream_service(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criteria A1 + A3.

    Pre-change, at the tool level: `symbol="../health"` was interpolated straight into the
    path and httpx normalized the dot segments, so the request left `/v1/quotes/` entirely
    and hit `http://data/v1/health` (1 request, HTTPStatusError). Post-change the advertised
    pattern rejects it in the agent loop before the tool function runs: 0 requests.
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "../health"})]))

    assert recorded_requests == []
    assert events[2]["ok"] is False
    assert events[-1]["type"] == "answer"


async def test_a_traversal_symbol_cannot_reach_an_arbitrary_endpoint(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criteria A1 + A3.

    Pre-change, at the tool level: `get_capital_flow` with `../../v1/quotes/700.HK` landed on
    `http://data/v1/quotes/700.HK` and answered a capital-flow call with a quote payload
    (`result["price"] == "388.2000"`) — the caller, not the tool, chose the upstream path.
    Post-change: 0 requests and a failed tool result.
    """
    events = await _events(
        scripted_analyst([PlannedCall("get_capital_flow", {"symbol": "../../v1/quotes/700.HK"})])
    )

    assert recorded_requests == []
    assert events[2]["ok"] is False
    assert events[-1]["type"] == "answer"


async def test_a_symbol_with_a_slash_never_extends_the_upstream_path(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criterion A1.

    Pre-change, at the tool level: `700.HK/x` (the work item's own example) was not rejected
    and produced `http://data/v1/quotes/700.HK/x`, a path the data contract does not define.
    Post-change: 0 requests.
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "700.HK/x"})]))

    assert recorded_requests == []
    assert events[2]["ok"] is False
    assert events[-1]["type"] == "answer"


@pytest.mark.parametrize("symbol", ["700.hk", "AAPL", 700])
async def test_symbols_outside_the_advertised_pattern_are_rejected(
    symbol: object,
    scripted_analyst: ScriptedAnalyst,
    recorded_requests: list[httpx.Request],
) -> None:
    """AMEND by acceptance criterion A1.

    Pre-change, at the tool level, a lowercase market suffix, a missing suffix and a
    non-string symbol all reached the upstream service (1 request each, at
    `http://data/v1/quotes/{symbol}`). Post-change all three violate `Tool.parameters` and
    are rejected with 0 requests.
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": symbol})]))

    assert recorded_requests == []
    assert events[2]["ok"] is False
    assert events[-1]["type"] == "answer"


async def test_a_missing_required_argument_no_longer_aborts_the_stream(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criterion A1 ("a violation emits tool_result(ok=false) and the
    stream continues").

    Pre-change the tool body did `args["symbol"]`, so a missing required argument raised
    KeyError out of the agent loop — past both `except httpx.*` handlers: no tool_result, no
    answer, the SSE stream died mid-way. Post-change the loop reports the violation.
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {})]))

    assert [event["type"] for event in events] == [
        "thinking",
        "tool_call",
        "tool_result",
        "answer",
    ]
    assert events[2]["ok"] is False
    assert recorded_requests == []


async def test_a_traversal_attempt_is_distinguishable_from_an_ordinary_upstream_404(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criteria A1 + A3.

    Pre-change the event stream could not tell a traversal attempt from a real 404: it
    reported `ok=false` with `summary="HTTP 404"` while one request had already escaped to
    `http://data/v1/health`. Post-change the same `ok=false` arrives with 0 requests and a
    summary that is not an upstream status. Only the count and that distinction are pinned;
    the summary-text exemption is documented in the module docstring.
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "../health"})]))

    assert [event["type"] for event in events] == [
        "thinking",
        "tool_call",
        "tool_result",
        "answer",
    ]
    assert events[2]["ok"] is False
    assert events[2]["summary"] != "HTTP 404"
    assert recorded_requests == []


async def test_a_rejected_call_does_not_stop_the_calls_after_it(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """AMEND by acceptance criterion A1 — only the two marked assertions.

    Pre-change all three calls executed (3 requests, the second escaping to
    `http://data/v1/health`). Post-change the hostile call is rejected without a request
    (2 requests) while the third call still runs and the stream still ends in an answer.
    """
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": "700.HK"}),
                PlannedCall("get_quote", {"symbol": "../health"}),
                PlannedCall("search_news", {"symbol": "700.HK"}),
            ]
        )
    )

    assert [event["ok"] for event in events if event["type"] == "tool_result"] == [
        True,
        False,
        True,
    ]
    assert events[-1]["type"] == "answer"
    assert _urls(recorded_requests) == [VALID_QUOTE_URL, VALID_NEWS_URL]


# --- NO AMEND: what TD-01 must leave byte-identical -------------------------------------


def test_the_schema_td01_makes_executable_is_unchanged(
    recording_client: httpx.AsyncClient,
) -> None:
    """NO AMEND. TD-01 starts enforcing this exact object, so its content is pinned here:
    one shared schema for all three tools, `symbol` required, string, contract pattern.
    """
    tools = build_tools(recording_client)

    assert tools["get_quote"].parameters == {
        "type": "object",
        "required": ["symbol"],
        "properties": {"symbol": {"type": "string", "pattern": r"^[0-9A-Z]{1,20}\.(HK|US|SH|SZ)$"}},
    }
    assert tools["search_news"].parameters is tools["get_quote"].parameters
    assert tools["get_capital_flow"].parameters is tools["get_quote"].parameters


async def test_valid_symbol_request_urls_survive_url_encoding(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. A2 encodes the symbol where it enters a path; for a symbol matching the
    advertised pattern encoding is a no-op, so these URLs must stay byte-identical — including
    the widest legal symbol, a real option code from production watchlists.
    """
    tools = build_tools(recording_client)

    await tools["get_quote"].run({"symbol": "700.HK"})
    await tools["get_capital_flow"].run({"symbol": "700.HK"})
    with pytest.raises(httpx.HTTPStatusError):
        await tools["get_quote"].run({"symbol": WIDEST_LEGAL_SYMBOL})

    assert _urls(recorded_requests) == [
        VALID_QUOTE_URL,
        VALID_CAPITAL_FLOW_URL,
        f"http://data/v1/quotes/{WIDEST_LEGAL_SYMBOL}",
    ]


async def test_search_news_keeps_the_symbol_in_the_query_string(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. A2 concerns symbols entering a *path*; `search_news` passes it as a query
    parameter, which httpx already percent-encodes, so this request must not change shape.
    """
    await build_tools(recording_client)["search_news"].run({"symbol": "700.HK", "limit": 5})

    assert _urls(recorded_requests) == ["http://data/v1/news?symbol=700.HK&limit=5"]


async def test_arguments_the_schema_does_not_declare_stay_allowed(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. `Tool.parameters` sets no `additionalProperties: false`, so JSON Schema
    permits arguments it does not declare — `limit` is used by `search_news` yet absent from
    the schema. A validator that rejected undeclared keys would break the tool as soon as a
    real planner (BL-05) sends one.
    """
    result = await build_tools(recording_client)["search_news"].run(
        {"symbol": "700.HK", "limit": 2}
    )

    assert len(recorded_requests) == 1
    assert result[0]["headline"] == "700.HK news"


async def test_an_unknown_tool_is_still_reported_before_execution(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. Validation belongs after the registry lookup, so an unknown tool keeps its
    own summary, still makes no request and still leaves the stream running.
    """
    events = await _events(scripted_analyst([PlannedCall("nope", {"symbol": "700.HK"})]))

    assert events[1] == {"type": "tool_call", "tool": "nope", "args": {"symbol": "700.HK"}}
    assert events[2] == {
        "type": "tool_result",
        "tool": "nope",
        "ok": False,
        "summary": "unknown tool",
    }
    assert events[-1]["type"] == "answer"
    assert recorded_requests == []


async def test_a_valid_symbol_the_upstream_does_not_know_still_reports_http_404(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. Validation must not swallow genuine upstream errors: `0000.HK` matches the
    pattern, so it is still sent and still reported as `HTTP 404` (tests/test_analyst.py).
    """
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "0000.HK"})]))

    assert events[2]["ok"] is False
    assert events[2]["summary"] == "HTTP 404"
    assert events[-1]["type"] == "answer"
    assert _urls(recorded_requests) == ["http://data/v1/quotes/0000.HK"]


async def test_the_happy_path_events_and_observation_keys_are_unchanged(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. The whole path TD-01 wraps: `tool_call` is emitted before execution, the
    observation key keeps its `tool:symbol` shape and the summaries keep their legacy text.
    """
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": "700.HK"}),
                PlannedCall("search_news", {"symbol": "700.HK"}),
            ]
        )
    )

    assert [event["type"] for event in events] == [
        "thinking",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "answer",
    ]
    assert events[0]["text"] == "scripted plan"
    assert events[1]["args"] == {"symbol": "700.HK"}
    assert (events[2]["ok"], events[2]["summary"]) == (True, "price 388.2000")
    assert (events[4]["ok"], events[4]["summary"]) == (True, "1 items")
    assert events[-1]["markdown"] == "observations: get_quote:700.HK, search_news:700.HK"
    assert _urls(recorded_requests) == [VALID_QUOTE_URL, VALID_NEWS_URL]


async def test_the_stub_planner_makes_the_same_requests_as_before(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """NO AMEND. Every argument the stub planner synthesizes is already schema-valid, so
    TD-01 must not change what leaves the service on the demo path.
    """
    analyst = Analyst(StubProvider(), build_tools(recording_client))
    events = [
        event.model_dump()
        async for event in analyst.run("What is the capital flow for Tencent today?")
    ]

    assert _urls(recorded_requests) == [
        VALID_QUOTE_URL,
        VALID_NEWS_URL,
        VALID_CAPITAL_FLOW_URL,
    ]
    assert all(event["ok"] for event in events if event["type"] == "tool_result")
    assert events[-1]["type"] == "answer"
