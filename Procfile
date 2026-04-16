backend:  cd backend && uv run python server.py
worker:   cd backend && uv run celery -A background.celery_app worker --loglevel=info
frontend: cd frontend && pnpm dev
