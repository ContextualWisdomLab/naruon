import { useId } from 'react';
import type { CalendarWritebackActionKey, CalendarWritebackSource, CalendarWritebackIntentResponse, WritebackStatus } from './types';
import { getCalendarSourceLabel, getProtocolLabel, getCapabilityLabel, getEtagLabel, getWritebackModeLabel, getIntentProtocolLabel, getProviderExecutionLabel, getProviderRetryLabel } from './helpers';
import { Loader2 } from 'lucide-react';

type Props = {
  requestWritebackIntent: (action: 'create' | 'update', executeProvider?: boolean) => void;
  isWritebackActionDisabled: boolean;
  pendingWritebackAction: CalendarWritebackActionKey | null;
  isProviderExecutionDisabled: boolean;
  writebackSources: CalendarWritebackSource[];
  selectedWritebackSource: CalendarWritebackSource | null;
  setSelectedSourceId: (id: string) => void;
  isCustomerOwnedWritableSource: (source: CalendarWritebackSource) => boolean;
  sourceLoadStatus: 'loading' | 'ready' | 'error';
  writebackStatus: WritebackStatus;
  writebackResult: CalendarWritebackIntentResponse | null;
};

export function CalendarWritebackSection({
  requestWritebackIntent,
  isWritebackActionDisabled,
  pendingWritebackAction,
  isProviderExecutionDisabled,
  writebackSources,
  selectedWritebackSource,
  setSelectedSourceId,
  isCustomerOwnedWritableSource,
  sourceLoadStatus,
  writebackStatus,
  writebackResult,
}: Props) {
  const writebackControlStatusId = useId();
  const isCreatePending = pendingWritebackAction === 'create';
  const isUpdatePending = pendingWritebackAction === 'update';
  const isExecutePending = pendingWritebackAction === 'execute';
  const hasWritableSelectedSource = selectedWritebackSource !== null;
  const areIntentActionsDisabled = isWritebackActionDisabled || !hasWritableSelectedSource;
  const isExecutionActionDisabled = isProviderExecutionDisabled || !hasWritableSelectedSource;
  const writebackControlStatus = isWritebackActionDisabled
    ? pendingWritebackAction
      ? '일정 반영 요청을 처리 중이라 새 점검을 시작할 수 없습니다.'
      : sourceLoadStatus === 'loading'
        ? '일정 원본을 확인 중이라 반영 의도 점검을 시작할 수 없습니다.'
        : sourceLoadStatus === 'error'
          ? '일정 원본을 확인할 수 없어 반영 의도 점검을 시작할 수 없습니다.'
          : '일정 원본 준비가 끝나야 반영 의도 점검을 시작할 수 있습니다.'
    : !hasWritableSelectedSource
      ? '반영 가능한 일정 원본이 없어 반영 의도 점검을 시작할 수 없습니다.'
      : isProviderExecutionDisabled
        ? '반영 의도 점검은 가능하지만 선택한 원본에 충돌 토큰이 없어 외부 실행 요청은 사용할 수 없습니다.'
        : '선택한 고객 원본 일정에 반영할 의도와 외부 실행 조건을 점검할 수 있습니다.';

  return (
    <section aria-label="일정 반영 의도 점검" className="rounded-2xl border border-border bg-card p-4 shadow-sm md:p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-black text-primary">고객 원본 일정</p>
          <h2 className="mt-1 text-lg font-black text-foreground">고객 원본 일정 반영 의도</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Naruon은 캘린더 서버가 아니라 고객 원본 계정에 반영할 의도를 기록합니다.
            실제 외부 쓰기는 원본 기능, 출처 근거, 충돌 토큰, 감사 기록을 통과해야 합니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void requestWritebackIntent('create')}
            disabled={areIntentActionsDisabled}
            aria-describedby={writebackControlStatusId}
            aria-busy={isCreatePending}
            className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
          >
            {isCreatePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isCreatePending ? '새 일정 처리 중' : '새 일정 intent 점검'}
          </button>
          <button
            type="button"
            onClick={() => void requestWritebackIntent('update')}
            disabled={areIntentActionsDisabled}
            aria-describedby={writebackControlStatusId}
            aria-busy={isUpdatePending}
            className="inline-flex items-center justify-center rounded-xl border border-border bg-background px-4 py-2 text-sm font-bold hover:bg-secondary disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {isUpdatePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isUpdatePending ? 'ETag 업데이트 처리 중' : 'ETag 업데이트 점검'}
          </button>
          <button
            type="button"
            onClick={() => void requestWritebackIntent('update', true)}
            disabled={isExecutionActionDisabled}
            aria-describedby={writebackControlStatusId}
            aria-busy={isExecutePending}
            className="inline-flex items-center justify-center rounded-xl border border-primary/40 bg-primary/10 px-4 py-2 text-sm font-bold text-primary hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {isExecutePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isExecutePending ? 'ETag 실행 처리 중' : 'ETag 실행 요청'}
          </button>
        </div>
      </div>

      <p
        id={writebackControlStatusId}
        role="status"
        aria-live="polite"
        className="mt-3 text-xs font-semibold leading-5 text-muted-foreground"
      >
        {writebackControlStatus}
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {writebackSources.map((source, index) => {
          const sourceWritable = isCustomerOwnedWritableSource(source);
          const sourceSelected = selectedWritebackSource?.source_id === source.source_id;
          const sourceLabel = getCalendarSourceLabel(index);
          return (
            <button
              key={source.source_id}
              type="button"
              aria-label={`${sourceLabel} ${sourceWritable ? '일정 반영 가능' : '읽기 전용'} 선택`}
              disabled={!sourceWritable}
              aria-pressed={sourceSelected}
              onClick={() => setSelectedSourceId(source.source_id)}
              className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-70 ${
                sourceSelected
                  ? 'border-primary bg-primary/10 shadow-sm'
                  : 'border-border bg-background/70 hover:border-primary/40'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-bold text-primary">{sourceLabel}</p>
                  <p className="mt-1 break-words text-sm font-bold">{getProtocolLabel(source.protocol)}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-black ${sourceWritable ? 'bg-green-100 text-green-700' : 'bg-secondary text-muted-foreground'}`}>
                  {sourceSelected ? '선택됨' : sourceWritable ? '반영 가능' : '읽기 전용'}
                </span>
              </div>
              <p className="mt-2 text-xs font-semibold text-muted-foreground">
                {source.capabilities.map(getCapabilityLabel).join(' · ')}
              </p>
              <p className="mt-2 text-xs font-semibold text-muted-foreground">
                {getEtagLabel(source.etag)} · {sourceWritable ? '외부 쓰기 전 의도 점검 가능' : '외부 쓰기 차단'}
              </p>
            </button>
          );
        })}
        {sourceLoadStatus === 'ready' && writebackSources.length === 0 && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-amber-700">
            연결된 CalDAV/CardDAV/WebDAV 원본이 없습니다.
          </p>
        )}
        {sourceLoadStatus === 'loading' && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-primary">
            일정 원본 목록을 확인하는 중입니다.
          </p>
        )}
        {sourceLoadStatus === 'error' && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-amber-700">
            서명 세션으로 일정 원본 목록을 확인할 수 없습니다.
          </p>
        )}
      </div>

      <div role="status" aria-live="polite" className="mt-4 rounded-xl border border-border bg-background/70 p-4 text-sm">
        {writebackStatus === 'idle' && (
          <p className="text-muted-foreground">아직 외부 일정 쓰기는 실행하지 않았습니다. 반영 의도 점검으로 원본 계정과 충돌 조건만 확인합니다.</p>
        )}
        {writebackStatus === 'loading' && <p className="font-bold text-primary">일정 반영 의도 요청 중입니다.</p>}
        {writebackStatus === 'no_source' && (
          <p className="font-bold text-amber-700">원본 CalDAV/CardDAV/WebDAV 계정이 없어 일정 반영 의도를 만들 수 없습니다.</p>
        )}
        {writebackStatus === 'conflict' && (
          <p className="font-bold text-red-700">ETag/If-Match 충돌이 감지되어 원본 일정을 덮어쓰지 않았습니다.</p>
        )}
        {writebackStatus === 'auth' && (
          <p className="font-bold text-red-700">서명 세션이 필요합니다. 공개 헤더로는 일정 반영 의도를 만들 수 없습니다.</p>
        )}
        {writebackStatus === 'error' && (
          <p className="font-bold text-red-700">일정 반영 의도 점검에 실패했습니다.</p>
        )}
        {writebackStatus === 'success' && writebackResult && (
          <dl className="grid gap-3 text-xs sm:grid-cols-2 2xl:grid-cols-3">
            <div>
              <dt className="font-black text-muted-foreground">반영 방식</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">{getWritebackModeLabel(writebackResult.writeback_mode)}</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">원본 종류</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">{getIntentProtocolLabel(writebackResult.protocol)}</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">대상 원본</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">선택한 일정 원본</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">충돌 검사</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">{writebackResult.if_match ? 'If-Match 필요' : 'If-Match 생략 가능'}</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">감사 근거</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">기록됨</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">커넥터 실행</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">{getProviderExecutionLabel(writebackResult)}</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">재시도 상태</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">{getProviderRetryLabel(writebackResult)}</dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}
