import { Clock, Video, Users, CalendarDays, Paperclip, X } from 'lucide-react';
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
          <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold text-muted-foreground">공개</span>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" size="icon-sm" aria-label="닫기" className="rounded-md"><X className="size-4" aria-hidden="true" /></Button>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center gap-3">
          <div className={`size-4 rounded-full ${selectedDetailEvent?.dotClassName ?? 'bg-muted'}`}></div>
          <h2 className="text-xl font-bold">{selectedDetailEvent ? `${selectedDetailEvent.title} (Naruon 2.0)` : '표시 중인 일정 없음'}</h2>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{selectedDetailEvent?.description ?? '왼쪽 캘린더 목록에서 하나 이상의 캘린더를 표시하세요.'}</p>
      </div>

      <div className="mt-6 space-y-5">
        <div className="flex gap-3">
          <Clock className="size-5 text-muted-foreground shrink-0" />
          <div>
            <p className="text-sm font-semibold">2026.05.23 (목) {selectedDetailEvent?.time ?? '--:--'} - 11:00</p>
            <p className="text-xs text-muted-foreground">{selectedDetailEvent?.duration ?? '일정 없음'}</p>
          </div>
        </div>
        <div className="flex gap-3 items-center">
          <Video className="size-5 text-muted-foreground shrink-0" />
          <p className="text-sm font-semibold">{selectedDetailEvent?.location ?? '장소 없음'}</p>
          <button type="button" aria-label={`${selectedDetailEvent?.location ?? '장소'} 위치 보기`} className="text-xs text-primary font-semibold ml-auto hover:underline rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">위치 보기</button>
        </div>
        <div className="flex gap-3 items-start">
          <Users className="size-5 text-muted-foreground shrink-0" />
          <div>
            <p className="text-sm font-semibold mb-2">참석자 6명</p>
            <div className="flex -space-x-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="size-8 rounded-full border-2 border-card bg-slate-200"></div>
              ))}
              <div className="flex size-8 items-center justify-center rounded-full border-2 border-card bg-secondary text-xs font-bold">+2</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3 items-start">
          <CalendarDays className="size-5 text-muted-foreground shrink-0" />
          <div>
            <p className="text-sm font-semibold mb-1">설명</p>
            <p className="text-sm text-muted-foreground">{selectedDetailEvent?.description ?? '표시할 일정 설명이 없습니다.'}</p>
          </div>
        </div>
        <div className="flex gap-3 items-start">
          <Paperclip className="size-5 text-muted-foreground shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold mb-2">첨부파일 <span className="text-muted-foreground font-normal">2개</span></p>
            <div className="space-y-2">
              <div className="flex items-center justify-between rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-semibold">Naruon_2.0_런칭계획.pptx</span>
                <span className="text-xs text-muted-foreground">2.4 MB</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-semibold">출시_체크리스트.xlsx</span>
                <span className="text-xs text-muted-foreground">1.1 MB</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button type="button" aria-label="출시 회의 일정 삭제" className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">삭제</button>
        <button type="button" aria-label="출시 회의 일정 복사" className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">복사</button>
        <button type="button" aria-label="출시 회의 일정 수정" className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90">수정</button>
      </div>
    </aside>
  );
}
