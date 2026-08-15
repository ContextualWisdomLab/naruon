import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const tokenSource = readFileSync(
  new URL("./storybook-design-tokens.css", import.meta.url),
  "utf8",
);

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

describe("storybook design token contract", () => {
  it("keeps every token category annotated for the Storybook token panel", () => {
    for (const category of requiredCategories) {
      expect(tokenSource).toContain(`@tokens ${category}`);
    }

    expect(tokenSource.match(/@presenter /g)).toHaveLength(requiredCategories.length);
  });

  it("maps Storybook-facing tokens to the live Naruon CSS variables", () => {
    for (const declaration of requiredLiveMappings) {
      expect(tokenSource).toContain(declaration);
    }
  });

  it("does not fetch external style resources from the token source", () => {
    expect(tokenSource).not.toMatch(/@import\s+url\(/i);
    expect(tokenSource).not.toMatch(/https?:\/\//i);
  });
});
