import { expect, test } from '@playwright/test';

import { mockDashboardApi } from './helpers';

test('keeps OIDC logout pending identity and recovers from a failed session clear', async ({ page }, testInfo) => {
  let deleteCalls = 0;
  let signalDeleteStarted!: () => void;
  let releaseDelete!: () => void;
  const deleteStarted = new Promise<void>((resolve) => {
    signalDeleteStarted = resolve;
  });
  const deleteRelease = new Promise<void>((resolve) => {
    releaseDelete = resolve;
  });

  await mockDashboardApi(page);
  await page.route('**/auth/session', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname !== '/auth/session') {
      await route.continue();
      return;
    }

    if (request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          authenticated: true,
          claims: {
            userId: 'alice',
            organizationId: 'org-acme',
            workspaceId: 'workspace-org-acme',
          },
        }),
      });
      return;
    }

    if (request.method() === 'DELETE') {
      deleteCalls += 1;
      signalDeleteStarted();
      await deleteRelease;
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'identity provider unavailable' }),
      });
      return;
    }

    await route.fulfill({ status: 405, body: 'method not allowed' });
  });

  await page.goto('/settings');
  await page.getByRole('button', { name: '개발자' }).first().click();

  const sessionRegion = page.getByRole('region', { name: 'OIDC 인증 세션' });
  await expect(sessionRegion).toBeVisible();
  await expect(sessionRegion.getByText('서명된 세션 연결됨 · 조직 스코프')).toBeVisible();

  const logoutButton = sessionRegion.getByRole('button', { name: '로그아웃' });
  await expect(logoutButton).toBeEnabled();

  if (testInfo.project.name === 'desktop') {
    await logoutButton.focus();
    await page.keyboard.press('Enter');
  } else {
    await logoutButton.tap();
  }

  await deleteStarted;
  const pendingButton = sessionRegion.getByRole('button', { name: '로그아웃 중' });
  await expect(pendingButton).toBeDisabled();
  await expect(pendingButton).toHaveAttribute('aria-busy', 'true');
  await expect(pendingButton.locator('svg[aria-hidden="true"]')).toHaveCount(1);
  expect(deleteCalls).toBe(1);

  await page.waitForTimeout(50);
  expect(deleteCalls).toBe(1);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await sessionRegion.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath(`settings-oidc-logout-pending-${testInfo.project.name}.png`),
    fullPage: false,
  });

  releaseDelete();

  await expect(sessionRegion.getByRole('alert')).toHaveText('OIDC session clear failed');
  const restoredButton = sessionRegion.getByRole('button', { name: '로그아웃' });
  await expect(restoredButton).toBeEnabled();
  await expect(restoredButton).toHaveAttribute('aria-busy', 'false');
  await expect(sessionRegion.getByText('서명된 세션 연결됨 · 조직 스코프')).toBeVisible();
  expect(deleteCalls).toBe(1);
});
