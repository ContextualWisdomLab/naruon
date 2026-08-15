# Storybook design-token library rollout plan

## Goal

Turn Naruon's repeated UI objects into a reviewable component library without breaking the current Next.js runtime or adding unpinned design dependencies in the same slice as token-definition work.

## Current slice

This PR ships only the bounded first step:

1. Add a Storybook-readable CSS token source.
2. Test the token categories and live CSS variable mappings.
3. Document the security and product boundary.

## Follow-on implementation sequence

### Task 1 — Storybook runtime dependency

- Select `@storybook/nextjs` or `@storybook/nextjs-vite` after checking compatibility with the current Next.js and React versions.
- Pin package versions in `frontend/package.json`.
- Update `pnpm-lock.yaml` in the same commit.
- Add `storybook` and `build-storybook` scripts.
- Add `.storybook/main.ts` and `.storybook/preview.ts`.

### Task 2 — token docs page

- Configure the selected design-token addon version.
- Render categories from `frontend/src/app/storybook-design-tokens.css`.
- Add a build test or smoke contract proving all categories are present.

### Task 3 — repeated UI primitives

Create stories for:

- Button / Async Action Button;
- Card / Evidence Card;
- Navigation Item / GNB and LNB entry;
- Evidence Pill / confidence and source-state labels;
- Modal / destructive confirmation;
- Empty, loading, permission-denied, and provider-writeback-conflict states.

### Task 4 — Figma bridge

- Map Storybook token names to Figma variables.
- Produce a component-mapping table before using any Figma automation.
- Keep production CSS as the source of truth unless an ADR explicitly changes authority.

### Task 5 — CI and release gates

- Build Storybook in CI.
- Prove no external font, analytics, or image fetch is required.
- Run accessibility checks for keyboard focus, disabled, busy, and error states.
- Publish component screenshots or static Storybook artifact only after the build is reproducible.

## Merge gate for this PR

- Frontend test suite must pass on the exact head.
- No package or lockfile drift is allowed in this slice.
- Storybook dependency installation remains a separate review unit.
