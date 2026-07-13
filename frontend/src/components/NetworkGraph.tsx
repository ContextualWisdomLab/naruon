'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';

interface Node {
  id: number | string;
  label: string;
  [key: string]: unknown;
}

interface Edge {
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
    edges: data.edges.flatMap((edge) => {
      const normalized = normalizeEdge(edge);
      return normalized ? [sanitizeGraphItem(normalized)] : [];
    }),
  };
}

import { apiClient } from '@/lib/api-client';

export default function NetworkGraph() {
  const containerRef = useRef<HTMLDivElement>(null);

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

      const fitGraph = () => {
        network.fit({ animation: false });
      };

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
      </div>
      <div
        ref={containerRef}
        aria-label={`${nodes.length}개 노드와 ${edges.length}개 관계가 있는 관계 맥락`}
        className="min-h-0 flex-1 w-full bg-[radial-gradient(circle_at_center,rgb(37_99_255_/_0.08),transparent_32rem)]"
      />
    </div>
  );
}
