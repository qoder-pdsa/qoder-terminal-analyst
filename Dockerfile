FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project
COPY . .
RUN uv sync --no-dev
EXPOSE 8082
CMD ["uv", "run", "--no-dev", "uvicorn", "qoder_analyst.app:app", "--host", "0.0.0.0", "--port", "8082"]
