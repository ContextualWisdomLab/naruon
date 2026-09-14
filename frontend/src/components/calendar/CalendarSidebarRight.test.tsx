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

const DETAIL_EVENT_WITH_LOCATION: CalendarDetailEvent = {
  ...DETAIL_EVENT,
  location: '서울 회의실',
};

describe('CalendarSidebarRight action honesty', () => {
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

  it('keeps unsupported event actions disabled with a visible associated reason', () => {
    renderComponent(null);

    const reason = container!.querySelector<HTMLElement>(
      '#calendar-action-disabled-reason',
    );
    expect(reason?.textContent).toBe(
      '삭제·복사·수정은 이 상세 패널에서 지원하지 않습니다.',
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

  it('does not expose enabled controls when no action callback exists', () => {
    renderComponent(DETAIL_EVENT_WITH_LOCATION);

    const reason = container!.querySelector<HTMLElement>(
      '#calendar-action-disabled-reason',
    );
    expect(reason?.textContent).toBe(
      '삭제·복사·수정은 이 상세 패널에서 지원하지 않습니다.',
    );

    for (const label of [
      '제품 검토 일정 삭제',
      '제품 검토 일정 복사',
      '제품 검토 일정 수정',
    ]) {
      const button = buttonByLabel(label);
      expect(button.disabled).toBe(true);
      expect(button.getAttribute('aria-describedby')).toBe(
        'calendar-action-disabled-reason',
      );
    }

    const locationButton = buttonByLabel('서울 회의실 위치 보기');
    expect(locationButton.disabled).toBe(true);
    expect(locationButton.getAttribute('aria-describedby')).toBe(
      'calendar-location-action-disabled-reason',
    );
    expect(
      container!.querySelector('#calendar-location-action-disabled-reason')
        ?.textContent,
    ).toBe('위치 보기는 이 상세 패널에서 지원하지 않습니다.');

    expect(container!.querySelector('button[aria-label="닫기"]')).toBeNull();
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
