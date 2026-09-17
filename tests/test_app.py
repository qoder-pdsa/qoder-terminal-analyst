import json

import httpx
from fastapi.testclient import TestClient

from qoder_analyst.app import create_app


def test_health(data_client: httpx.AsyncClient) -> None:
    with TestClient(create_app(data_client=data_client)) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ask_streams_sse(data_client: httpx.AsyncClient) -> None:
    with TestClient(create_app(data_client=data_client)) as client:
        resp = client.post("/v1/ask", json={"question": "How is Tencent doing?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[len("data: ") :]) for line in resp.text.splitlines() if line]
    assert events[-1]["type"] == "answer"


def test_ask_rejects_empty_question(data_client: httpx.AsyncClient) -> None:
    with TestClient(create_app(data_client=data_client)) as client:
        assert client.post("/v1/ask", json={"question": ""}).status_code == 422


def test_internal_data_client_ignores_system_proxy() -> None:
    # A local system proxy would route localhost requests out and return 502,
    # so service-to-service calls must connect directly
    from qoder_analyst.app import build_data_client

    client = build_data_client("http://localhost:8081")
    assert client.trust_env is False
