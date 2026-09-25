import json
from typing import Any

import httpx
import pytest

QUOTES = {
    "700.HK": {
        "symbol": "700.HK",
        "price": "388.2000",
        "change": "8.2000",
        "changePercent": "2.1578",
        "currency": "HKD",
        "asOf": "2026-09-17T00:00:00Z",
    },
}

# CapitalFlow payloads shaped exactly as the provider contract requires
# (qoder-terminal-data/api/openapi.yaml:261): every amount is a decimal *string*, `flow` is
# ascending by time and a negative inflow means outflow.
CAPITAL_FLOWS: dict[str, dict[str, Any]] = {
    "700.HK": {
        "symbol": "700.HK",
        "currency": "HKD",
        "asOf": "2026-09-25T09:35:00Z",
        "flow": [
            {"time": "2026-09-25T09:31:00Z", "inflow": "4800000.0000"},
            {"time": "2026-09-25T09:34:00Z", "inflow": "-2600000.5000"},
            {"time": "2026-09-25T09:35:00Z", "inflow": "-1200000.0000"},
        ],
        "distribution": {
            "in": {"large": "5000000.0000", "medium": "1200000.0000", "small": "300000.0000"},
            "out": {"large": "4100000.0000", "medium": "1000000.0000", "small": "250000.0000"},
            "net": {"large": "900000.0000", "medium": "200000.0000", "small": "50000.0000"},
        },
    },
    # Before the first trade of the HK session the real provider answers 200 with an empty
    # `flow` while `distribution` still reports. Not an error: see HUMAN comment 10041.
    "9988.HK": {
        "symbol": "9988.HK",
        "currency": "HKD",
        "asOf": "2026-09-25T09:29:00Z",
        "flow": [],
        "distribution": {
            "in": {"large": "0.0000", "medium": "0.0000", "small": "0.0000"},
            "out": {"large": "0.0000", "medium": "0.0000", "small": "0.0000"},
            "net": {"large": "0.0000", "medium": "0.0000", "small": "0.0000"},
        },
    },
}

# Symbols the mock answers with a server error, to exercise the 5xx half of the criterion.
CAPITAL_FLOW_5XX = {"0005.HK"}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.startswith("/v1/quotes/"):
        symbol = path.rsplit("/", 1)[-1]
        if symbol in QUOTES:
            return httpx.Response(200, json=QUOTES[symbol])
        return httpx.Response(404, json={"code": "not_found", "message": "symbol not found"})
    if path.startswith("/v1/capital-flow/"):
        symbol = path.rsplit("/", 1)[-1]
        if symbol in CAPITAL_FLOW_5XX:
            return httpx.Response(500, json={"code": "internal", "message": "upstream unavailable"})
        if symbol in CAPITAL_FLOWS:
            return httpx.Response(200, json=CAPITAL_FLOWS[symbol])
        return httpx.Response(404, json={"code": "not_found", "message": "symbol not found"})
    if path == "/v1/news":
        symbol = request.url.params["symbol"]
        items = [
            {
                "id": "1",
                "headline": f"{symbol} news",
                "source": "Mock",
                "url": "https://example.com/1",
                "publishedAt": "2026-09-17T00:00:00Z",
            }
        ]
        return httpx.Response(200, content=json.dumps(items))
    return httpx.Response(404)


@pytest.fixture
def data_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="http://data", transport=httpx.MockTransport(_handler))
