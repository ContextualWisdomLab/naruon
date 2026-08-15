# Storybook design-token contract

## Buyer-visible gap

Naruon has many screens and repeated interface objects, but a reviewer currently has to inspect the application manually to understand whether colors, typography, spacing, radius, elevation, focus, and state styling are shared product decisions or one-off styling. That slows product review, Figma handoff, accessibility review, white-label readiness, and safe reuse across CWL products.

## Decision

Naruon exposes a static Storybook-readable token adapter at:

```text
frontend/src/app/storybook-design-tokens.css
```

The file mirrors live CSS custom properties from `frontend/src/app/globals.css` and annotates categories with the comment contract used by the community `storybook-design-token` addon:

```css
/**
 * @tokens Naruon Colors
 * @presenter Color
 */
--naruon-token-primary: var(--primary);
```

This slice does not add Storybook runtime dependencies or mutate the pnpm lockfile. It creates the reviewed token adapter and regression tests first, so a later dependency PR can add exact Storybook framework and addon versions without inventing the token model during installation.

The regression contract validates every alias target against `globals.css`, not merely a sampled list, and rejects duplicate Storybook token names and remote resource references.

## Standards boundary

The CSS annotation grammar is addon-specific. It is useful for Storybook documentation but is not a tool-neutral exchange standard.

The first stable Design Tokens Community Group format is DTCG 2025.10. Before automated Figma synchronization or publication of tokens for other CWL products, Naruon must add either:

1. a validated DTCG 2025.10 artifact that becomes the authoritative semantic token source; or
2. a deterministic, tested converter from the accepted production source to DTCG 2025.10.

An ADR must prevent circular generation and identify ownership of semantic names, theme modes, aliases, deprecations, and generated artifacts.

## Storybook installation target

Naruon is a Next.js 16.2 application. The eventual Storybook runtime should use one of the official Next.js framework packages:

- `@storybook/nextjs` for the Webpack-aligned path; or
- `@storybook/nextjs-vite` when an executable spike proves the Vite-based path preserves the required Next.js behavior.

The current Storybook documentation supports Next.js and Next.js with Vite, and Storybook 10.4 reports explicit Next.js 16.2 support. The selected framework must still be pinned and verified on Naruon's exact dependency graph. The selected `storybook-design-token` addon major must match the Storybook major: its v5 line targets Storybook 10 and newer, while v4 targets Storybook 9.

The dependency PR must update `frontend/package.json` and `pnpm-lock.yaml` together and add `.storybook/main.ts`, `.storybook/preview.ts`, `storybook`, and `build-storybook` scripts.

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

The token adapter is static CSS only.

It must not:

- import remote fonts;
- fetch external images or styles;
- include user content;
- include provider credentials;
- encode tenant-specific branding secrets;
- replace runtime authorization, audit, or evidence controls;
- allow Figma or Storybook automation to overwrite production values without a reviewed code change.

Regression tests reject remote resources, duplicate token names, and aliases that do not resolve to a production CSS variable.

## Accessibility contract

Storybook component stories must make hard-to-reach states visible, but a rendered story is not accessibility evidence by itself.

The follow-on library must:

- install Storybook's official accessibility addon;
- configure production stories to fail CI on automated violations;
- target WCAG 2.2 Level AA;
- include keyboard focus, disabled, busy, success, recoverable error, destructive, dark-theme, narrow viewport, and 200% zoom states;
- test keyboard activation, focus return, status announcements, and error recovery;
- document manual checks for focus order, accessible names, screen-reader output, reflow, reduced motion, and high contrast.

Automated axe-based checks are a first-line heuristic and do not replace manual or assistive-technology testing.

## Figma and component-library boundary

Figma should consume stable semantic token identifiers, preferably through the DTCG exchange artifact, but Figma remains a design-review workspace rather than an unreviewed source of production changes. Storybook documents component states against the same identifiers, while production code remains authoritative until an accepted ADR changes that boundary.

The next UI-system slices should add:

1. pinned Storybook dependencies and lockfile update;
2. a token documentation page using the selected design-token addon;
3. a DTCG 2025.10 exchange artifact or deterministic converter;
4. first component stories for Button, Card, Navigation Item, Evidence Pill, Modal, and Async Action Button;
5. interaction and accessibility tests for focus, disabled, loading, error, evidence-linked, offline, and provider-conflict states;
6. Figma variable and component mapping only after the static Storybook surface is reproducible in CI.

## Done criteria for this slice

- Token adapter exists in the frontend package.
- Token categories are annotated for Storybook design-token documentation.
- Token aliases mirror existing Naruon runtime CSS variable names.
- Tests prove category coverage, unique names, complete alias resolution, required mappings, and no remote resources.
- Doctoring records current Storybook, DTCG 2025.10, and WCAG 2.2 references.
- Documentation does not imply that Storybook runtime, DTCG exchange, Figma mapping, or component accessibility evidence is already shipped.
