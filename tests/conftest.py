import json

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


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.startswith("/v1/quotes/"):
        symbol = path.rsplit("/", 1)[-1]
        if symbol in QUOTES:
            return httpx.Response(200, json=QUOTES[symbol])
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
