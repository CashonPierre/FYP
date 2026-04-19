FROM python:3.12-slim

# git + ca-certificates needed to clone the trading_engine submodule below.
# Railway doesn't init git submodules during build, so the repo's trading_engine/
# directory arrives empty in the build context — we clone it ourselves at a
# pinned SHA. Bump TRADING_ENGINE_SHA when pulling submodule updates.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /repo

ARG TRADING_ENGINE_SHA=bce6028845a7d726374c845b928ce3a4bafcbfa8
RUN git clone https://github.com/Quant-Backtester/trading_engine.git ./trading_engine \
    && git -C ./trading_engine checkout ${TRADING_ENGINE_SHA}

COPY backend/ ./backend/

# Install Python dependencies (locked)
WORKDIR /repo/backend
RUN uv sync --frozen --no-dev

# Default start command — Railway overrides this per-service:
#   API:    uv run python server.py
#   Worker: uv run celery -A background.celery_app worker --loglevel=info
EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
