#!/usr/bin/env bash
# Start the full dev stack: Docker containers + backend + Celery worker + frontend
set -e

echo "Starting Docker containers..."
docker start timescaledb valkey

# Clear orphaned processes so ports are predictable
lsof -ti :8000 | xargs kill -9 2>/dev/null || true   # backend
lsof -ti :5173 | xargs kill -9 2>/dev/null || true   # frontend (Vite tries these in order)
lsof -ti :5174 | xargs kill -9 2>/dev/null || true
lsof -ti :5175 | xargs kill -9 2>/dev/null || true

echo "Starting backend, worker, and frontend..."
cd "$(dirname "$0")"
cd backend && uv run honcho start -f ../Procfile
