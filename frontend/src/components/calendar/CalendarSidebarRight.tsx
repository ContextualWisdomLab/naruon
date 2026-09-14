import { Clock, Video, Users, CalendarDays, Paperclip, X, CalendarPlus, ChevronRight, Link as LinkIcon } from 'lucide-react';
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
          <button type="button" disabled={!selectedDetailEvent?.location} aria-label={`${selectedDetailEvent?.location ?? '장소'} 위치 보기`} className="text-xs text-primary font-semibold ml-auto hover:underline rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:no-underline">위치 보기</button>
        </div>
        <div className="flex gap-3 items-start w-full">
          <Users className="size-5 text-muted-foreground shrink-0" />
          <div className="flex-1">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold">참여자 10</p>
              <button type="button" className="text-xs text-muted-foreground hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 rounded-sm">모두 보기</button>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="size-6 rounded-full bg-slate-200 shrink-0"></div>
                  <span className="text-sm font-medium">김나루</span>
                </div>
                <span className="text-xs text-muted-foreground">소유자</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="size-6 rounded-full bg-slate-200 shrink-0"></div>
                  <span className="text-sm font-medium">이준호 <span className="text-muted-foreground text-xs font-normal">마케팅 리드</span></span>
                </div>
                <span className="text-xs text-muted-foreground">예</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="size-6 rounded-full bg-slate-200 shrink-0"></div>
                  <span className="text-sm font-medium">김현진 <span className="text-muted-foreground text-xs font-normal">DevOps 리드</span></span>
                </div>
                <span className="text-xs text-muted-foreground">예</span>
              </div>
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
        <div className="flex gap-3 items-start w-full">
          <Paperclip className="size-5 text-muted-foreground shrink-0" />
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold">첨부파일 <span className="text-muted-foreground font-normal">6</span></p>
            </div>
            <div className="space-y-2">
              <div className="flex flex-col justify-center rounded-lg border border-border bg-background p-2 gap-1">
                <span className="text-xs font-semibold">런칭 마스터 일정 v3.xlsx</span>
                <span className="text-xs text-muted-foreground">1.2 MB - 2024.05.19</span>
              </div>
              <div className="flex flex-col justify-center rounded-lg border border-border bg-background p-2 gap-1">
                <span className="text-xs font-semibold">B2B 계약 협상안 (v2).pdf</span>
                <span className="text-xs text-muted-foreground">2.1 MB - 2024.05.18</span>
              </div>
              <div className="flex flex-col justify-center rounded-lg border border-border bg-background p-2 gap-1">
                <span className="text-xs font-semibold">B2B 현지화 이슈 정리.docx</span>
                <span className="text-xs text-muted-foreground">1.1 MB - 2024.05.17</span>
              </div>
            </div>
            <button type="button" className="mt-2 text-left text-xs text-muted-foreground hover:text-primary transition-colors py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 rounded-sm">
              + 3개 더보기
            </button>
          </div>
        </div>
        <div className="flex gap-3 items-start w-full">
          <CalendarPlus className="size-5 text-muted-foreground shrink-0" />
          <div className="flex-1">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold">회의 제안</p>
              <button type="button" className="text-xs text-muted-foreground hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 rounded-sm">모두 보기</button>
            </div>
            <div className="rounded-lg border border-border bg-background p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">릴리즈 준비 주간 동기화 미팅</span>
                <ChevronRight className="size-4 text-muted-foreground" />
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="size-3" />
                <span>5/22 (수) 오전 10:00 - 11:00</span>
              </div>
              <div className="flex items-center gap-1 mt-1">
                <div className="flex -space-x-1">
                  <div className="size-5 rounded-full bg-slate-200 border border-background"></div>
                  <div className="size-5 rounded-full bg-slate-300 border border-background"></div>
                  <div className="size-5 rounded-full bg-slate-400 border border-background"></div>
                </div>
                <span className="text-xs text-muted-foreground ml-1">외 3명</span>
              </div>
              <button type="button" className="mt-2 w-full flex items-center justify-center gap-2 rounded-md bg-secondary py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">
                <CalendarPlus className="size-3" />
                캘린더에 추가
              </button>
            </div>
          </div>
        </div>
        <div className="flex gap-3 items-start w-full">
          <LinkIcon className="size-5 text-muted-foreground shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold mb-3">연결된 과거 메일/스레드</p>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">QA 후보 선정 결과 공유</span>
                <span className="text-xs text-muted-foreground">2024.05.10</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">런칭 일정 1차 조율</span>
                <span className="text-xs text-muted-foreground">2024.05.02</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">글로벌 시장 진출 검토</span>
                <span className="text-xs text-muted-foreground">2024.04.25</span>
              </div>
            </div>
            <button type="button" className="mt-2 text-left text-xs text-muted-foreground hover:text-primary transition-colors py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 rounded-sm">
              + 3개 더보기
            </button>
          </div>
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 삭제` : '일정 삭제'} className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">삭제</button>
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 복사` : '일정 복사'} className="flex-1 rounded-lg border border-border bg-background py-2 text-sm font-bold shadow-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">복사</button>
        <button type="button" disabled={!selectedDetailEvent} aria-label={selectedDetailEvent ? `${selectedDetailEvent.title} 일정 수정` : '일정 수정'} className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50 disabled:cursor-not-allowed">수정</button>
      </div>
    </aside>
  );
}
