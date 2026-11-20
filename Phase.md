# Biashara Pulse — Development Phases and Copilot Prompts
Version: 0.4 | Date: 2026-11-20

## How to use this file
Work through the phases in order. Do not start a later phase until the earlier phase is complete and tested.

After each Copilot prompt, use the commit message shown directly beneath it. Review generated code, migrations, and security-sensitive changes before committing.

## Phase 0 — Project setup
### Goal
Create repository, backend, frontend, database, testing, Docker, and CI setup.

### Copilot prompts and commit messages
```text
Create a Django 5 project named backend for Biashara Pulse.
Use a modular monolith with config and apps folders.
Create apps: accounts, organisations, rbac, billing, notifications, audit, reporting, integrations, retail, wholesale, schools, pharmacy.
Create core utilities for tenancy, permissions, exceptions, pagination, money, and audit.
Use PostgreSQL, Redis, Celery, and Django REST Framework.
Create base, development, testing, and production settings.
Do not create sector models yet.
```
**Commit message:**
```text
chore: set up Django project structure and settings
```

```text
Create a React + TypeScript + Vite project named frontend.
Use Tailwind CSS, React Router, TanStack Query, React Hook Form, Zod, Vitest, and React Testing Library.
Create app, features, shared, styles, and tests folders.
Create API client, auth provider, organisation provider, and layout components.
Do not create sector pages yet.
```
**Commit message:**
```text
chore: set up React TypeScript frontend structure
```

```text
Create Docker Compose configuration for Django backend, PostgreSQL, Redis, Celery worker, and React frontend.
Create development and production configurations.
Use environment variables for secrets and create .env.example without real secrets.
```
**Commit message:**
```text
chore: add Docker Compose development and production setup
```

```text
Create a GitHub Actions CI workflow for backend linting, Django tests, frontend linting, TypeScript checks, and frontend tests.
Use PostgreSQL and Redis services.
Do not deploy to production automatically.
```
**Commit message:**
```text
ci: add backend and frontend CI workflow
```

### Definition of done
Backend and frontend run locally; database and Redis connect; CI passes; secrets are not committed.

## Phase 1 — Shared platform foundation
### Goal
Build authentication, organisations, memberships, roles, permissions, tenant isolation, audit logging, and subscriptions.

### Copilot prompts and commit messages
```text
Create Django models for User, Organisation, Branch, Membership, Role, Permission, RolePermission, BranchGrant, Subscription, ModuleEntitlement, AuditEvent, and SupportGrant.
Use UUID primary keys.
Every tenant-owned model must have organisation_id.
Add indexes and constraints.
Do not create sector models.
```
**Commit message:**
```text
feat(platform): add core tenancy, RBAC, billing, and audit models
```

```text
Create reusable tenant-scoped queryset and manager.
Every tenant-owned model must filter by organisation.
Create TenantModel abstract base with organisation, created_at, updated_at, and version.
Resolve active organisation from authenticated membership, not client input.
```
**Commit message:**
```text
feat(platform): add tenant-scoped models and organisation resolution
```

```text
Create Django REST Framework authentication endpoints: register, login, logout, password reset request, password reset confirm, current user, and session refresh.
Use secure session cookies, CSRF protection, rate limiting, and password validation.
Do not store tokens in localStorage.
```
**Commit message:**
```text
feat(auth): add secure authentication and session endpoints
```

```text
Create role-based access control.
Create permissions for organisation, staff, retail sales, stock, customers, reporting, audit, and subscriptions.
Create permission classes checking membership, role permissions, branch access, and module entitlement.
Write cross-tenant denial tests.
```
**Commit message:**
```text
feat(rbac): add role-based permissions and access enforcement
```

```text
Create audit logging service.
Log actor, action, target type and ID, organisation, reason, correlation ID, timestamp, and redacted metadata.
Log login, permission denial, organisation creation, staff invitation, role change, sale, stock adjustment, payment, refund, and support access.
Do not log passwords, tokens, or raw provider payloads.
```
**Commit message:**
```text
feat(audit): add audit logging for sensitive platform actions
```

### Definition of done
Users can register and manage organisations; staff roles work; tenant isolation tests pass; audit events are created.

## Phase 2 — Retail catalogue and inventory
### Goal
Build products, categories, suppliers, stock balances, movements, receiving, and adjustments.

### Copilot prompts and commit messages
```text
Create Retail models: Category, Product, Supplier, StockBalance, StockMovement, GoodsReceipt, GoodsReceiptLine, and StockAdjustment.
Every model must be organisation-scoped.
Use UUIDs, decimal money and quantity fields, and indexes.
Do not create sales, payments, returns, or shifts yet.
```
**Commit message:**
```text
feat(retail): add catalogue, supplier, and inventory models
```

```text
Create product catalogue API: list, create, retrieve, update, deactivate.
Support search by name, SKU, and barcode.
Enforce tenant isolation, permissions, and cursor pagination.
Write cross-tenant denial tests.
```
**Commit message:**
```text
feat(retail): add product catalogue API and search
```

