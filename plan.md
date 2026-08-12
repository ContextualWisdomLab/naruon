1. Modify `frontend/src/components/NetworkGraph.tsx` to replace `O(N)` `.find()` lookups with `O(1)` map lookups:
   - Apply edits via `run_in_bash_session` running `sed` or directly use `replace_with_git_merge_diff` on `frontend/src/components/NetworkGraph.tsx` with the following changes.
   - Insert map initializations right after the `nodeMap` block:
   <<<<<<< SEARCH
    return map;
  }, [nodes]);

  useEffect(() => {
=======
    return map;
  }, [nodes]);

  const edgeObjectMap = useMemo(() => {
    const map = new Map<string, Edge>();
    for (const edge of edges) {
      if (edge.id != null) {
        map.set(String(edge.id), edge);
      }
    }
    return map;
  }, [edges]);

  const nodeObjectMap = useMemo(() => {
    const map = new Map<string, Node>();
    for (const node of nodes) {
      map.set(String(node.id), node);
    }
    return map;
  }, [nodes]);

  useEffect(() => {
>>>>>>> REPLACE

   - Update `selectEdge` and `selectNode` lookups:
   <<<<<<< SEARCH
      const selectEdge = (edgeId: number | string) => {
        const edge = edges.find((candidate) => graphIdEquals(candidate.id, edgeId));
        if (!edge) return;
        setRelationshipOptionId(String(edge.id));
        setNodeOptionId('');
        setSelectedGraphDetail(`선택된 관계: ${describeEdge(edge, nodes, nodeMap)}`);
        setGraphActionStatus('그래프에서 관계를 선택했습니다.');
      };

      const selectNode = (nodeId: number | string) => {
        setRelationshipOptionId('');
        setNodeOptionId(String(nodeId));
        setSelectedGraphDetail(`선택된 노드: ${findNodeLabel(nodes, nodeId)}`);
        setGraphActionStatus('그래프에서 노드를 선택했습니다.');
      };
=======
      const selectEdge = (edgeId: number | string) => {
        const edge = edgeObjectMap.get(String(edgeId));
        if (!edge) return;
        setRelationshipOptionId(String(edge.id));
        setNodeOptionId('');
        setSelectedGraphDetail(`선택된 관계: ${describeEdge(edge, nodes, nodeMap)}`);
        setGraphActionStatus('그래프에서 관계를 선택했습니다.');
      };

      const selectNode = (nodeId: number | string) => {
        setRelationshipOptionId('');
        setNodeOptionId(String(nodeId));
        setSelectedGraphDetail(`선택된 노드: ${nodeMap.get(String(nodeId)) ?? String(nodeId)}`);
        setGraphActionStatus('그래프에서 노드를 선택했습니다.');
      };
>>>>>>> REPLACE

   - Update `selectGraphNode` lookups:
   <<<<<<< SEARCH
  const selectGraphNode = (node: Node, status: string) => {
    if (!isGraphId(node.id)) return;
    setRelationshipOptionId('');
    setNodeOptionId(String(node.id));
    setSelectedGraphDetail(`선택된 노드: ${findNodeLabel(nodes, node.id)}`);
    setGraphActionStatus(status);
    networkRef.current?.selectNodes?.([node.id]);
    networkRef.current?.fit?.({ nodes: [node.id], animation: false });
  };
=======
  const selectGraphNode = (node: Node, status: string) => {
    if (!isGraphId(node.id)) return;
    setRelationshipOptionId('');
    setNodeOptionId(String(node.id));
    setSelectedGraphDetail(`선택된 노드: ${nodeMap.get(String(node.id)) ?? String(node.id)}`);
    setGraphActionStatus(status);
    networkRef.current?.selectNodes?.([node.id]);
    networkRef.current?.fit?.({ nodes: [node.id], animation: false });
  };
>>>>>>> REPLACE

   - Update `handleRelationshipOptionChange` and `handleNodeOptionChange`:
   <<<<<<< SEARCH
  const handleRelationshipOptionChange = (value: string) => {
    const edge = edges.find((candidate) => String(candidate.id) === value);
    if (!edge) return;
    selectRelationship(edge, '선택한 관계를 열었습니다.');
  };

  const handleNodeOptionChange = (value: string) => {
    const node = nodes.find((candidate) => String(candidate.id) === value);
    if (!node) return;
    selectGraphNode(node, '선택한 노드를 열었습니다.');
  };
=======
  const handleRelationshipOptionChange = (value: string) => {
    const edge = edgeObjectMap.get(value);
    if (!edge) return;
    selectRelationship(edge, '선택한 관계를 열었습니다.');
  };

  const handleNodeOptionChange = (value: string) => {
    const node = nodeObjectMap.get(value);
    if (!node) return;
    selectGraphNode(node, '선택한 노드를 열었습니다.');
  };
>>>>>>> REPLACE

2. Format the code by running `run_in_bash_session` with `cd frontend && pnpm run lint --fix`.
3. Use the `read_file` tool on `frontend/src/components/NetworkGraph.tsx` to confirm changes.
4. Test by running `run_in_bash_session` with `cd frontend && pnpm run test && pnpm run build && pnpm run test:e2e`.
5. Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
6. Submit PR using the `submit` tool with exactly:
   - branch_name: "perf-optimize-network-graph-lookups"
   - commit_message: "⚡ Bolt: 네트워크 그래프 O(N) 탐색을 O(1) 맵 탐색으로 최적화"
   - title: "⚡ Bolt: [네트워크 그래프 관계 및 노드 선택 O(1) 맵 최적화]"
   - description: """
💡 What
- `NetworkGraph.tsx`에서 노드/관계 선택 및 레이블 렌더링 시 발생하는 `edges.find()`와 `nodes.find()`(`O(N)`)를 `useMemo`로 사전 계산된 `Map.get()`(`O(1)`)으로 대체했습니다.

🎯 Why
- 복잡한 네트워크 그래프를 렌더링하고 유저 인터랙션 시, 노드나 관계의 개수가 많아질 경우 매번 배열 전체를 순회(`O(N)`)하게 되어 불필요한 연산 오버헤드와 프레임 저하가 발생할 수 있습니다. 맵을 사용하면 이 병목을 해결할 수 있습니다.

📊 Impact
- 그래프 노드 및 엣지 선택 이벤트 발생 시 탐색 복잡도를 O(N)에서 O(1)로 줄여 빠른 UI 응답성을 제공합니다.

🔬 Measurement
- `pnpm test` 및 `pnpm run test:e2e` 통과 여부 확인을 통해 정상 작동을 검증했습니다.
"""
