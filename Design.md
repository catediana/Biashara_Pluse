# Biashara Pulse — Design System
Version: 0.4 | Date: 2026-11-20

## 1. Design principles
- Simple and familiar for non-technical users.
- Mobile-first, with responsive tablet and desktop layouts.
- Clear hierarchy and generous touch targets.
- Consistent terminology across sectors.
- Accessible colour contrast and readable typography.
- Professional, trustworthy, and modern appearance.

## 2. Brand direction
Biashara Pulse should feel reliable, professional, simple, modern, business-focused, and locally relevant.

Avoid overly playful, cluttered, or overly technical interfaces.

## 3. Colour palette
| Token | Colour | Use |
|---|---|---|
| primary | #1D4ED8 | Primary actions, links, active states |
| primary-dark | #1E3A8A | Hover and pressed states |
| primary-light | #DBEAFE | Soft backgrounds and highlights |
| secondary | #0F766E | Secondary actions and supporting accents |
| success | #15803D | Successful actions and positive status |
| warning | #B45309 | Warnings and attention-required states |
| danger | #B91C1C | Errors, destructive actions, failed states |
| neutral-900 | #111827 | Primary text |
| neutral-700 | #374151 | Secondary text |
| neutral-500 | #6B7280 | Muted text |
| neutral-200 | #E5E7EB | Borders and dividers |
| neutral-100 | #F3F4F6 | Backgrounds |
| white | #FFFFFF | Cards, surfaces, primary backgrounds |

## 4. Colour usage rules
- Use primary blue for main actions such as Complete Sale, Save, and Continue.
- Use secondary teal for supporting actions and highlights.
- Use green only for success states.
- Use amber only for warnings.
- Use red only for errors, destructive actions, and failed states.
- Do not rely on colour alone; use icons and text labels too.
- Maintain accessible contrast.

## 5. Typography
Use a highly legible sans-serif typeface.

Recommended fonts:
- Inter for interface text
- Inter or IBM Plex Sans for headings
- JetBrains Mono or Roboto Mono for numbers, codes, and technical values where needed

### Type scale
| Style | Font size | Line height | Weight | Use |
|---|---:|---:|---:|---|
| Display | 36px | 40px | 700 | Major page titles |
| H1 | 28px | 34px | 700 | Page titles |
| H2 | 22px | 28px | 600 | Section titles |
| H3 | 18px | 24px | 600 | Card and panel titles |
| Body large | 16px | 24px | 400 | Important body text |
| Body | 14px | 20px | 400 | Default interface text |
| Small | 12px | 16px | 400 | Supporting text |
| Caption | 11px | 16px | 500 | Labels, badges, metadata |

## 6. Typography rules
- Use sentence case for buttons, labels, and headings.
- Use bold weights sparingly.
- Do not use more than two font families.
- Use clear hierarchy.
- Use tabular numbers for financial values where supported.
- Do not use text below 12px for important information.

## 7. Spacing scale
| Token | Value | Use |
|---|---:|---|
| space-1 | 4px | Tight spacing |
| space-2 | 8px | Small spacing |
| space-3 | 12px | Component padding |
| space-4 | 16px | Standard spacing |
| space-5 | 24px | Section spacing |
| space-6 | 32px | Large section spacing |
| space-7 | 48px | Page-level spacing |
| space-8 | 64px | Major layout spacing |

## 8. Border radius
| Token | Value | Use |
|---|---:|---|
| radius-sm | 4px | Small inputs and badges |
| radius-md | 8px | Buttons, inputs, cards |
| radius-lg | 12px | Panels and modals |
| radius-full | 9999px | Pills and avatars |

## 9. Shadows
| Token | Value | Use |
|---|---|---|
| shadow-sm | 0 1px 2px rgba(0,0,0,0.05) | Cards and inputs |
| shadow-md | 0 4px 6px rgba(0,0,0,0.07) | Dropdowns and popovers |
| shadow-lg | 0 10px 15px rgba(0,0,0,0.10) | Modals and drawers |

## 10. Themes
### Light theme
| Surface | Colour |
|---|---|
| App background | #F9FAFB |
| Card background | #FFFFFF |
| Sidebar background | #FFFFFF |
| Primary button | #1D4ED8 |
| Primary button text | #FFFFFF |
| Secondary button | #FFFFFF |
| Secondary button border | #E5E7EB |
| Input background | #FFFFFF |
| Input border | #E5E7EB |
| Table header background | #F3F4F6 |

### Dark theme
| Surface | Colour |
|---|---|
| App background | #0B1120 |
| Card background | #111827 |
| Sidebar background | #0F172A |
| Primary button | #3B82F6 |
| Primary button text | #FFFFFF |
| Secondary button | #1F2937 |
| Secondary button border | #374151 |
| Input background | #111827 |
| Input border | #374151 |
| Table header background | #1F2937 |

## 11. Components
- Buttons: primary, secondary, danger, ghost, disabled, loading
- Inputs: text, number, select, date, search, file
- Cards, tables, tabs, modals, drawers, toasts, badges
- Empty states, skeletons, error messages, confirmation dialogs
- Receipt and statement templates

## 12. POS-specific design rules
- Make product search fast and prominent.
- Use large touch targets.
- Show running total clearly.
- Show payment method clearly.
- Make Complete Sale the primary action.
- Show clear errors for insufficient stock, invalid payment, or permission issues.
- Make receipt preview easy to access.
- Avoid unnecessary checkout steps.
- Support keyboard and barcode scanner input.

## 13. Accessibility
- Maintain sufficient colour contrast.
- Do not rely on colour alone.
- Provide visible focus states.
- Ensure keyboard navigation.
- Use descriptive labels.
- Provide alt text for meaningful images.
- Avoid small touch targets.
- Support screen-reader semantics.

## 14. Content rules
- Use plain English and Swahili where appropriate.
- Avoid technical jargon in customer-facing interfaces.
- Use sentence case for labels and buttons.
- Explain required fields and errors clearly.
- Use consistent terminology.
