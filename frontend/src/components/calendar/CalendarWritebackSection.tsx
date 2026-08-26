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
  const isCreatePending = pendingWritebackAction === 'create';
  const isUpdatePending = pendingWritebackAction === 'update';
  const isExecutePending = pendingWritebackAction === 'execute';

  return (
    <section aria-label="일정 반영 점검" className="rounded-2xl border border-border bg-card p-4 shadow-sm md:p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-black text-primary">고객 원본 일정</p>
          <h2 className="mt-1 text-lg font-black text-foreground">고객 원본 일정 반영</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            선택한 연결 계정에 새 일정을 반영하기 전에 겹치는 일정과 최근 변경을 먼저 점검합니다.
            점검 기록과 반영 결과는 이 화면에서 언제든 다시 확인할 수 있습니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void requestWritebackIntent('create')}
            disabled={isWritebackActionDisabled}
            aria-busy={isCreatePending}
            className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
          >
            {isCreatePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isCreatePending ? '점검 처리 중' : '새 일정 반영 점검'}
          </button>
          <button
            type="button"
            onClick={() => void requestWritebackIntent('update')}
            disabled={isWritebackActionDisabled}
            aria-busy={isUpdatePending}
            className="inline-flex items-center justify-center rounded-xl border border-border bg-background px-4 py-2 text-sm font-bold hover:bg-secondary disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {isUpdatePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isUpdatePending ? '점검 처리 중' : '변경 확인 후 재점검'}
          </button>
          <button
            type="button"
            onClick={() => void requestWritebackIntent('update', true)}
            disabled={isProviderExecutionDisabled}
            aria-busy={isExecutePending}
            className="inline-flex items-center justify-center rounded-xl border border-primary/40 bg-primary/10 px-4 py-2 text-sm font-bold text-primary hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {isExecutePending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {isExecutePending ? '실행 요청 처리 중' : '실제 반영 실행 요청'}
          </button>
        </div>
      </div>

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
                {getEtagLabel(source.etag)} · {sourceWritable ? '점검 후 실제 반영까지 진행할 수 있습니다' : '실제 반영은 차단됩니다'}
              </p>
            </button>
          );
        })}
        {sourceLoadStatus === 'ready' && writebackSources.length === 0 && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-amber-700">
            연결된 외부 캘린더·주소록 계정이 없습니다. 설정에서 계정을 연결하면 이 목록에 표시됩니다.{' '}
            <a href="/settings" className="underline">설정에서 계정 연결하기</a>
          </p>
        )}
        {sourceLoadStatus === 'loading' && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-primary">
            일정 원본 목록을 확인하는 중입니다.
          </p>
        )}
        {sourceLoadStatus === 'error' && (
          <p className="rounded-xl border border-border bg-background/70 p-3 text-sm font-bold text-amber-700">
            일정 원본 목록을 확인하지 못했습니다. 잠시 후 다시 시도하세요.
          </p>
        )}
      </div>

      <div role="status" aria-live="polite" className="mt-4 rounded-xl border border-border bg-background/70 p-4 text-sm">
        {writebackStatus === 'idle' && (
          <p className="text-muted-foreground">아직 반영 기록이 없습니다. [새 일정 반영 점검]을 누르면 선택한 계정의 겹침 여부를 먼저 확인합니다.</p>
        )}
        {writebackStatus === 'loading' && <p className="font-bold text-primary">일정 반영 점검을 진행하는 중입니다.</p>}
        {writebackStatus === 'no_source' && (
          <p className="font-bold text-amber-700">반영 가능한 연결 계정이 없어 새 일정 반영을 진행할 수 없습니다. 설정에서 캘린더 계정을 연결한 뒤 다시 시도하세요.{' '}<a href="/settings" className="underline">설정 열기</a></p>
        )}
        {writebackStatus === 'conflict' && (
          <p className="font-bold text-red-700">원본 일정이 다른 곳에서 변경되어 충돌이 감지되었습니다. 기존 일정을 덮어쓰지 않았습니다. 최신 내용을 확인한 뒤 다시 점검하세요.</p>
        )}
        {writebackStatus === 'auth' && (
          <p className="font-bold text-red-700">로그인 상태를 확인하지 못했습니다. 다시 로그인한 뒤 일정 반영을 진행하세요.</p>
        )}
        {writebackStatus === 'error' && (
          <p className="font-bold text-red-700">일정 반영 점검에 실패했습니다. 잠시 후 위 버튼으로 다시 시도하세요.</p>
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
              <dd className="mt-1 text-sm font-bold text-foreground">{writebackResult.if_match ? '최신 변경 확인 필요' : '충돌 위험 없음'}</dd>
            </div>
            <div>
              <dt className="font-black text-muted-foreground">활동 기록</dt>
              <dd className="mt-1 text-sm font-bold text-foreground">저장됨</dd>
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
