# Storybook design-token contract

## Buyer-visible gap

Naruon has many screens and repeated interface objects, but a reviewer currently has to inspect the application manually to understand whether colors, typography, spacing, radius, and elevation are shared product decisions or one-off styling. That slows product review, Figma handoff, accessibility review, and future white-label work.

## Decision

Naruon exposes a static Storybook-readable token source at:

```text
frontend/src/app/storybook-design-tokens.css
```

The file mirrors live CSS custom properties from `frontend/src/app/globals.css` and annotates categories with the comment contract used by Storybook design-token documentation addons:

```css
/**
 * @tokens Naruon Colors
 * @presenter Color
 */
--naruon-token-primary: var(--primary);
```

This slice does not add Storybook runtime dependencies or mutate the pnpm lockfile. It creates the reviewed token source and regression tests first, so a later dependency PR can add the exact Storybook framework and addon versions without inventing the token model during installation.

## Storybook installation target

Naruon is a Next.js app. The eventual Storybook runtime should use one of the official Next.js framework packages:

- `@storybook/nextjs` for the Webpack-aligned path; or
- `@storybook/nextjs-vite` if the team deliberately chooses the Vite-based Storybook path.

The selected framework must be pinned in `frontend/package.json` and the lockfile in the same PR that adds `.storybook/main.ts`, `.storybook/preview.ts`, and `storybook` scripts.

## Token categories

| Category | Purpose |
|---|---|
| Naruon Colors | App background, foreground, card, action, chart, status, border, and focus colors. |
| Naruon Sidebar Colors | Global navigation and workspace shell colors. |
| Naruon Typography | Korean-first UI and monospaced technical text font stacks. |
| Naruon Font Sizes | Reusable caption, body, lead, title, and display scale. |
| Naruon Line Heights | Compact UI, ordinary body text, and reading-dense email/document text. |
| Naruon Spacing | Shared layout rhythm for cards, panels, drawers, and button groups. |
| Naruon Radius | Surface and control corner scale. |
| Naruon Elevation | Panel and floating-surface shadows. |

## Security and privacy boundary

The token source is static CSS only.

It must not:

- import remote fonts;
- fetch external images or styles;
- include user content;
- include provider credentials;
- encode tenant-specific branding secrets;
- replace runtime authorization, audit, or evidence controls.

A regression test rejects remote URL imports from the token source.

## Figma and component-library boundary

Figma should consume the same token names semantically, but Figma remains a design-review workspace rather than the source of production truth. Production code owns the token values through reviewed CSS and tests. Storybook then documents component states against those same token names.

The next UI-system slice should add:

1. Storybook dependency and lockfile update;
2. token documentation page using the selected design-token addon;
3. first component stories for Button, Card, Navigation Item, Evidence Pill, and Async Action Button;
4. visual regression or interaction tests for focus, disabled, loading, error, and evidence-linked states;
5. Figma component mapping only after the Storybook surface is reproducible in CI.

## Done criteria for this slice

- Token source exists in the frontend package.
- Token categories are annotated for Storybook design-token documentation.
- Token variables mirror the existing Naruon runtime CSS variable names.
- Tests prove the categories, live mappings, and no-remote-resource boundary.
- Doctoring records the current Storybook and design-token documentation references.
