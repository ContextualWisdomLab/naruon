import { expect, test } from '@playwright/test';

import { mockDashboardApi } from './helpers';

const publicIdentityHeaders = [
  'x-user-id',
  'x-organization-id',
  'x-group-id',
  'x-group-ids',
  'x-user-role',
  'x-dev-auth-token',
];

const viewports = [
  { name: 'desktop', width: 1280, height: 720 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

for (const viewport of viewports) {
  test(`renders source-backed AI Hub with scroll at ${viewport.name}`, async ({ page }, testInfo) => {
    const sessionToken = `signed-ai-hub.${viewport.name}.token`;
    const surfaceRequestHeaders: Record<string, string>[] = [];
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await mockDashboardApi(page, (path, request) => {
      if (path === '/api/ai-hub/surface' && request.method() === 'GET') {
        surfaceRequestHeaders.push(request.headers());
      }
    });
    await page.addInitScript((token) => {
      document.cookie = `naruon_session=${token}; Path=/; SameSite=Lax`;
    }, sessionToken);

    await page.goto('/ai-hub');
    await expect.poll(() => surfaceRequestHeaders.length).toBeGreaterThan(0);

    const headers = surfaceRequestHeaders.at(-1) ?? {};
    expect(headers.authorization).toBeUndefined();
    expect(headers.cookie).toContain(`naruon_session=${sessionToken}`);
    for (const headerName of publicIdentityHeaders) {
      expect(headers[headerName]).toBeUndefined();
    }

    await expect(page.getByRole('heading', { name: 'AI 허브' })).toBeVisible();
    await expect(page.getByRole('region', { name: '맥락 종합' })).toBeVisible();
    await expect(page.getByRole('region', { name: '판단 포인트' })).toBeVisible();
    await expect(page.getByRole('region', { name: '실행 항목' })).toBeVisible();
    await expect(
      page.getByRole('region', { name: '맥락 종합' }).getByRole('heading', { name: '의사결정 로그 맥락 종합' }),
    ).toBeVisible();
    await page.getByRole('tab', { name: /워크플로우/ }).click();
    await expect(
      page.getByRole('tabpanel', { name: '워크플로우' }).getByRole('heading', { name: '의사결정 로그 자동 작성' }),
    ).toBeVisible();
    await page.getByRole('tab', { name: /판단 보조/ }).click();
    await expect(page.getByRole('tabpanel', { name: '판단 보조' }).getByRole('heading', { name: 'Primary OpenAI' })).toBeVisible();
    await page.getByRole('tab', { name: /평가/ }).click();
    await expect(page.getByRole('tabpanel', { name: '평가' }).getByRole('heading', { name: '연동 준비도' })).toBeVisible();
    await page.getByRole('tab', { name: /실행 이력/ }).click();
    await expect(page.getByRole('tabpanel', { name: '실행 이력' }).getByText('agent_run_records')).toBeVisible();

    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);

    const aiHubScroller = page.locator('main').last();
    const scrollMetrics = await aiHubScroller.evaluate((node) => {
      const element = node as HTMLElement;
      element.scrollTop = 0;
      const before = element.scrollTop;
      element.scrollTop = element.scrollHeight;
      return {
        before,
        after: element.scrollTop,
        maxScroll: element.scrollHeight - element.clientHeight,
      };
    });
    expect(scrollMetrics.maxScroll).toBeGreaterThan(0);
    expect(scrollMetrics.after).toBeGreaterThan(scrollMetrics.before);

    await page.screenshot({ path: testInfo.outputPath(`ai-hub-${viewport.name}-scrolled.png`), fullPage: false });

    if (viewport.name === 'mobile') {
      await page.getByRole('button', { name: '워크스페이스 메뉴 열기' }).click();
      const mobileMenu = page.locator('#mobile-workspace-menu');
      await expect(mobileMenu).toBeVisible();
      await expect(mobileMenu.getByRole('link', { name: /AI 허브/ })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath('ai-hub-mobile-hamburger.png'), fullPage: false });
    }
  });
}
