FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation for installation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

ARG COMPILE_CORES=0

# Determine the number of cores to use
RUN if [ "$COMPILE_CORES" -gt 0 ]; then \
        CORES="$COMPILE_CORES"; \
    elif [ "$COMPILE_CORES" -eq 0 ]; then \
        CORES=$(nproc); \
    else \
        CORES=1; \
    fi && \
    echo "Using $CORES cores for compilation" && \
    COMPILE_CORES="$CORES"

# First phase: Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Second phase: compile deps
RUN python -m compileall -f -j $COMPILE_CORES -o2 /app/.venv

# Third phase: Install project
COPY uv.lock pyproject.toml alembic.ini README.md /app/
COPY /src /app/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Fourth phase: compile app code
RUN python -m compileall -f -j $COMPILE_CORES -o2 /app/src

# Disable bytecode compilation at runtime since we've already done it
ENV UV_COMPILE_BYTECODE=0

# Place executables in the environment
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["uv", "run"]
