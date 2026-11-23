# Biashara Pulse — Development Phases
Version: 1.0 | Date: 2026-11-20  URL: http://127.0.0.1:8000/admin/login/
Email/username: local-admin@example.test
Password: Cc87GUt50U0e_5OaGO1hyZJcUryVtjpv

This file contains four implementation tracks: Backend, Frontend, QA and Security, and Deployment.
Follow the phases in order. After each Copilot prompt, use the commit message shown beneath it.

## How to use
1. Build Backend Phase.
2. Build matching Frontend Phase.
3. Run QA and Security Phase.
4. Deploy when ready.
5. Move to next phase.

# Backend Implementation Phases

## Backend Phase 1 — Project setup
### Goal
Set up Django project, PostgreSQL, Redis, Celery, and project structure.

### Tasks
- Create Django project
- Create apps
- Set up settings
- Connect PostgreSQL
- Set up Redis and Celery
- Create requirements files

### Copilot prompt
```text
Create a Django 5 project named backend for Biashara Pulse.
Use a modular monolith with config and apps folders.
Create apps: accounts, organisations, rbac, billing, notifications, audit, reporting, integrations, retail, wholesale, schools, pharmacy.
Create core utilities for tenancy, permissions, exceptions, pagination, money, and audit.
Use PostgreSQL, Redis, Celery, and Django REST Framework.
Create base, development, testing, and production settings.
Do not create sector models yet.
```

### Commit message
```text
chore: set up Django project structure and settings
```

### Definition of done
- Django project runs
- PostgreSQL connects
- Redis connects
- Celery worker runs
- Settings are organised

## Backend Phase 2 — Authentication and users
### Goal
Build user registration, login, logout, password reset, and session management.

### Tasks
- Create User model
- Create authentication APIs
- Add password reset
- Add session management
- Add rate limiting

### Copilot prompt
```text
Create Django REST Framework authentication endpoints: register, login, logout, password reset request, password reset confirm, current user, and session refresh.
Use secure session cookies, CSRF protection, rate limiting, and password validation.
Do not store tokens in localStorage.
```

### Commit message
```text
feat(auth): add secure authentication and session endpoints
```

### Definition of done
- Users can register
- Users can log in
- Users can reset password
- Sessions are secure

## Backend Phase 3 — Organisations, branches, roles
### Goal
Build organisations, branches, memberships, roles, permissions, and tenant isolation.

### Tasks
- Create Organisation model
- Create Branch model
- Create Membership model
- Create Role and Permission models
- Create tenant-scoped querysets
- Create permission classes

### Copilot prompt
```text
Create Django models for Organisation, Branch, Membership, Role, Permission, RolePermission, and BranchGrant.
Every tenant-owned model must have organisation_id.
Create reusable tenant-scoped queryset and manager.
Create permission classes that check membership, role permissions, branch access, and module entitlement.
Write cross-tenant denial tests.
```

### Commit message
```text
feat(platform): add organisations, roles, permissions, and tenant isolation
```

### Definition of done
- Organisations can be created
- Staff can be invited
- Roles and permissions work
- Tenant isolation is enforced

## Backend Phase 4 — Retail catalogue and stock
### Goal
Build products, categories, suppliers, stock balances, stock movements, goods receiving, and adjustments.

### Tasks
- Create Product model
- Create Category model
- Create Supplier model
- Create StockBalance model
- Create StockMovement model
- Create GoodsReceipt model
- Create StockAdjustment model

### Copilot prompt
```text
Create Retail models: Category, Product, Supplier, StockBalance, StockMovement, GoodsReceipt, GoodsReceiptLine, and StockAdjustment.
Every model must be organisation-scoped.
Use UUIDs, decimal money and quantity fields, and indexes.
Create product catalogue API, goods receiving workflow, and stock adjustment workflow.
Use database transactions and idempotency keys.
Write tests for duplicate submission, invalid quantity, and cross-tenant denial.
```

### Commit message
```text
feat(retail): add catalogue, stock, receiving, and adjustments
```

### Definition of done
- Products can be managed
- Stock can be received
- Stock adjustments work
- Stock movements are traceable

