import { expect, test } from '@playwright/test';

import { mockDashboardApi } from './helpers';

test('loads attachment evidence only when opened and follows its exact citation', async ({ page }) => {
  const segmentRequests: string[] = [];
  const message = {
    id: 7, message_id: '<q2@example.com>', thread_id: 'thread-q2',
    sender: '김지현 PM', recipients: 'user@naruon.ai', subject: 'Invoice',
    date: '2026-05-11T09:30:00Z', body: 'Please review',
    attachment_evidence: [{ attachment_id: 91, filename: 'invoice.txt', parse_status: 'parsed', segments: [] }],
  };
  await mockDashboardApi(page);
  await page.route('**/api/emails/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/emails/7') {
      await route.fulfill({ json: message });
      return;
    }
    if (url.pathname === '/api/emails/thread/thread-q2') {
      await route.fulfill({ json: { thread: [message] } });
      return;
    }
    if (url.pathname === '/api/emails/attachment-facts/7') {
      await route.fulfill({ json: { facts: [{
        object_uid: 'fact-1', email_id: 7, attachment_id: 91, fact_kind: 'amount',
        value: '$1,200', source_segment_uid: 'segment-2', evidence_excerpt: 'Total: $1,200',
      }], next_offset: null } });
      return;
    }
    if (url.pathname.startsWith('/api/emails/attachments/91/segments')) {
      segmentRequests.push(url.pathname + url.search);
      if (segmentRequests.length === 1) {
        await route.fulfill({ status: 503, json: { detail: 'temporarily unavailable' } });
        return;
      }
      if (url.pathname.endsWith('/segment-2')) {
        await route.fulfill({ json: { uid: 'segment-2', text: 'Total: $1,200' } });
      } else {
        await route.fulfill({ json: url.searchParams.get('offset') === '100'
          ? { segments: [{ uid: 'segment-3', text: 'Payment due tomorrow' }], next_offset: null }
          : { segments: [{ uid: 'segment-1', text: 'Invoice date: 2026-05-11' }], next_offset: 100 } });
      }
      return;
    }
    await route.fallback();
  });

  await page.goto('/');
  await page.getByRole('button', { name: '메일함 바로가기' }).first().click();
  await page.getByRole('button', { name: /김지현 PM/ }).click();

  const attachment = page.getByText('첨부: invoice.txt');
  await expect(attachment).toBeVisible();
  expect(segmentRequests).toEqual([]);

  await attachment.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('alert').filter({ hasText: '첨부 내용을 불러오지 못했습니다.' })).toBeVisible();
  await page.getByRole('button', { name: '첨부 내용 다시 불러오기' }).click();
  await expect(page.getByText('Invoice date: 2026-05-11')).toBeVisible();
  await page.getByRole('link', { name: 'invoice.txt의 금액 원문 근거 보기' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#attachment-segment-segment-2')).toBeFocused();
  await page.getByRole('button', { name: '첨부 내용 더 보기' }).click();
  await expect(page.getByText('Payment due tomorrow')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  expect(segmentRequests).toContain('/api/emails/attachments/91/segments/segment-2');
});
