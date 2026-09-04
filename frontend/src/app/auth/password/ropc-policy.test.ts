import { access, readFile } from "node:fs/promises";

import { describe, expect, it } from "vitest";

async function sourceFile(relativePath: string): Promise<string> {
  return readFile(new URL(relativePath, import.meta.url), "utf8");
}

describe("password-route authentication authority", () => {
  it("keeps Naruon password routes fail-closed until Keyverse publishes a released headless contract", async () => {
    const [loginRoute, signupRoute] = await Promise.all([
      sourceFile("./login/route.ts"),
      sourceFile("./signup/route.ts"),
    ]);

    for (const source of [loginRoute, signupRoute]) {
      expect(source).not.toContain("exchangePasswordForSessionResponse");
      expect(source).not.toContain('grant_type: "password"');
      expect(source).not.toContain("grant_type=password");
    }
  });

  it("does not retain dormant ROPC or password-registration authority", async () => {
    const oidcShared = await sourceFile("../../oidc/shared.ts");

    expect(oidcShared).not.toContain("exchangePasswordForSessionResponse");
    expect(oidcShared).not.toContain('grant_type: "password"');
    await expect(
      access(new URL("../../../../lib/account-unification-client.ts", import.meta.url)),
    ).rejects.toBeDefined();
  });

  it("keeps ADR-0005 Proposed while the released Keyverse capability is unavailable", async () => {
    const adrIndex = await sourceFile("../../../../../docs/adr/README.md");
    const adrRow = adrIndex
      .split("\n")
      .find((line) => line.includes("[ADR-0005]"));

    expect(adrRow).toBeDefined();
    expect(adrRow).toContain("| Proposed |");
    expect(adrRow).toContain("BLOCKED-UPSTREAM");
    expect(adrRow).not.toContain("working end-to-end");
  });
});
