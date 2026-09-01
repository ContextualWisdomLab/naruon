import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RuntimeConfig } from "./runtime-config";

type RuntimeConfigWireFixture = {
  product_name: string;
  version: string;
  features: Record<string, boolean>;
};

describe("fetchRuntimeConfig", () => {
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

  const mockRuntimeConfig: RuntimeConfig = {
    product_name: "TestProduct",
    product_version: "1.0.0",
    feature_flags: { test_feature: true },
  };

  const mockRuntimeConfigWire: RuntimeConfigWireFixture = {
    product_name: "TestProduct",
    version: "1.0.0",
    features: { test_feature: true },
  };

  const fallbackRuntimeConfig: RuntimeConfig = {
    product_name: "Naruon",
    product_version: "fallback",
    feature_flags: {},
  };

  it("fetches runtime config without baseUrl and caches the result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRuntimeConfigWire,
    });
    vi.stubGlobal("fetch", fetchMock);

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/runtime-config");
    expect(runtimeConfig).toEqual(mockRuntimeConfig);
  });

  it("fetches runtime config with baseUrl", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRuntimeConfigWire,
    });
    vi.stubGlobal("fetch", fetchMock);

    const runtimeConfig = await fetchRuntimeConfig("https://example.com");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("https://example.com/api/runtime-config");
    expect(runtimeConfig).toEqual(mockRuntimeConfig);
  });

  it("returns cached config on subsequent calls without fetching again", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRuntimeConfigWire,
    });
    vi.stubGlobal("fetch", fetchMock);

    const firstRuntimeConfig = await fetchRuntimeConfig();
    const secondRuntimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(firstRuntimeConfig).toEqual(mockRuntimeConfig);
    expect(secondRuntimeConfig).toEqual(mockRuntimeConfig);
  });

  it("returns the in-flight promise if a fetch is already in progress", async () => {
    let resolveRuntimeConfigWire: (value: RuntimeConfigWireFixture) => void;
    const runtimeConfigWirePromise = new Promise<RuntimeConfigWireFixture>((resolve) => {
      resolveRuntimeConfigWire = resolve;
    });

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => runtimeConfigWirePromise,
    });
    vi.stubGlobal("fetch", fetchMock);

    const firstPromise = fetchRuntimeConfig();
    const secondPromise = fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveRuntimeConfigWire!(mockRuntimeConfigWire);

    const [firstRuntimeConfig, secondRuntimeConfig] = await Promise.all([firstPromise, secondPromise]);

    expect(firstRuntimeConfig).toEqual(mockRuntimeConfig);
    expect(secondRuntimeConfig).toEqual(mockRuntimeConfig);
  });

  it("returns fallback config when fetch response is not ok", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false });
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "Error",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config when fetch throws a network error", async () => {
    const networkError = new Error("Network Error");
    const fetchMock = vi.fn().mockRejectedValue(networkError);
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "Error",
    });
    const loggedArguments = consoleErrorSpy.mock.calls[0] ?? [];
    expect(loggedArguments).not.toContain(networkError);
    expect(JSON.stringify(loggedArguments)).not.toContain("Network Error");
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config and logs string error type correctly", async () => {
    const fetchMock = vi.fn().mockRejectedValue("String Error");
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "string",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config and logs custom error name correctly", async () => {
    class CustomError extends Error {
      constructor(message: string) {
        super(message);
        this.name = "MyCustomError";
      }
    }
    const fetchMock = vi.fn().mockRejectedValue(new CustomError("Custom error message"));
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "MyCustomError",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config and logs default Error type for error without name", async () => {
    const unnamedError = new Error("Unnamed");
    unnamedError.name = "";
    const fetchMock = vi.fn().mockRejectedValue(unnamedError);
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "Error",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config and logs object error type for null correctly", async () => {
    const fetchMock = vi.fn().mockRejectedValue(null);
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "object",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });

  it("returns fallback config and logs object error type for generic objects", async () => {
    const fetchMock = vi.fn().mockRejectedValue({});
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const runtimeConfig = await fetchRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith("Runtime config fetch failed, using fallback", {
      error_type: "object",
    });
    expect(runtimeConfig).toEqual(fallbackRuntimeConfig);
  });
});
