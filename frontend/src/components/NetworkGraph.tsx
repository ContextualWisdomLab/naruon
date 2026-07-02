'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';

interface Node {
  id: number | string;
  label: string;
  [key: string]: unknown;
}

interface Edge {
  id?: number | string;
  from: number | string;
  to: number | string;
  [key: string]: unknown;
}

interface ApiEdge {
  from?: number | string;
  to?: number | string;
  source?: number | string;
  target?: number | string;
  [key: string]: unknown;
}

interface NetworkData {
  nodes: Node[];
  edges: ApiEdge[];
}

interface NormalizedNetworkData {
  nodes: Node[];
  edges: Edge[];
}

interface GraphSelectionEvent {
  nodes?: Array<number | string>;
  edges?: Array<number | string>;
}

function textOnlyTooltip(value: unknown): HTMLElement {
  const tooltip = document.createElement('div');
  tooltip.textContent = value == null ? '' : String(value);
  return tooltip;
}

const HTML_TEXT_ESCAPE_PATTERN = /[&<>"']/g;
const HTML_TEXT_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function escapeGraphLabel(value: unknown): string {
  return String(value ?? '').replace(
    HTML_TEXT_ESCAPE_PATTERN,
    (character) => HTML_TEXT_ESCAPES[character] ?? character,
  );
}

function sanitizeGraphItem<T extends Node | Edge>(item: T): T {
  const sanitized = { ...item };

  if (Object.prototype.hasOwnProperty.call(item, 'title')) {
    sanitized.title = textOnlyTooltip(item.title);
  }

  return sanitized;
}

function escapeVisNetworkLabels<T extends Node | Edge>(items: T[]): T[] {
  return items.map((item) => {
    if (!Object.prototype.hasOwnProperty.call(item, 'label')) return item;
    return {
      ...item,
      label: escapeGraphLabel(item.label),
    };
  });
}

function isGraphId(value: unknown): value is number | string {
  return typeof value === 'number' || typeof value === 'string';
}

function graphIdEquals(left: unknown, right: unknown) {
  return isGraphId(left) && isGraphId(right) && String(left) === String(right);
}

function stableEdgeId(edge: Edge, index: number) {
  if (isGraphId(edge.id)) return edge.id;
  return `relationship-${index}-${String(edge.from)}-${String(edge.to)}`;
}

function normalizeEdge(edge: ApiEdge): Edge | null {
  const from = edge.from ?? edge.source;
  const to = edge.to ?? edge.target;

  if (!isGraphId(from) || !isGraphId(to)) return null;

  const rest = { ...edge };
  delete rest.source;
  delete rest.target;
  return {
    ...rest,
    from,
    to,
  };
}

function sanitizeNetworkData(data: NetworkData): NormalizedNetworkData {
  return {
    nodes: data.nodes.map(sanitizeGraphItem),
    edges: data.edges.flatMap((edge, index) => {
      const normalized = normalizeEdge(edge);
      return normalized ? [sanitizeGraphItem({ ...normalized, id: stableEdgeId(normalized, index) })] : [];
    }),
  };
}

function titleText(value: unknown) {
  if (typeof HTMLElement !== 'undefined' && value instanceof HTMLElement) {
    return value.textContent?.trim() ?? '';
  }
  return value == null ? '' : String(value).trim();
}

function findNodeLabel(nodes: Node[], id: number | string) {
  const node = nodes.find((candidate) => graphIdEquals(candidate.id, id));
  return String(node?.label ?? id);
}

function describeEdge(edge: Edge, nodes: Node[]) {
  const fromLabel = findNodeLabel(nodes, edge.from);
  const toLabel = findNodeLabel(nodes, edge.to);
  const title = titleText(edge.title);
  return title ? `${fromLabel} -> ${toLabel} (${title})` : `${fromLabel} -> ${toLabel}`;
}

import { apiClient } from '@/lib/api-client';

export default function NetworkGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGraphDetail, setSelectedGraphDetail] = useState<string | null>(null);
  const [graphActionStatus, setGraphActionStatus] = useState('그래프 준비 완료');

  useEffect(() => {
    apiClient.get<NetworkData>('/api/network/graph')
      .then((data) => {
        const sanitized = sanitizeNetworkData(data);
        setNodes(sanitized.nodes);
        setEdges(sanitized.edges);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load network graph:', err);
        setError('관계 맥락을 불러오지 못했습니다.');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (containerRef.current && nodes.length > 0) {
      const container = containerRef.current;
      const network = new Network(container, {
        nodes: escapeVisNetworkLabels(nodes),
        edges: escapeVisNetworkLabels(edges),
      }, {
        nodes: { shape: 'dot', size: 16 },
        edges: { arrows: 'to' }
      });
      networkRef.current = network;

      const fitGraph = () => {
        network.fit({ animation: false });
      };

      const selectEdge = (edgeId: number | string) => {
        const edge = edges.find((candidate) => graphIdEquals(candidate.id, edgeId));
        if (!edge) return;
        setSelectedGraphDetail(`선택된 관계: ${describeEdge(edge, nodes)}`);
        setGraphActionStatus('그래프에서 관계를 선택했습니다.');
      };

      const selectNode = (nodeId: number | string) => {
        setSelectedGraphDetail(`선택된 노드: ${findNodeLabel(nodes, nodeId)}`);
        setGraphActionStatus('그래프에서 노드를 선택했습니다.');
      };

      const handleEdgeSelection = (event: GraphSelectionEvent) => {
        const edgeId = event.edges?.[0];
        if (isGraphId(edgeId)) selectEdge(edgeId);
      };

      const handleNodeSelection = (event: GraphSelectionEvent) => {
        const nodeId = event.nodes?.[0];
        if (isGraphId(nodeId)) selectNode(nodeId);
      };

      network.on('selectEdge', handleEdgeSelection);
      network.on('selectNode', handleNodeSelection);

      let resizeTimer: ReturnType<typeof setTimeout> | null = null;
      const resizeObserver = typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            if (resizeTimer !== null) {
              clearTimeout(resizeTimer);
            }
            resizeTimer = setTimeout(fitGraph, 50);
          });

      resizeObserver?.observe(container);

      return () => {
        if (resizeTimer !== null) {
          clearTimeout(resizeTimer);
        }
        resizeObserver?.disconnect();
        network.off('selectEdge', handleEdgeSelection);
        network.off('selectNode', handleNodeSelection);
        if (networkRef.current === network) {
          networkRef.current = null;
        }
        network.destroy();
      };
    }
  }, [nodes, edges]);

  const nodeLabels = useMemo(() => {
    return nodes
      .map((node) => String(node.label ?? node.id))
      .filter(Boolean)
      .slice(0, 5);
  }, [nodes]);

  const firstEdge = edges[0] ?? null;

  const handleSelectFirstRelationship = () => {
    if (!firstEdge) return;
    setSelectedGraphDetail(`선택된 관계: ${describeEdge(firstEdge, nodes)}`);
    setGraphActionStatus('첫 관계를 선택했습니다.');
    if (isGraphId(firstEdge.id)) {
      networkRef.current?.selectEdges([firstEdge.id]);
    }
    networkRef.current?.fit({ nodes: [firstEdge.from, firstEdge.to], animation: false });
  };

  const handleZoomGraph = () => {
    networkRef.current?.moveTo({ scale: 1.15, animation: false });
    setGraphActionStatus('그래프 확대 완료');
  };

  const handleFitGraph = () => {
    networkRef.current?.fit({ animation: false });
    setGraphActionStatus('그래프 맞춤 완료');
  };

  if (loading) {
    return <div role="status" aria-live="polite" className="flex h-full min-h-[320px] w-full items-center justify-center text-sm text-muted-foreground sm:min-h-[420px]">관계 그래프를 불러오는 중입니다...</div>;
  }

  if (error) {
    return (
      <div role="alert" aria-live="polite" className="flex h-full min-h-[320px] w-full items-center justify-center p-6 text-center sm:min-h-[420px]">
        <div className="max-w-xs rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">
          <h4 className="font-bold">관계 맥락을 불러오지 못했습니다</h4>
          <p className="mt-2 text-sm leading-6">{error}</p>
        </div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div role="status" aria-live="polite" className="flex h-full min-h-[320px] w-full items-center justify-center p-6 text-center sm:min-h-[420px]">
        <div className="max-w-xs rounded-2xl border border-primary/15 bg-primary/5 p-5">
          <div className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl bg-primary/10 text-2xl" aria-hidden="true">✦</div>
          <h4 className="font-bold text-foreground">관계 데이터가 없습니다</h4>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">메일이 연결되면 사람, 주제, 일정의 흐름을 그래프로 보여줍니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[320px] flex-col sm:min-h-[420px]">
      <div className="border-b border-border bg-card/80 p-4">
        <h4 className="text-sm font-black text-foreground">관계 이해</h4>
        <p className="mt-1 text-xs text-muted-foreground">
          {nodes.length}개 노드와 {edges.length}개 관계가 이 스레드 맥락에 연결되어 있습니다.
        </p>
        <div className="mt-3 rounded-xl border border-primary/10 bg-primary/5 p-3 text-xs text-muted-foreground">
          <p className="font-semibold text-foreground">텍스트 관계 맥락 종합</p>
          <p className="mt-1">
            관련 노드: {nodeLabels.join(', ')}
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSelectFirstRelationship}
            disabled={!firstEdge}
            className="rounded-md border border-primary/25 bg-background px-3 py-2 text-xs font-bold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            첫 관계 보기
          </button>
          <button
            type="button"
            onClick={handleZoomGraph}
            className="rounded-md border border-border bg-background px-3 py-2 text-xs font-bold text-foreground transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            그래프 확대
          </button>
          <button
            type="button"
            onClick={handleFitGraph}
            className="rounded-md border border-border bg-background px-3 py-2 text-xs font-bold text-foreground transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            전체 그래프 맞춤
          </button>
        </div>
        <div aria-live="polite" className="mt-3 rounded-md border border-border bg-background p-3 text-xs text-muted-foreground">
          <p className="font-semibold text-foreground">관계 상세</p>
          <p className="mt-1">
            {selectedGraphDetail ?? '관계를 선택하면 담당자와 일정 흐름을 확인합니다.'}
          </p>
          <p className="mt-1 font-medium text-primary">{graphActionStatus}</p>
        </div>
      </div>
      <div
        ref={containerRef}
        aria-label={`${nodes.length}개 노드와 ${edges.length}개 관계가 있는 관계 맥락`}
        className="min-h-0 flex-1 w-full bg-[radial-gradient(circle_at_center,rgb(37_99_255_/_0.08),transparent_32rem)]"
      />
    </div>
  );
}
