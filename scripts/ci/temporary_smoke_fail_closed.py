from pathlib import Path

source_path = Path("frontend/scripts/full-product-ui-smoke.mjs")
test_path = Path("frontend/scripts/full-product-ui-smoke.test.mjs")
source = source_path.read_text(encoding="utf-8")
tests = test_path.read_text(encoding="utf-8")

replacements = [
    (
        "async function installRoutes(page) {",
        "async function installRoutes(page, unhandledApiRequests = new Set()) {",
    ),
    (
        "    return routeJson(route, { ok: true });\n",
        "    unhandledApiRequests.add(`${request.method()} ${endpoint}`);\n"
        "    return route.abort(\"failed\");\n",
    ),
    (
        "  const consoleErrors = [];\n  let screenshotArtifact;",
        "  const consoleErrors = [];\n  const unhandledApiRequests = new Set();\n  let screenshotArtifact;",
    ),
    (
        "    await installRoutes(page);",
        "    await installRoutes(page, unhandledApiRequests);",
    ),
    (
        "  if (consoleErrors.length > 0) {\n    throw new Error(`Route ${routeSpec.path} emitted console errors:\\n${consoleErrors.join(\"\\n\")}`);\n  }\n  return { screenshotPath: screenshotArtifact, interactionEvidence, accessibilityEvidence };",
        "  if (unhandledApiRequests.size > 0) {\n"
        "    throw new Error(\n"
        "      `Route ${routeSpec.path} requested unregistered mocked APIs:\\n${[...unhandledApiRequests].join(\"\\n\")}`,\n"
        "    );\n"
        "  }\n"
        "  if (consoleErrors.length > 0) {\n"
        "    throw new Error(`Route ${routeSpec.path} emitted console errors:\\n${consoleErrors.join(\"\\n\")}`);\n"
        "  }\n"
        "  return { screenshotPath: screenshotArtifact, interactionEvidence, accessibilityEvidence };",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected one source match, found {count}: {old[:80]!r}")
    source = source.replace(old, new, 1)

marker = 'describe("route smoke late browser errors", () => {'
if tests.count(marker) != 1:
    raise SystemExit("route-smoke test insertion marker changed")

regression = r'''describe("route smoke API fixture boundary", () => {
  it("fails closed when the product requests an unregistered mocked API", async () => {
    let apiRouteHandler;
    let abortReason;
    let evaluationCount = 0;
    const page = {
      on: () => {},
      route: async (pattern, handler) => {
        if (pattern === "**/api/**") apiRouteHandler = handler;
      },
      goto: async () => {
        expect(apiRouteHandler).toBeTypeOf("function");
        await apiRouteHandler({
          request: () => ({
            url: () => "http://127.0.0.1:3001/api/unregistered-smoke-endpoint",
            method: () => "GET",
          }),
          abort: async (reason) => {
            abortReason = reason;
          },
        });
      },
      waitForLoadState: async () => {},
      locator: () => ({ waitFor: async () => {}, innerText: async () => "Naruon" }),
      evaluate: async () => {
        evaluationCount += 1;
        if (evaluationCount === 1) return { duplicateIds: [], unnamedInteractive: [] };
        return { tagName: "BUTTON" };
      },
      keyboard: { press: async () => {} },
      screenshot: async () => {},
      close: async () => {},
    };

    await expect(runRouteSmoke(
      { newPage: async () => page },
      FULL_PRODUCT_ROUTES[0],
      { name: "desktop", width: 1440, height: 1024 },
      1,
      path.join(tmpdir(), "naruon-full-product-smoke-unit"),
    )).rejects.toThrow("GET /api/unregistered-smoke-endpoint");
    expect(abortReason).toBe("failed");
  });
});

'''
tests = tests.replace(marker, regression + marker, 1)

source_path.write_text(source, encoding="utf-8")
test_path.write_text(tests, encoding="utf-8")
