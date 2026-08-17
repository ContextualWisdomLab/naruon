"use client";

import { calendarCoordinationProposals } from "./constants";
import {
  formatCoordinationProposalLabel,
  getCalendarSourceLabel,
  getCapabilityLabel,
  getEtagLabel,
  getProtocolLabel,
} from "./helpers";
import type { CalendarWritebackSource } from "./types";

type CalendarCoordinationViewProps = {
  writebackSources?: CalendarWritebackSource[];
  selectedSourceId?: string | null;
  setSelectedSourceId?: (sourceId: string) => void;
  sourceLoadStatus?: "loading" | "ready" | "error";
};

export function CalendarCoordinationView({
  writebackSources = [],
  selectedSourceId = null,
  setSelectedSourceId,
  sourceLoadStatus = "ready",
}: CalendarCoordinationViewProps) {
  const selectedSource = writebackSources.find((source) => source.source_id === selectedSourceId) ?? null;

  return (
    <section aria-label="회의 조율" className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">회의 조율</h3>
        <p className="text-sm text-muted-foreground mb-4">
          서명된 고객 일정 원본을 선택합니다. 고정 ICS 예시나 미리 정해 둔 충돌 결과는
          조율 증거가 아닙니다. 원본 VEVENT 읽기는 커넥터 조회가 준비될 때까지 대기합니다.
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
                onClick={() => setSelectedSourceId?.(source.source_id)}
                className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                  sourceSelected
                    ? "border-primary bg-primary/10 shadow-sm"
                    : "border-border bg-background hover:border-primary/40"
                }`}
              >
                <p className="text-xs font-bold text-primary">{sourceLabel}</p>
                <p className="mt-1 text-sm font-bold">{getProtocolLabel(source.protocol)}</p>
                <p className="mt-2 text-xs font-semibold text-muted-foreground">
                  {source.capabilities.map(getCapabilityLabel).join(" · ")}
                </p>
                <p className="mt-2 text-xs font-semibold text-muted-foreground">
                  {getEtagLabel(source.etag)}
                </p>
              </button>
            );
          })}
        </div>
        <p role="status" aria-live="polite" className="mt-4 text-sm font-semibold">
          {sourceLoadStatus === "loading" && "서명된 일정 원본을 확인하는 중입니다."}
          {sourceLoadStatus === "error" && "서명 세션으로 일정 원본을 확인할 수 없습니다. 공개 헤더로는 조율할 수 없습니다."}
          {sourceLoadStatus === "ready" && writebackSources.length === 0 && "서명된 고객 일정 원본이 없어 조율 결과를 보여 주지 않습니다."}
          {sourceLoadStatus === "ready" && selectedSource !== null && "선택한 일정 원본의 서명된 증거만 조율에 사용합니다."}
          {sourceLoadStatus === "ready" && writebackSources.length > 0 && selectedSource === null && "조율에 사용할 서명된 일정 원본을 선택하세요."}
        </p>
        <div className="grid gap-3 max-w-lg mt-4">
          {calendarCoordinationProposals.map((proposal) => {
            const slotLabel = formatCoordinationProposalLabel(proposal.startsAt, proposal.endsAt);
            return (
              <button
                key={proposal.id}
                type="button"
                aria-label={`${proposal.rankLabel} 제안하기: ${slotLabel}, ${proposal.availability}`}
                className={`flex items-center justify-between rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                  proposal.emphasized
                    ? "border-primary/20 bg-primary/5 hover:bg-primary/10"
                    : "border-border bg-card hover:bg-secondary"
                }`}
              >
                <div className="flex items-center gap-3" aria-hidden="true">
                  <span className={`grid size-8 place-items-center rounded-lg font-bold ${
                    proposal.emphasized
                      ? "bg-primary/20 text-primary"
                      : "bg-secondary text-muted-foreground"
                  }`}
                  >
                    {proposal.rankLabel}
                  </span>
                  <div className="text-left">
                    <p className="font-bold">{slotLabel}</p>
                    <p className="text-xs text-muted-foreground">{proposal.availability}</p>
                  </div>
                </div>
                <span className={`text-xs font-bold ${
                  proposal.emphasized ? "text-primary" : "text-muted-foreground"
                }`}
                aria-hidden="true"
                >
                  제안하기
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