## Backend Phase 5 — Retail POS and sales
### Goal
Build sales, sale lines, receipts, and checkout.

### Tasks
- Create Sale model
- Create SaleLine model
- Create receipt logic
- Create checkout API
- Add stock reduction

### Copilot prompt
```text
Create Retail sales models: Sale, SaleLine, and receipt logic.
Create checkout API that validates permissions, branch, shift, stock, and payment method.
Use one database transaction and idempotency key.
Create sale, lines, stock movements, receipt, and audit event atomically.
Test success, insufficient stock, concurrency, duplicate key, and cross-tenant denial.
```

### Commit message
```text
feat(retail): add POS checkout, sales, and receipts
```

### Definition of done
- Sales can be created
- Stock reduces correctly
- Receipts are generated
- Checkout is atomic

## Backend Phase 6 — Payments, credit, returns
### Goal
Build payments, customer credit, collections, returns, and refunds.

### Tasks
- Create Payment model
- Create PaymentAllocation model
- Create Customer model
- Create Return model
- Create Refund model

### Copilot prompt
```text
Create payment handling for cash, M-Pesa, split payment, and customer credit.
Create payment allocation, customer collection, return, and refund workflows.
Use database transactions.
Prevent over-allocation and excessive returns.
Test pending payment, confirmed payment, duplicate provider event, invalid allocation, and cross-tenant denial.
```

### Commit message
```text
feat(retail): add payments, credit, collections, returns, and refunds
```

### Definition of done
- Payments work
- Credit works
- Collections work
- Returns and refunds work

## Backend Phase 7 — Shifts, expenses, reports
### Goal
Build shifts, cash reconciliation, expenses, reports, and exports.

### Tasks
- Create Shift model
- Create Expense model
- Create report APIs
- Create CSV export

### Copilot prompt
```text
Create cashier shift workflow, expense management, and reporting endpoints.
Calculate expected cash, counted cash, and variance.
Create sales summary, stock report, customer debt report, expense report, and profit report.
Support date and branch filters, pagination, and CSV export.
```

### Commit message
```text
feat(retail): add shifts, expenses, reports, and exports
```

### Definition of done
- Shifts work
- Expenses work
- Reports work
- CSV export works

## Backend Phase 8 — Integrations and background jobs
### Goal
Build M-Pesa, email, SMS, WhatsApp, and Celery tasks.

### Tasks
- Create integration services
- Create Celery tasks
- Add notifications
- Add M-Pesa integration

### Copilot prompt
```text
Create integration services for M-Pesa, email, SMS, and WhatsApp.
Create Celery tasks for notifications, reminders, and reports.
Use environment variables for secrets.
Make tasks idempotent and retry-safe.
```

### Commit message
```text
feat(integrations): add M-Pesa, notifications, and background jobs
```

### Definition of done
- Integrations work
- Background jobs work
- Notifications work

# Frontend Implementation Phases

## Frontend Phase 1 — Project setup
### Goal
Set up React, TypeScript, Tailwind, routing, and API client.

### Tasks
- Create React project
- Set up Tailwind
- Set up routing
- Create API client
- Create layout

### Copilot prompt
```text
Create a React + TypeScript + Vite project named frontend.
Use Tailwind CSS, React Router, TanStack Query, React Hook Form, Zod, Vitest, and React Testing Library.
Create app, features, shared, styles, and tests folders.
Create API client, auth provider, organisation provider, and layout components.
```

### Commit message
```text
chore: set up React TypeScript frontend structure
```

### Definition of done
- React project runs
- Tailwind works
- Routing works
- API client works

## Frontend Phase 2 — Authentication and layout
### Goal
Build login, signup, password reset, and layout.

### Tasks
- Create login page
- Create signup page
- Create password reset pages
- Create layout

### Copilot prompt
```text
Create authentication pages: login, signup, forgot password, reset password.
Create layout with sidebar and top bar.
Connect to backend authentication APIs.
Handle loading, error, and success states.
```

### Commit message
```text
feat(auth): add authentication pages and layout
```

### Definition of done
- Login works
- Signup works
- Password reset works
- Layout works

