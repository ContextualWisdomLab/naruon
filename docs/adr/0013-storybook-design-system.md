# ADR-0013: Isolate the shared UI contract in Storybook

- Status: Accepted
- Date: 2026-08-20 (UTC)
- Owners: Naruon frontend maintainers
- Figma file ID: `68b5XB58w8nwT2LYOOnikK`

## Context

Naruon's Next.js UI already centralizes recurring components and CSS custom
properties under `frontend/src/components/ui` and `frontend/src/app/globals.css`,
but their supported visual states are otherwise discoverable only through the
application. Buyers and maintainers need a safe place to inspect the same
buttons, badges, focus rings, and color/radius tokens before a screen change is
promoted across the mail, data, and security workspaces.

## Decision

Use Storybook's `@storybook/nextjs-vite` framework with CSF stories for the
shared UI components. Storybook imports the production global stylesheet, so
stories exercise the existing design tokens instead of defining a second theme.
The first inventory covers `Button` and `Badge`, including ordinary, outline,
destructive, and disabled states. Analysis/judgment/execution stories cover
`DecisionPointCard` scene events (source open, draft review, calendar reflect,
task create) and edge events (loading, empty, error, low confidence, missing
source, blocked/intent-only) using the same production tokens. New reusable UI
components must add stories for their meaningful states and accessibility
labels; page-specific stories remain optional until a page has a stable
isolated contract.

The existing Figma file remains the visual reference for design decisions, while
Storybook is the executable authority for the shared component inventory. No
new Figma file or Code Connect integration is created by this delivery; record
any future replacement file ID in this ADR before changing token values.

## Consequences

- `pnpm storybook` gives maintainers an isolated component inventory.
- `pnpm build-storybook` provides a deterministic CI build artifact.
- The CSS token source stays in one production stylesheet, avoiding theme drift.
- Interaction and security behavior remains covered by Vitest and browser tests;
  Storybook documents visual states and is not a substitute for those tests.
- The current Storybook Next.js Vite plugin is patched to use the already-pinned
  `sharp` metadata API instead of its vulnerable `image-size` dependency; remove
  `frontend/patches/vite-plugin-storybook-nextjs@3.3.2.patch` only after an
  upstream release removes the affected parser.

## Verification

```bash
cd frontend
pnpm build-storybook
pnpm test -- --run
pnpm run lint
pnpm run typecheck
```

## References (APA 7th)

Storybook. (n.d.). *Component Story Format (CSF)*. Retrieved August 20, 2026,
from https://storybook.js.org/docs/api/csf

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/
