# Biashara Pulse — Project Memory
Version: 0.4 | Date: 2026-11-20

## 1. Project identity
- Product name: Biashara Pulse
- Product type: Modular multi-tenant business-management platform
- Parent platform: Biashara Pulse shared foundation
- Sector divisions: Retail / Dukas, Wholesale / Distribution, Schools, Pharmacy / Chemist
- First sector to build: Retail / Dukas
- Primary market: Kenya
- Primary users: Shop owners, cashiers, stock clerks, wholesale managers, school administrators, pharmacy owners, platform administrators

## 2. Core product decision
Biashara Pulse is the parent platform. The four sector products operate as business divisions or modules under it.

Each division may have its own POS or transaction-processing interface, but all divisions use the same shared platform foundation.

Do not build four completely independent POS systems and connect them later. Build shared services once and reuse them.

## 3. Shared platform services
- Authentication
- Organisations
- Branches
- Memberships
- Roles and permissions
- Subscriptions
- Audit logs
- Notifications
- Reporting infrastructure
- Integrations
- Background jobs

## 4. Sector module boundaries
| Module | Transaction interface | Core work |
|---|---|---|
| Retail / Dukas | Retail POS | Sales, stock, suppliers, expenses, customer credit, receipts |
| Wholesale / Distribution | Wholesale sales terminal | Bulk orders, customer pricing, credit, invoices, deliveries |
| Schools | Fee collection interface | Students, families, fees, allocations, arrears |
| Pharmacy / Chemist | Pharmacy POS | Medicines, batches, expiry, purchases, sales |

## 5. Technology decisions
| Decision | Choice | Reason |
|---|---|---|
| Backend | Python + Django | Strong business-logic and admin ecosystem |
| API | Django REST Framework | Clear API layer |
| Database | PostgreSQL | Reliable relational database |
| Frontend | React + TypeScript | Type-safe interactive UI |
| Styling | Tailwind CSS | Consistent responsive design |
| Background jobs | Celery + Redis | Asynchronous tasks |
| Testing | Pytest / Django tests | Backend testing |
| Frontend testing | Vitest + React Testing Library | Component testing |
| End-to-end testing | Playwright | Critical user journeys |
| Version control | Git + GitHub | Collaboration and source history |
| Deployment | Docker + cloud hosting | Portable deployment |
| Architecture | Modular monolith | Simpler to build, test, secure, maintain initially |

## 6. Important architecture decisions
| Date | Decision | Reason | Status |
|---|---|---|---|
| 2026-11-20 | Build a modular monolith first | Faster delivery, simpler testing, easier security and maintenance | Approved for MVP |
| 2026-11-20 | Use organisation-based multi-tenancy | Multiple businesses need isolated data | Approved for MVP |
| 2026-11-20 | Build Retail first | Clear transactional workflow and faster validation | Approved for MVP |
| 2026-11-20 | Keep sector domain models separate | Retail, schools, pharmacy have different business concepts | Approved for MVP |
| 2026-11-20 | Enforce permissions in backend | Frontend controls can be bypassed | Approved for MVP |
| 2026-11-20 | Use PostgreSQL | Reliable relational database | Approved for MVP |
| 2026-11-20 | Use React + TypeScript | Type-safe frontend | Approved for MVP |
| 2026-11-20 | Use Tailwind CSS | Consistent styling | Approved for MVP |
| 2026-11-20 | Use Celery + Redis | Background jobs and notifications | Approved for MVP |

## 7. Important product decisions
| Date | Decision | Reason | Status |
|---|---|---|---|
| 2026-11-20 | Retail is the first sector | Clear workflow and faster validation | Approved |
| 2026-11-20 | Do not build all four sectors at once | Reduces risk and scope creep | Approved |
| 2026-11-20 | Retail MVP excludes offline synchronisation | Reduces initial complexity | Approved |
| 2026-11-20 | Retail MVP excludes multi-branch transfers | Reduces initial complexity | Approved |
| 2026-11-20 | Retail MVP excludes full accounting | Reduces initial complexity | Approved |
| 2026-11-20 | Retail MVP excludes payroll and HR | Not core to first release | Approved |
| 2026-11-20 | Pharmacy dispensing workflows require regulatory review | Compliance risk | Pending review |

