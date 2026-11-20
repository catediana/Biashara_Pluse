# Biashara Pulse — Architecture
Version: 0.4 | Date: 2026-11-20

## 1. Architecture approach
Build Biashara Pulse as a modular monolith.

One Django backend contains clearly separated apps for shared platform services and sector modules. A React frontend communicates with the backend through a REST API. PostgreSQL stores persistent business records. Redis and Celery handle background jobs.

Do not start with microservices. Split services later only if real scale, team size, or operational needs justify it.

## 2. High-level architecture
```text
React Frontend
        |
        | HTTPS / REST API
        v
Django REST Framework API
        |
        v
Django Modular Monolith
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
PostgreSQL Database     Redis / Celery          External Integrations
                        Background jobs         M-Pesa, Email, SMS, WhatsApp
```

## 3. Core principles
- Every business record belongs to an organisation.
- Every API request must resolve the active organisation from authenticated membership.
- Every tenant-owned database query must be filtered by organisation.
- Permissions must be enforced in backend services and querysets.
- The frontend may hide actions, but it must never be the only security control.
- Financial and stock operations must use database transactions.
- Sensitive actions must create audit events.
- Sector modules must not depend directly on one another.
- Shared services expose stable internal functions or APIs to sector modules.

## 4. Backend folder structure
```text
backend/
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── testing.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/
│   ├── organisations/
│   ├── rbac/
│   ├── billing/
│   ├── notifications/
│   ├── audit/
│   ├── reporting/
│   ├── integrations/
│   ├── retail/
│   ├── wholesale/
│   ├── schools/
│   └── pharmacy/
├── core/
│   ├── tenancy.py
│   ├── permissions.py
│   ├── exceptions.py
│   ├── pagination.py
│   ├── money.py
│   └── audit.py
└── tests/
```

### App responsibilities
| App | Responsibility |
|---|---|
| accounts | Users, authentication, profiles, sessions |
| organisations | Organisations, branches, memberships, settings |
| rbac | Roles, permissions, role assignments |
| billing | Plans, subscriptions, entitlements, invoices |
| notifications | In-app, email, SMS, and WhatsApp notifications |
| audit | Security and business audit events |
| reporting | Shared reporting services and exports |
| integrations | M-Pesa, email, SMS, WhatsApp, and future integrations |
| retail | Products, sales, stock, suppliers, expenses, shifts |
| wholesale | Customers, orders, pricing, credit, deliveries, transfers |
| schools | Students, guardians, families, fees, payments, statements |
| pharmacy | Medicines, batches, expiry, purchases, sales |

## 5. Frontend folder structure
```text
frontend/
├── public/
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── layout/
│   ├── features/
│   │   ├── auth/
│   │   ├── organisations/
│   │   ├── staff/
│   │   ├── retail/
│   │   ├── wholesale/
│   │   ├── schools/
│   │   └── pharmacy/
│   ├── shared/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── utils/
│   │   └── types/
│   └── styles/
├── tests/
└── package.json
```

### Frontend rules
- Organise code by feature, not only by technical type.
- Keep API calls in a dedicated API layer.
- Use TypeScript types for all API responses and form data.
- Use reusable components from the design system.
- Handle loading, empty, error, success, forbidden, and offline states.
- Do not store authentication secrets in localStorage.
- Do not implement permissions only in the frontend.

## 6. Application flow
### Organisation onboarding
```text
Sign up
  → Verify account
  → Create organisation
  → Select sector
  → Enable relevant module
  → Complete business profile
  → Invite staff
  → Assign roles and branches
  → Start daily operations
```

### Retail sale
```text
Cashier opens shift
  → Searches or scans product
  → Adds product to cart
  → Adjusts quantity
  → Selects customer if credit sale
  → Selects payment method
  → Reviews sale
  → Completes sale
  → System validates stock and permissions
  → System creates sale, receipt, stock movement, and audit event
  → Cashier shares or prints receipt
```

### Stock receiving
```text
Manager or stock clerk selects supplier
  → Adds received products
  → Enters quantities and costs
  → Reviews receipt
  → Posts receipt
  → System updates stock and creates stock movement
  → System records audit event
```