```text
Create goods receiving workflow.
Create supplier receipt, receipt lines, stock balance update, and stock movement.
Use a database transaction and idempotency key.
Calculate moving weighted-average cost.
Test duplicate submission, invalid quantity, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add supplier goods receiving and stock valuation
```

```text
Create stock adjustment workflow.
Stock clerks request adjustments; managers approve.
Require reason, expected stock version, and audit event.
Use transaction, prevent negative stock, and create stock movement.
Test approval, rejection, stale version, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add approved stock adjustments and movement ledger
```

```text
Create low-stock alert logic.
Compare stock quantity with reorder level.
Create idempotent Celery notification task.
Test low stock, sufficient stock, duplicate prevention, and tenant isolation.
```
**Commit message:**
```text
feat(retail): add low-stock notifications
```

### Definition of done
Catalogue, receiving, stock movements, adjustments, and alerts work; cross-tenant tests pass.

## Phase 3 — Retail POS and sales
### Goal
Build POS, sales, receipts, payments, customer credit, collections, returns, and refunds.

### Copilot prompts and commit messages
```text
Create Retail sales models: Customer, Sale, SaleLine, Payment, PaymentAllocation, Return, ReturnLine, Refund, Expense, and Shift.
Use organisation scoping, UUIDs, decimals, immutable posted records, and constraints.
Snapshot product name, SKU, unit, price, discount, tax, and cost on sale lines.
Do not allow editing or deleting posted sales.
```
**Commit message:**
```text
feat(retail): add sales, payments, returns, and shift models
```

```text
Create retail checkout endpoint.
Input: branch, shift, optional customer, sale lines, tenders, and override reason.
Validate permissions, branch, shift, stock, customer credit, and payment method.
Use one database transaction and idempotency key.
Create sale, lines, stock movements, allocations, receipt, and audit event atomically.
Test success, insufficient stock, concurrency, duplicate key, invalid payment, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add atomic POS checkout and stock allocation
```

```text
Create payment handling for cash, M-Pesa, split payment, and customer credit.
A pending M-Pesa payment must not settle a sale until verified.
Prevent over-allocation.
Create collection logic that reduces the correct customer balance.
Test pending, confirmed, duplicate provider event, invalid allocation, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add payment verification, allocation, and collections
```

```text
Create retail return workflow.
Returns must reference original sale and sale lines.
Prevent returning more than remaining sold quantity.
Create return, return lines, stock movements, debt reversal, and refund records.
Use transaction and separate asynchronous refund workflow.
Test excessive return, duplicate return, refund failure, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add bounded returns and refund workflow
```

```text
Create immutable receipt generation.
Include business, receipt number, date, cashier, customer, lines, totals, tax, discounts, payment breakdown, and change.
Support PDF and reprint.
Use transactional outbox so printer or email failure does not cancel a posted sale.
```
**Commit message:**
```text
feat(retail): add immutable receipts and outbox delivery
```

### Definition of done
POS completes sales; stock and receipts update correctly; credit, collections, returns, and refunds work; atomic tests pass.

## Phase 4 — Shifts, reports, and admin
### Goal
Build shifts, cash reconciliation, expenses, reports, exports, and administration.

### Copilot prompts and commit messages
```text
Create cashier shift workflow.
Open shift with float; close with counted cash.
Calculate expected cash, counted cash, and variance.
Prevent posting after close.
Use transactions and row locking.
Test open, close, duplicate open, posting after close, and variance.
```
**Commit message:**
```text
feat(retail): add shift opening, closing, and cash reconciliation
```

```text
Create expense management.
Allow authorised users to record expenses and cash payouts.
Link expenses to shifts where applicable.
Use transactions and audit events.
Test creation, approval, reconciliation, and cross-tenant denial.
```
**Commit message:**
```text
feat(retail): add expense recording and approval
```

```text
Create reporting endpoints for sales summary, stock, customer debt, expenses, and profit.
Support date and branch filters, pagination, and CSV export.
Distinguish gross sales, returns, net revenue, tax, expenses, and pending refunds.
Do not present estimated profit as final accounting profit.
```
**Commit message:**
```text
feat(retail): add sales, stock, debt, and profit reports
```

```text
Create organisation admin dashboard API.
Return profile, staff, roles, branches, subscription, audit summary, and retail metrics.
Enforce permissions and tenant isolation.
Test owner, manager, cashier, and unauthorised access.
```
**Commit message:**
```text
feat(platform): add organisation admin dashboard API
```

### Definition of done
Shift reconciliation, expenses, reports, exports, dashboard, and audit viewer work.

## Phase 5 — QA, security, and pilot
### Goal
Test, secure, prepare support, and pilot the Retail MVP.

### Copilot prompts and commit messages
```text
Create Playwright end-to-end tests for onboarding, staff invitation, product creation, stock receiving, POS sale, receipt, credit sale, collection, return, shift close, and reports.
Include loading, empty, error, and success states.
```
**Commit message:**
```text
test: add Retail end-to-end user journey tests
```

```text
Create security tests for unauthenticated access, revoked membership, wrong branch, foreign tenant access, privilege escalation, invalid CSRF, rate limiting, and sensitive data exposure.
```
**Commit message:**
```text
test(security): add authentication and tenant isolation tests
```