## 8. Security decisions
| Date | Decision | Reason | Status |
|---|---|---|---|
| 2026-11-20 | Enforce tenant isolation in backend | Frontend checks are not sufficient | Approved |
| 2026-11-20 | Use role-based access control | Least privilege and auditability | Approved |
| 2026-11-20 | Log sensitive actions | Traceability and accountability | Approved |
| 2026-11-20 | Use controlled support access | Prevent unlimited invisible access | Approved |
| 2026-11-20 | Use HTTPS everywhere | Protect data in transit | Approved |
| 2026-11-20 | Store secrets outside source code | Security best practice | Approved |

## 9. Current project status
| Area | Status | Completion |
|---|---|---:|
| Product strategy | Defined | 90% |
| Product requirements | Defined | 85% |
| Retail PRD | Drafted | 80% |
| Architecture | Defined | 85% |
| Database design | Drafted | 75% |
| API design | Drafted | 75% |
| UX/UI design | Foundation defined | 45% |
| Figma designs | Not started | 0% |
| Backend implementation | Not started | 0% |
| Frontend implementation | Not started | 0% |
| Testing | Not started | 0% |
| Security review | Not started | 0% |
| Deployment | Not started | 0% |
| Pilot | Not started | 0% |
| Overall project completion | In progress | 28% |

## 10. Progress log
| Date | Update | Area | Completion |
|---|---|---|---:|
| 2026-11-20 | Created six root project files | Project setup | 90% |
| 2026-11-20 | Defined strategy, portfolio, governance, roles | Strategy | 90% |
| 2026-11-20 | Defined PRD, user stories, acceptance criteria, roadmap | Product management | 85% |
| 2026-11-20 | Defined architecture, database, tenancy, API, integrations | Architecture | 85% |
| 2026-11-20 | Defined coding standards, backend/frontend guidelines, Git workflow | Engineering | 80% |
| 2026-11-20 | Defined security, privacy, testing, release checklist | Security and QA | 75% |
| 2026-11-20 | Defined infrastructure, deployment, monitoring, backup | Operations | 75% |
| 2026-11-20 | Created detailed Retail PRD, database, ERD, API | Retail specification | 80% |
| 2026-11-20 | Added commit messages after every Copilot prompt | Phase planning | 95% |
| 2026-11-20 | Created Figma app-flow and wireframe specification | UX/UI | 45% |
| 2026-11-20 | Created screen-by-screen wireframe layout | UX/UI | 50% |

## 11. Open questions
| Question | Area | Owner | Status |
|---|---|---|---|
| Which M-Pesa integration method will be used? | Payments | Product owner | Open |
| What is the refund process for M-Pesa? | Payments | Product owner | Open |
| What are applicable tax and fiscalisation requirements? | Compliance | Finance / legal | Open |
| What receipt format and printer will be supported? | Retail | Product owner | Open |
| What is the customer-data retention policy? | Privacy | Product owner | Open |
| What is the credit-limit override policy? | Retail | Product owner | Open |
| What is the support-access approval process? | Security | Security owner | Open |
| What are English and Swahili language priorities? | UX | Product owner | Open |

## 12. Risks
| Risk | Impact | Likelihood | Mitigation | Status |
|---|---|---|---|---|
| Cross-tenant data leakage | Critical | Medium | Tenant-scoped querysets, permission tests, security review | Open |
| Building four sectors too early | High | High | Launch Retail first | Open |
| Payment reconciliation failures | High | Medium | Idempotent integrations, reconciliation reports, manual fallback | Open |
| Poor usability for non-technical users | High | Medium | User research, simple workflows, pilot testing | Open |
| Offline connectivity interruptions | High | High | Define MVP offline expectations | Open |
| Regulatory risk in pharmacy | High | Medium | Specialist and legal review before dispensing features | Open |
| Data loss | Critical | Low | Backups, recovery testing, monitoring | Open |
| Scope creep | High | High | MVP definition, roadmap governance, decision log | Open |

## 13. Next actions
1. Review and approve the six root project files.
2. Create Figma designs and app-flow diagram.
3. Set up backend and frontend repositories.
4. Build shared platform foundation.
5. Build Retail catalogue and inventory.
6. Build Retail POS and sales.
7. Build shifts, reports, and admin.
8. Run QA, security review, and pilot.
