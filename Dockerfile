FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation for installation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# First phase: Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Second phase: Install project
COPY uv.lock pyproject.toml alembic.ini README.md /app/
COPY /src /app/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Third phase: Pre-compile all Python files to bytecode
RUN python -m compileall -f /app

# Disable bytecode compilation at runtime since we've already done it
ENV UV_COMPILE_BYTECODE=0

# Place executables in the environment
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["uv", "run"]
