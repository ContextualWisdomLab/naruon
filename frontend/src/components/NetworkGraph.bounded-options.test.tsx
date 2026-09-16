/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const { apiGetMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
}));

const destroyMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

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

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("NetworkGraph bounded option materialization", () => {
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

  it("stops each option iterator at its limit and preserves insertion order", async () => {
    const nodes = Array.from({ length: 15 }, (_, index) => ({
      id: `node-${index}`,
      label: `노드 ${index}`,
    }));
    const edges = Array.from({ length: 10 }, (_, index) => ({
      id: `edge-${index}`,
      from: `node-${index}`,
      to: `node-${index + 1}`,
      title: `관계 ${index}`,
    }));

    apiGetMock.mockResolvedValue({ nodes, edges });

    const originalMapValues = Map.prototype.values;
    const edgeIteratorReadCounts: number[] = [];
    const nodeIteratorReadCounts: number[] = [];

    // Track each iterator independently so repeated renders cannot hide an
    // unbounded iterator behind an aggregate read-count assertion.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Map.prototype.values = function(this: Map<any, any>) {
      const iterator = originalMapValues.call(this);
      const readCounts = this.has("edge-0")
        ? edgeIteratorReadCounts
        : this.has("node-0")
          ? nodeIteratorReadCounts
          : null;
      const readCountIndex = readCounts?.push(0);

      return {
        next: () => {
          if (readCounts && readCountIndex !== undefined) {
            readCounts[readCountIndex - 1] += 1;
          }
          return iterator.next();
        },
        [Symbol.iterator]() {
          return this;
        },
      };
    } as any; // eslint-disable-line @typescript-eslint/no-explicit-any

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    try {
      await act(async () => {
        root?.render(<NetworkGraph />);
      });
      await flushAsyncWork();

      const relationshipSelect = container.querySelector(
        'select[aria-label="관계 선택"]',
      ) as HTMLSelectElement | null;
      const nodeSelect = container.querySelector(
        'select[aria-label="노드 선택"]',
      ) as HTMLSelectElement | null;

      expect(relationshipSelect?.options.length).toBe(6);
      expect(nodeSelect?.options.length).toBe(9);

      const actualEdgeOptions = Array.from(relationshipSelect?.options ?? [])
        .map((option) => option.value)
        .slice(1);
      expect(actualEdgeOptions).toEqual([
        "edge-0",
        "edge-1",
        "edge-2",
        "edge-3",
        "edge-4",
      ]);

      const actualNodeOptions = Array.from(nodeSelect?.options ?? [])
        .map((option) => option.value)
        .slice(1);
      expect(actualNodeOptions).toEqual([
        "node-0",
        "node-1",
        "node-2",
        "node-3",
        "node-4",
        "node-5",
        "node-6",
        "node-7",
      ]);

      expect(edgeIteratorReadCounts.length).toBeGreaterThan(0);
      expect(nodeIteratorReadCounts.length).toBeGreaterThan(0);
      for (const readCount of edgeIteratorReadCounts) {
        expect(readCount).toBeLessThanOrEqual(6);
      }
      for (const readCount of nodeIteratorReadCounts) {
        expect(readCount).toBeLessThanOrEqual(9);
      }
    } finally {
      Map.prototype.values = originalMapValues;
      expect(Map.prototype.values).toBe(originalMapValues);
    }
  });
});
