#!/bin/sh
set -e
echo "Running database migrations..."
alembic upgrade head

echo "Starting CodeRadar API server..."
if [ "$ENVIRONMENT" = "production" ] || [ "$APP_ENV" = "production" ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
