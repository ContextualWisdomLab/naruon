/* @vitest-environment jsdom */
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";

const { useIdSpy } = vi.hoisted(() => ({
  useIdSpy: vi.fn(),
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useId: () => {
      useIdSpy();
      return actual.useId();
    },
  };
});

vi.mock("vis-network", () => ({
  Network: vi.fn(),
}));

import NetworkGraph from "./NetworkGraph";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  };
}

async function flushAsyncWork() {
  for (let index = 0; index < 3; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

function ParentHarness() {
  const [parentRenderCount, setParentRenderCount] = useState(0);

  return (
    <>
      <button type="button" onClick={() => setParentRenderCount((value) => value + 1)}>
        parent {parentRenderCount}
      </button>
      <NetworkGraph />
    </>
  );
}

let root: Root | null = null;
let container: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root?.unmount());
  }
  root = null;
  container?.remove();
  container = null;
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("skips NetworkGraph render work when only its parent rerenders", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(jsonResponse({ nodes: [], edges: [] }))),
  );

  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(<ParentHarness />);
  });
  await flushAsyncWork();

  const childRenderCountAfterLoad = useIdSpy.mock.calls.length;
  expect(childRenderCountAfterLoad).toBeGreaterThan(0);

  const parentButton = container.querySelector("button");
  expect(parentButton).toBeInstanceOf(HTMLButtonElement);

  await act(async () => {
    parentButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(parentButton?.textContent).toBe("parent 1");
  expect(useIdSpy).toHaveBeenCalledTimes(childRenderCountAfterLoad);
});
