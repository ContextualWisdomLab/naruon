import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const networkGraphSource = readFileSync(
  fileURLToPath(new URL("./NetworkGraph.tsx", import.meta.url)),
  "utf8",
);

function sourceBetween(startMarker: string, endMarker: string): string {
  const startIndex = networkGraphSource.indexOf(startMarker);
  const endIndex = networkGraphSource.indexOf(endMarker, startIndex);

  expect(startIndex).toBeGreaterThanOrEqual(0);
  expect(endIndex).toBeGreaterThan(startIndex);

  return networkGraphSource.slice(startIndex, endIndex);
}

describe("NetworkGraph node-label lookup", () => {
  it("uses the memoized node map for graph and control selections", () => {
    const graphSelectionHandler = sourceBetween(
      "const selectNode =",
      "const handleEdgeSelection =",
    );
    const controlSelectionHandler = sourceBetween(
      "const selectGraphNode =",
      "const handleSelectFirstRelationship =",
    );

    expect(graphSelectionHandler).toContain("nodeMap.get(String(nodeId))");
    expect(graphSelectionHandler).toContain("?? String(nodeId)");
    expect(graphSelectionHandler).not.toContain("findNodeLabel(");

    expect(controlSelectionHandler).toContain("nodeMap.get(String(node.id))");
    expect(controlSelectionHandler).toContain("?? String(node.id)");
    expect(controlSelectionHandler).not.toContain("findNodeLabel(");
  });
});
