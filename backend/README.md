# Biashara Pulse backend

Django 5 modular monolith API foundation. Sector apps are registered but intentionally contain no domain models yet.

## Local setup

From this directory, create and activate a virtual environment, then install:

```text
pip install -r requirements/development.txt
```

Configure PostgreSQL with `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT`. Redis is configured through `REDIS_URL`; Celery can override it with `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

Run the development server with:

```text
python manage.py runserver
```

Set `DJANGO_SETTINGS_MODULE=config.settings.testing` when running tests. Production uses `config.settings.production` and requires `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`.
