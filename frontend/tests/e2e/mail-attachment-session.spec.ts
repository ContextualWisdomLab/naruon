import { expect, test } from '@playwright/test';

import { mockDashboardApi } from './helpers';

const PUBLIC_IDENTITY_HEADERS = [
  'x-user-id',
  'x-organization-id',
  'x-group-id',
  'x-group-ids',
  'x-user-role',
  'x-dev-auth-token',
];

function expectCookieSession(headers: Record<string, string>, token: string) {
  expect(headers.authorization).toBeUndefined();
  expect(headers.cookie ?? '').toContain(`naruon_session=${token}`);
  for (const headerName of PUBLIC_IDENTITY_HEADERS) {
    expect(headers[headerName]).toBeUndefined();
  }
}

test('opens a mail HWPX preview through the cookie-backed signed API path', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'The mail detail interaction is owned by the desktop shell project.');
  const sessionToken = 'signed-mail-attachment.preview.token';
  await page.addInitScript((token) => {
    document.cookie = `naruon_session=${token}; Path=/; SameSite=Lax`;
  }, sessionToken);
  await mockDashboardApi(page);

  const detailRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === '/api/emails/7' && request.method() === 'GET';
  });

  await page.goto('/');
  await page.getByRole('button', { name: '메일함 바로가기' }).first().click();
  await page.getByRole('button', { name: /김지현 PM/ }).click();
  expectCookieSession((await detailRequest).headers(), sessionToken);

  const previewRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === '/api/data/repository-assets/asset_mail_hwpx_recognized/preview'
      && request.method() === 'GET';
  });
  await page.getByRole('button', { name: 'decision.hwpx 인식된 본문 열기' }).click();
  expectCookieSession((await previewRequest).headers(), sessionToken);

  await expect(page.getByText('Quarterly decision record')).toBeVisible();
  await expect(page.getByText('Approve the next action.')).toBeVisible();
});
