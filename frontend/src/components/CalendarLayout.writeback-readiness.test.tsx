/* @vitest-environment jsdom */
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('lucide-react', () => ({
  ChevronLeft: () => <svg aria-hidden="true" />,
  ChevronRight: () => <svg aria-hidden="true" />,
  Settings: () => <svg aria-hidden="true" />,
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('./calendar/CalendarMonthView', () => ({ CalendarMonthView: () => null }));
vi.mock('./calendar/CalendarWeekView', () => ({ CalendarWeekView: () => null }));
vi.mock('./calendar/CalendarDetailView', () => ({ CalendarDetailView: () => null }));
vi.mock('./calendar/CalendarCoordinationView', () => ({ CalendarCoordinationView: () => null }));
vi.mock('./calendar/CalendarCandidateView', () => ({ CalendarCandidateView: () => null }));
vi.mock('./calendar/CalendarSidebarLeft', () => ({ CalendarSidebarLeft: () => null }));
vi.mock('./calendar/CalendarWritebackSection', () => ({ CalendarWritebackSection: () => null }));
vi.mock('./calendar/CalendarSidebarRight', () => ({
  CalendarSidebarRight: ({ isWritebackDisabled }: { isWritebackDisabled: boolean }) => (
    <button type="button" data-testid="sidebar-writeback" disabled={isWritebackDisabled}>
      일정 수정 점검
    </button>
  ),
}));

import { apiClient } from '@/lib/api-client';
import { CalendarLayout } from './CalendarLayout';
import type { CalendarWritebackSource } from './calendar/types';

const readOnlySource: CalendarWritebackSource = {
  source_id: 'caldav-readonly',
  provider: 'Customer CalDAV',
  protocol: 'caldav',
  owner_id: 'user-1',
  organization_id: 'org-1',
  capabilities: ['read'],
  writeback_enabled: false,
  etag: null,
};

async function flushAsyncWork() {
  for (let index = 0; index < 3; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe('CalendarLayout writeback readiness', () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.clearAllMocks();
  });

  it('keeps the sidebar update action disabled when the ready registry has no writable source', async () => {
    vi.mocked(apiClient.get).mockResolvedValue([readOnlySource]);
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(<CalendarLayout />);
    });
    await flushAsyncWork();

    const sidebarWriteback = container.querySelector<HTMLButtonElement>('[data-testid="sidebar-writeback"]');
    expect(sidebarWriteback).not.toBeNull();
    expect(sidebarWriteback?.disabled).toBe(true);
    expect(apiClient.get).toHaveBeenCalledWith('/api/calendar/writeback-sources');
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
