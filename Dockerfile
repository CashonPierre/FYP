FROM python:3.12-slim

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /repo

# Copy trading engine submodule and backend source.
# Layout mirrors local dev: /repo/trading_engine and /repo/backend
# so that the relative ENGINE_PATH resolution in backtest.py keeps working.
COPY trading_engine/ ./trading_engine/
COPY backend/ ./backend/

# Install Python dependencies (locked)
WORKDIR /repo/backend
RUN uv sync --frozen --no-dev

# Default start command — Railway overrides this per-service:
#   API:    uv run python server.py
#   Worker: uv run celery -A background.celery_app worker --loglevel=info
EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
