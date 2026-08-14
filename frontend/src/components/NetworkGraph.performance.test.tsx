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

describe("NetworkGraph lookup complexity", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  async function renderGraph(body: unknown) {
    onMock.mockClear();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(body))));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkGraph />);
    });
    await flushAsyncWork();
  }

  function registeredHandler(eventName: "selectEdge" | "selectNode") {
    const registration = onMock.mock.calls.find(([name]) => name === eventName);
    expect(registration).toBeDefined();
    return registration?.[1] as
      | ((event: { nodes?: Array<number | string>; edges?: Array<number | string> }) => void)
      | undefined;
  }

  function expectNoNewArrayFind(action: () => void) {
    const findSpy = vi.spyOn(Array.prototype, "find");
    const callsBefore = findSpy.mock.calls.length;
    act(action);
    expect(findSpy.mock.calls.length).toBe(callsBefore);
    findSpy.mockRestore();
  }

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
    await renderGraph({
      nodes: [
        { id: "known-1", label: "Known 1" },
        { id: "known-2", label: "Known 2" },
      ],
      edges: [],
    });

    const selectNodeHandler = registeredHandler("selectNode");
    expect(selectNodeHandler).toBeTypeOf("function");

    expectNoNewArrayFind(() => {
      selectNodeHandler?.({ nodes: ["stale-node"] });
    });

    expect(container?.textContent).toContain("선택된 노드: stale-node");
  });

  it("does not linearly scan edges for a graph edge selection", async () => {
    await renderGraph({
      nodes: [
        { id: "sender-1", label: "Sender" },
        { id: "recipient-1", label: "Recipient" },
      ],
      edges: [{ source: "sender-1", target: "recipient-1", title: "Mail" }],
    });

    const selectEdgeHandler = registeredHandler("selectEdge");
    expect(selectEdgeHandler).toBeTypeOf("function");

    expectNoNewArrayFind(() => {
      selectEdgeHandler?.({ edges: ["relationship-0-sender-1-recipient-1"] });
    });

    expect(container?.textContent).toContain("선택된 관계: Sender -> Recipient (Mail)");
  });

  it("does not linearly scan edges when a relationship option is selected", async () => {
    await renderGraph({
      nodes: [
        { id: "sender-1", label: "Sender" },
        { id: "recipient-1", label: "Recipient" },
      ],
      edges: [{ source: "sender-1", target: "recipient-1", title: "Mail" }],
    });

    const relationshipSelect = container?.querySelector('select[aria-label="관계 선택"]');
    expect(relationshipSelect).toBeInstanceOf(HTMLSelectElement);

    expectNoNewArrayFind(() => {
      if (relationshipSelect instanceof HTMLSelectElement) {
        relationshipSelect.value = "relationship-0-sender-1-recipient-1";
        relationshipSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    expect(container?.textContent).toContain("선택한 관계를 열었습니다.");
  });

  it("does not linearly scan nodes when a node option is selected", async () => {
    await renderGraph({
      nodes: [
        { id: "node-1", label: "Node 1" },
        { id: "node-2", label: "Node 2" },
      ],
      edges: [],
    });

    const nodeSelect = container?.querySelector('select[aria-label="노드 선택"]');
    expect(nodeSelect).toBeInstanceOf(HTMLSelectElement);

    expectNoNewArrayFind(() => {
      if (nodeSelect instanceof HTMLSelectElement) {
        nodeSelect.value = "node-2";
        nodeSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    expect(container?.textContent).toContain("선택된 노드: Node 2");
  });
});
