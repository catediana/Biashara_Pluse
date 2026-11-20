# Biashara Pulse — Product Requirements Document
Version: 0.4 | Date: 2026-11-20 | Status: Working draft

## 1. What we are building
Biashara Pulse is a modular, multi-tenant business-management web platform for small and growing organisations in Kenya. It gives each organisation a secure workspace to manage daily operations, records, staff, transactions, inventory, customers, payments, and reports.

The product has one shared platform foundation and separate sector modules:

| Module | Main interface | Core work |
|---|---|---|
| Retail / Dukas | Retail POS | Sales, stock, suppliers, expenses, customer credit, receipts |
| Wholesale / Distribution | Wholesale sales terminal | Bulk orders, customer pricing, credit, invoices, deliveries |
| Schools | Fee collection interface | Students, families, fees, payments, statements, arrears |
| Pharmacy / Chemist | Pharmacy POS | Medicines, batches, expiry, purchases, sales, alerts |

For the first release, build the shared platform foundation and the Retail / Dukas module. Do not build all four sectors at once.

## 2. Who we are building for
- Shop owners and managers who need visibility into sales, stock, expenses, profit, and customer debt.
- Cashiers who need a fast, simple way to record sales and issue receipts.
- Stock clerks who receive goods, count stock, and request adjustments.
- Wholesale managers who manage customers, orders, credit, deliveries, and stock.
- School administrators and bursars who manage students, guardians, fees, payments, and arrears.
- Pharmacy owners and attendants who manage medicines, batches, expiry dates, suppliers, and sales.
- Platform administrators who manage organisations, subscriptions, support, and system health.

## 3. Problems to solve
- Sales, stock, expenses, and customer balances are recorded in separate places.
- Owners cannot easily see daily performance, profit, low stock, or outstanding debt.
- Cashiers need a fast checkout process that reduces mistakes.
- Businesses need clear records of who changed what and when.
- Generic software does not match sector-specific workflows.
- Multiple businesses must not be able to see one another’s private data.

## 4. Product goals
1. Let an organisation create its workspace, invite staff, assign roles, and operate securely.
2. Let a retail business sell products, manage stock, record expenses, track customer credit, and view reports.
3. Keep every organisation’s data isolated from every other organisation.
4. Make important actions traceable through audit logs.
5. Make the product simple enough for non-technical staff to use with little training.
6. Validate the Retail module with real users before adding other sectors.

## 5. MVP scope
### Shared platform
- User registration, login, logout, password reset, and session management.
- Organisation creation and sector selection.
- Staff invitations, memberships, roles, and permissions.
- Organisation settings and profile.
- Subscription status and module entitlements.
- Audit logging for sensitive actions.
- Notifications foundation.
- Basic platform administration and support tooling.

### Retail / Dukas module
- Product catalogue with categories, SKU, barcode, price, cost, tax rate, and active status.
- Retail POS with product search and barcode support.
- Cash, M-Pesa, split-payment, and customer-credit sales.
- Receipt creation, reprinting, and export.
- Customer records, credit limits, balances, statements, and collections.
- Supplier records and goods receiving.
- Stock balances, stock movements, stock counts, and reason-coded adjustments.
- Low-stock alerts.
- Cashier shifts, opening float, cash reconciliation, and variance review.
- Expenses and cash payouts.
- Sales, stock, debt, expense, and profit reports.
- CSV export for authorised users.

## 6. Explicit exclusions for MVP
- Offline sales and background synchronisation.
- Multi-branch stock transfers.
- Supplier accounts payable and purchase-order approvals.
- Full accounting or general-ledger functionality.
- Payroll and HR.
- Loyalty programmes.
- Native mobile applications.
- Full pharmacy dispensing or prescription workflows.
- Wholesale, Schools, and Pharmacy modules before Retail is validated.

## 7. Functional requirements
### Organisation and access
- A user may belong to more than one organisation.
- Each organisation has one sector and its own staff, roles, settings, and records.
- A user must select an active organisation before accessing business data.
- Permissions must be enforced in the backend, not only in the user interface.
- A cashier must not access another organisation’s sales, products, customers, or reports.
- Sensitive actions must be logged with actor, action, target, timestamp, and reason where applicable.

### Retail sales
- A cashier can search products by name, SKU, or barcode.
- A cashier can add products to a sale, change quantity, and review the order.
- A cashier can record cash, M-Pesa, split payment, or customer credit.
- A sale must create a receipt and reduce available stock.
- A credit sale must create or update a customer balance.
- A collection must reduce the correct customer balance and allocate to the correct sale.
- A return must reference the original sale and cannot return more than the remaining sold quantity.
- A posted sale cannot be edited or deleted; corrections require a separate auditable workflow.

### Inventory
- A stock clerk can receive stock from a supplier.
- A stock clerk can request a stock adjustment, subject to approval.
- A manager can approve stock adjustments and record the reason.
- The system must prevent negative stock.
- Stock movements must be traceable to sales, receipts, returns, or adjustments.
- Low-stock alerts must identify products below their reorder level.

### Shifts and cash control
- A cashier opens a shift with an opening cash float.
- A cashier closes a shift by recording counted cash.
- The system calculates expected cash, counted cash, and variance.
- A closed shift must not accept new sales or payments.
- Managers can review shift variances and supporting records.

### Reporting
- Owners and authorised managers can view sales, tax, net revenue, expenses, gross margin, customer debt, and stock reports.
- Reports must support date-range and branch filters.
- Reports must distinguish gross sales, returns, net revenue, and pending refunds.
- Reports must not present estimated figures as final accounting profit.

## 8. Non-functional requirements
| Area | Requirement |
|---|---|
| Security | Enforce authentication, role-based permissions, tenant isolation, and audit trails |
| Data integrity | Use database transactions for sales, stock, payments, returns, and fee allocations |
| Usability | Make core workflows usable by non-technical staff with minimal training |
| Responsiveness | Support mobile, tablet, and desktop layouts |
| Performance | Common POS actions should respond within 2 seconds under normal conditions |
| Availability | Target 99.5% monthly availability for the MVP |
| Accessibility | Follow WCAG 2.2 AA principles where practical |
| Auditability | Record critical create, update, delete, login, permission, and payment events |

## 9. Success measures
- Number of activated organisations.
- Weekly active organisations.
- Number of transactions recorded per organisation.
- Trial-to-paid conversion rate.
- 30-day organisation retention.
- Support tickets per active organisation.
- Number of critical security incidents: target zero.
- Percentage of pilot shops using the system on at least four trading days per week.

## 10. Open decisions
- Exact M-Pesa integration method, refund process, and reconciliation workflow.
- Applicable tax and fiscalisation requirements.
- Receipt format and printer compatibility.
- Customer-data retention and deletion policy.
- Credit-limit override rules.
- Support-access approval process.
- English and Swahili language priorities.
