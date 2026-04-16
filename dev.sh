#!/usr/bin/env bash
# Start the full dev stack: Docker containers + backend + Celery worker + frontend
set -e

echo "Starting Docker containers..."
docker start timescaledb valkey

echo "Starting backend, worker, and frontend..."
cd "$(dirname "$0")"
cd backend && uv run honcho start -f ../Procfile
