import { describe, expect, it } from "vitest";
import net from "node:net";

import {
  FULL_PRODUCT_ACCESSIBILITY_CHECK_NAMES,
  FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES,
  FULL_PRODUCT_CRITICAL_INTERACTION_VIEWPORT_NAMES,
  FULL_PRODUCT_DESKTOP_INTERACTION_ROUTE_NAMES,
  FULL_PRODUCT_ROUTES,
  fullProductScreenshotName,
  isTcpPortOpen,
  resolveFullProductBaseUrl,
  resolveFullProductViewportSpecs,
} from "./full-product-ui-smoke.mjs";

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

  it("resolves desktop and mobile responsive capture viewports", () => {
    expect(resolveFullProductViewportSpecs("desktop,mobile").map((viewport) => viewport.name)).toEqual([
      "desktop",
      "mobile",
    ]);
    expect(resolveFullProductViewportSpecs("all").map((viewport) => viewport.name)).toEqual(["desktop", "mobile"]);
    expect(() => resolveFullProductViewportSpecs("tablet")).toThrow("Unknown full-product viewport");
    expect(() => resolveFullProductViewportSpecs("desktop,desktop")).toThrow("Duplicate full-product viewport");
  });

  it("keeps the legacy desktop screenshot names unless multiple viewports are captured", () => {
    const [homeRoute] = FULL_PRODUCT_ROUTES;
    const [desktopViewport, mobileViewport] = resolveFullProductViewportSpecs("desktop,mobile");
    expect(fullProductScreenshotName(homeRoute, desktopViewport, 1)).toBe("home.png");
    expect(fullProductScreenshotName(homeRoute, desktopViewport, 2)).toBe("desktop-home.png");
    expect(fullProductScreenshotName(homeRoute, mobileViewport, 2)).toBe("mobile-home.png");
  });

  it("tracks only buyer-critical interaction routes with existing smoke route names", () => {
    const routeNames = new Set(FULL_PRODUCT_ROUTES.map((route) => route.name));
    expect(FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES).toEqual([
      "mail",
      "search",
      "calendar",
      "tasks",
      "projects",
      "data",
      "ai-hub",
      "security",
      "settings",
    ]);
    expect(FULL_PRODUCT_CRITICAL_INTERACTION_VIEWPORT_NAMES).toEqual(["desktop", "mobile"]);
    expect(FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES.every((routeName) => routeNames.has(routeName))).toBe(true);
    expect(FULL_PRODUCT_DESKTOP_INTERACTION_ROUTE_NAMES).toEqual(FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES);
  });

  it("keeps the full-product accessibility smoke scoped to basic automatable checks", () => {
    expect(FULL_PRODUCT_ACCESSIBILITY_CHECK_NAMES).toEqual([
      "visible-duplicate-id",
      "visible-interactive-accessible-name",
      "keyboard-tab-focus-entry",
    ]);
  });

  it("detects an existing local TCP listener before spawning another dev server", async () => {
    const server = net.createServer();
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));

    try {
      const address = server.address();
      expect(address).not.toBeNull();
      expect(typeof address).not.toBe("string");
      await expect(isTcpPortOpen(new URL(`http://127.0.0.1:${address.port}`))).resolves.toBe(true);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
});
