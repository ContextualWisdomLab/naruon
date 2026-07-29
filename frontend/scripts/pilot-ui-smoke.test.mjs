import { describe, expect, it } from "vitest";

import { resolvePilotBaseUrl } from "./pilot-ui-smoke.mjs";

describe("pilot UI smoke base URL guard", () => {
  it("allows localhost pilot smoke targets", () => {
    expect(resolvePilotBaseUrl("http://127.0.0.1:3001").hostname).toBe("127.0.0.1");
    expect(resolvePilotBaseUrl("http://localhost:3001").hostname).toBe("localhost");
    expect(resolvePilotBaseUrl("http://[::1]:3001").hostname).toBe("[::1]");
  });

  it("rejects non-localhost targets", () => {
    expect(() => resolvePilotBaseUrl("https://staging.example.com")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("https://naruon.example.com")).toThrow("localhost targets");
  });
});
