import { useEffect, useState } from 'react';

import { apiClient } from '@/lib/api-client';

type RelationType = 'enables' | 'conflicts' | 'unrelated';
type VisibilityScope = 'personal' | 'organization';

interface EventSource {
  event_uid: string;
  title: string;
  status_code: string;
  starts_at: string;
  ends_at: string;
  email_id: number | null;
  document_id: string | null;
  citations: Array<{ segment_uid: string; label: string; excerpt: string }>;
}

interface EventRelation {
  relation_uid: string;
  relation_type: RelationType;
  enabler_event_uid: string | null;
  confidence: number;
  corrected: boolean;
  source: EventSource;
  target: EventSource;
}

interface CalendarSourceList {
  items: Array<{ document_id: string; visibility_scope: VisibilityScope; created_at: string }>;
  next_cursor: string | null;
}

interface RelationPage {
  items: EventRelation[];
  next_cursor: string | null;
}

interface ReconcilePage {
  next_cursor: string | null;
}

type VisibleRelation = EventRelation & { scope: VisibilityScope };

const scopes: VisibilityScope[] = ['personal', 'organization'];
const labels: Record<RelationType, string> = {
  enables: '진행에 도움',
  conflicts: '시간 충돌',
  unrelated: '별개 일정',
};
const statusLabels: Record<string, string> = {
  confirmed: '확정',
  tentative: '잠정',
  desired: '희망',
  cancelled: '취소',
};

function EventEvidence({ event }: { event: EventSource }) {
  const time = new Date(event.starts_at).toLocaleString('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
  return (
    <div className="min-w-0">
      <p className="truncate font-semibold">{event.title}</p>
      <p className="text-xs text-muted-foreground">{time}</p>
      <p className="text-xs text-muted-foreground">원본 상태: {statusLabels[event.status_code] ?? '확인 필요'}</p>
      {event.citations.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground" aria-label={`${event.title} 원본 근거`}>
          {event.citations.map((citation) => (
            <li key={citation.segment_uid}><span className="font-semibold">{citation.label}</span>: {citation.excerpt}</li>
          ))}
        </ul>
      ) : null}
      {event.email_id !== null ? (
        <a
          href={`/mail?id=${encodeURIComponent(event.email_id)}`}
          className="text-xs font-semibold text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          원본 메일 보기
        </a>
      ) : null}
      {event.document_id !== null ? (
        <a
          href={`/api/events/sources/${encodeURIComponent(event.document_id)}`}
          className="text-xs font-semibold text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          원본 일정 파일 보기
        </a>
      ) : null}
    </div>
  );
}

