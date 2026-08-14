/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const destroyMock = vi.fn();
const fitMock = vi.fn();
const offMock = vi.fn();
const onMock = vi.fn();

vi.mock("vis-network", () => ({
  Network: vi.fn(function MockNetwork() {
    return {
      destroy: destroyMock,
      fit: fitMock,
      off: offMock,
      on: onMock,
    };
  }),
}));

import NetworkGraph from "./NetworkGraph";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  };
}

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("NetworkGraph node lookup complexity", () => {
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
    vi.restoreAllMocks();
  });

  it("does not fall back to a linear node scan for a stale graph selection", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [
            { id: "known-1", label: "Known 1" },
            { id: "known-2", label: "Known 2" },
          ],
          edges: [],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkGraph />);
    });
    await flushAsyncWork();

    const selectNodeRegistration = onMock.mock.calls.find(([eventName]) => eventName === "selectNode");
    expect(selectNodeRegistration).toBeDefined();
    const selectNodeHandler = selectNodeRegistration?.[1] as
      | ((event: { nodes?: Array<number | string> }) => void)
      | undefined;
    expect(selectNodeHandler).toBeTypeOf("function");

    const findSpy = vi.spyOn(Array.prototype, "find");
    const findCallsBeforeSelection = findSpy.mock.calls.length;

    act(() => {
      selectNodeHandler?.({ nodes: ["stale-node"] });
    });

    expect(findSpy.mock.calls.length).toBe(findCallsBeforeSelection);
    expect(container.textContent).toContain("선택된 노드: stale-node");
  });
});