```text
Create reconciliation tests comparing stock ledger to balances, sale totals to lines, confirmed payments to allocations, and customer debt to sales, payments, returns, and refunds.
Create alerts; do not auto-repair discrepancies.
```
**Commit message:**
```text
test(retail): add financial and inventory reconciliation tests
```

```text
Create backup and recovery documentation with PostgreSQL schedule, restore steps, RTO, RPO, verification, and restore test script.
Do not store secrets in source code.
```
**Commit message:**
```text
docs(operations): add backup and recovery procedures
```

### Definition of done
E2E, security, reconciliation, and restore tests pass; pilot customers onboarded; critical defects resolved.

## Phase 6 — Wholesale module
### Goal
Build Wholesale after Retail validation.

### Copilot prompts and commit messages
```text
Create Wholesale models: WholesaleCustomer, CustomerPriceList, WholesaleOrder, WholesaleOrderLine, Delivery, StockTransfer, and Invoice.
Organisation scope, UUIDs, decimals, constraints.
Do not reuse Retail sale models directly.
```
**Commit message:**
```text
feat(wholesale): add wholesale domain models
```

```text
Create wholesale order workflow with bulk orders, customer pricing, credit limits, invoices, and delivery tracking.
Use transactions; prevent orders exceeding approved credit.
Test order, credit, delivery, invoice, and cross-tenant denial.
```
**Commit message:**
```text
feat(wholesale): add orders, credit limits, invoices, and deliveries
```

```text
Create stock transfer workflow between warehouses or branches.
Use transactions, stock movements, and prevent negative stock.
Test success, insufficient stock, duplicate transfer, and cross-tenant denial.
```
**Commit message:**
```text
feat(wholesale): add inter-branch stock transfers
```

### Definition of done
Wholesale customers, orders, invoices, deliveries, transfers, and credit limits work.

## Phase 7 — Schools module
### Goal
Build Schools after Wholesale is stable.

### Copilot prompts and commit messages
```text
Create Schools models: Student, Guardian, FamilyAccount, FeeStructure, FeePayment, FeeAllocation, Statement, and ArrearsReport.
Organisation scope, UUIDs, decimals, constraints.
Do not reuse Retail customer models.
```
**Commit message:**
```text
feat(schools): add students, families, fees, and payments models
```

```text
Create fee payment workflow.
Identify student or family, view balance, record payment, allocate to fee categories, generate receipt.
Use transactions; prevent over-allocation.
Test payment, allocation, statement, arrears, and cross-tenant denial.
```
**Commit message:**
```text
feat(schools): add fee collection and payment allocation
```

```text
Create arrears reporting by class, term, and family.
Add CSV export and Celery payment reminders.
Test arrears calculation, reminders, and tenant isolation.
```
**Commit message:**
```text
feat(schools): add arrears reporting and reminders
```

### Definition of done
Students, families, fees, payments, statements, arrears, and reminders work.

## Phase 8 — Pharmacy module
### Goal
Build Pharmacy after Schools and regulatory review.

### Copilot prompts and commit messages
```text
Create Pharmacy models: Medicine, MedicineBatch, Supplier, Purchase, PurchaseLine, PharmacySale, PharmacySaleLine, and StockAdjustment.
Organisation scope, UUIDs, decimals, constraints.
Do not reuse Retail product or sale models.
```
**Commit message:**
```text
feat(pharmacy): add medicines, batches, and pharmacy sales models
```

```text
Create batch and expiry workflow.
Track batch number, expiry, quantity, and cost.
Prevent expired batch sales.
Create low-stock and expiry alerts.
Test batch selection, expiry validation, stock reduction, duplicate prevention, and tenant isolation.
```
**Commit message:**
```text
feat(pharmacy): add batch tracking and expiry controls
```

```text
Create pharmacy POS workflow.
Search medicines, select batches, complete sales, generate receipts.
Use transactions; prevent expired batch sales.
Test success, expired rejection, insufficient stock, and cross-tenant denial.
```
**Commit message:**
```text
feat(pharmacy): add pharmacy POS and batch-aware sales
```

### Definition of done
Medicines, batches, expiry, suppliers, purchases, sales, and alerts work; regulatory review complete for dispensing.

## Phase 9 — Scale and improvement
### Goal
Improve performance, reliability, and customer experience.

### Copilot prompts and commit messages
```text
Analyse Django codebase for N+1 queries, missing indexes, slow reports, and unnecessary calls.
Do not change business logic.
Suggest safe optimisations with query counts and test coverage.
```
**Commit message:**
```text
perf: identify query and indexing optimisations
```

```text
Create performance tests for catalogue search, checkout, reports, receiving, and concurrent cashiers.
Use realistic staging data.
Report p95 latency, error rate, and query count.
```
**Commit message:**
```text
test(performance): add Retail performance benchmarks
```

```text
Create customer feedback analysis workflow.
Collect pilot feedback, categorise issues, identify recurring problems, propose prioritised improvements.
Do not add features without validated need.
```
**Commit message:**
```text
docs(product): add customer feedback analysis workflow
```

### Definition of done
Performance improves; feedback addressed; system stable; new features validated.
