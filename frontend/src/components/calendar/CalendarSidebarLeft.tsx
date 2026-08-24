import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { calendarDefinitions } from './constants';

type Props = {
  calendarVisibility: Record<string, boolean>;
  toggleCalendarVisibility: (calendarId: string) => void;
};

export function CalendarSidebarLeft({ calendarVisibility, toggleCalendarVisibility }: Props) {
  return (
    <aside className="w-64 shrink-0 flex-col overflow-y-auto border-r border-border bg-card p-4 hidden lg:flex">
      <Button type="button" className="h-10 w-full" aria-label="새 일정 추가">
        <Plus className="size-4 mr-2" aria-hidden="true" />새 일정
      </Button>

      <div className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-bold text-muted-foreground">캘린더 목록</h2>
        </div>
        <ul className="space-y-3">
          {calendarDefinitions.map((cal) => (
            <li key={cal.id} className="text-sm">
              <label className="flex cursor-pointer items-center gap-3 group">
                <input
                  type="checkbox"
                  checked={calendarVisibility[cal.id] ?? false}
                  onChange={() => toggleCalendarVisibility(cal.id)}
                  className="size-4 cursor-pointer rounded border-border text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  aria-label={`${cal.name} 캘린더 표시 토글`}
                />
                <span className={`size-3 rounded-full ${cal.colorClass}`} aria-hidden="true" />
                <span className="font-medium text-foreground transition-colors group-hover:text-primary">{cal.name}</span>
              </label>
            </li>
          ))}
        </ul>
        <Button type="button" variant="ghost" className="mt-4 w-full justify-start text-primary hover:text-primary" aria-label="새 캘린더 추가">
          <Plus className="size-4 mr-2" aria-hidden="true" /> 캘린더 추가
        </Button>
      </div>
    </aside>
  );
}
