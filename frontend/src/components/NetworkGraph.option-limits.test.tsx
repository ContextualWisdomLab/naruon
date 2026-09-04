/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const destroyMock = vi.fn();

vi.mock("vis-network", () => ({
  Network: vi.fn(function MockNetwork() {
    return {
      destroy: destroyMock,
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

describe("NetworkGraph display limits", () => {
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

  it("renders bounded options while preserving the first five non-empty node labels", async () => {
    const nodes = [
      { id: "blank-1", label: "" },
      { id: "node-1", label: "노드 1" },
      { id: "blank-2", label: "" },
      { id: "node-2", label: "노드 2" },
      { id: "node-3", label: "노드 3" },
      { id: "node-4", label: "노드 4" },
      { id: "node-5", label: "노드 5" },
      { id: "node-6", label: "노드 6" },
      { id: "node-7", label: "노드 7" },
      { id: "node-8", label: "노드 8" },
    ];
    const edges = Array.from({ length: 7 }, (_, index) => ({
      id: `edge-${index + 1}`,
      from: "node-1",
      to: "node-2",
      title: `관계 ${index + 1}`,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({ nodes, edges }))),
    );

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkGraph />);
    });
    await flushAsyncWork();

    const relationshipSelect = container.querySelector<HTMLSelectElement>(
      'select[aria-label="관계 선택"]',
    );
    const nodeSelect = container.querySelector<HTMLSelectElement>(
      'select[aria-label="노드 선택"]',
    );
    const relationshipValues = Array.from(relationshipSelect?.options ?? []).map(
      (option) => option.value,
    );
    const nodeValues = Array.from(nodeSelect?.options ?? []).map(
      (option) => option.value,
    );

    expect(relationshipValues).toEqual([
      "",
      "edge-1",
      "edge-2",
      "edge-3",
      "edge-4",
      "edge-5",
    ]);
    expect(nodeValues).toEqual([
      "",
      "blank-1",
      "node-1",
      "blank-2",
      "node-2",
      "node-3",
      "node-4",
      "node-5",
      "node-6",
    ]);

    const summary = Array.from(container.querySelectorAll("p")).find((element) =>
      element.textContent?.includes("관련 노드:"),
    );
    expect(summary?.textContent).toContain(
      "관련 노드: 노드 1, 노드 2, 노드 3, 노드 4, 노드 5",
    );
    expect(summary?.textContent).not.toContain("노드 6");
  });
});
