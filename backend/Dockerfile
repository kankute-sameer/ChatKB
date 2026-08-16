FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY --chmod=755 entrypoint.sh ./entrypoint.sh
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 chatkb \
    && mkdir -p /home/chatkb/.cache \
    && chown -R chatkb:chatkb /home/chatkb

USER chatkb

EXPOSE 8000

# entrypoint.sh intentionally starts one uvicorn process for in-memory streams.
CMD ["./entrypoint.sh"]
