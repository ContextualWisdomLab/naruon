/* @vitest-environment jsdom */
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('lucide-react', () => ({
  Loader2: () => <svg aria-hidden="true" />,
}));

import { CalendarWritebackSection } from './CalendarWritebackSection';
import type { CalendarWritebackSource } from './types';

const writableSource: CalendarWritebackSource = {
  source_id: 'caldav-primary',
  provider: 'Customer CalDAV',
  protocol: 'caldav',
  owner_id: 'user-1',
  organization_id: 'org-1',
  capabilities: ['read', 'write', 'etag'],
  writeback_enabled: true,
  etag: 'etag-1',
};

const readOnlySource: CalendarWritebackSource = {
  ...writableSource,
  source_id: 'caldav-readonly',
  capabilities: ['read'],
  writeback_enabled: false,
  etag: null,
};

describe('CalendarWritebackSection accessibility contract', () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
  });

  function renderSection(overrides: Partial<React.ComponentProps<typeof CalendarWritebackSection>> = {}) {
    const requestWritebackIntent = vi.fn();
    const setSelectedSourceId = vi.fn();
    const props: React.ComponentProps<typeof CalendarWritebackSection> = {
      requestWritebackIntent,
      isWritebackActionDisabled: false,
      pendingWritebackAction: null,
      isProviderExecutionDisabled: false,
      writebackSources: [writableSource],
      selectedWritebackSource: writableSource,
      setSelectedSourceId,
      isCustomerOwnedWritableSource: (source) => source.writeback_enabled && source.capabilities.includes('write'),
      sourceLoadStatus: 'ready',
      writebackStatus: 'idle',
      writebackResult: null,
      ...overrides,
    };

    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(<CalendarWritebackSection {...props} />);
    });

    return { requestWritebackIntent, setSelectedSourceId };
  }

  function getControlStatus(createButton: HTMLButtonElement | undefined) {
    const descriptionId = createButton?.getAttribute('aria-describedby');
    expect(descriptionId).toBeTruthy();
    const status = descriptionId
      ? container?.querySelector<HTMLElement>(`[id="${descriptionId}"][role="status"]`)
      : null;
    expect(status).not.toBeNull();
    return { descriptionId, status };
  }

  it('keeps unavailable async actions natively disabled and exposes the reason as a live status', () => {
    const { requestWritebackIntent } = renderSection({
      isWritebackActionDisabled: true,
      isProviderExecutionDisabled: true,
      sourceLoadStatus: 'loading',
      writebackSources: [],
      selectedWritebackSource: null,
    });

    const createButton = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('새 일정 intent 점검'));
    const executeButton = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('ETag 실행 요청'));
    const { descriptionId, status } = getControlStatus(createButton);

    expect(createButton?.disabled).toBe(true);
    expect(executeButton?.disabled).toBe(true);
    expect(executeButton?.getAttribute('aria-describedby')).toBe(descriptionId);
    expect(status?.getAttribute('aria-live')).toBe('polite');
    expect(status?.textContent).toContain('일정 원본을 확인 중이라 반영 의도 점검을 시작할 수 없습니다.');

    act(() => {
      createButton?.click();
      executeButton?.click();
    });
    expect(requestWritebackIntent).not.toHaveBeenCalled();
  });

  it('keeps enabled actions operable while describing provider execution readiness', () => {
    const { requestWritebackIntent } = renderSection();
    const createButton = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('새 일정 intent 점검'));
    const executeButton = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('ETag 실행 요청'));
    const { status } = getControlStatus(createButton);

    expect(createButton?.disabled).toBe(false);
    expect(executeButton?.disabled).toBe(false);
    expect(status?.textContent)
      .toContain('선택한 고객 원본 일정에 반영할 의도와 외부 실행 조건을 점검할 수 있습니다.');

    act(() => {
      createButton?.click();
      executeButton?.click();
    });
    expect(requestWritebackIntent).toHaveBeenNthCalledWith(1, 'create');
    expect(requestWritebackIntent).toHaveBeenNthCalledWith(2, 'update', true);
  });

  it('keeps read-only sources non-interactive and names the write restriction in visible content', () => {
    const { setSelectedSourceId } = renderSection({
      writebackSources: [readOnlySource],
      selectedWritebackSource: readOnlySource,
      isProviderExecutionDisabled: true,
    });
    const sourceButton = container?.querySelector<HTMLButtonElement>('button[aria-label="일정 원본 1 읽기 전용 선택"]');
    const createButton = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? [])
      .find((button) => button.textContent?.includes('새 일정 intent 점검'));
    const { status } = getControlStatus(createButton);

    expect(sourceButton?.disabled).toBe(true);
    expect(sourceButton?.textContent).toContain('읽기 전용');
    expect(sourceButton?.textContent).toContain('외부 쓰기 차단');
    expect(status?.textContent)
      .toContain('반영 가능한 일정 원본이 없어 반영 의도 점검을 시작할 수 없습니다.');

    act(() => {
      sourceButton?.click();
    });
    expect(setSelectedSourceId).not.toHaveBeenCalled();
  });

  it('disables intent checks when the ready registry has no writable source', () => {
    const { requestWritebackIntent } = renderSection({
      writebackSources: [readOnlySource],
      selectedWritebackSource: readOnlySource,
      sourceLoadStatus: 'ready',
      isWritebackActionDisabled: false,
      isProviderExecutionDisabled: true,
    });
    const buttons = Array.from(container?.querySelectorAll<HTMLButtonElement>('button') ?? []);
    const createButton = buttons.find((button) => button.textContent?.includes('새 일정 intent 점검'));
    const updateButton = buttons.find((button) => button.textContent?.includes('ETag 업데이트 점검'));
    const executeButton = buttons.find((button) => button.textContent?.includes('ETag 실행 요청'));
    const { status } = getControlStatus(createButton);

    expect(createButton?.disabled).toBe(true);
    expect(updateButton?.disabled).toBe(true);
    expect(executeButton?.disabled).toBe(true);
    expect(status?.textContent)
      .toContain('반영 가능한 일정 원본이 없어 반영 의도 점검을 시작할 수 없습니다.');

    act(() => {
      createButton?.click();
      updateButton?.click();
      executeButton?.click();
    });
    expect(requestWritebackIntent).not.toHaveBeenCalled();
  });

  it('keeps aria-describedby targets unique when reusable writeback sections share a document', () => {
    const requestWritebackIntent = vi.fn();
    const setSelectedSourceId = vi.fn();
    const props: React.ComponentProps<typeof CalendarWritebackSection> = {
      requestWritebackIntent,
      isWritebackActionDisabled: false,
      pendingWritebackAction: null,
      isProviderExecutionDisabled: false,
      writebackSources: [writableSource],
      selectedWritebackSource: writableSource,
      setSelectedSourceId,
      isCustomerOwnedWritableSource: (source) => source.writeback_enabled && source.capabilities.includes('write'),
      sourceLoadStatus: 'ready',
      writebackStatus: 'idle',
      writebackResult: null,
    };

    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(
        <>
          <CalendarWritebackSection {...props} />
          <CalendarWritebackSection {...props} />
        </>,
      );
    });

    const sectionElements = Array.from(container.querySelectorAll<HTMLElement>('section[aria-label="일정 반영 의도 점검"]'));
    expect(sectionElements).toHaveLength(2);

    const descriptionIds = sectionElements.map((section) => {
      const createButton = Array.from(section.querySelectorAll<HTMLButtonElement>('button'))
        .find((button) => button.textContent?.includes('새 일정 intent 점검'));
      const descriptionId = createButton?.getAttribute('aria-describedby');
      expect(descriptionId).toBeTruthy();
      expect(section.querySelector<HTMLElement>(`[id="${descriptionId}"][role="status"]`)).not.toBeNull();
      return descriptionId;
    });

    expect(new Set(descriptionIds).size).toBe(2);
  });
});
