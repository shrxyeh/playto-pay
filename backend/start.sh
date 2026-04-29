#!/usr/bin/env sh
set -ex

python manage.py migrate --noinput
python manage.py seed
python manage.py collectstatic --noinput

C_FORCE_ROOT=1 celery -A config worker -l info --detach \
  --logfile=/tmp/celery-worker.log \
  --pidfile=/tmp/celery-worker.pid

C_FORCE_ROOT=1 celery -A config beat -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --detach \
  --logfile=/tmp/celery-beat.log \
  --pidfile=/tmp/celery-beat.pid

exec gunicorn wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2
