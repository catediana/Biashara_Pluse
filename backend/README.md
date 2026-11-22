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

## Integrations and background tasks

The existing `DarajaClient` provides the M-Pesa STK Push and query integration.
Email uses Django's configured mail backend; SMS uses Africa's Talking; and
WhatsApp uses the Meta WhatsApp Cloud API. Configure credentials only through
environment variables:

| Integration | Environment variables |
|---|---|
| Email | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL` |
| Africa's Talking SMS | `AFRICASTALKING_USERNAME`, `AFRICASTALKING_API_KEY`, optional `AFRICASTALKING_SENDER_ID` |
| WhatsApp Cloud API | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` |
| M-Pesa | `MPESA_ENV`, `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`, `MPESA_CALLBACK_URL` |

`queue_notification()` writes an organisation-scoped outbox record with a
required idempotency key and queues delivery after the transaction commits.
Notifications and reminders support email, SMS, and WhatsApp; provide
`scheduled_at` to queue a reminder for a future time. No recurring Celery Beat
schedules are enabled. Workers claim deliveries with a database lease, avoid
resending completed records, retry transient provider failures with backoff,
and mark permanent failures for inspection. Since external messaging providers
do not all guarantee idempotency, a provider timeout or worker crash after
acceptance can still result in at-least-once delivery.

`generate_report_task` accepts an organisation UUID, one of `sales_summary`,
`stock`, `customer_debt`, `expenses`, or `profit`, and optional
`branch_id`/`from_date`/`to_date` filters. It is read-only and returns
JSON-compatible rows, so retries do not create duplicate side effects. A stable
Celery `task_id` can be used to correlate the result, but does not deduplicate
broker messages.

Configure Redis with `REDIS_URL` (or `CELERY_BROKER_URL` and
`CELERY_RESULT_BACKEND`); workers use late acknowledgement and reject tasks
when a worker is lost.

## Cashier shifts and expenses

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/retail/shifts/open/` | Open the authenticated cashier's shift with a branch and opening float |
| GET | `/api/retail/shifts/` | List shifts with optional branch and date filters |
| POST | `/api/retail/shifts/<uuid>/close/` | Close a shift with a counted cash amount |
| GET, POST | `/api/retail/expenses/` | List or record expenses |

Expense creation requires `Idempotency-Key`, the cashier's open shift, a
category, a positive amount, and a `cash` or `mpesa` payment method. Expense
records are immutable. Closing a shift stores expected cash, counted cash, and
variance (`counted_cash - expected_cash`). Expected cash is the opening float
plus confirmed cash sales and collections, less cash expenses and cash refunds
recorded against that shift. Pending M-Pesa payments are excluded. A cash refund
requires the cashier's open shift at the sale's branch.

Assign `retail.shifts.open`, `retail.shifts.view`, `retail.shifts.close`,
`retail.expenses.view`, and `retail.expenses.create` to the appropriate roles.
List endpoints accept `branch_id`, `from_date`, and `to_date` and use
page-number pagination.

## Retail reports

All reports require the `retail.reports.view` permission and Retail module
entitlement. They accept optional `branch_id`, `from_date`, and `to_date`
filters. JSON responses use page-number pagination; add `export=csv` to download
all matching rows as CSV.

| Path | Contents |
|---|---|
| `/api/reporting/sales-summary/` | Daily posted sales, returns, and net sales by branch |
| `/api/reporting/stock/` | Product stock with opening and closing quantities, change, and estimated value |
| `/api/reporting/customer-debt/` | Remaining balances for credit sales in the selected date range |
| `/api/reporting/expenses/` | Expenses by date, category, branch, and payment method |
| `/api/reporting/profit/` | Net sales less net cost of goods sold and expenses by day and branch |

The customer debt report uses confirmed collections and credit reductions on
returns through `to_date`; a supplied `from_date` scopes the credit sales being
reported. Stock quantities for a date range are reconstructed from stock
movements; estimated values use each balance's current average cost. Profit is
an operational estimate based on sale-line cost snapshots and excludes tax
accounting.

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
