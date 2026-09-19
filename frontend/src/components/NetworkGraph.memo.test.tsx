/* @vitest-environment jsdom */
import React, { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("vis-network", () => ({
  Network: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(() => new Promise(() => undefined)),
  },
}));

import NetworkGraph from "./NetworkGraph";

describe("NetworkGraph memo boundary", () => {
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

  it("exports the zero-prop graph as a React memo component", () => {
    const memoComponent = NetworkGraph as unknown as { $$typeof?: symbol };

    expect(memoComponent.$$typeof).toBe(Symbol.for("react.memo"));
  });

  it("does not render again when an unrelated parent state changes", async () => {
    // Spy on the internal render function wrapped by memo
    const memoComponent = NetworkGraph as unknown as { type: (...args: any[]) => any };
    const originalRender = memoComponent.type;
    const renderSpy = vi.fn(originalRender);
    memoComponent.type = renderSpy;

    function Parent() {
      const [, setParentVersion] = useState(0);
      return (
        <>
          <button type="button" onClick={() => setParentVersion((value) => value + 1)}>
            update parent
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

    expect(renderSpy).toHaveBeenCalledTimes(1);

    const parentUpdateButton = container.querySelector("button");
    expect(parentUpdateButton).toBeInstanceOf(HTMLButtonElement);

    await act(async () => {
      parentUpdateButton?.click();
    });

    // If memo is working, the component's internal render function is not called again
    expect(renderSpy).toHaveBeenCalledTimes(1);

    // Restore original
    memoComponent.type = originalRender;
  });
});
