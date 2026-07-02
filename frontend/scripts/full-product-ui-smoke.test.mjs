import { describe, expect, it } from "vitest";

import { FULL_PRODUCT_ROUTES, resolveFullProductBaseUrl } from "./full-product-ui-smoke.mjs";

describe("full product UI smoke base URL guard", () => {
  it("allows localhost full-product smoke targets", () => {
    expect(resolveFullProductBaseUrl("http://127.0.0.1:3001").hostname).toBe("127.0.0.1");
    expect(resolveFullProductBaseUrl("http://localhost:3001").hostname).toBe("localhost");
    expect(resolveFullProductBaseUrl("http://[::1]:3001").hostname).toBe("[::1]");
  });

  it("rejects non-localhost targets", () => {
    expect(() => resolveFullProductBaseUrl("https://staging.example.com")).toThrow("localhost targets");
    expect(() => resolveFullProductBaseUrl("https://naruon.example.com")).toThrow("localhost targets");
    expect(() => resolveFullProductBaseUrl("http://192.168.0.10:3000")).toThrow("localhost targets");
  });

  it("covers the ten buyer-review IA routes", () => {
    expect(FULL_PRODUCT_ROUTES.map((route) => route.path)).toEqual([
      "/",
      "/mail",
      "/search",
      "/calendar",
      "/tasks",
      "/projects",
      "/data",
      "/ai-hub",
      "/security",
      "/settings",
    ]);
  });
});
