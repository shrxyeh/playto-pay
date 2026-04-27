web: cd backend && python manage.py migrate && python manage.py seed && gunicorn config.wsgi --bind 0.0.0.0:$PORT
worker: cd backend && celery -A config worker -l info
beat: cd backend && celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
