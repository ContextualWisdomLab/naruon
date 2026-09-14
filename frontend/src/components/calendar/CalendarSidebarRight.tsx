import { Clock, Video, CalendarDays, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { CalendarDetailEvent } from './types';

type Props = {
  selectedDetailEvent: CalendarDetailEvent | null;
};

export function CalendarSidebarRight({ selectedDetailEvent }: Props) {
  return (
    <aside className="w-[340px] shrink-0 flex-col overflow-y-auto border-l border-border bg-card p-5 hidden xl:flex">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <span className={`rounded-md px-2 py-1 text-xs font-bold ${selectedDetailEvent?.badgeClassName ?? 'bg-secondary text-muted-foreground'}`}>
            {selectedDetailEvent ? `★ ${selectedDetailEvent.badgeLabel}` : '선택 없음'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" size="icon-sm" aria-label="닫기" className="rounded-md"><X className="size-4" aria-hidden="true" /></Button>
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
        <div className="flex gap-3 items-center">
          <Video className="size-5 text-muted-foreground shrink-0" />
          <p id="calendar-location-summary" className="text-sm font-semibold">{selectedDetailEvent?.location || '장소 없음'}</p>
          <button type="button" disabled={!selectedDetailEvent?.location} aria-label={`${selectedDetailEvent?.location || '장소'} 위치 보기`} aria-describedby={!selectedDetailEvent?.location ? 'calendar-location-summary' : undefined} className="text-xs text-primary font-semibold ml-auto hover:underline rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:no-underline">위치 보기</button>
        </div>
        <div className="flex gap-3 items-start">
          <CalendarDays className="size-5 text-muted-foreground shrink-0" />
          <div>
            <p className="text-sm font-semibold mb-1">설명</p>
            <p className="text-sm text-muted-foreground">{selectedDetailEvent?.description ?? '표시할 일정 설명이 없습니다.'}</p>
          </div>
        </div>
      </div>

      {!selectedDetailEvent && (
        <p id="calendar-action-disabled-reason" className="mt-8 text-xs text-muted-foreground">
          일정을 선택하면 삭제·복사·수정할 수 있습니다.
        </p>
      )}
      <div className={`${selectedDetailEvent ? 'mt-8' : 'mt-3'} flex gap-3`}>
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 삭제` : '일정 삭제'} aria-describedby={!selectedDetailEvent ? 'calendar-action-disabled-reason' : undefined} className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">삭제</button>
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 복사` : '일정 복사'} aria-describedby={!selectedDetailEvent ? 'calendar-action-disabled-reason' : undefined} className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">복사</button>
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 수정` : '일정 수정'} aria-describedby={!selectedDetailEvent ? 'calendar-action-disabled-reason' : undefined} className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">수정</button>
      </div>
    </aside>
  );
}
