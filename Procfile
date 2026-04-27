web: python manage.py migrate && python manage.py seed && gunicorn config.wsgi --bind 0.0.0.0:$PORT
worker: celery -A config worker -l info
beat: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
