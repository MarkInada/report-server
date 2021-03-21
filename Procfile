worker: celery -A app.celery worker --loglevel=info
web: gunicorn app:app --timeout 30 --keep-alive 15 --log-file -