## 2024-03-20 - Ensure focus-visible on Interactive Elements
**Learning:** In Naruon 2.0 component library, sometimes tailwind buttons lack `focus-visible` styles which hurts keyboard accessibility because the default browser outline is suppressed by reset styles or it's visually insufficient. Adding `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40` improves the keyboard experience without affecting mouse users.
**Action:** When creating or fixing custom buttons, ensure they have proper `focus-visible` ring classes so keyboard navigation is apparent.
