import { expect, it, vi } from 'vitest';

vi.mock('@/components/WorkspaceHome', () => ({ WorkspaceHome: () => null }));

import MailPage from './page';

it.each([
  ['23', 23],
  ['0', null],
  ['-1', null],
  ['9007199254740992', null],
  [['23', '24'], null],
])('accepts only one safe positive mail ID from the URL', async (id, expected) => {
  const page = await MailPage({ searchParams: Promise.resolve({ id }) });
  expect(page.props.initialEmailId).toBe(expected);
});
