# Run via ./dev.sh from repo root — honcho CWD is backend/
backend:  uv run python server.py
worker:   uv run celery -A background.celery_app worker --loglevel=info
frontend: cd ../frontend && pnpm dev
