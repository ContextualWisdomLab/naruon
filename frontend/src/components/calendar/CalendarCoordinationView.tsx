"use client";

import { getCalendarSourceLabel, getCapabilityLabel, getEtagLabel, getProtocolLabel } from './helpers';
import type { CalendarWritebackSource } from './types';

type CalendarCoordinationViewProps = {
  writebackSources: CalendarWritebackSource[];
  selectedSourceId: string | null;
  setSelectedSourceId: (sourceId: string) => void;
  sourceLoadStatus: 'loading' | 'ready' | 'error';
};

export function CalendarCoordinationView({
  writebackSources,
  selectedSourceId,
  setSelectedSourceId,
  sourceLoadStatus,
}: CalendarCoordinationViewProps) {
  const selectedSource = writebackSources.find((source) => source.source_id === selectedSourceId) ?? null;

  return (
    <section aria-label="회의 조율" className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">회의 조율</h3>
        <p className="text-sm text-muted-foreground mb-4">
          조율에 사용할 연결 계정을 선택하면 그 계정의 실제 일정을 기준으로 겹침 여부를 판단합니다.
          계정을 연결하려면 설정에서 캘린더 계정을 먼저 연결하세요.
        </p>
        <div className="grid gap-3 max-w-2xl md:grid-cols-2">
          {writebackSources.map((source, index) => {
            const sourceLabel = getCalendarSourceLabel(index);
            const sourceSelected = selectedSource?.source_id === source.source_id;
            return (
              <button
                key={source.source_id}
                type="button"
                aria-label={`${sourceLabel} 조율 원본 선택`}
                aria-pressed={sourceSelected}
                onClick={() => setSelectedSourceId(source.source_id)}
                className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                  sourceSelected
                    ? 'border-primary bg-primary/10 shadow-sm'
                    : 'border-border bg-background hover:border-primary/40'
                }`}
              >
                <p className="text-xs font-bold text-primary">{sourceLabel}</p>
                <p className="mt-1 text-sm font-bold">{getProtocolLabel(source.protocol)}</p>
                <p className="mt-2 text-xs font-semibold text-muted-foreground">
                  {source.capabilities.map(getCapabilityLabel).join(' · ')}
                </p>
                <p className="mt-2 text-xs font-semibold text-muted-foreground">
                  {getEtagLabel(source.etag)}
                </p>
              </button>
            );
          })}
        </div>
        <p role="status" aria-live="polite" className="mt-4 text-sm font-semibold">
          {sourceLoadStatus === 'loading' && '일정 원본 목록을 확인하는 중입니다. 잠시만 기다려 주세요.'}
          {sourceLoadStatus === 'error' && '일정 원본 목록을 확인하지 못했습니다. 잠시 후 다시 시도하세요.'}
          {sourceLoadStatus === 'ready' && writebackSources.length === 0 && '연결된 캘린더 계정이 없어 조율 결과를 표시하지 않습니다. 설정에서 계정을 연결하면 결과가 표시됩니다.'}
          {sourceLoadStatus === 'ready' && selectedSource !== null && '선택한 계정의 실제 일정을 기준으로 조율합니다.'}
          {sourceLoadStatus === 'ready' && writebackSources.length > 0 && selectedSource === null && '조율에 사용할 캘린더 계정을 선택하세요.'}
        </p>
      </div>
    </section>
  );
}