## Frontend Phase 3 — Organisation and staff
### Goal
Build organisation selection, creation, staff, roles.

### Tasks
- Create organisation selection
- Create organisation creation
- Create staff management
- Create roles management

### Copilot prompt
```text
Create organisation selection, organisation creation, staff management, and roles management pages.
Connect to backend APIs.
Handle loading, empty, error, and success states.
```

### Commit message
```text
feat(organisations): add organisation and staff management
```

### Definition of done
- Organisation selection works
- Organisation creation works
- Staff management works
- Roles management works

## Frontend Phase 4 — Retail dashboard
### Goal
Build retail dashboard with KPIs and quick actions.

### Tasks
- Create dashboard page
- Create KPI cards
- Create charts
- Create quick actions

### Copilot prompt
```text
Create retail dashboard with KPI cards, sales trend chart, low-stock alerts, recent sales, and quick actions.
Connect to backend reporting APIs.
Handle loading, empty, error, and success states.
```

### Commit message
```text
feat(retail): add dashboard with KPIs and quick actions
```

### Definition of done
- Dashboard works
- KPIs work
- Charts work
- Quick actions work

## Frontend Phase 5 — Product catalogue
### Goal
Build product list, add product, edit product.

### Tasks
- Create product list
- Create add product
- Create edit product
- Create category filter

### Copilot prompt
```text
Create product catalogue pages: list, add, edit, deactivate.
Connect to backend product APIs.
Handle loading, empty, error, and success states.
```

### Commit message
```text
feat(retail): add product catalogue pages
```

### Definition of done
- Product list works
- Add product works
- Edit product works
- Category filter works

## Frontend Phase 6 — POS and cart
### Goal
Build POS screen, cart, and checkout.

### Tasks
- Create POS screen
- Create product search
- Create cart
- Create checkout

### Copilot prompt
```text
Create POS screen with product search, product grid, cart, quantity controls, totals, and checkout.
Connect to backend checkout API.
Handle loading, empty, error, and success states.
```

### Commit message
```text
feat(retail): add POS screen and cart
```

### Definition of done
- POS works
- Cart works
- Checkout works

## Frontend Phase 7 — Payments and receipts
### Goal
Build payment screen and receipt screen.

### Tasks
- Create payment screen
- Create receipt screen
- Create reprint

### Copilot prompt
```text
Create payment screen with cash, M-Pesa, split payment, and customer credit.
Create receipt screen with print, share, reprint.
Connect to backend payment and receipt APIs.
Handle loading, error, and success states.
```

### Commit message
```text
feat(retail): add payment and receipt screens
```

### Definition of done
- Payment works
- Receipt works
- Reprint works

## Frontend Phase 8 — Reports and settings
### Goal
Build reports, settings, audit log.

### Tasks
- Create reports page
- Create settings page
- Create audit log page

### Copilot prompt
```text
Create reports page with filters and CSV export.
Create settings page with organisation, staff, roles, branches, notifications, subscription.
Create audit log page with filters and details.
Connect to backend APIs.
```

### Commit message
```text
feat(platform): add reports, settings, and audit log
```

### Definition of done
- Reports work
- Settings work
- Audit log works

# QA and Security Phases

## QA Phase 1 — Test setup
### Goal
Set up backend and frontend testing.

### Tasks
- Set up Pytest
- Set up Vitest
- Set up Playwright
- Create test folders

### Copilot prompt
```text
Set up Pytest, Vitest, and Playwright for Biashara Pulse.
Create test folders and example tests.
Ensure tests run in CI.
```

### Commit message
```text
chore: set up testing tools and folders
```

### Definition of done
- Pytest works
- Vitest works
- Playwright works

## QA Phase 2 — Backend tests
### Goal
Write backend unit and API tests.

### Tasks
- Test authentication
- Test organisations
- Test retail catalogue
- Test sales
- Test payments

### Copilot prompt
```text
Write backend unit and API tests for authentication, organisations, retail catalogue, sales, payments, returns, shifts, and reports.
Include happy path, invalid input, permission denial, and cross-tenant denial.
```

