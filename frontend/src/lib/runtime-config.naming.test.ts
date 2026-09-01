import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("runtime config naming boundary", () => {
  let fetchRuntimeConfig: typeof import("./runtime-config").fetchRuntimeConfig;

  beforeEach(async () => {
    vi.resetModules();
    const runtimeConfigModule = await import("./runtime-config");
    fetchRuntimeConfig = runtimeConfigModule.fetchRuntimeConfig;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("translates legacy wire keys into semantic internal names", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        product_name: "TestProduct",
        version: "1.2.3",
        features: { llm_enabled: true },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchRuntimeConfig()).resolves.toEqual({
      product_name: "TestProduct",
      product_version: "1.2.3",
      feature_flags: { llm_enabled: true },
    });
  });
});
