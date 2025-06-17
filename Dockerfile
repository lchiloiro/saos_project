FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm

COPY --from=builder --chown=app:app /app /app
COPY ./src/saos_project/client_secrets.json /app/client_secrets.json

ENV PATH="/app/.venv/bin:$PATH"

CMD ["flask", "--app", "saos_project", "run", "--host", "0.0.0.0", "--debug"]

STOPSIGNAL SIGINT