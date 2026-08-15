# Storybook design-token contract doctoring

## Scope

This note records the external design-system references used for the Naruon Storybook token bridge.

The shipped slice adds a static CSS token source and regression tests only. It does not claim Storybook is installed, does not add npm dependencies, and does not change application runtime behavior.

## Product interpretation

Storybook describes itself as a frontend workshop for building UI components and pages in isolation and sharing hard-to-reach states and edge cases. For Naruon, that maps to evidence states that are hard to review inside the full product flow: async buttons, disabled provider writes, confidence badges, review queues, empty states, and destructive confirmations.

The official Storybook Next.js documentation identifies Next.js-specific support for routing, image optimization, styling, TypeScript path aliases, `next/navigation`, and the App Router. It also describes the Vite-based `@storybook/nextjs-vite` framework option. Naruon should choose between `@storybook/nextjs` and `@storybook/nextjs-vite` in the dependency PR, not in this token-source PR.

The Storybook Design Token addon documents a CSS-comment annotation workflow using `@tokens` categories and `@presenter` hints. The token source in this PR follows that convention while keeping the values tied to Naruon's existing CSS custom properties.

## APA 7th references

Storybook. (2026). *Get started with Storybook*. https://storybook.js.org/docs

Storybook. (2026). *Storybook for Next.js*. https://storybook.js.org/docs/9/get-started/frameworks/nextjs

Storybook. (2026). *Storybook for React & Vite*. https://storybook.js.org/docs/9/get-started/frameworks/react-vite

Storybook. (2026). *Vite*. https://storybook.js.org/docs/9/builders/vite

Storybook. (2026). *Storybook Design Token*. https://storybook.js.org/addons/storybook-design-token

## Shipped-state boundary

- Static token source: shipped.
- Token-source regression tests: shipped.
- Storybook runtime dependency: not shipped.
- Storybook UI build: not shipped.
- Figma component mapping: not shipped.
- Component stories: not shipped.

## Follow-on acceptance checks

A future Storybook installation PR must show exact-head evidence for:

1. lockfile-consistent dependency installation;
2. `storybook` and `build-storybook` scripts;
3. `.storybook/main.ts` and `.storybook/preview.ts` matching the chosen framework;
4. token documentation page rendering the categories in `storybook-design-tokens.css`;
5. at least one interactive component story per repeated UI primitive;
6. no remote font or analytics fetch during CI Storybook build;
7. accessibility and keyboard-focus states visible in component stories.
