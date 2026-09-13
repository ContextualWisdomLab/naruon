/**
 * @vitest-environment jsdom
 */

import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it } from 'vitest';
import { CalendarSidebarRight } from './CalendarSidebarRight';

describe('CalendarSidebarRight title attributes', () => {
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

  function renderComponent(props: any) {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root!.render(<CalendarSidebarRight {...props} />);
    });
  }

  it('adds title attribute explaining why action buttons are disabled when no event is selected', () => {
    renderComponent({ selectedDetailEvent: null });

    const buttons = Array.from(container!.querySelectorAll('button'));

    const deleteBtn = buttons.find(b => b.getAttribute('aria-label') === '일정 삭제');
    const copyBtn = buttons.find(b => b.getAttribute('aria-label') === '일정 복사');
    const editBtn = buttons.find(b => b.getAttribute('aria-label') === '일정 수정');

    expect(deleteBtn?.disabled).toBe(true);
    expect(copyBtn?.disabled).toBe(true);
    expect(editBtn?.disabled).toBe(true);

    expect(deleteBtn?.getAttribute('title')).toBe('일정을 먼저 선택해주세요');
    expect(copyBtn?.getAttribute('title')).toBe('일정을 먼저 선택해주세요');
    expect(editBtn?.getAttribute('title')).toBe('일정을 먼저 선택해주세요');
  });
});
