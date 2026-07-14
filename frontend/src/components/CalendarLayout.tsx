"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Settings } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';

import { CalendarWritebackIntentResponse, CalendarWritebackSource, WritebackStatus } from './calendar/types';
import { calendarDefinitions, calendarMonthEvents, calendarWeekEvents, calendarCandidateEvents } from './calendar/constants';
import { buildInitialCalendarVisibility, isCustomerOwnedWritableSource, getApiErrorStatus } from './calendar/helpers';
import { CalendarMonthView } from './calendar/CalendarMonthView';
import { CalendarWeekView } from './calendar/CalendarWeekView';
import { CalendarDetailView } from './calendar/CalendarDetailView';
import { CalendarCoordinationView } from './calendar/CalendarCoordinationView';
import { CalendarCandidateView } from './calendar/CalendarCandidateView';
import { CalendarSidebarLeft } from './calendar/CalendarSidebarLeft';
import { CalendarSidebarRight } from './calendar/CalendarSidebarRight';
import { CalendarWritebackSection } from './calendar/CalendarWritebackSection';










export function CalendarLayout() {
  const [viewMode, setViewMode] = useState<'월간 캘린더' | '주간 캘린더' | '일정 상세' | '회의 조율' | '일정 후보'>('월간 캘린더');
  const [writebackStatus, setWritebackStatus] = useState<WritebackStatus>('idle');
  const [writebackResult, setWritebackResult] = useState<CalendarWritebackIntentResponse | null>(null);
  const [writebackSources, setWritebackSources] = useState<CalendarWritebackSource[]>([]);
  const [sourceLoadStatus, setSourceLoadStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [calendarVisibility, setCalendarVisibility] = useState<Record<string, boolean>>(() => buildInitialCalendarVisibility());

  const visibleCalendarIds = useMemo(() => {
    return new Set(
      calendarDefinitions
        .filter((calendar) => calendarVisibility[calendar.id] ?? false)
        .map((calendar) => calendar.id),
    );
  }, [calendarVisibility]);

  const visibleMonthEvents = useMemo(
    () => calendarMonthEvents.filter((event) => visibleCalendarIds.has(event.calendarId)),
    [visibleCalendarIds],
  );
  const visibleWeekEvents = useMemo(
    () => calendarWeekEvents.filter((event) => visibleCalendarIds.has(event.calendarId)),
    [visibleCalendarIds],
  );
  const visibleCandidateEvents = useMemo(
    () => calendarCandidateEvents.filter((event) => visibleCalendarIds.has(event.calendarId)),
    [visibleCalendarIds],
  );
  const selectedDetailEvent = visibleMonthEvents.find((event) => event.id === 'launch-meeting') ?? visibleMonthEvents[0] ?? null;

  const toggleCalendarVisibility = useCallback((calendarId: string) => {
    setCalendarVisibility((currentVisibility) => ({
      ...currentVisibility,
      [calendarId]: !(currentVisibility[calendarId] ?? false),
    }));
  }, []);

  useEffect(() => {
    let isMounted = true;
    void apiClient.get<CalendarWritebackSource[]>('/api/calendar/writeback-sources')
      .then((sources) => {
        if (!isMounted) return;
        setWritebackSources(sources);
        setSelectedSourceId(sources.find(isCustomerOwnedWritableSource)?.source_id ?? null);
        setSourceLoadStatus('ready');
      })
      .catch(() => {
        if (!isMounted) return;
        setWritebackSources([]);
        setSourceLoadStatus('error');
        setSelectedSourceId(null);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedWritebackSource = useMemo(() => {
    const selectedSource = writebackSources.find((source) => source.source_id === selectedSourceId);
    if (selectedSource && isCustomerOwnedWritableSource(selectedSource)) return selectedSource;
    return writebackSources.find(isCustomerOwnedWritableSource) ?? null;
  }, [selectedSourceId, writebackSources]);
  const isSourceRegistryReady = sourceLoadStatus === 'ready';

  const requestWritebackIntent = useCallback(async (action: 'create' | 'update', executeProvider = false) => {
    if (!isSourceRegistryReady) {
      setWritebackResult(null);
      setWritebackStatus(sourceLoadStatus === 'error' ? 'error' : 'loading');
      return;
    }
    if (selectedWritebackSource === null) {
      setWritebackResult(null);
      setWritebackStatus('no_source');
      return;
    }
    setWritebackStatus('loading');
    setWritebackResult(null);
    try {
      const result = await apiClient.post<CalendarWritebackIntentResponse>('/api/calendar/writeback-intent', {
        action,
        summary: action === 'create'
          ? 'Naruon 일정 후보 writeback intent 점검'
          : 'Naruon 기존 일정 ETag/If-Match 충돌 점검',
        ...(selectedWritebackSource ? { target_source_id: selectedWritebackSource.source_id } : {}),
        ...(executeProvider ? { execute_provider: true } : {}),
      });
      setWritebackResult(result);
      setWritebackStatus('success');
    } catch (error: unknown) {
      const status = getApiErrorStatus(error);
      if (status === 422) {
        setWritebackStatus('no_source');
      } else if (status === 409) {
        setWritebackStatus('conflict');
      } else if (status === 401 || status === 403) {
        setWritebackStatus('auth');
      } else {
        setWritebackStatus('error');
      }
    }
  }, [isSourceRegistryReady, selectedWritebackSource, sourceLoadStatus]);

  const isWritebackLoading = writebackStatus === 'loading';
  const isWritebackActionDisabled = isWritebackLoading || !isSourceRegistryReady;
  const isProviderExecutionDisabled = isWritebackActionDisabled || !selectedWritebackSource?.etag;

  return (
    <div className="flex h-full min-h-0 bg-background text-foreground">
      {/* Left Sidebar - Calendar List */}
      <CalendarSidebarLeft
        calendarVisibility={calendarVisibility}
        toggleCalendarVisibility={toggleCalendarVisibility}
      />

      {/* Main Calendar Area */}
      <main className="flex min-w-0 flex-1 flex-col bg-background">
        <header className="flex h-auto min-h-16 shrink-0 flex-col items-start gap-3 border-b border-border bg-card px-4 py-3 lg:px-6">
          <div className="flex min-w-0 flex-wrap items-center gap-3 lg:gap-4">
            <Button type="button" variant="outline" size="sm" className="h-8 rounded-md text-xs font-semibold">오늘</Button>
            <div className="flex items-center gap-1">
              <Button type="button" variant="ghost" size="icon-sm" aria-label="이전 달" className="rounded-md"><ChevronLeft className="size-5" aria-hidden="true" /></Button>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="다음 달" className="rounded-md"><ChevronRight className="size-5" aria-hidden="true" /></Button>
            </div>
            <h1 className="text-xl font-bold">일정 관리</h1>
            <h2 className="text-sm font-bold text-muted-foreground lg:ml-2">2026년 5월</h2>
          </div>
          <div className="flex w-full min-w-0 items-center gap-3">
            <div className="flex min-w-0 overflow-x-auto rounded-md border border-border">
              {['월간 캘린더', '주간 캘린더', '일정 상세', '회의 조율', '일정 후보'].map((mode) => (
                <button type="button"
                  key={mode}
                  aria-pressed={viewMode === mode}
                  onClick={() => setViewMode(mode as '월간 캘린더' | '주간 캘린더' | '일정 상세' | '회의 조율' | '일정 후보')}
                  className={`shrink-0 px-4 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-1 focus-visible:ring-offset-background ${viewMode === mode ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-secondary'}`}
                >
                  {mode}
                </button>
              ))}
            </div>
            <Button type="button" variant="outline" size="icon-sm" className="size-9 rounded-md" aria-label="설정">
              <Settings className="size-5" aria-hidden="true" />
            </Button>
          </div>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto p-4 pb-[calc(7rem+env(safe-area-inset-bottom))] md:p-6 lg:pb-6">
          <p className="sr-only">원본 계정 일정 반영 흐름</p>
          <CalendarWritebackSection
            requestWritebackIntent={requestWritebackIntent}
            isWritebackActionDisabled={isWritebackActionDisabled}
            isWritebackLoading={isWritebackLoading}
            isProviderExecutionDisabled={isProviderExecutionDisabled}
            writebackSources={writebackSources}
            selectedWritebackSource={selectedWritebackSource}
            setSelectedSourceId={setSelectedSourceId}
            isCustomerOwnedWritableSource={isCustomerOwnedWritableSource}
            sourceLoadStatus={sourceLoadStatus}
            writebackStatus={writebackStatus}
            writebackResult={writebackResult}
          />

          {viewMode === '월간 캘린더' && <CalendarMonthView visibleMonthEvents={visibleMonthEvents} />}
          {viewMode === '주간 캘린더' && <CalendarWeekView visibleWeekEvents={visibleWeekEvents} />}
          {viewMode === '일정 상세' && <CalendarDetailView selectedDetailEvent={selectedDetailEvent} />}
          {viewMode === '회의 조율' && <CalendarCoordinationView />}
          {viewMode === '일정 후보' && <CalendarCandidateView visibleCandidateEvents={visibleCandidateEvents} />}
        </div>
      </main>

      {/* Right Sidebar - Event Detail */}
      <CalendarSidebarRight selectedDetailEvent={selectedDetailEvent} />
    </div>
  );
}
