# Biashara Pulse backend

Django 5 modular monolith API foundation. Sector apps are registered but intentionally contain no domain models yet.

## Authentication API

All endpoints are under `/api/auth/`:

| Method | Path | Purpose |
|---|---|---|
| GET | `csrf/` | Set a CSRF cookie and return a request token |
| POST | `register/` | Create an account and start a session |
| POST | `login/` | Authenticate and start a session |
| POST | `logout/` | End the current session |
| POST | `password-reset/request/` | Send a reset link without revealing whether an email exists |
| POST | `password-reset/confirm/<uidb64>/<token>/` | Validate a reset link and update the password |
| GET | `me/` | Return the authenticated user's profile |
| POST | `session/refresh/` | Rotate the session key and renew its expiry |

Call `csrf/` first and send its `csrf_token` as `X-CSRFToken` on unsafe requests,
including login and registration. The authentication credential is the
HttpOnly session cookie; no bearer token is issued. Keep browser requests
credentialed and do not persist authentication tokens in browser storage.
`SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are enabled outside debug
mode. These defaults assume a same-site deployment, preferably serving the API
and frontend through the same origin. A separate browser origin also requires
an explicit CORS allowlist and credential support; `CSRF_TRUSTED_ORIGINS` alone
does not enable CORS. Auth endpoints use scoped DRF throttles backed by the
configured cache. `REST_FRAMEWORK_NUM_PROXIES` defaults to `0`; set it to the
number of trusted reverse proxies only when the deployment proxy chain is
configured to overwrite forwarded client-address headers.

Password reset email links use `PASSWORD_RESET_URL` and `DEFAULT_FROM_EMAIL`.
Configure these for the deployed frontend and mail backend.

## Organisations and tenant access

`Organisation` is the tenant root. `Branch`, `Membership`, `Role`,
`RolePermission`, `BranchGrant`, and `ModuleEntitlement` carry an
`organisation_id`; the shared `Permission` catalog is global. Tenant models
inherit UUID keys and timestamps from `core.tenancy.TenantModel`.

Always scope tenant queries explicitly, for example
`Branch.objects.for_organisation(request.active_organisation)`. Set
`request.active_organisation` only from trusted server-side organisation
resolution, never directly from an unverified client-supplied organisation ID.
Protected views can use `HasTenantAccess` with a `required_permission`
codename, optional `required_module`, and `branch_scoped = True`. Branch-scoped
list views must also filter their queryset by the requested, authorised branch;
detail views should enable object-permission checks.

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

Set `DJANGO_SETTINGS_MODULE=config.settings.testing` when running tests; the
test settings use in-memory SQLite and a local-memory cache. Production uses
`config.settings.production` and requires `DJANGO_SECRET_KEY` and
`DJANGO_ALLOWED_HOSTS`.
