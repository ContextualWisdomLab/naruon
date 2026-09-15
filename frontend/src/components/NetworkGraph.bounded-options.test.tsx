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

  it("instrumented iterable/Map fixture proves iteration stops early and preserves insertion order", async () => {
    // Generate items beyond the limits to ensure it truncates correctly
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
    let edgeIterationCount = 0;
    let nodeIterationCount = 0;

    // Instrument Map.prototype.values to count iterations for our specific edges and nodes
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Map.prototype.values = function(this: Map<any, any>) {
      const iterator = originalMapValues.call(this);
      const isEdgeMap = this.has('edge-0');
      const isNodeMap = this.has('node-0');

      return {
        next: () => {
          if (isEdgeMap) edgeIterationCount++;
          if (isNodeMap) nodeIterationCount++;
          return iterator.next();
        },
        [Symbol.iterator]() { return this; }
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

      // Verify option caps still apply (1 default + limit)
      expect(relationshipSelect?.options.length).toBe(6);
      expect(nodeSelect?.options.length).toBe(9);

      // Verify exact insertion order preservation
      const actualEdgeOptions = Array.from(relationshipSelect?.options ?? []).map(o => o.value).slice(1);
      expect(actualEdgeOptions).toEqual(['edge-0', 'edge-1', 'edge-2', 'edge-3', 'edge-4']);

      const actualNodeOptions = Array.from(nodeSelect?.options ?? []).map(o => o.value).slice(1);
      expect(actualNodeOptions).toEqual(['node-0', 'node-1', 'node-2', 'node-3', 'node-4', 'node-5', 'node-6', 'node-7']);

      // A 'break' after adding the Nth item means it evaluated `next()` N times for the values,
      // plus potentially one more depending on React's render lifecycle / strict mode.
      // We strictly assert <= 6 for edges (limit 5) and <= 9 for nodes (limit 8).
      expect(edgeIterationCount).toBeLessThanOrEqual(6);
      expect(nodeIterationCount).toBeLessThanOrEqual(9);
    } finally {
      Map.prototype.values = originalMapValues;
      expect(Map.prototype.values).toBe(originalMapValues);
    }
  });
});
