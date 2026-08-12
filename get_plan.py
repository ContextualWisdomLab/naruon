import sys

content = """
1. **Modify `frontend/src/components/NetworkGraph.tsx` to replace `O(N)` `.find()` array lookups with `O(1)` map lookups**:
   - The memory entry `2025-02-12 - Replaced O(N) Array Lookups with O(1) Maps in Loops` explicitly states: "When generating derived UI state in useMemo that joins separate data arrays (like graph edges referencing node IDs), calling helper functions that use `Array.prototype.find()` for every item creates an `O(M * N)` bottleneck. Action: When a loop needs to repeatedly look up related items from another array by ID, pre-compute an `O(N)` `Map` before the loop and use `map.get()` for `O(1)` lookups instead of inline array `.find()` calls."
   - The current `NetworkGraph.tsx` component iterates through `edges` via `.map()` inside a `useMemo` for `relationshipOptions` and calls `describeEdge`.
   - `describeEdge` uses `nodes.find` if `nodeMap` is not fully covering or when directly finding nodes inside `findNodeLabel`. Wait, looking closer: `describeEdge` takes `nodeMap` and looks up nodes: `nodeMap.get(String(edge.from))`. It correctly uses the map if available.
   - However, what about `findNodeLabel(nodes, nodeId)`? It uses `nodes.find()`. `findNodeLabel` is called in `selectNode` and `selectGraphNode` for individual node selections. Is there a loop?
   - Wait, `nodeMap` is passed to `describeEdge`. `describeEdge` is called in a loop in `relationshipOptions`:
   `edges.slice(0, 5).map((edge, index) => ({ edge, id: String(edge.id), label: \`관계 \${index + 1}: \${describeEdge(edge, nodes, nodeMap)}\` }))`
   This is only 5 items, not an issue.

Wait, are there other places in the codebase? Let's check `CalendarMonthView.tsx` again or search for `Map` pre-computation.
"""
print(content)
