# Biashara Pulse — Figma App Flow and Wireframe Specification
Version: 0.1 | Date: 2026-11-20

## 1. Purpose
Use this document to create the actual Figma designs and app-flow diagram for Biashara Pulse. It defines screens, flows, states, components, and developer handoff requirements for the Retail-first MVP.

## 2. Design sources
- Use Design.md for colours, typography, spacing, themes, and components.
- Use PRD.md for product scope and features.
- Use Architecture.md for technical structure and app flow.

## 3. Figma file structure
Create one Figma file named Biashara Pulse — Product Design.

Use these pages:
1. Cover
2. Foundations
3. User flows
4. Wireframes
5. High-fidelity designs
6. Prototype
7. Developer handoff

## 4. App-flow diagram
Create the diagram in Figma FigJam, Miro, draw.io, or Excalidraw.

### Main platform flow
```text
Start
  → Sign up / Log in
  → Verify account
  → Select or create organisation
  → Choose sector
  → Role-based dashboard
  → Module workspace
```

### Retail user flow
```text
Retail dashboard
  → POS
  → Sales history
  → Stock
  → Customers
  → Suppliers
  → Expenses
  → Reports
  → Settings
```

### Checkout flow
```text
Open shift
  → Search / scan product
  → Add to cart
  → Adjust quantity
  → Add customer if credit sale
  → Review sale
  → Select payment method
  → Complete sale
  → Check stock and permissions
  → Create receipt
  → Share or print receipt
```

### Decision points
Include:
- Does the user have permission?
- Is the shift open?
- Is the product in stock?
- Is the payment confirmed?
- Is the customer within credit limit?
- Did the transaction succeed?
- Did the receipt print or send successfully?

### Diagram style
- Use rectangles for screens.
- Use diamonds for decisions.
- Use arrows for user movement.
- Use colour for success, error, and permission paths.
- Label every decision with Yes / No.
- Include error and recovery paths.

## 5. Screen inventory
### Shared platform screens
| Screen | Purpose | Primary user |
|---|---|---|
| Sign up | Create account | New user |
| Log in | Access platform | Existing user |
| Forgot password | Request reset | Existing user |
| Reset password | Set new password | Existing user |
| Organisation selection | Choose active organisation | User with multiple organisations |
| Create organisation | Create business workspace | New owner |
| Sector selection | Choose Retail, Wholesale, Schools, or Pharmacy | Organisation owner |
| Dashboard | Business overview | Owner / manager |
| Staff | Manage team members | Owner / manager |
| Roles and permissions | Manage access | Owner |
| Settings | Organisation settings | Owner |
| Notifications | View alerts | Permitted users |
| Audit log | View sensitive action history | Owner / authorised manager |

### Retail screens
| Screen | Purpose | Primary user |
|---|---|---|
| Retail dashboard | Daily sales, stock, debt, alerts | Owner / manager |
| Product catalogue | Manage products | Owner / manager |
| Product detail | View or edit product | Owner / manager |
| POS | Complete sales | Cashier |
| Cart | Review selected products | Cashier |
| Payment | Choose payment method | Cashier |
| Receipt | View or reprint receipt | Cashier |
| Sales history | View past sales | Owner / manager |
| Sale detail | View sale and receipt | Owner / manager |
| Customer list | Manage customers | Owner / manager |
| Customer detail | View balance and statement | Owner / manager |
| Collection | Record customer payment | Owner / manager |
| Supplier list | Manage suppliers | Owner / manager |
| Goods receiving | Record received stock | Manager / stock clerk |
| Stock list | View stock levels | Owner / manager |
| Stock adjustment | Request or approve adjustment | Manager / stock clerk |
| Stock count | Record counted stock | Manager / stock clerk |
| Expense entry | Record business expense | Owner / manager |
| Shift open | Start cashier shift | Cashier |
| Shift close | Reconcile cash | Cashier |
| Reports | View business performance | Owner / manager |

## 6. Wireframe standards
Create these layouts for every screen:
- Mobile: 390 x 844
- Tablet: 820 x 1180
- Desktop: 1440 x 900

Include:
- Empty state
- Loading state
- Error state
- Success state
- Permission-denied state
- Offline or connectivity warning where relevant

## 7. Key screen specifications
### Retail dashboard
Show:
- Today’s sales
- Today’s transactions
- Gross sales
- Net revenue
- Expenses
- Gross margin
- Customer debt
- Low-stock alerts
- Recent sales
- Quick actions: New sale, Receive stock, Add expense, View reports

States:
- Empty: No sales recorded yet.
- Loading: skeleton cards.
- Error: Could not load dashboard. Try again.
- Permission denied: You do not have access to this report.

### POS screen
Layout:
- Left: product search and catalogue
- Right: cart, totals, checkout
- Bottom: payment actions

Show:
- Product name
- SKU or barcode
- Available stock
- Quantity
- Unit price
- Line total
- Cart subtotal
- Tax
- Discount
- Total
- Payment method
- Complete Sale button

States:
- Empty cart
- Product not found
- Insufficient stock
- Payment pending
- Payment failed
- Successful sale
- Receipt generated

### Receipt screen
Show:
- Business name
- Receipt number
- Date and time
- Cashier name
- Customer name if applicable
- Product lines
- Quantity
- Unit price
- Line total
- Tax
- Discount
- Total
- Payment breakdown
- Change
- Print / Share / Reprint actions

### Stock receiving screen
Show:
- Supplier
- Receipt reference
- Product lines
- Quantity received
- Unit cost
- Total cost
- Notes
- Save draft
- Post receipt

States:
- Empty receipt
- Invalid quantity
- Missing supplier
- Successful posting
- Duplicate submission prevented

### Customer credit screen
Show:
- Customer name
- Phone
- Credit limit
- Outstanding balance
- Sales history
- Payment history
- Record collection
- Allocate payment

States:
- No outstanding balance
- Payment pending
- Payment confirmed
- Over-allocation error
- Successful collection

### Shift close screen
Show:
- Opening float
- Cash sales
- Cash collections
- Cash refunds
- Cash expenses
- Expected cash
- Counted cash
- Variance
- Close shift button

States:
- Open shift
- Already closed
- Variance warning
- Successful close

## 8. Component library
Create reusable components:
- Button: primary, secondary, danger, ghost, disabled, loading
- Input: text, number, search, select, date, file
- Card
- Table
- Tabs
- Badge
- Modal
- Drawer
- Toast
- Empty state
- Skeleton loader
- Error state
- Confirmation dialog
- Product card
- Cart line item
- Receipt preview
- Stock badge
- Payment method selector

## 9. Accessibility
- Maintain sufficient colour contrast.
- Do not rely on colour alone.
- Provide visible focus states.
- Use descriptive labels.
- Support keyboard navigation.
- Use large touch targets.
- Provide alt text for meaningful images.
- Test with screen readers where possible.

## 10. Developer handoff
For every screen, provide:
- Component names
- Colour tokens
- Typography styles
- Spacing values
- Interaction notes
- Empty, loading, error, and success states
- Permission rules
- Mobile adaptation notes
- Developer notes

## 11. Design approval checklist
- All MVP screens designed
- Mobile, tablet, and desktop layouts created
- All states included
- Accessibility checked
- Design system applied
- Prototype created
- Developer handoff ready
