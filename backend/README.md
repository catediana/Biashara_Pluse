# Biashara Pulse backend

Django 5 modular monolith API foundation. Retail catalogue and inventory are the
first sector workflows; other sector apps have no domain models yet.

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

## Retail catalogue and inventory API

Select an organisation on authenticated requests with the `X-Organisation-ID`
header. The middleware resolves it only when the authenticated user has an
active membership. Retail inventory endpoints also require an enabled Retail
module, the matching role permission, and branch access where applicable.

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/api/retail/products/` | Search/list or create products |
| GET, PATCH | `/api/retail/products/<uuid>/` | Retrieve or update a tenant product |
| POST | `/api/retail/goods-receipts/` | Receive supplier stock atomically |
| POST | `/api/retail/stock-adjustments/` | Request a reason-coded adjustment |
| POST | `/api/retail/stock-adjustments/<uuid>/<approve\|reject>/` | Review an adjustment |

Send a UUID in `Idempotency-Key` for receipt and adjustment submissions.
Replaying the same key and payload returns the original resource; reusing the
key for a different payload returns `409 Conflict`. Receipt lines and stock
movements are created with their balance updates in one database transaction.
Adjustments do not affect stock until approved. Approval checks the expected
stock version and prevents negative stock. Product search matches name, SKU,
or barcode; list results use page-number pagination.

Assign these `Permission` codenames to a role as needed:
`retail.products.view`, `retail.products.create`, `retail.products.update`,
`retail.stock.receive`, `retail.stock.adjustment.request`,
`retail.stock.adjustment.approve`, and `retail.stock.adjustment.reject`.
Grant branch access using `BranchGrant`, or set membership `all_branches` for
organisation-wide branch access.

## Retail checkout and payments

`POST /api/retail/checkout/` requires `X-Organisation-ID`,
`Idempotency-Key`, an active `retail.sales.checkout` permission, and branch
access. The shift must be open and belong to the authenticated cashier at the
selected branch. Checkout supports cash, M-Pesa, split cash/M-Pesa, and customer
credit. Cash accepts optional `amount_tendered` and returns change. Split
checkout requires one cash and one M-Pesa allocation whose amounts equal the
sale total. Credit checkout requires an active customer and enforces the
customer's hard credit limit. Customer credit balances are derived from credit
sales, confirmed collections, and credit reductions on returns.

Checkout locks the shift and stock rows and creates the sale, immutable line
snapshots, payment records and allocations, stock movements, receipt snapshot,
and `retail.sale.checkout` audit event in one transaction. A repeated
idempotency key and matching request returns the original sale; the same key
with a different request returns `409 Conflict`. M-Pesa payments remain pending
until the callback is matched to the payment and verified with a Daraja STK
query. Daraja amounts must be whole currency units. Do not retry an STK request
whose initiation outcome is unresolved; reconcile it before attempting another
prompt. A verified failure on an M-Pesa-only sale cancels the sale, voids its
pending receipt, and restores reserved stock exactly once. A failed M-Pesa
allocation on a split sale remains unresolved because its cash allocation has
already been accepted and requires operator follow-up. Receipts can be retrieved
through `GET /api/retail/sales/<uuid>/receipt/`, subject to tenant and branch
access.

## Customers, collections, returns, and refunds

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/api/retail/customers/` | List or create tenant customers |
| POST | `/api/retail/customers/<uuid>/collections/` | Record a customer collection and allocate it to credit sales |
| POST | `/api/retail/payments/<uuid>/stk-push/` | Start a pending M-Pesa STK Push |
| POST | `/api/retail/mpesa/callback/` | Receive and verify a Daraja callback |
| POST | `/api/retail/sales/<uuid>/returns/` | Return original sale lines and restore accepted stock |
| POST | `/api/retail/refunds/<uuid>/complete/` | Record completion of a pending M-Pesa refund payout |

Collections require an open cashier shift, an idempotency key, and allocations
equal to the payment amount. Allocations are locked and checked against each
credit sale's remaining balance. Returns require the original sale, a reason,
and quantities no greater than the unreturned sold quantity. Returned quantities
are restocked with linked stock movements. Returns against a credit sale reduce
that sale's remaining debt first. Cash refunds are recorded as complete in the
return transaction; M-Pesa refunds remain pending for an external payout and
must be completed with its payout reference.

All payment and return endpoints enforce tenant and branch access. Configure
`MPESA_ENV` (`sandbox` or `production`), `MPESA_CONSUMER_KEY`,
`MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`,
`MPESA_TRANSACTION_TYPE` (`CustomerPayBillOnline` or
`CustomerBuyGoodsOnline`), and the public `MPESA_CALLBACK_URL` using deployment
environment variables. Production callback URLs must use HTTPS. Provider
callbacks are not trusted as payment proof by themselves: the backend queries
Daraja before confirming a payment and treats repeated callback events
idempotently. The callback endpoint should be reachable only over HTTPS.

Assign these `Permission` codenames to roles for the related workflows:
`retail.sales.payment`, `retail.sales.collection`, `retail.sales.return`,
`retail.sales.refund`, `retail.customers.view`, and
`retail.customers.create`. Grant branch access using `BranchGrant`, or set
membership `all_branches` for organisation-wide branch access.

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
