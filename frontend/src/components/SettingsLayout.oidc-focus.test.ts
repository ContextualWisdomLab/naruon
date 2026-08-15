import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const settingsLayoutSource = readFileSync(
  new URL("./SettingsLayout.tsx", import.meta.url),
  "utf8",
);

function buttonSource(label: string): string {
  const labelIndex = settingsLayoutSource.indexOf(label);
  expect(labelIndex).toBeGreaterThan(-1);
  const openingButtonIndex = settingsLayoutSource.lastIndexOf("<button", labelIndex);
  const closingButtonIndex = settingsLayoutSource.indexOf("</button>", labelIndex);
  expect(openingButtonIndex).toBeGreaterThan(-1);
  expect(closingButtonIndex).toBeGreaterThan(labelIndex);
  return settingsLayoutSource.slice(openingButtonIndex, closingButtonIndex);
}

describe("SettingsLayout OIDC keyboard focus contract", () => {
  it.each(["OIDC 로그인", "로그아웃"])(
    "keeps a keyboard-only visible focus indicator on %s",
    (label) => {
      const source = buttonSource(label);

      expect(source).toContain("focus-visible:outline-none");
      expect(source).toContain("focus-visible:ring-2");
      expect(source).toContain("focus-visible:ring-ring/40");
    },
  );
});
