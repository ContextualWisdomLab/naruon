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
    relation_type: 'conflicts',
    confidence: 0.8,
    corrected: false,
    source: {
      event_uid: 'event_1', title: '워크숍', starts_at: '2026-09-27T10:00:00Z',
      ends_at: '2026-09-27T11:00:00Z', email_id: 12,
    },
    target: {
      event_uid: 'event_2', title: '회의', starts_at: '2026-09-27T10:30:00Z',
      ends_at: '2026-09-27T11:30:00Z', email_id: 13,
    },
  };
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (path) => (
    path.includes('visibility_scope=organization') ? [relation] : []
  ));
  const patch = vi.spyOn(apiClient, 'patch').mockResolvedValue({
    ...relation, relation_type: 'unrelated', confidence: 1, corrected: true,
  });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(<EventRelationsSection />);
    await Promise.resolve();
  });
  expect(post).toHaveBeenCalledTimes(2);
  expect(container.querySelectorAll('a[href^="/mail?id="]')).toHaveLength(2);
  expect(container.textContent).toContain('자동 판단 80%');

  const correction = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === '별개 일정',
  );
  expect(correction).toBeDefined();
  await act(async () => { correction?.click(); });

  expect(patch).toHaveBeenCalledWith(
    '/api/events/relations/erel_1?visibility_scope=organization',
    { relation_type: 'unrelated' },
  );
  expect(container.textContent).toContain('직접 수정함');
});
