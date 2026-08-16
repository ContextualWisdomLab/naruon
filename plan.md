1. Modify `frontend/src/components/NetworkGraph.tsx` to pre-compute an `edgeMap` and a `nodeInstanceMap` using `useMemo`.
   - Add `const edgeMap = useMemo(() => new Map(edges.map(e => [String(e.id), e])), [edges]);`
   - Add `const nodeInstanceMap = useMemo(() => new Map(nodes.map(n => [String(n.id), n])), [nodes]);`
   - Update `selectEdge` inside `useEffect` (line 204) to use `edgeMap.get(String(edgeId))` instead of `edges.find(...)`. Pass `edgeMap` as dependency.
   - Update `handleRelationshipOptionChange` (line 317) to use `edgeMap.get(value)` instead of `edges.find(...)`.
   - Update `handleNodeOptionChange` (line 323) to use `nodeInstanceMap.get(value)` instead of `nodes.find(...)`.

2. Pre-commit check
   - Use `pre_commit_instructions` and follow its instructions to make sure proper testing, verifications, reviews and reflections are done.

3. Submit the change
   - Submit the PR with the title "⚡ Bolt: [O(1) Map lookups in NetworkGraph]".