export function EventRelationsSection() {
  const [relations, setRelations] = useState<VisibleRelation[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [retryKey, setRetryKey] = useState(0);
  const [savingUid, setSavingUid] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [sources, setSources] = useState<CalendarSourceList['items']>([]);
  const [sourceCursor, setSourceCursor] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState(false);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [relationCursors, setRelationCursors] = useState<Record<VisibilityScope, string | null>>({ personal: null, organization: null });
  const [loadingMoreRelations, setLoadingMoreRelations] = useState(false);
  const [relationPageError, setRelationPageError] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all(
      scopes.map(async (scope) => {
        for (const mode of ['dependencies', 'overlaps'] as const) {
          let cursor: string | null = null;
          do {
            const page: ReconcilePage = await apiClient.post<ReconcilePage>(
              `/api/events/relations/reconcile?visibility_scope=${scope}&mode=${mode}${cursor ? `&after=${encodeURIComponent(cursor)}` : ''}`,
              {},
            );
            cursor = page.next_cursor ?? null;
          } while (cursor !== null && active);
        }
        if (!active) return { scope, page: { items: [], next_cursor: null } };
        const page = await apiClient.get<RelationPage>(
          `/api/events/relations?visibility_scope=${scope}`,
        );
        return { scope, page };
      }),
    )
      .then((pages) => {
        if (!active) return;
        setRelations(pages.flatMap(({ scope, page }) => page.items.map((item) => ({ ...item, scope }))));
        setRelationCursors(Object.fromEntries(pages.map(({ scope, page }) => [scope, page.next_cursor])) as Record<VisibilityScope, string | null>);
        setRelationPageError(false);
        setStatus('ready');
      })
      .catch(() => {
        if (active) setStatus('error');
      });
    return () => { active = false; };
  }, [retryKey]);

  useEffect(() => {
    let active = true;
    void apiClient.get<CalendarSourceList>('/api/events/sources')
      .then((page) => {
        if (!active) return;
        setSources(page.items);
        setSourceCursor(page.next_cursor);
        setSourceError(false);
      })
      .catch(() => { if (active) setSourceError(true); });
    return () => { active = false; };
  }, [retryKey]);

  async function correct(relation: VisibleRelation, relationType: RelationType, enablerEventUid: string | null = null) {
    if (savingUid !== null || (relation.relation_type === relationType && relation.enabler_event_uid === enablerEventUid)) return;
    setSavingUid(relation.relation_uid);
    setSaveError(null);
    try {
      const next = await apiClient.patch<EventRelation>(
        `/api/events/relations/${encodeURIComponent(relation.relation_uid)}?visibility_scope=${relation.scope}`,
        { relation_type: relationType, enabler_event_uid: enablerEventUid },
      );
      setRelations((current) => current.map((item) => (
        item.relation_uid === next.relation_uid ? { ...next, scope: item.scope } : item
      )));
    } catch {
      setSaveError(relation.relation_uid);
    } finally {
      setSavingUid(null);
    }
  }

  async function importIcs(file: File) {
    setImporting(true);
    setImportResult(null);
    try {
      if (file.size > 262_144) throw new Error('Calendar file too large');
      const icsText = await file.text();
      const events = await apiClient.post<EventSource[]>('/api/events/sources/ics', {
        ics_text: icsText,
        visibility_scope: 'personal',
      });
      setImportResult(`일정 ${events.length}개를 가져왔습니다.`);
      setStatus('loading');
      setRetryKey((key) => key + 1);
    } catch {
      setImportResult('일정 파일을 가져오지 못했습니다. 파일을 확인하고 다시 시도해 주세요.');
    } finally {
      setImporting(false);
    }
  }

  async function loadMoreSources() {
    if (!sourceCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await apiClient.get<CalendarSourceList>(
        `/api/events/sources?after=${encodeURIComponent(sourceCursor)}`,
      );
      setSources((current) => [...current, ...page.items]);
      setSourceCursor(page.next_cursor);
      setSourceError(false);
    } catch {
      setSourceError(true);
    } finally {
      setLoadingMore(false);
    }
  }

  async function loadMoreRelations() {
    if (loadingMoreRelations) return;
    setLoadingMoreRelations(true);
    try {
      const pages = await Promise.all(scopes.filter((scope) => relationCursors[scope]).map(async (scope) => {
        const page = await apiClient.get<RelationPage>(
          `/api/events/relations?visibility_scope=${scope}&after=${encodeURIComponent(relationCursors[scope]!)}`,
        );
        return { scope, page };
      }));
      setRelations((current) => [...current, ...pages.flatMap(({ scope, page }) => page.items.map((item) => ({ ...item, scope })))]);
      setRelationCursors((current) => ({ ...current, ...Object.fromEntries(pages.map(({ scope, page }) => [scope, page.next_cursor])) }));
      setRelationPageError(false);
    } catch {
      setRelationPageError(true);
    } finally {
      setLoadingMoreRelations(false);
    }
  }

  async function removeSource(documentId: string) {
    if (!window.confirm('이 일정 파일과 연결된 일정, 수정 기록을 삭제할까요?')) return;
    setDeletingSource(documentId);
    try {
      await apiClient.delete(`/api/events/sources/${encodeURIComponent(documentId)}`);
      setImportResult('일정 파일을 삭제했습니다.');
      setStatus('loading');
      setRetryKey((key) => key + 1);
    } catch {
      setSourceError(true);
    } finally {
      setDeletingSource(null);
    }
  }

  return (
    <section aria-labelledby="event-relations-heading" className="border border-border bg-card p-4 text-sm">
      <h2 id="event-relations-heading" className="text-base font-bold">일정 관계</h2>
      <p className="mt-1 text-muted-foreground">초대장과 일정 파일에서 일정의 시간과 선행 관계를 확인했습니다. 연결이 틀리면 아래에서 바로 고칠 수 있습니다.</p>
      <label className="mt-3 block text-sm font-semibold">
        내 일정 파일 가져오기 (.ics)
        <input
          type="file"
          accept=".ics,text/calendar"
          disabled={importing}
          className="mt-1 block w-full text-xs"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = '';
            if (file) void importIcs(file);
          }}
        />
      </label>
      {importing ? <p role="status" className="mt-2">일정 파일을 가져오는 중입니다.</p> : null}
      {importResult ? <p role="status" className="mt-2">{importResult}</p> : null}
      {sources.length > 0 ? (
        <div className="mt-3">
          <h3 className="font-semibold">가져온 일정 파일</h3>
          <ul className="mt-1 space-y-1">
            {sources.map((source) => (
              <li key={source.document_id} className="flex flex-wrap items-center gap-2 text-xs">
                <a href={`/api/events/sources/${encodeURIComponent(source.document_id)}`} className="text-primary underline-offset-2 hover:underline">{new Date(source.created_at).toLocaleString('ko-KR')} 일정 파일</a>
                <span className="text-muted-foreground">{source.visibility_scope === 'personal' ? '개인' : '조직'}</span>
                <button type="button" disabled={deletingSource !== null} onClick={() => void removeSource(source.document_id)} className="text-destructive underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60">삭제</button>
              </li>
            ))}
          </ul>
          {sourceCursor ? <button type="button" disabled={loadingMore} onClick={() => void loadMoreSources()} className="mt-2 text-xs font-semibold text-primary underline-offset-2 hover:underline disabled:opacity-60">더 보기</button> : null}
        </div>
      ) : null}
      {sourceError ? <p role="alert" className="mt-2 text-destructive">일정 파일 목록을 처리하지 못했습니다. <button type="button" className="underline" onClick={() => setRetryKey((key) => key + 1)}>다시 시도</button></p> : null}
      {status === 'loading' ? <p role="status" className="mt-4">일정 관계를 확인하는 중입니다.</p> : null}
      {status === 'error' ? (
        <div className="mt-4" role="alert">
          <p>일정 관계를 불러오지 못했습니다.</p>
          <button type="button" className="mt-2 font-semibold text-primary underline" onClick={() => { setStatus('loading'); setRetryKey((key) => key + 1); }}>다시 시도</button>
        </div>
      ) : null}
      {status === 'ready' && relations.length === 0 ? (
        <p className="mt-4 text-muted-foreground">확인된 일정 관계가 아직 없습니다.</p>
      ) : null}
      {status === 'ready' ? relations.map((relation) => (
        <article key={relation.relation_uid} className="mt-4 border-t border-border pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">{relation.scope === 'personal' ? '개인' : '조직'}</span>
            <span className="font-semibold">{labels[relation.relation_type]}</span>
            <span className="text-xs text-muted-foreground">{relation.corrected ? '직접 수정함' : relation.relation_type === 'enables' ? '원본 일정의 선행 관계 기준' : '원본 일정 시간 기준'}</span>
          </div>
          {relation.relation_type === 'enables' && relation.enabler_event_uid ? (
            <p className="mt-2 text-xs text-muted-foreground">{relation.enabler_event_uid === relation.source.event_uid ? relation.source.title : relation.target.title} → {relation.enabler_event_uid === relation.source.event_uid ? relation.target.title : relation.source.title}</p>
          ) : null}
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <EventEvidence event={relation.source} />
            <EventEvidence event={relation.target} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="일정 관계 수정">
            {(['conflicts', 'unrelated'] as const).map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={relation.relation_type === type}
                disabled={savingUid !== null}
                onClick={() => void correct(relation, type)}
                className={`border px-3 py-1.5 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60 ${relation.relation_type === type ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-secondary'}`}
              >
                {labels[type]}
              </button>
            ))}
            {([relation.source, relation.target] as const).map((event, index) => (
              <button
                key={event.event_uid}
                type="button"
                aria-pressed={relation.relation_type === 'enables' && relation.enabler_event_uid === event.event_uid}
                disabled={savingUid !== null}
                onClick={() => void correct(relation, 'enables', event.event_uid)}
                className={`border px-3 py-1.5 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60 ${relation.relation_type === 'enables' && relation.enabler_event_uid === event.event_uid ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-secondary'}`}
              >
                {index === 0 ? '왼쪽 일정이 오른쪽 일정에 도움' : '오른쪽 일정이 왼쪽 일정에 도움'}
              </button>
            ))}
          </div>
          {saveError === relation.relation_uid ? <p role="alert" className="mt-2 text-destructive">수정하지 못했습니다. 다시 시도해 주세요.</p> : null}
        </article>
      )) : null}
      {status === 'ready' && scopes.some((scope) => relationCursors[scope]) ? (
        <button type="button" disabled={loadingMoreRelations} onClick={() => void loadMoreRelations()} className="mt-4 text-xs font-semibold text-primary underline-offset-2 hover:underline disabled:opacity-60">관계 더 보기</button>
      ) : null}
      {relationPageError ? <p role="alert" className="mt-2 text-destructive">추가 관계를 불러오지 못했습니다. 더 보기를 다시 눌러 주세요.</p> : null}
    </section>
  );
}
