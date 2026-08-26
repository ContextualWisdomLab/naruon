import type { CalendarDetailEvent } from './types';

type Props = {
  selectedDetailEvent: CalendarDetailEvent | null;
};

export function CalendarDetailView({ selectedDetailEvent }: Props) {
  return (
    <section aria-label="일정 상세" className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-bold">{selectedDetailEvent ? `${selectedDetailEvent.title} 상세` : '일정 상세'}</h3>
      <dl className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-background p-4">
          <dt className="text-xs font-black text-muted-foreground">원본 계정</dt>
          <dd className="mt-2 text-sm font-bold">{selectedDetailEvent ? `${selectedDetailEvent.source} · 최근 변경 확인` : '표시 중인 원본 없음'}</dd>
        </div>
        <div className="rounded-xl border border-border bg-background p-4">
          <dt className="text-xs font-black text-muted-foreground">충돌 검사</dt>
          <dd className="mt-2 text-sm font-bold">반영 전에 최근 변경과 충돌 여부를 서버에서 다시 확인합니다.</dd>
        </div>
      </dl>
    </section>
  );
}
