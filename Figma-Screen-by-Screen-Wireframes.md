# Biashara Pulse — Screen-by-Screen Figma Wireframe Layout
Version: 0.1 | Date: 2026-11-20 | Status: Design specification

This document defines the exact placement of navigation, cards, tables, buttons, and form fields for each Retail MVP screen. Use it with Design.md for colours, typography, and spacing.

## Layout rules
- Mobile: 390 x 844, single column, bottom action bar where needed.
- Tablet: 820 x 1180, two-column layouts where useful.
- Desktop: 1440 x 900, sidebar navigation plus main content.
- Use 16px page padding on mobile, 24px on tablet, 32px on desktop.
- Use 8px spacing scale.
- Primary action button is bottom-right on desktop and fixed bottom on mobile.
- Every screen needs loading, empty, error, success, and permission-denied states.

## Global navigation
### Desktop
Left sidebar 240px wide:
1. Logo: Biashara Pulse
2. Dashboard
3. POS
4. Sales
5. Inventory
6. Customers
7. Suppliers
8. Expenses
9. Reports
10. Settings

Top bar 64px high:
- Left: page title
- Right: organisation selector, notifications icon, user avatar

### Mobile
Top bar 56px high:
- Left: hamburger menu
- Center: page title
- Right: notifications icon

Bottom navigation 64px high:
- Dashboard
- POS
- Stock
- Customers
- More

## 1. Sign up
### Layout
- Centered card, max width 400px.
- Logo at top.
- Heading: Create your account.
- Fields: Full name, Email, Phone, Password, Confirm password.
- Primary button: Create account.
- Secondary link: Already have an account? Log in.

### States
- Loading: button shows spinner.
- Error: field-level messages.
- Success: redirect to organisation creation.

## 2. Log in
### Layout
- Centered card, max width 400px.
- Logo.
- Heading: Welcome back.
- Fields: Email, Password.
- Primary button: Log in.
- Link: Forgot password?

### States
- Invalid credentials: generic error message.
- Locked account: account recovery message.
- Success: redirect to organisation selection.

## 3. Organisation selection
### Layout
- Page title: Choose organisation.
- Card list of organisations.
- Each card: organisation name, sector badge, role, last accessed.
- Primary button: Create new organisation.

### States
- Empty: No organisations yet.
- Loading: skeleton cards.

## 4. Create organisation
### Layout
- Page title: Create organisation.
- Card with fields:
  - Organisation name
  - Business type
  - Sector: Retail, Wholesale, Schools, Pharmacy
  - Country
  - Currency
  - Timezone
- Primary button: Continue.
- Secondary button: Cancel.

### States
- Validation errors under each field.
- Success: sector module enabled.

## 5. Retail dashboard
### Desktop layout
- Sidebar navigation.
- Top bar with page title: Dashboard.
- Row 1: four KPI cards: Today sales, Transactions, Gross margin, Customer debt.
- Row 2: Sales trend chart and Low-stock alerts.
- Row 3: Recent sales table and Quick actions.

### KPI cards
Each card contains:
- Label
- Value
- Trend indicator
- Small icon

### Quick actions
- New sale
- Receive stock
- Add expense
- View reports

### Mobile layout
- Greeting and date.
- KPI cards stacked.
- Quick actions grid.
- Recent sales list.
- Low-stock alerts.

## 6. Product catalogue
### Desktop layout
- Page title: Products.
- Search bar and category filter.
- Primary button: Add product.
- Table columns: Product, SKU, Category, Price, Stock, Status, Actions.

### Row actions
- View
- Edit
- Deactivate

### Mobile layout
- Search bar.
- Filter chips.
- Product cards with name, SKU, price, stock, and actions.

### States
- Empty: No products yet.
- Loading: table skeleton.
- Error: retry button.

## 7. Add / edit product
### Layout
- Page title: Add product or Edit product.
- Form fields:
  - Product name
  - SKU
  - Barcode
  - Category
  - Base unit
  - Selling price
  - Cost price
  - Tax rate
  - Reorder level
  - Status
- Primary button: Save product.
- Secondary button: Cancel.

### States
- Validation errors.
- Duplicate SKU error.
- Success toast.

## 8. POS screen
### Desktop layout
- Left 60%: product search and catalogue grid.
- Right 40%: cart panel.
- Bottom right: Complete Sale button.

### Product search
- Search input with barcode support.
- Category chips.
- Product cards with image placeholder, name, price, stock.

### Cart panel
- Customer selector.
- Cart line items.
- Quantity controls.
- Remove item.
- Subtotal.
- Tax.
- Discount.
- Total.
- Payment method selector.
- Complete Sale button.

### Mobile layout
- Search bar at top.
- Product grid.
- Floating cart button with item count.
- Cart drawer from bottom.
- Complete Sale button fixed at bottom.

### States
- Empty cart.
- Insufficient stock.
- Payment pending.
- Payment failed.
- Successful sale.
- Receipt generated.

## 9. Payment screen
### Layout
- Page title: Payment.
- Order summary.
- Payment method options:
  - Cash
  - M-Pesa
  - Split payment
  - Customer credit
