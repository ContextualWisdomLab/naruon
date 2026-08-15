# Storybook design-token contract doctoring

## Scope

This note records the external design-system and accessibility references used for the Naruon Storybook token bridge.

The shipped slice adds a static CSS token adapter and regression tests only. It does not claim Storybook is installed, does not add npm dependencies, and does not change application runtime behavior.

## Product interpretation

Storybook defines itself as a frontend workshop for developing and sharing UI components and hard-to-reach states in isolation. For Naruon, those states include async actions, disabled provider writes, confidence/evidence labels, review queues, empty states, provider conflicts, offline recovery, and destructive confirmations.

The current official documentation is on the Storybook 10.5 line. Its installation requirements cover Next.js 14+, Node.js 20+, pnpm 9+, TypeScript 4.9+, and Vitest 3+, all below Naruon's current Next.js 16.2, Node 26, pnpm 11, TypeScript 6, and Vitest 4 baselines. Compatibility must nevertheless be demonstrated by an executable exact-head build rather than inferred only from version ranges.

## Framework decision

The follow-on runtime PR should use `@storybook/nextjs-vite`.

Storybook's official Vitest addon requires a Vite-based Storybook framework. For Next.js projects, the documentation explicitly requires `@storybook/nextjs-vite`. It also recommends a separate Vitest project when an application already uses Vitest 4. This makes the Vite framework the coherent target for Naruon's existing test stack and avoids maintaining the superseded Jest-based Storybook test runner.

The dependency PR must still validate:

- App Router routing and navigation mocks;
- server/client component boundaries;
- `next/font` behavior without remote CI fetches;
- global CSS and Tailwind processing;
- module aliases;
- browser-mode interaction tests;
- production static build output;
- no telemetry or external resource dependency.

## Addon boundary

`storybook-design-token` is a community addon listed in Storybook's integration catalog, not a Storybook core standard. Addon v5 supports Storybook 10 and newer and is ESM-only. The CSS comments used by this slice—`@tokens` and `@presenter`—are therefore an addon adapter contract.

Literal values in categories marked `@status candidate` are not production tokens. They must be audited and either promoted into an authoritative token graph or removed before components or Figma consume them.

## Tool-neutral exchange boundary

The Design Tokens Community Group's Design Tokens Format Module 2025.10 is the latest published stable exchange format. It specifies JSON-based, typed, aliasable design-token data intended to move between design, translation, documentation, and development tools.

The report is a stable W3C Community Group report, not a W3C Recommendation or Standards Track document. Naruon can use it as the interoperability contract while recording that standards status accurately.

Before Figma automation or cross-product publication, Naruon should add a validated DTCG 2025.10 artifact or deterministic converter and accept an ADR that names one authoritative source. This avoids coupling Figma, Storybook, and production code to a community addon's private annotation grammar.

## Accessibility boundary

Storybook's accessibility addon uses axe-core rendered-DOM heuristics and integrates with the Vitest addon. Storybook states that this automation catches up to 57% of WCAG issues, so a passing automated run is a first-line defect screen, not a WCAG conformance claim.

WCAG 2.2 remains the target. Component stories must supplement automation with keyboard, focus order and visibility, accessible-name, screen-reader announcement, zoom/reflow, reduced-motion, target-size, high-contrast, and cognitive usability review.

## APA 7th references

Design Tokens Community Group. (2025, October 28). *Design Tokens Format Module 2025.10*. https://www.designtokens.org/TR/2025.10/format/

Storybook. (2026). *Accessibility tests*. https://storybook.js.org/docs/writing-tests/accessibility-testing

Storybook. (2026). *Get started with Storybook*. https://storybook.js.org/docs

Storybook. (2026). *Install Storybook*. https://storybook.js.org/docs/10.5/get-started/install

Storybook. (2026). *Storybook Design Token*. https://storybook.js.org/addons/storybook-design-token

Storybook. (2026). *Vitest addon*. https://storybook.js.org/docs/writing-tests/integrations/vitest-addon/

World Wide Web Consortium. (2023, October 5). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

## Shipped-state boundary

- Static Storybook token adapter: shipped.
- Token-source regression tests: shipped.
- Complete alias-to-runtime-variable validation: shipped.
- Candidate-status validation for literal scales: shipped.
- Storybook runtime dependency: not shipped.
- Storybook UI build: not shipped.
- DTCG 2025.10 exchange artifact: not shipped.
- Figma variable or component mapping: not shipped.
- Component stories: not shipped.
- Automated or manual component accessibility evidence: not shipped.

## Follow-on acceptance checks

A future Storybook installation PR must show exact-head evidence for:

1. lockfile-consistent `@storybook/nextjs-vite` installation on Storybook 10.5;
2. a separate Storybook Vitest 4 project using browser mode;
3. explicit compatibility evidence for Next.js 16.2, React 19, and the design-token addon;
4. `storybook`, `build-storybook`, and non-interactive CI scripts;
5. `.storybook/main.ts`, `.storybook/preview.ts`, and `.storybook/vitest.setup.ts`;
6. token documentation rendering every category and maturity class;
7. at least one interactive story per repeated UI primitive;
8. WCAG 2.2-oriented a11y checks configured as CI failures for production stories;
9. manual keyboard and screen-reader-name evidence for states automation cannot establish;
10. no remote font, analytics, image, or telemetry fetch during CI;
11. a DTCG 2025.10 authority decision before Figma token automation;
12. promotion or removal of candidate scales before production component consumption.
