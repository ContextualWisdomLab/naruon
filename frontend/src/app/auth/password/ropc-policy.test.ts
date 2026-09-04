import { readFile } from "node:fs/promises";

import { describe, expect, it } from "vitest";

async function routeSource(relativePath: string): Promise<string> {
  return readFile(new URL(relativePath, import.meta.url), "utf8");
}

describe("password-route authentication authority", () => {
  it("keeps Naruon password routes fail-closed until Keyverse publishes a released headless contract", async () => {
    const [loginRoute, signupRoute] = await Promise.all([
      routeSource("./login/route.ts"),
      routeSource("./signup/route.ts"),
    ]);

    for (const source of [loginRoute, signupRoute]) {
      expect(source).not.toContain("exchangePasswordForSessionResponse");
      expect(source).not.toContain('grant_type: "password"');
      expect(source).not.toContain("grant_type=password");
    }
  });
});