### Customer credit collection
```text
Staff searches customer
  → Views outstanding balance and sales
  → Records payment
  → Allocates payment to sales
  → System updates balance and receipt
  → System records audit event
```

## 7. Figma design and app-flow diagram
Create the actual Figma designs and app-flow diagram from this architecture.

### Figma file structure
1. Foundations
2. User flows
3. Wireframes
4. High-fidelity designs
5. Prototype
6. Developer handoff

### App-flow diagram
```text
User
  → Authentication
  → Organisation selection
  → Role-based dashboard
  → Module workspace

Retail user
  → Retail dashboard
  → POS
  → Sales
  → Stock
  → Customers
  → Suppliers
  → Expenses
  → Reports
  → Settings

Platform admin
  → Organisations
  → Users
  → Subscriptions
  → Audit logs
  → Support access
  → System health
```

Use Figma FigJam, Miro, draw.io, or Excalidraw. Show decision points for permission, stock, payment, credit limit, shift status, and transaction success or failure.

## 8. Technology stack
| Layer | Technology | Responsibility |
|---|---|---|
| Backend | Python + Django | Business logic and platform services |
| API | Django REST Framework | Communication between frontend and backend |
| Database | PostgreSQL | Persistent business records |
| Frontend | React + TypeScript | Interactive user interfaces |
| Styling | Tailwind CSS | Consistent responsive design |
| State and data fetching | React Query or TanStack Query | Server-state management |
| Forms | React Hook Form + Zod | Form validation |
| Background jobs | Celery + Redis | Reminders, reports, notifications, asynchronous jobs |
| Testing | Pytest / Django tests | Backend tests |
| Frontend testing | Vitest + React Testing Library | Frontend tests |
| End-to-end testing | Playwright | Critical user journeys |
| API testing | Postman | Endpoint and integration testing |
| Version control | Git + GitHub | Source history and collaboration |
| Deployment | Docker + cloud hosting | Application deployment |
| Monitoring | Application monitoring and error tracking | Production observability |

## 9. Data and tenancy model
### Core entities
- User
- Organisation
- Branch
- Membership
- Role
- Permission
- Subscription
- AuditEvent
- Notification

### Retail entities
- Product
- Category
- Customer
- Supplier
- StockBalance
- StockMovement
- GoodsReceipt
- Sale
- SaleLine
- Payment
- PaymentAllocation
- Return
- Refund
- Expense
- Shift

### Tenancy rules
1. Every tenant-owned record must include organisation_id.
2. Every query must filter by the active organisation.
3. A user’s permissions are evaluated per organisation membership.
4. A cashier cannot access another organisation’s records.
5. A Super Admin must not have unlimited, invisible access to customer data.
6. Support access must be time-limited, approved, and audited.

## 10. Security architecture
- Use HTTPS everywhere.
- Use secure, HttpOnly session cookies.
- Protect unsafe requests with CSRF protection.
- Rate-limit authentication endpoints.
- Use strong password rules and password reset.
- Consider multi-factor authentication for administrators.
- Use role-based access control.
- Enforce tenant isolation in backend querysets.
- Log sensitive actions.
- Store secrets in environment variables or a secrets manager.
- Never store provider secrets in source code.

## 11. Deployment architecture
```text
GitHub
  → CI/CD pipeline
  → Staging environment
  → QA and security checks
  → Production deployment
  → Monitoring and alerts
```

### Environments
| Environment | Purpose |
|---|---|
| Local | Developer workstations |
| Staging | Pre-production testing |
| Pilot | Controlled customer testing |
| Production | Live customer traffic |

## 12. Operations
- Use managed PostgreSQL backups.
- Use daily backups and test restoration regularly.
- Monitor application errors, latency, database health, background jobs, and payment failures.
- Alert on downtime, elevated errors, failed jobs, backup failures, and suspicious access.
- Maintain an incident-response process.
- Deploy small, reversible changes.
- Maintain rollback plans for releases.
