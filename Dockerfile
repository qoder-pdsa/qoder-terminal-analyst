FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
# 直接使用构建期安装好的虚拟环境：容器启动不联网、不重新安装依赖
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8082
CMD ["uvicorn", "qoder_analyst.app:app", "--host", "0.0.0.0", "--port", "8082"]
