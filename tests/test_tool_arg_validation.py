"""TD-01: tool arguments are validated against `Tool.parameters` before they reach a URL.

Written before the implementation (SDLC step 10001, TDD) and observed failing for business
reasons on the unchanged tree — see `evidence/tdd-red.log`: hostile symbols escaped to
`/v1/health`, out-of-pattern symbols were sent upstream, and a missing `symbol` raised
`KeyError` out of the agent loop.

Everything runs on the conftest `recording_client` (`httpx.MockTransport`), so no test can
reach the network and "without any HTTP call" is provable by an empty `recorded_requests`.
"""

from collections.abc import Callable, Sequence
from typing import Any

import httpx
import pytest

from qoder_analyst.analyst import Analyst
from qoder_analyst.llm import PlannedCall
from qoder_analyst.tools import build_tools, validate_tool_args

ScriptedAnalyst = Callable[[Sequence[PlannedCall]], Analyst]

QUOTE_URL = "http://data/v1/quotes/700.HK"
CAPITAL_FLOW_URL = "http://data/v1/capital-flow/700.HK"
WIDEST_LEGAL_SYMBOL = "MSFT261016P420000.US"
TRAVERSAL_SYMBOL = "../health"


async def _events(analyst: Analyst) -> list[dict[str, Any]]:
    return [event.model_dump() async for event in analyst.run("scripted")]


def _urls(recorded_requests: list[httpx.Request]) -> list[str]:
    return [str(request.url) for request in recorded_requests]


def _tool_results(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["type"] == "tool_result"]


# --- A1 + A3: the loop rejects a schema violation before the tool function runs ----------


@pytest.mark.parametrize(
    "symbol",
    [TRAVERSAL_SYMBOL, "../../v1/quotes/700.HK", "700.HK/x", "700.hk", "AAPL", "A" * 21 + ".US"],
)
async def test_an_invalid_symbol_is_rejected_without_any_http_call(
    symbol: str,
    scripted_analyst: ScriptedAnalyst,
    recorded_requests: list[httpx.Request],
) -> None:
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": symbol})]))

    assert recorded_requests == [], "a rejected argument must not reach the upstream service"
    results = _tool_results(events)
    assert len(results) == 1
    assert results[0]["ok"] is False
    assert events[-1]["type"] == "answer", "the stream must continue past a rejected argument"


@pytest.mark.parametrize(
    "args",
    [{}, {"symbol": 700}, {"symbol": None}, {"symbol": ["700.HK"]}, {"symbol": "700.HK\n"}],
)
async def test_arguments_that_violate_the_schema_are_rejected_without_any_http_call(
    args: dict[str, Any],
    scripted_analyst: ScriptedAnalyst,
    recorded_requests: list[httpx.Request],
) -> None:
    """A missing required argument, a non-string symbol and a trailing-newline symbol (which a
    `$`-anchored pattern admits under `re.search`) are all violations of `Tool.parameters`."""
    events = await _events(scripted_analyst([PlannedCall("get_capital_flow", args)]))

    assert recorded_requests == []
    assert [result["ok"] for result in _tool_results(events)] == [False]
    assert events[-1]["type"] == "answer"


async def test_every_tool_validates_its_arguments(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """Validation belongs to the loop, so it covers every registered tool alike."""
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": TRAVERSAL_SYMBOL}),
                PlannedCall("search_news", {"symbol": TRAVERSAL_SYMBOL}),
                PlannedCall("get_capital_flow", {"symbol": TRAVERSAL_SYMBOL}),
            ]
        )
    )

    assert recorded_requests == []
    assert [result["ok"] for result in _tool_results(events)] == [False, False, False]


async def test_a_rejected_call_does_not_stop_the_calls_after_it(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": "700.HK"}),
                PlannedCall("get_quote", {"symbol": TRAVERSAL_SYMBOL}),
                PlannedCall("search_news", {"symbol": "700.HK"}),
            ]
        )
    )

    assert [result["ok"] for result in _tool_results(events)] == [True, False, True]
    assert events[-1]["type"] == "answer"
    assert _urls(recorded_requests) == [QUOTE_URL, "http://data/v1/news?symbol=700.HK&limit=3"]


async def test_a_rejected_call_contributes_no_observation(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """A rejection is not data: the answer must not be summarized from it."""
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": TRAVERSAL_SYMBOL}),
                PlannedCall("get_quote", {"symbol": "700.HK"}),
            ]
        )
    )

    assert events[-1]["markdown"] == "observations: get_quote:700.HK"
    assert _urls(recorded_requests) == [QUOTE_URL]


async def test_the_tool_call_event_is_still_emitted_for_a_rejected_call(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """The event schema is out of scope for TD-01: `tool_call` precedes execution and still
    carries the arguments the planner produced, rejected or not."""
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "700.HK/x"})]))

    assert events[1] == {"type": "tool_call", "tool": "get_quote", "args": {"symbol": "700.HK/x"}}
    assert events[2]["type"] == "tool_result"
    assert events[2]["tool"] == "get_quote"


async def test_the_rejection_names_the_argument_but_never_echoes_its_value(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """The summary is rendered by the web client, so model-chosen input must not be reflected
    into it — only the argument name and the violated rule."""
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": TRAVERSAL_SYMBOL}),
                PlannedCall("get_quote", {}),
                PlannedCall("get_quote", {"symbol": 700}),
            ]
        )
    )

    summaries = [str(result["summary"]) for result in _tool_results(events)]
    assert len(summaries) == 3
    for summary in summaries:
        assert summary.startswith("invalid arguments:")
        assert "symbol" in summary
        assert TRAVERSAL_SYMBOL not in summary
        assert "700" not in summary


