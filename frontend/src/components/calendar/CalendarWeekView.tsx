import type { CalendarWeekEvent } from './types';

type Props = {
  visibleWeekEvents: CalendarWeekEvent[];
};

export function CalendarWeekView({ visibleWeekEvents }: Props) {
  return (
    <section aria-label="주간 캘린더" className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-bold">주간 캘린더</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-5">
        {visibleWeekEvents.map((event) => (
          <article key={event.id} className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs font-black text-primary">{event.day}</p>
            <h4 className="mt-2 text-sm font-bold">{event.title}</h4>
            <p className="mt-2 text-xs font-semibold text-muted-foreground">{event.source}</p>
          </article>
        ))}
        {visibleWeekEvents.length === 0 && (
          <p className="rounded-xl border border-border bg-background p-4 text-sm font-bold text-muted-foreground">
            표시 중인 캘린더 일정이 없습니다.
          </p>
        )}
      </div>
    </section>
  );
}
