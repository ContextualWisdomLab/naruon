import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const tokenSource = readFileSync(
  new URL("./storybook-design-tokens.css", import.meta.url),
  "utf8",
);
const runtimeSource = readFileSync(new URL("./globals.css", import.meta.url), "utf8");

const requiredCategories = [
  "Naruon Colors",
  "Naruon Sidebar Colors",
  "Naruon Typography",
  "Naruon Font Sizes",
  "Naruon Line Heights",
  "Naruon Spacing",
  "Naruon Radius",
  "Naruon Elevation",
] as const;

const requiredLiveMappings = [
  "--naruon-token-primary: var(--primary);",
  "--naruon-token-background: var(--background);",
  "--naruon-token-sidebar-primary: var(--sidebar-primary);",
  "--naruon-token-font-sans: var(--font-naruon-sans);",
  "--naruon-token-radius-large: var(--radius-lg);",
] as const;

const storybookTokenNames = Array.from(
  tokenSource.matchAll(/^\s*(--naruon-token-[a-z0-9-]+)\s*:/gim),
  (match) => match[1],
);
const liveVariableNames = new Set(
  Array.from(
    runtimeSource.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gim),
    (match) => match[1],
  ),
);
const aliasedLiveVariables = Array.from(
  tokenSource.matchAll(
    /^\s*--naruon-token-[a-z0-9-]+\s*:\s*var\((--[a-z0-9-]+)\)\s*;/gim,
  ),
  (match) => match[1],
);

describe("storybook design token contract", () => {
  it("keeps every token category annotated for the Storybook token panel", () => {
    for (const category of requiredCategories) {
      expect(tokenSource).toContain(`@tokens ${category}`);
    }

    expect(tokenSource.match(/@presenter /g)).toHaveLength(requiredCategories.length);
  });

  it("maps the required Storybook-facing tokens to live Naruon CSS variables", () => {
    for (const declaration of requiredLiveMappings) {
      expect(tokenSource).toContain(declaration);
    }
  });

  it("keeps every Storybook token name unique", () => {
    expect(storybookTokenNames.length).toBeGreaterThan(0);
    expect(new Set(storybookTokenNames).size).toBe(storybookTokenNames.length);
  });

  it("resolves every CSS variable alias against the production token source", () => {
    expect(aliasedLiveVariables.length).toBeGreaterThan(0);

    for (const liveVariable of aliasedLiveVariables) {
      expect(liveVariableNames, `${liveVariable} must exist in globals.css`).toContain(
        liveVariable,
      );
    }
  });

  it("does not fetch external style resources from the token source", () => {
    expect(tokenSource).not.toMatch(/@import\s+url\(/i);
    expect(tokenSource).not.toMatch(/url\s*\(\s*["']?\s*(?:https?:)?\/\//i);
    expect(tokenSource).not.toMatch(/https?:\/\//i);
  });
});
