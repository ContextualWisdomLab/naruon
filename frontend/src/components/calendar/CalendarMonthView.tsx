import { useMemo } from 'react';

import type { CalendarMonthEvent } from './types';

type Props = {
  visibleMonthEvents: CalendarMonthEvent[];
};

export function CalendarMonthView({ visibleMonthEvents }: Props) {
  const monthEventsByDay = useMemo(() => {
    const grouped = new Map<number, CalendarMonthEvent[]>();
    for (const event of visibleMonthEvents) {
      const dayEvents = grouped.get(event.dayIndex);
      if (dayEvents) {
        dayEvents.push(event);
      } else {
        grouped.set(event.dayIndex, [event]);
      }
    }
    return grouped;
  }, [visibleMonthEvents]);

  return (
    <div className="h-full rounded-2xl border border-border bg-card shadow-sm flex flex-col overflow-hidden">
      <div className="grid grid-cols-7 border-b border-border bg-secondary/50 text-center text-sm font-semibold py-3">
        <div className="text-red-500">일</div><div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div className="text-blue-500">토</div>
      </div>
      <div className="grid grid-cols-7 grid-rows-5 flex-1 divide-x divide-y divide-border">
        {/* Simulated Grid Cells */}
        {Array.from({ length: 35 }).map((_, i) => {
          const dayEvents = monthEventsByDay.get(i) ?? [];
          return (
            <div key={i} className="min-h-[84px] p-2 sm:min-h-[100px]">
              <span className={`text-sm font-semibold ${i % 7 === 0 ? 'text-red-500' : i % 7 === 6 ? 'text-blue-500' : 'text-muted-foreground'}`}>{i < 31 ? i + 1 : ''}</span>
              {dayEvents.map((event) => (
                <div key={event.id} className={`mt-1 rounded px-1.5 py-1 text-[10px] font-semibold leading-tight sm:px-2 sm:text-xs ${event.monthClassName}`}>
                  {event.time}<span className="hidden sm:inline"> {event.title}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
