/* @vitest-environment jsdom */
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';

import { apiClient } from '@/lib/api-client';

import { EventRelationsSection } from './EventRelationsSection';

let root: Root | null = null;
let container: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root?.unmount());
  root = null;
  container?.remove();
  container = null;
  vi.restoreAllMocks();
});

it('shows cited source links and saves a relation correction in one click', async () => {
  const relation = {
    relation_uid: 'erel_1',
    relation_type: 'candidate',
    enabler_event_uid: null,
    confidence: null,
    corrected: false,
    source: {
      event_uid: 'event_1', title: '워크숍', status_code: 'confirmed', location_text: 'Conference Hall', starts_at: '2026-09-27T10:00:00Z',
      ends_at: '2026-09-27T11:00:00Z', email_id: 12, document_id: null,
      citations: [{ segment_uid: 'segment_1', label: '시작', excerpt: '20260927T100000Z' }],
    },
    target: {
      event_uid: 'event_2', title: '회의', status_code: 'tentative', location_text: null, starts_at: '2026-09-27T10:30:00Z',
      ends_at: '2026-09-27T11:30:00Z', email_id: null, document_id: 'doc_13',
      citations: [{ segment_uid: 'segment_2', label: '시작', excerpt: '20260927T103000Z' }],
    },
  };
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ next_cursor: null });
  vi.spyOn(apiClient, 'get').mockImplementation(async (path) => (
    path.includes('visibility_scope=organization')
      ? { items: [relation], next_cursor: null }
      : { items: [], next_cursor: null }
  ));
  const patch = vi.spyOn(apiClient, 'patch').mockImplementation(async (_path, body) => ({
    ...relation, ...(body as object), corrected: true,
  }));
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(<EventRelationsSection />);
    await Promise.resolve();
  });
  expect(post).toHaveBeenCalledTimes(4);
  expect(container.querySelectorAll('a[href^="/mail?id="]')).toHaveLength(1);
  expect(container.querySelector('a[href="/api/events/sources/doc_13"]')).not.toBeNull();
  expect(container.textContent).toContain('20260927T100000Z');
  expect(container.textContent).toContain('원본 상태: 확정');
  expect(container.textContent).toContain('원본 상태: 잠정');
  expect(container.textContent).toContain('원본 장소: Conference Hall');
  expect(container.textContent).toContain('시간이 겹침');
  expect(container.textContent).toContain('시간만 확인됨 · 관계 판단 전');

  const correction = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === '별개 일정',
  );
  expect(correction).toBeDefined();
  await act(async () => { correction?.click(); });

  expect(patch).toHaveBeenCalledWith(
    '/api/events/relations/erel_1?visibility_scope=organization',
    { relation_type: 'unrelated', enabler_event_uid: null },
  );
  expect(container.textContent).toContain('직접 수정함');

  const direction = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === '오른쪽 일정이 왼쪽 일정에 도움',
  );
  await act(async () => { direction?.click(); });
  expect(patch).toHaveBeenLastCalledWith(
    '/api/events/relations/erel_1?visibility_scope=organization',
    { relation_type: 'enables', enabler_event_uid: 'event_2' },
  );
  expect(container.textContent).toContain('회의 → 워크숍');
  expect(direction?.getAttribute('aria-pressed')).toBe('true');
});

it('imports an iCalendar file into personal events and refreshes relations', async () => {
  const ics = 'BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR';
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (path) => (
    path === '/api/events/sources/ics' ? [{ event_uid: 'event_1' }] : { next_cursor: null }
  ));
  vi.spyOn(apiClient, 'get').mockImplementation(async (path) => (
    path === '/api/events/sources'
      ? { items: [{ document_id: 'caldoc_1', visibility_scope: 'personal', created_at: '2026-09-27T10:00:00Z' }], next_cursor: null }
      : { items: [], next_cursor: null }
  ));
  const remove = vi.spyOn(apiClient, 'delete').mockResolvedValue({});
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  await act(async () => { root?.render(<EventRelationsSection />); });

  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File([ics], 'calendar.ics', { type: 'text/calendar' });
  Object.defineProperty(file, 'text', { value: async () => ics });
  Object.defineProperty(input, 'files', { configurable: true, value: [file] });
  await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })); });

  expect(post).toHaveBeenCalledWith('/api/events/sources/ics', {
    ics_text: ics,
    visibility_scope: 'personal',
  });
  expect(container.textContent).toContain('일정 1개를 가져왔습니다.');
  expect(post).toHaveBeenCalledTimes(9);
  const deleteButton = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === '삭제',
  );
  await act(async () => { deleteButton?.click(); });
  expect(remove).toHaveBeenCalledWith('/api/events/sources/caldoc_1');
  expect(container.textContent).toContain('일정 파일을 삭제했습니다.');
});

it('continues bounded reconciliation and loads the next relation page', async () => {
  const pairCursor = `event_${'a'.repeat(32)}:event_${'b'.repeat(32)}`;
  const relationCursor = `erel_${'c'.repeat(32)}`;
  const event = {
    event_uid: 'event_1', title: '첫 일정', starts_at: '2026-09-27T10:00:00Z',
    ends_at: '2026-09-27T11:00:00Z', email_id: null, document_id: null, citations: [],
  };
  const relation = {
    relation_uid: relationCursor, relation_type: 'candidate', confidence: null,
    enabler_event_uid: null, corrected: false, source: event,
    target: { ...event, event_uid: 'event_2', title: '둘째 일정' },
  };
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (path) => ({
    next_cursor: path.includes('visibility_scope=personal&mode=overlaps') && !path.includes('&after=') ? pairCursor : null,
  }));
  const get = vi.spyOn(apiClient, 'get').mockImplementation(async (path) => (
    path === '/api/events/relations?visibility_scope=personal'
      ? { items: [relation], next_cursor: relationCursor }
      : path.includes('visibility_scope=personal&after=')
        ? { items: [{ ...relation, relation_uid: `erel_${'d'.repeat(32)}`, source: { ...event, title: '셋째 일정' } }], next_cursor: null }
        : { items: [], next_cursor: null }
  ));
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  await act(async () => { root?.render(<EventRelationsSection />); });

  expect(post).toHaveBeenCalledWith(
    `/api/events/relations/reconcile?visibility_scope=personal&mode=overlaps&after=${encodeURIComponent(pairCursor)}`,
    {},
  );
  const more = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === '관계 더 보기',
  );
  await act(async () => { more?.click(); });
  expect(get).toHaveBeenCalledWith(
    `/api/events/relations?visibility_scope=personal&after=${relationCursor}`,
  );
  expect(container.textContent).toContain('셋째 일정');
});
