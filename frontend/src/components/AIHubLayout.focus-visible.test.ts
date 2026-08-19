import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const SOURCE = readFileSync(new URL('./AIHubLayout.tsx', import.meta.url), 'utf8');

describe('AIHubLayout keyboard focus contract', () => {
  it('keeps an explicit focus-visible indicator on the roving tab buttons', () => {
    const start = SOURCE.indexOf('id={`ai-hub-tab-${tab.id}`}');
    const end = SOURCE.indexOf('</button>', start);

    expect(start).toBeGreaterThanOrEqual(0);
    expect(end).toBeGreaterThan(start);

    const tabButton = SOURCE.slice(start, end);
    expect(tabButton).toContain('role="tab"');
    expect(tabButton).toContain('focus-visible:outline-none');
    expect(tabButton).toContain('focus-visible:ring-2');
    expect(tabButton).toContain('focus-visible:ring-ring/40');
  });
});
