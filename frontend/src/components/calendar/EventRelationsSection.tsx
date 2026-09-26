import { useEffect, useState } from 'react';

import { apiClient } from '@/lib/api-client';

type RelationType = 'enables' | 'conflicts' | 'unrelated';
type VisibilityScope = 'personal' | 'organization';

interface EventSource {
  event_uid: string;
  title: string;
  starts_at: string;
  ends_at: string;
  email_id: number | null;
  citations: Array<{ segment_uid: string; label: string; excerpt: string }>;
}

interface EventRelation {
  relation_uid: string;
  relation_type: RelationType;
  confidence: number;
  corrected: boolean;
  source: EventSource;
  target: EventSource;
}

type VisibleRelation = EventRelation & { scope: VisibilityScope };

const scopes: VisibilityScope[] = ['personal', 'organization'];
const labels: Record<RelationType, string> = {
  enables: '진행에 도움',
  conflicts: '시간 충돌',
  unrelated: '별개 일정',
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
    </div>
  );
}

export function EventRelationsSection() {
  const [relations, setRelations] = useState<VisibleRelation[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [retryKey, setRetryKey] = useState(0);
  const [savingUid, setSavingUid] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all(
      scopes.map(async (scope) => {
        const items = await apiClient.post<EventRelation[]>(
          `/api/events/relations/reconcile?visibility_scope=${scope}`,
          {},
        );
        return items.map((item) => ({ ...item, scope }));
      }),
    )
      .then((items) => {
        if (!active) return;
        setRelations(items.flat());
        setStatus('ready');
      })
      .catch(() => {
        if (active) setStatus('error');
      });
    return () => { active = false; };
  }, [retryKey]);

  async function correct(relation: VisibleRelation, relationType: RelationType) {
    if (savingUid !== null || relation.relation_type === relationType) return;
    setSavingUid(relation.relation_uid);
    setSaveError(null);
    try {
      const next = await apiClient.patch<EventRelation>(
        `/api/events/relations/${encodeURIComponent(relation.relation_uid)}?visibility_scope=${relation.scope}`,
        { relation_type: relationType },
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

  return (
    <section aria-labelledby="event-relations-heading" className="border border-border bg-card p-4 text-sm">
      <h2 id="event-relations-heading" className="text-base font-bold">일정 관계</h2>
      <p className="mt-1 text-muted-foreground">초대장에 적힌 시간을 비교했습니다. 연결이 틀리면 아래에서 바로 고칠 수 있습니다.</p>
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
            <span className="text-xs text-muted-foreground">{relation.corrected ? '직접 수정함' : '초대장 시간 기준'}</span>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <EventEvidence event={relation.source} />
            <EventEvidence event={relation.target} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="일정 관계 수정">
            {(Object.keys(labels) as RelationType[]).map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={relation.relation_type === type}
                disabled={savingUid !== null || relation.relation_type === type}
                onClick={() => void correct(relation, type)}
                className="border border-border px-3 py-1.5 text-xs font-semibold hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              >
                {labels[type]}
              </button>
            ))}
          </div>
          {saveError === relation.relation_uid ? <p role="alert" className="mt-2 text-destructive">수정하지 못했습니다. 다시 시도해 주세요.</p> : null}
        </article>
      )) : null}
    </section>
  );
}
