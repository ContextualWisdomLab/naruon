# Storybook design-token contract doctoring

## Scope

This note records the external design-system references used for the Naruon Storybook token bridge.

The shipped slice adds a static CSS token source and regression tests only. It does not claim Storybook is installed, does not add npm dependencies, and does not change application runtime behavior.

## Product interpretation

Storybook describes itself as a frontend workshop for building UI components and pages in isolation and sharing hard-to-reach states and edge cases. For Naruon, that maps to evidence states that are hard to review inside the full product flow: async buttons, disabled provider writes, confidence badges, review queues, empty states, provider conflicts, and destructive confirmations.

The current Storybook documentation supports Next.js and Next.js with Vite. The installation requirements are compatible with Naruon's current Next.js 16.2, React 19, pnpm 11, TypeScript 6, and Vitest 4 baseline. Storybook 10.4 also reports explicit Next.js 16.2 support. The dependency PR must still validate the exact current stable Storybook release against Naruon's App Router, server/client component boundaries, CSS pipeline, and test environment before choosing `@storybook/nextjs` or `@storybook/nextjs-vite`.

The `storybook-design-token` package is a community addon listed in Storybook's integrations catalog, not a Storybook core standard. Its current compatibility contract is major-specific: addon v5 targets Storybook 10 and newer and is ESM-only, while addon v4 targets Storybook 9. The dependency PR must pin the addon major that matches the selected Storybook major and must not rely on an unversioned catalog page.

The addon documents the CSS-comment annotation workflow used in this slice: `@tokens` categories and `@presenter` hints. The CSS file is therefore a Storybook documentation adapter over Naruon's existing runtime variables, not yet a tool-neutral token exchange artifact.

The Design Tokens Community Group published its first stable format, Design Tokens Format Module 2025.10, for interoperable token exchange between tools. Before Figma automation or cross-product token publication, Naruon should add a validated DTCG 2025.10 artifact or a deterministic converter and define which artifact is authoritative in an ADR. This avoids coupling Figma, Storybook, and production code to a community addon's private annotation grammar.

Storybook's accessibility addon runs rendered-DOM heuristics through axe-core and can fail component tests in CI. The official documentation states that automation catches only a portion of WCAG issues, so component stories must supplement automated checks with keyboard, focus-order, zoom/reflow, screen-reader-name, reduced-motion, and high-contrast review.

## APA 7th references

Design Tokens Community Group. (2025, October 28). *Design Tokens Format Module 2025.10*. https://www.designtokens.org/TR/2025.10/format/

Storybook. (2026). *Accessibility tests*. https://storybook.js.org/docs/writing-tests/accessibility-testing

Storybook. (2026). *Get started with Storybook*. https://storybook.js.org/docs

Storybook. (2026). *Install Storybook*. https://storybook.js.org/docs/get-started/install

Storybook. (2026, May 18). *Storybook 10.4*. https://storybook.js.org/blog/storybook-10-4/

Storybook. (2026). *Storybook Design Token*. https://storybook.js.org/addons/storybook-design-token

World Wide Web Consortium. (2023, October 5). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

## Shipped-state boundary

- Static Storybook token adapter: shipped.
- Token-source regression tests: shipped.
- Complete alias-to-runtime-variable validation: shipped.
- Storybook runtime dependency: not shipped.
- Storybook UI build: not shipped.
- DTCG 2025.10 exchange artifact: not shipped.
- Figma variable or component mapping: not shipped.
- Component stories: not shipped.
- Automated or manual component accessibility evidence: not shipped.

## Follow-on acceptance checks

A future Storybook installation PR must show exact-head evidence for:

1. lockfile-consistent dependency installation on the current stable Storybook major;
2. explicit compatibility evidence for the selected Next.js framework and design-token addon majors;
3. `storybook` and `build-storybook` scripts;
4. `.storybook/main.ts` and `.storybook/preview.ts` matching the selected framework;
5. token documentation rendering every category in `storybook-design-tokens.css`;
6. at least one interactive component story per repeated UI primitive;
7. WCAG 2.2-oriented a11y checks configured as CI failures for production stories;
8. manual keyboard and screen-reader-name checks documented for states automation cannot establish;
9. no remote font, analytics, or image fetch during the CI Storybook build;
10. a DTCG 2025.10 exchange decision before Figma token automation.
