"""FastAPI application implementing api/openapi.yaml."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, TypeAdapter

from qoder_analyst.analyst import Analyst
from qoder_analyst.events import AgentEvent
from qoder_analyst.llm import LLMProvider, StubProvider
from qoder_analyst.tools import build_tools

_event_adapter: TypeAdapter[AgentEvent] = TypeAdapter(AgentEvent)


class AskContext(BaseModel):
    activeSymbol: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: AskContext | None = None


def _build_llm(name: str) -> LLMProvider:
    if name == "stub":
        return StubProvider()
    raise RuntimeError(f"Unsupported LLM_PROVIDER={name!r}; only 'stub' is implemented yet")


def build_data_client(base_url: str) -> httpx.AsyncClient:
    """HTTP client for service-to-service calls.

    `trust_env=False`: ignore system/environment proxies so localhost requests are not
    routed through a local proxy (which returns 502).
    """
    return httpx.AsyncClient(base_url=base_url, timeout=10.0, trust_env=False)


def create_app(
    data_client: httpx.AsyncClient | None = None, llm: LLMProvider | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = data_client or build_data_client(
            os.environ.get("DATA_BASE_URL", "http://localhost:8081")
        )
        provider = llm or _build_llm(os.environ.get("LLM_PROVIDER", "stub"))
        app.state.analyst = Analyst(provider, build_tools(client))
        yield
        if data_client is None:
            await client.aclose()

    app = FastAPI(title="Qoder Terminal Analyst", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/ask")
    async def ask(req: AskRequest) -> StreamingResponse:
        analyst: Analyst = app.state.analyst

        async def stream() -> AsyncIterator[bytes]:
            async for event in analyst.run(req.question):
                yield b"data: " + _event_adapter.dump_json(event) + b"\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


app = create_app()