### Commit message
```text
test(backend): add unit and API tests
```

### Definition of done
- Backend tests pass
- API tests pass
- Permission tests pass

## QA Phase 3 — Frontend tests
### Goal
Write frontend component and end-to-end tests.

### Tasks
- Test login
- Test dashboard
- Test POS
- Test checkout

### Copilot prompt
```text
Write frontend component tests and Playwright end-to-end tests for login, dashboard, POS, checkout, receipt, stock, and reports.
Include loading, empty, error, and success states.
```

### Commit message
```text
test(frontend): add component and end-to-end tests
```

### Definition of done
- Frontend tests pass
- E2E tests pass

## QA Phase 4 — Security and tenant isolation
### Goal
Test permissions and tenant isolation.

### Tasks
- Test cross-tenant access
- Test privilege escalation
- Test CSRF
- Test rate limiting

### Copilot prompt
```text
Create security tests for unauthenticated access, revoked membership, wrong branch, foreign tenant access, privilege escalation, invalid CSRF, rate limiting, and sensitive data exposure.
```

### Commit message
```text
test(security): add tenant isolation and permission tests
```

### Definition of done
- Security tests pass
- Tenant isolation tests pass

## QA Phase 5 — Release readiness
### Goal
Prepare release checklist.

### Tasks
- Review acceptance criteria
- Review security
- Review performance
- Prepare release notes

### Copilot prompt
```text
Create release checklist for Biashara Pulse.
Include acceptance criteria, security review, performance review, backup verification, rollback plan, and release notes.
```

### Commit message
```text
docs: add release checklist
```

### Definition of done
- Release checklist ready
- Security reviewed
- Performance reviewed

# Deployment Phases

## Deployment Phase 1 — Local environment
### Goal
Set up local Docker environment.

### Tasks
- Create Dockerfile
- Create docker-compose
- Set up env variables

### Copilot prompt
```text
Create Dockerfile and docker-compose for Django backend, PostgreSQL, Redis, Celery worker, and React frontend.
Use environment variables for secrets.
Create .env.example without real secrets.
```

### Commit message
```text
chore: add Docker and local environment setup
```

### Definition of done
- Docker works
- Local environment runs

## Deployment Phase 2 — CI/CD
### Goal
Set up GitHub Actions.

### Tasks
- Create CI workflow
- Run tests
- Build Docker image

### Copilot prompt
```text
Create GitHub Actions CI workflow for backend linting, Django tests, frontend linting, TypeScript checks, and frontend tests.
Use PostgreSQL and Redis services.
Do not deploy to production automatically.
```

### Commit message
```text
ci: add backend and frontend CI workflow
```

### Definition of done
- CI runs
- Tests pass
- Docker image builds

## Deployment Phase 3 — Staging
### Goal
Deploy to staging.

### Tasks
- Create staging environment
- Deploy backend
- Deploy frontend
- Run smoke tests

### Copilot prompt
```text
Create staging deployment configuration for Biashara Pulse.
Deploy backend and frontend.
Run smoke tests after deployment.
```

### Commit message
```text
chore: add staging deployment
```

### Definition of done
- Staging works
- Smoke tests pass

## Deployment Phase 4 — Production
### Goal
Deploy to production.

### Tasks
- Create production environment
- Deploy backend
- Deploy frontend
- Run post-deployment checks

### Copilot prompt
```text
Create production deployment configuration for Biashara Pulse.
Deploy backend and frontend.
Run post-deployment checks.
```

### Commit message
```text
chore: add production deployment
```

### Definition of done
- Production works
- Post-deployment checks pass

## Deployment Phase 5 — Monitoring and backups
### Goal
Set up monitoring and backups.

### Tasks
- Set up monitoring
- Set up alerts
- Set up backups
- Test recovery

### Copilot prompt
```text
Set up monitoring, alerts, backups, and recovery testing for Biashara Pulse.
Monitor application errors, latency, database health, background jobs, and payment failures.
```

### Commit message
```text
chore: add monitoring, alerts, and backups
```

### Definition of done
- Monitoring works
- Alerts work
- Backups work
- Recovery tested
