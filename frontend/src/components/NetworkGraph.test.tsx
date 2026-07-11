/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const destroyMock = vi.fn();
const fitMock = vi.fn();

vi.mock("vis-network", () => ({
  Network: vi.fn(function MockNetwork() {
    return { destroy: destroyMock, fit: fitMock };
  }),
}));

import { Network } from "vis-network";

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

describe("NetworkGraph", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;
  let resizeObserverCallback: ResizeObserverCallback | null = null;

  class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();

    constructor(callback: ResizeObserverCallback) {
      resizeObserverCallback = callback;
    }
  }

  async function renderGraph() {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkGraph />);
    });
  }

  function getMountedContainer(): HTMLDivElement {
    if (!container) {
      throw new Error("NetworkGraph test container was not mounted.");
    }
    return container;
  }

  afterEach(() => {
    if (root) {
      act(() => root?.unmount());
    }
    root = null;
    container?.remove();
    container = null;
    resizeObserverCallback = null;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("announces an empty graph as a polite status region", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [],
          edges: [],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderGraph();
    await flushAsyncWork();

    const status = container?.querySelector('[role="status"][aria-live="polite"]');
    expect(status?.textContent).toContain("관계 데이터가 없습니다");
    expect(Network).not.toHaveBeenCalled();
  });

  it("announces graph loading failures as a polite alert", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = vi.fn(() => Promise.reject(new Error("network unavailable")));
    vi.stubGlobal("fetch", fetchMock);

    try {
      await renderGraph();
      await flushAsyncWork();

      const alert = container?.querySelector('[role="alert"][aria-live="polite"]');
      expect(alert?.textContent).toContain("관계 맥락을 불러오지 못했습니다");
      expect(Network).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
    }
  });

  it("coerces graph tooltip titles to text-only DOM nodes before vis-network renders them", async () => {
    const maliciousTitle = '<img src=x onerror="globalThis.__xss = true">';
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [{ id: "n1", label: "Node", title: maliciousTitle }],
          edges: [{ from: "n1", to: "n1", title: maliciousTitle }],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderGraph();
    await flushAsyncWork();

    expect(Network).toHaveBeenCalledTimes(1);
    const networkData = vi.mocked(Network).mock.calls[0]?.[1];
    const nodes = Array.isArray(networkData?.nodes) ? networkData.nodes : [];
    const edges = Array.isArray(networkData?.edges) ? networkData.edges : [];
    const nodeTitle = nodes[0]?.title;
    const edgeTitle = edges[0]?.title;

    expect(nodeTitle).toBeInstanceOf(HTMLElement);
    expect(edgeTitle).toBeInstanceOf(HTMLElement);
    expect((nodeTitle as HTMLElement).textContent).toBe(maliciousTitle);
    expect((edgeTitle as HTMLElement).textContent).toBe(maliciousTitle);
    expect((nodeTitle as HTMLElement).innerHTML).not.toContain("<img");
    expect((edgeTitle as HTMLElement).innerHTML).not.toContain("<img");
  });

  it("escapes graph labels before passing them to vis-network while keeping React text plain", async () => {
    const maliciousLabel = '<img src=x onerror="globalThis.__xss = true">';
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [{ id: "n1", label: maliciousLabel, title: "Node" }],
          edges: [{ from: "n1", to: "n1" }],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderGraph();
    await flushAsyncWork();

    const mountedContainer = getMountedContainer();
    expect(Network).toHaveBeenCalledTimes(1);
    const networkData = vi.mocked(Network).mock.calls[0]?.[1];
    const nodes = Array.isArray(networkData?.nodes) ? networkData.nodes : [];

    expect(nodes[0]?.label).toBe("&lt;img src=x onerror=&quot;globalThis.__xss = true&quot;&gt;");
    expect(nodes[0]?.label).not.toContain("<img");
    expect(mountedContainer.textContent).toContain(maliciousLabel);
    expect(mountedContainer.innerHTML).not.toContain("<img");
  });

  it("renders a Korean text fallback for graph relationships", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [{ id: "person-1", label: "김지현", title: "PM" }],
          edges: [{ source: "person-1", target: "person-1", title: "관련 메일" }],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderGraph();
    await flushAsyncWork();

    const mountedContainer = getMountedContainer();
    expect(mountedContainer.textContent).toContain("관계 이해");
    expect(mountedContainer.textContent).toContain("1개 노드");
    expect(mountedContainer.textContent).toContain("1개 관계");
    expect(mountedContainer.textContent).toContain("김지현");
    expect(mountedContainer.textContent).not.toContain("nodes and");
  });

  it("normalizes backend source target edges before rendering the graph", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [
            { id: "sender-1", label: "김지현", title: "PM" },
            { id: "recipient-1", label: "사용자", title: "Owner" },
          ],
          edges: [{ source: "sender-1", target: "recipient-1", weight: 2, title: "메일 2건" }],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderGraph();
    await flushAsyncWork();

    expect(Network).toHaveBeenCalledTimes(1);
    const networkData = vi.mocked(Network).mock.calls[0]?.[1];
    const edges = Array.isArray(networkData?.edges) ? networkData.edges : [];
    expect(edges[0]).toMatchObject({ from: "sender-1", to: "recipient-1", weight: 2 });
    expect(edges[0]).not.toHaveProperty("source");
    expect(edges[0]).not.toHaveProperty("target");
  });

  it("refits the graph when the viewport changes", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          nodes: [{ id: "person-1", label: "김지현", title: "PM" }],
          edges: [{ from: "person-1", to: "person-1", title: "관련 메일" }],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("ResizeObserver", MockResizeObserver);

    await renderGraph();
    await flushAsyncWork();

    expect(Network).toHaveBeenCalledTimes(1);
    expect(resizeObserverCallback).not.toBeNull();
    expect(fitMock).toHaveBeenCalledTimes(0);

    vi.useFakeTimers();
    try {
      await act(async () => {
        resizeObserverCallback?.([] as ResizeObserverEntry[], {} as ResizeObserver);
        vi.advanceTimersByTime(49);
      });

      expect(fitMock).toHaveBeenCalledTimes(0);

      await act(async () => {
        vi.advanceTimersByTime(1);
      });

      expect(fitMock).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
