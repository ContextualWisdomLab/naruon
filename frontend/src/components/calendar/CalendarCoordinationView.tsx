"use client";

import { useEffect, useState } from 'react';

import { apiClient } from '@/lib/api-client';

import { calendarConflictPairs } from './constants';
import { getApiErrorStatus, getConflictDecisionLabel, getConflictNextActionLabel } from './helpers';
import type { CalendarConflictDecisionCode, CalendarConflictResponse } from './types';

type PairDecisionState =
  | { status: 'loading' }
  | { status: 'auth' }
  | { status: 'error' }
  | { status: 'ready'; decisionCode: CalendarConflictDecisionCode };

export function CalendarCoordinationView() {
  const [pairDecisions, setPairDecisions] = useState<Record<string, PairDecisionState>>(() => (
    Object.fromEntries(calendarConflictPairs.map((pair) => [pair.pair_id, { status: 'loading' }]))
  ));

  useEffect(() => {
    let isMounted = true;

    void Promise.all(
      calendarConflictPairs.map(async (pair) => {
        try {
          const result = await apiClient.post<CalendarConflictResponse>(
            '/api/calendar/conflicts/evaluate',
            {
              proposed_ics: pair.proposed_ics,
              existing_ics: pair.existing_ics,
            },
          );
          if (!isMounted) return;
          setPairDecisions((current) => ({
            ...current,
            [pair.pair_id]: { status: 'ready', decisionCode: result.decision_code },
          }));
        } catch (error: unknown) {
          if (!isMounted) return;
          const status = getApiErrorStatus(error);
          setPairDecisions((current) => ({
            ...current,
            [pair.pair_id]: { status: status === 401 || status === 403 ? 'auth' : 'error' },
          }));
        }
      }),
    );

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section aria-label="회의 조율" className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">회의 조율</h3>
        <p className="text-sm text-muted-foreground mb-4">
          고객 CalDAV에서 가져온 알려진 VEVENT 쌍을 상태 가중으로 비교합니다.
          취소된 일정은 시간을 차지하지 않고, 잠정/확정 겹침은 다음 행동을 보여 줍니다.
        </p>
        <div className="grid gap-3 max-w-2xl" role="list">
          {calendarConflictPairs.map((pair, index) => {
            const decision = pairDecisions[pair.pair_id] ?? { status: 'loading' };
            return (
              <article
                key={pair.pair_id}
                role="listitem"
                aria-label={pair.pair_label}
                className="rounded-xl border border-border bg-background p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-primary">{`${index + 1}안`}</p>
                    <h4 className="mt-1 text-sm font-bold">{pair.pair_label}</h4>
                  </div>
                  {decision.status === 'ready' && (
                    <span className="shrink-0 rounded-full bg-primary/10 px-2 py-1 text-xs font-black text-primary">
                      {getConflictDecisionLabel(decision.decisionCode)}
                    </span>
                  )}
                </div>
                <p role="status" aria-live="polite" className="mt-3 text-sm font-semibold">
                  {decision.status === 'loading' && '상태 가중 일정 충돌을 확인하는 중입니다.'}
                  {decision.status === 'auth' && '서명 세션이 필요합니다. 공개 헤더로는 일정 충돌을 확인할 수 없습니다.'}
                  {decision.status === 'error' && '일정 충돌을 확인할 수 없습니다. 서명 세션으로 다시 확인하세요.'}
                  {decision.status === 'ready' && getConflictNextActionLabel(decision.decisionCode)}
                </p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
