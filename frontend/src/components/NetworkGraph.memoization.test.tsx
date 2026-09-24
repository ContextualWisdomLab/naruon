/* @vitest-environment jsdom */

import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const { apiGetMock, useIdSpy } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  useIdSpy: vi.fn(),
}));

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  useIdSpy.mockImplementation(actual.useId);
  return {
    ...actual,
    default: actual,
    useId: useIdSpy,
  };
});

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock("vis-network", () => ({
  Network: vi.fn(function MockNetwork() {
    return {
      destroy: vi.fn(),
      fit: vi.fn(),
      moveTo: vi.fn(),
      off: vi.fn(),
      on: vi.fn(),
      selectEdges: vi.fn(),
      selectNodes: vi.fn(),
    };
  }),
}));

import NetworkGraph from "./NetworkGraph";

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("NetworkGraph memoization", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) {
      act(() => root?.unmount());
    }
    root = null;
    container?.remove();
    container = null;
    vi.clearAllMocks();
  });

  it("does not rerender when unrelated parent state changes", async () => {
    apiGetMock.mockResolvedValue({
      nodes: [{ id: "node-1", label: "노드" }],
      edges: [],
    });

    function Parent() {
      const [unrelatedParentState, setUnrelatedParentState] = useState(0);
      return (
        <>
          <button
            type="button"
            onClick={() => setUnrelatedParentState((value) => value + 1)}
          >
            parent:{unrelatedParentState}
          </button>
          <NetworkGraph />
        </>
      );
    }

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<Parent />);
    });
    await flushAsyncWork();

    const childRenderProbeCount = useIdSpy.mock.calls.length;
    expect(childRenderProbeCount).toBeGreaterThan(0);

    const parentButton = container.querySelector("button");
    expect(parentButton?.textContent).toBe("parent:0");

    await act(async () => {
      parentButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(parentButton?.textContent).toBe("parent:1");
    expect(useIdSpy).toHaveBeenCalledTimes(childRenderProbeCount);
  });
});
