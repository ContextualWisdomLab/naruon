/**
 * @vitest-environment jsdom
 */

import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it } from 'vitest';
import { CalendarSidebarRight } from './CalendarSidebarRight';
import type { CalendarDetailEvent } from './types';

const DETAIL_EVENT: CalendarDetailEvent = {
  id: 'event-1',
  calendarId: 'calendar-1',
  dayIndex: 1,
  time: '10:00',
  title: '제품 검토',
  source: 'caldav',
  description: '출시 전 검토',
  monthClassName: 'bg-secondary',
  dotClassName: 'bg-primary',
  badgeClassName: 'bg-secondary text-foreground',
  badgeLabel: '업무',
  duration: '1시간',
  location: '',
};

describe('CalendarSidebarRight disabled reasons', () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root && container) {
      act(() => {
        root!.unmount();
      });
      container.remove();
    }
    root = null;
    container = null;
  });

  function renderComponent(selectedDetailEvent: CalendarDetailEvent | null) {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root!.render(
        <CalendarSidebarRight selectedDetailEvent={selectedDetailEvent} />,
      );
    });
  }

  function buttonByLabel(label: string): HTMLButtonElement {
    const button = container!.querySelector<HTMLButtonElement>(
      `button[aria-label="${label}"]`,
    );
    expect(button).not.toBeNull();
    return button!;
  }

  it('exposes one visible and associated reason when event actions are unavailable', () => {
    renderComponent(null);

    const reason = container!.querySelector<HTMLElement>(
      '#calendar-action-disabled-reason',
    );
    expect(reason?.textContent).toBe(
      '일정을 선택하면 삭제·복사·수정할 수 있습니다.',
    );

    for (const label of ['일정 삭제', '일정 복사', '일정 수정']) {
      const button = buttonByLabel(label);
      expect(button.disabled).toBe(true);
      expect(button.getAttribute('aria-describedby')).toBe(
        'calendar-action-disabled-reason',
      );
      expect(button.hasAttribute('title')).toBe(false);
    }

    expect(container!.textContent).not.toContain('2026.05.23 (목)');
    expect(container!.textContent).not.toContain('참석자 6명');
    expect(container!.textContent).not.toContain('Naruon_2.0_런칭계획.pptx');
    expect(container!.textContent).not.toContain('출시_체크리스트.xlsx');
  });

  it('associates the visible empty-location message with the disabled location action', () => {
    renderComponent(DETAIL_EVENT);

    const locationSummary = container!.querySelector<HTMLElement>(
      '#calendar-location-summary',
    );
    expect(locationSummary?.textContent).toBe('장소 없음');

    const locationButton = buttonByLabel('장소 위치 보기');
    expect(locationButton.disabled).toBe(true);
    expect(locationButton.getAttribute('aria-describedby')).toBe(
      'calendar-location-summary',
    );
    expect(locationButton.hasAttribute('title')).toBe(false);

    expect(
      container!.querySelector('#calendar-action-disabled-reason'),
    ).toBeNull();
    expect(buttonByLabel('제품 검토 일정 삭제').disabled).toBe(false);
    expect(buttonByLabel('제품 검토 일정 복사').disabled).toBe(false);
    expect(buttonByLabel('제품 검토 일정 수정').disabled).toBe(false);
  });

  it('renders selected-event facts only when they exist in the detail contract', () => {
    renderComponent(DETAIL_EVENT);

    expect(container!.textContent).toContain('제품 검토');
    expect(container!.textContent).toContain('10:00');
    expect(container!.textContent).toContain('1시간');
    expect(container!.textContent).toContain('출시 전 검토');

    expect(container!.textContent).not.toContain('(Naruon 2.0)');
    expect(container!.textContent).not.toContain('공개');
    expect(container!.textContent).not.toContain('2026.05.23 (목)');
    expect(container!.textContent).not.toContain('11:00');
    expect(container!.textContent).not.toContain('참석자 6명');
    expect(container!.textContent).not.toContain('Naruon_2.0_런칭계획.pptx');
    expect(container!.textContent).not.toContain('출시_체크리스트.xlsx');
  });
});
