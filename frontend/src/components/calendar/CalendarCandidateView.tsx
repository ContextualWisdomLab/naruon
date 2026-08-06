import { useMemo } from 'react';
import type { CalendarCandidateEvent } from './types';

type Props = {
  visibleCandidateEvents: CalendarCandidateEvent[];
};

export function CalendarCandidateView({ visibleCandidateEvents }: Props) {

  // ⚡ Bolt: Wrap candidate events map in useMemo to prevent O(N) re-renders
  // 🎯 Why: Mapping over event lists during unrelated parent renders (e.g. state changes) blocks the main thread.
  const candidateEventsList = useMemo(() => (
    <>
      {visibleCandidateEvents.map((event) => (
        <article key={event.id} className="rounded-xl border border-border bg-background p-4">
          <h4 className="text-sm font-bold">{event.title}</h4>
          <p className="mt-2 text-xs text-muted-foreground">{event.source}</p>
          <p className="mt-3 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">{event.mode}</p>
        </article>
      ))}
      {visibleCandidateEvents.length === 0 && (
        <p className="rounded-xl border border-border bg-background p-4 text-sm font-bold text-muted-foreground">
          표시 중인 캘린더 후보가 없습니다.
        </p>
      )}
    </>
  ), [visibleCandidateEvents]);
  return (
    <section aria-label="일정 후보" className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-bold">일정 후보</h3>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {candidateEventsList}
      </div>
    </section>
  );
}
