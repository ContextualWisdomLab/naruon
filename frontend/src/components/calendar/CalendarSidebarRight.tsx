import { CalendarDays, Clock, Video } from 'lucide-react';
import type { CalendarDetailEvent } from './types';

type Props = {
  selectedDetailEvent: CalendarDetailEvent | null;
};

export function CalendarSidebarRight({ selectedDetailEvent }: Props) {
  const locationDescriptionId = selectedDetailEvent?.location
    ? 'calendar-location-action-disabled-reason'
    : 'calendar-location-summary';

  return (
    <aside className="w-[340px] shrink-0 flex-col overflow-y-auto border-l border-border bg-card p-5 hidden xl:flex">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <span className={`rounded-md px-2 py-1 text-xs font-bold ${selectedDetailEvent?.badgeClassName ?? 'bg-secondary text-muted-foreground'}`}>
            {selectedDetailEvent ? `★ ${selectedDetailEvent.badgeLabel}` : '선택 없음'}
          </span>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center gap-3">
          <div className={`size-4 rounded-full ${selectedDetailEvent?.dotClassName ?? 'bg-muted'}`}></div>
          <h2 className="text-xl font-bold">{selectedDetailEvent?.title ?? '표시 중인 일정 없음'}</h2>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{selectedDetailEvent?.description ?? '왼쪽 캘린더 목록에서 하나 이상의 캘린더를 표시하세요.'}</p>
      </div>

      <div className="mt-6 space-y-5">
        {selectedDetailEvent && (
          <div className="flex gap-3">
            <Clock className="size-5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-sm font-semibold">{selectedDetailEvent.time}</p>
              <p className="text-xs text-muted-foreground">{selectedDetailEvent.duration}</p>
            </div>
          </div>
        )}
        <div className="flex gap-3 items-start">
          <Video className="size-5 text-muted-foreground shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p id="calendar-location-summary" className="min-w-0 flex-1 truncate text-sm font-semibold">{selectedDetailEvent?.location || '장소 없음'}</p>
              <button
                type="button"
                disabled
                aria-label={`${selectedDetailEvent?.location || '장소'} 위치 보기`}
                aria-describedby={locationDescriptionId}
                className="shrink-0 rounded-sm text-xs font-semibold text-primary opacity-50 cursor-not-allowed"
              >
                위치 보기
              </button>
            </div>
            {selectedDetailEvent?.location && (
              <p id="calendar-location-action-disabled-reason" className="mt-1 text-xs text-muted-foreground">
                위치 보기는 이 상세 패널에서 지원하지 않습니다.
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-3 items-start">
          <CalendarDays className="size-5 text-muted-foreground shrink-0" />
          <div>
            <p className="text-sm font-semibold mb-1">설명</p>
            <p className="text-sm text-muted-foreground">{selectedDetailEvent?.description ?? '표시할 일정 설명이 없습니다.'}</p>
          </div>
        </div>
      </div>

      <p id="calendar-action-disabled-reason" className="mt-8 text-xs text-muted-foreground">
        삭제·복사·수정은 이 상세 패널에서 지원하지 않습니다.
      </p>
      <div className="mt-3 flex gap-3">
        <button type="button" disabled aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 삭제` : '일정 삭제'} aria-describedby="calendar-action-disabled-reason" className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm opacity-50 cursor-not-allowed">삭제</button>
        <button type="button" disabled aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 복사` : '일정 복사'} aria-describedby="calendar-action-disabled-reason" className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm opacity-50 cursor-not-allowed">복사</button>
        <button type="button" disabled aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 수정` : '일정 수정'} aria-describedby="calendar-action-disabled-reason" className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-primary-foreground shadow-sm opacity-50 cursor-not-allowed">수정</button>
      </div>
    </aside>
  );
}