async def test_an_unknown_tool_is_reported_before_argument_validation(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """The registry lookup keeps its own legacy summary; validation must not swallow it."""
    events = await _events(scripted_analyst([PlannedCall("nope", {"symbol": TRAVERSAL_SYMBOL})]))

    assert _tool_results(events)[0]["summary"] == "unknown tool"
    assert recorded_requests == []


def test_the_validator_enforces_the_declared_json_type_keywords() -> None:
    """The registry only declares `string` today, but the validator is the boundary BL-05
    relies on, so a numeric keyword must not be silently ignored when the next tool adds one.
    """
    schema: dict[str, Any] = {"type": "object", "properties": {"limit": {"type": "integer"}}}

    assert validate_tool_args(schema, {"limit": 5}) is None
    assert validate_tool_args(schema, {}) is None, "an absent optional argument is not a violation"
    # isinstance(True, int) is True in Python, so the numeric keywords need an explicit guard
    assert validate_tool_args(schema, {"limit": True}) == "'limit' must be of type 'integer'"


# --- what validation must leave alone ----------------------------------------------------


async def test_valid_arguments_still_reach_the_upstream_unchanged(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    events = await _events(
        scripted_analyst(
            [
                PlannedCall("get_quote", {"symbol": "700.HK"}),
                PlannedCall("get_capital_flow", {"symbol": "700.HK"}),
            ]
        )
    )

    assert [result["ok"] for result in _tool_results(events)] == [True, True]
    assert _tool_results(events)[0]["summary"] == "price 388.2000"
    assert _urls(recorded_requests) == [QUOTE_URL, CAPITAL_FLOW_URL]


async def test_arguments_the_schema_does_not_declare_are_still_allowed(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """`Tool.parameters` sets no `additionalProperties: false`, and `search_news` already sends
    `limit`, which the schema never declares. Rejecting undeclared keys would break the tool as
    soon as a real planner (BL-05) uses one."""
    events = await _events(
        scripted_analyst([PlannedCall("search_news", {"symbol": "700.HK", "limit": 5})])
    )

    assert [result["ok"] for result in _tool_results(events)] == [True]
    assert _urls(recorded_requests) == ["http://data/v1/news?symbol=700.HK&limit=5"]


async def test_a_valid_symbol_the_upstream_does_not_know_still_reports_http_404(
    scripted_analyst: ScriptedAnalyst, recorded_requests: list[httpx.Request]
) -> None:
    """Validation must not swallow genuine upstream errors."""
    events = await _events(scripted_analyst([PlannedCall("get_quote", {"symbol": "0000.HK"})]))

    assert _tool_results(events)[0]["summary"] == "HTTP 404"
    assert _urls(recorded_requests) == ["http://data/v1/quotes/0000.HK"]


# --- A2: symbols are URL-encoded at the single place they enter a path -------------------


@pytest.mark.parametrize(
    ("tool_name", "endpoint"), [("get_quote", "quotes"), ("get_capital_flow", "capital-flow")]
)
async def test_a_symbol_that_bypasses_validation_stays_inside_its_endpoint(
    tool_name: str,
    endpoint: str,
    recording_client: httpx.AsyncClient,
    recorded_requests: list[httpx.Request],
) -> None:
    """Calling `Tool.run` directly skips the loop, so encoding is the second layer: httpx must
    not see dot segments it would normalize away from the endpoint."""
    with pytest.raises(httpx.HTTPStatusError):
        await build_tools(recording_client)[tool_name].run({"symbol": TRAVERSAL_SYMBOL})

    assert _urls(recorded_requests) == [f"http://data/v1/{endpoint}/..%2Fhealth"]


async def test_a_slash_in_a_symbol_that_bypasses_validation_is_not_a_path_separator(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        await build_tools(recording_client)["get_quote"].run({"symbol": "700.HK/x"})

    assert _urls(recorded_requests) == ["http://data/v1/quotes/700.HK%2Fx"]


async def test_encoding_is_a_no_op_for_legal_symbols(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """The widest legal symbol is a real option code from production watchlists; encoding must
    not alter a symbol that matches the advertised pattern."""
    tools = build_tools(recording_client)

    await tools["get_quote"].run({"symbol": "700.HK"})
    await tools["get_capital_flow"].run({"symbol": "700.HK"})
    with pytest.raises(httpx.HTTPStatusError):
        await tools["get_quote"].run({"symbol": WIDEST_LEGAL_SYMBOL})

    assert _urls(recorded_requests) == [
        QUOTE_URL,
        CAPITAL_FLOW_URL,
        f"http://data/v1/quotes/{WIDEST_LEGAL_SYMBOL}",
    ]


async def test_search_news_keeps_the_symbol_out_of_the_path(
    recording_client: httpx.AsyncClient, recorded_requests: list[httpx.Request]
) -> None:
    """`search_news` passes the symbol as a query parameter, which httpx already encodes; the
    path helper must not move it into the path."""
    await build_tools(recording_client)["search_news"].run({"symbol": "700.HK"})

    assert _urls(recorded_requests) == ["http://data/v1/news?symbol=700.HK&limit=3"]
