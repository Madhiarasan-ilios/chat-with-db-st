#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-2}"
WORKER_CLASS="${WORKER_CLASS:-uvicorn.workers.UvicornWorker}"
TIMEOUT="${TIMEOUT:-120}"

echo "▶  Starting SQL-Gen API"
echo "   Host:    $HOST:$PORT"
echo "   Workers: $WORKERS"
echo "   Env:     ${APP_ENV:-development}"

exec gunicorn app.main:app \
  --bind "$HOST:$PORT" \
  --workers "$WORKERS" \
  --worker-class "$WORKER_CLASS" \
  --timeout "$TIMEOUT" \
  --access-logfile - \
  --error-logfile - \
  --log-level "${LOG_LEVEL:-info}"