- Amount fields.
- Primary button: Complete Sale.
- Secondary button: Back.

### States
- Cash: received amount and change.
- M-Pesa: phone number and pending status.
- Split: multiple payment rows.
- Credit: customer selector and credit limit warning.

## 10. Receipt screen
### Layout
- Receipt preview card.
- Business name and logo.
- Receipt number and date.
- Cashier and customer.
- Product lines.
- Totals and payment breakdown.
- Actions: Print, Share, Reprint, Done.

### States
- Receipt ready.
- Print failed.
- Reprint available.

## 11. Sales history
### Desktop layout
- Page title: Sales.
- Filters: date range, cashier, payment method, status.
- Table columns: Receipt, Date, Customer, Total, Payment, Status, Actions.
- Row action: View receipt.

### Mobile layout
- Filter button.
- Sale cards with receipt number, date, total, status.

## 12. Customer list
### Desktop layout
- Page title: Customers.
- Search bar.
- Primary button: Add customer.
- Table columns: Name, Phone, Credit limit, Balance, Status, Actions.

### Mobile layout
- Search bar.
- Customer cards with name, phone, balance.

## 13. Customer detail
### Layout
- Customer header with name, phone, credit limit, balance.
- Tabs: Sales, Payments, Statements.
- Primary button: Record collection.

### States
- No outstanding balance.
- Payment pending.
- Over-allocation error.

## 14. Collection screen
### Layout
- Customer selector.
- Amount field.
- Payment method.
- Sale allocation list.
- Primary button: Record payment.

### States
- No outstanding balance.
- Over-allocation error.
- Successful collection.

## 15. Supplier list
### Desktop layout
- Page title: Suppliers.
- Search bar.
- Primary button: Add supplier.
- Table columns: Name, Phone, Products supplied, Last purchase, Actions.

### Mobile layout
- Supplier cards.

## 16. Goods receiving
### Layout
- Page title: Receive stock.
- Supplier selector.
- Receipt reference.
- Product lines:
  - Product
  - Quantity received
  - Unit cost
  - Line total
- Notes.
- Primary button: Post receipt.
- Secondary button: Save draft.

### States
- Empty receipt.
- Invalid quantity.
- Missing supplier.
- Duplicate submission prevented.
- Successful posting.

## 17. Stock list
### Desktop layout
- Page title: Stock.
- Search and branch filter.
- Table columns: Product, SKU, Branch, Quantity, Reorder level, Status, Actions.
- Row action: Adjust stock.

### Mobile layout
- Stock cards with product, quantity, status.

### States
- Low stock badge.
- Out of stock badge.
- Healthy stock badge.

## 18. Stock adjustment
### Layout
- Product selector.
- Branch selector.
- Quantity change.
- Reason.
- Expected stock version.
- Primary button: Submit adjustment.
- Manager approval section.

### States
- Pending approval.
- Approved.
- Rejected.
- Stale version conflict.

## 19. Expense entry
### Layout
- Page title: Add expense.
- Fields:
  - Category
  - Description
  - Amount
  - Payment method
  - Date
  - Notes
- Primary button: Save expense.

### States
- Validation errors.
- Successful save.

## 20. Shift open
### Layout
- Page title: Open shift.
- Cashier name.
- Branch.
- Opening float field.
- Primary button: Open shift.

### States
- Already open shift warning.
- Successful open.

## 21. Shift close
### Layout
- Page title: Close shift.
- Opening float.
- Cash sales.
- Cash collections.
- Cash refunds.
- Cash expenses.
- Expected cash.
- Counted cash field.
- Variance.
- Primary button: Close shift.

### States
- Variance warning.
- Already closed.
- Successful close.

## 22. Reports
### Desktop layout
- Page title: Reports.
- Report type tabs: Sales, Stock, Debt, Expenses, Profit.
- Filters: date range, branch, cashier, payment method.
- Chart or table.
- Export CSV button.

### Mobile layout
- Report type selector.
- Filters.
- Summary cards.
- Export button.

### States
- No data.
- Loading.
- Export ready.
- Permission denied.

## 23. Settings
### Layout
- Page title: Settings.
- Tabs: Organisation, Staff, Roles, Branches, Notifications, Subscription.
- Form fields per tab.
- Primary button: Save changes.

### States
- Validation errors.
- Successful save.
- Permission denied.

## 24. Audit log
### Desktop layout
- Page title: Audit log.
- Filters: date, actor, action, target.
- Table columns: Time, Actor, Action, Target, Reason, Correlation ID.
- Row action: View details.

### Mobile layout
- Filter button.
- Audit event cards.

## 25. Notifications
### Layout
- Page title: Notifications.
- List of notifications with icon, title, message, time.
- Mark as read.
- Filter by type.

### States
- Empty.
- Loading.
- Error.

## Figma build order
1. Create Foundations page.
2. Create global navigation components.
3. Create shared components.
4. Build shared platform screens.
5. Build Retail dashboard.
6. Build POS and payment.
7. Build receipt.
8. Build stock and receiving.
9. Build customers and collections.
10. Build shifts and expenses.
11. Build reports and settings.
12. Create prototype links.
13. Prepare developer handoff.
