#!/bin/bash

# Apply database migrations
echo "[Entrypoint] Applying database migrations..."
python manage.py migrate --noinput

# Start the application
echo "[Entrypoint] Starting server..."
exec "$@"
