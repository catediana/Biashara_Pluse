# Biashara Pulse — Development Rules
Version: 0.4 | Date: 2026-11-20

## 1. Purpose
These rules define boundaries, priorities, and non-negotiable standards for building Biashara Pulse. They prevent scope creep, security mistakes, duplicated work, and poor product decisions.

## 2. Product boundaries
### Build first
- Shared platform foundation.
- Retail / Dukas module.
- Core reports.
- Core security and audit logging.
- Pilot-ready onboarding and support tooling.

### Do not build yet
- Wholesale module.
- Schools module.
- Pharmacy module.
- Offline-first synchronisation.
- Multi-branch stock transfers.
- Full accounting or general ledger.
- Payroll and HR.
- Loyalty programmes.
- Native mobile apps.
- Advanced pharmacy dispensing workflows.

### Rule
Do not start a new sector module until the Retail module is validated with real users and the shared platform foundation is stable.

## 3. Security rules
### Always do
- Enforce authentication on every protected endpoint.
- Enforce role-based permissions in the backend.
- Filter every tenant-owned query by organisation.
- Validate permissions before business logic.
- Use database transactions for financial and stock operations.
- Log sensitive actions.
- Use HTTPS everywhere.
- Store secrets in environment variables or a secrets manager.
- Test cross-tenant access denial.
- Test permission boundaries.

### Never do
- Never rely on frontend checks alone for security.
- Never trust a client-supplied organisation ID without authorisation.
- Never expose another organisation’s data.
- Never store provider secrets in source code.
- Never give Super Admin unlimited invisible access to customer data.
- Never allow untested payment or financial logic into production.
- Never delete financial records silently; use reversing or correcting entries.
- Never deploy a migration without reviewing rollback and data impact.

## 4. Data rules
### Always do
- Give every tenant-owned model an organisation_id.
- Use UUID primary keys.
- Use decimal fields for money and quantities.
- Preserve immutable financial records.
- Use snapshots for product name, SKU, unit, price, discount, tax rate, and cost on sale lines.
- Keep stock movements traceable to sales, receipts, returns, or adjustments.
- Preserve audit history.

### Never do
- Never use floating-point numbers for money.
- Never allow negative stock where business rules require nonnegative stock.
- Never overwrite historical sale data.
- Never store a customer balance as the only source of truth; derive it from sales, payments, returns, and refunds.
- Never delete referenced financial or stock records directly.
- Never store raw provider secrets or unnecessary sensitive payloads in logs.

## 5. Engineering rules
### Backend
- Use Django apps with clear responsibilities.
- Keep business rules in service or domain layers.
- Use Django ORM and avoid raw SQL unless necessary.
- Use serializers for API validation.
- Use database transactions for multi-step operations.
- Use select_related and prefetch_related to avoid N+1 queries.
- Write tests for business rules, permissions, and tenant isolation.
- Use type hints where practical.
- Follow PEP 8.

### Frontend
- Use functional React components and hooks.
- Use TypeScript for API responses and form data.
- Keep components small and focused.
- Use reusable UI components.
- Handle loading, empty, error, success, forbidden, and offline states.
- Keep API calls in a dedicated API layer.
- Do not duplicate business logic in the frontend.

### Git
- Use feature branches.
- Use clear commit messages.
- Do not push directly to main.
- Require code review for important changes.
- Include test evidence in pull requests.
- Document database migration impact.
- Tag production releases.

## 6. UX rules
### Always do
- Design for mobile first.
- Keep high-frequency actions within two taps where possible.
- Use clear, simple language.
- Show loading, empty, error, and success states.
- Use accessible colour contrast.
- Provide visible focus states.
- Use descriptive labels for inputs.
- Support keyboard navigation for web interfaces.

### Never do
- Never use technical jargon in customer-facing screens.
- Never rely on colour alone to communicate status.
- Never make destructive actions easy to trigger accidentally.
- Never hide important validation errors.
- Never build a screen without considering empty, loading, error, and success states.

## 7. Quality rules
### Definition of done
A feature is done only when:
- Requirements are implemented.
- Unit, integration, and permission tests pass.
- Tenant isolation tests pass.
- UI works on mobile, tablet, and desktop breakpoints.
- Audit events are generated.
- Documentation is updated.
- No critical or high-severity defects remain open.
- Product owner and QA approval are received.

### Testing priorities
- Cross-tenant access denial.
- Permission boundaries.
- Sale creation and stock reduction.
- Payment allocation and customer balance.
- Return quantity limits.
- Shift reconciliation.
- Stock adjustment approval.
- Audit event creation.
- Invalid input handling.
- Concurrent transaction handling.

## 8. Decision rules
### Before building a feature
Ask:
1. Which user problem does this solve?
2. Which sector module does it belong to?
3. Is it required for the current phase?
4. Does it affect money, permissions, tenant isolation, or data deletion?
5. What are the acceptance criteria?
6. What tests are required?
7. What could fail in production?
8. What is the rollback plan?

### When a decision is made
Record it in Memory.md with date, decision, reason, alternatives, owner, impact, and status.

## 9. Communication rules
- Use one shared project memory document.
- Keep the task tracker updated.
- Record risks early.
- Do not make silent architectural changes.
- Do not change scope without recording the decision.
- Do not assume a business rule; confirm it with the product owner or target user.
- Do not claim compliance, security, or performance without evidence.

## 10. Prohibited shortcuts
Do not:
- Build all four sectors at once.
- Copy-paste sector logic instead of creating reusable shared services.
- Use generic models where sector-specific concepts are required.
- Store student records as generic customers.
- Store medicine batches as generic stock items.
- Use frontend-only permission checks.
- Skip tests for financial or security-critical code.
- Deploy unreviewed database migrations.
- Use hardcoded secrets.
- Ignore accessibility.
- Ship features without acceptance criteria.
