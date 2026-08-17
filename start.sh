#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is missing. In Render → Environment, set it to the Internal Database URL:"
  echo "postgresql://USER:PASSWORD@dpg-xxxxx-a/virtuals_signals"
  exit 1
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:"${PORT:-8000}"
