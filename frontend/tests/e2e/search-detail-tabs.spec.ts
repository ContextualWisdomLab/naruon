import { expect, test, type Page } from '@playwright/test';

import { mockDashboardApi } from './helpers';

async function openSearch(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await mockDashboardApi(page);
  await page.goto('/search');
  await expect(page.getByRole('heading', { name: '맥락 검색', exact: true })).toBeVisible();
  await expect(page.getByRole('tablist', { name: '맥락 검색 결과 증거 상세' })).toBeVisible();
}

async function expectSelectedTab(page: Page, name: string, panelSuffix: string) {
  const tab = page.getByRole('tab', { name, exact: true });
  await expect(tab).toHaveAttribute('aria-selected', 'true');
  await expect(tab).toHaveAttribute('tabindex', '0');
  await expect(tab).toHaveAttribute('aria-controls', `search-detail-panel-${panelSuffix}`);
  await expect(tab).toBeFocused();
  await expect(page.getByRole('tabpanel')).toHaveAttribute('id', `search-detail-panel-${panelSuffix}`);
  await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', `search-detail-tab-${panelSuffix}`);
}

test('keeps Search detail tabs keyboard-operable in a real browser', async ({ page }, testInfo) => {
  await openSearch(page, 1280, 1024);

  const contextTab = page.getByRole('tab', { name: '맥락 정보', exact: true });
  const sourceTab = page.getByRole('tab', { name: '관계 원본', exact: true });
  const assistTab = page.getByRole('tab', { name: '판단 보조', exact: true });

  await expect(contextTab).toHaveAttribute('aria-selected', 'true');
  await expect(sourceTab).toHaveAttribute('tabindex', '-1');
  await expect(assistTab).toHaveAttribute('tabindex', '-1');

  await contextTab.focus();
  await contextTab.press('ArrowRight');
  await expectSelectedTab(page, '관계 원본', 'source');

  await sourceTab.press('ArrowRight');
  await expectSelectedTab(page, '판단 보조', 'assist');

  await assistTab.press('ArrowRight');
  await expectSelectedTab(page, '맥락 정보', 'context');

  await contextTab.press('ArrowLeft');
  await expectSelectedTab(page, '판단 보조', 'assist');

  await assistTab.press('Home');
  await expectSelectedTab(page, '맥락 정보', 'context');

  await contextTab.press('End');
  await expectSelectedTab(page, '판단 보조', 'assist');

  await assistTab.press('ArrowUp');
  await expectSelectedTab(page, '관계 원본', 'source');

  await sourceTab.press('PageDown');
  await expectSelectedTab(page, '관계 원본', 'source');

  await page.screenshot({ path: testInfo.outputPath('search-detail-tabs-keyboard-desktop.png'), fullPage: false });
});

test('keeps Search detail-tab selection usable at mobile width without overflow', async ({ page }, testInfo) => {
  await openSearch(page, 390, 844);

  const sourceTab = page.getByRole('tab', { name: '관계 원본', exact: true });
  await sourceTab.click();
  await expect(sourceTab).toHaveAttribute('aria-selected', 'true');
  await expect(sourceTab).toHaveAttribute('aria-controls', 'search-detail-panel-source');
  await expect(page.getByRole('tabpanel')).toHaveAttribute('id', 'search-detail-panel-source');

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath('search-detail-tabs-mobile.png'), fullPage: false });
});

test.describe('touch-capable mobile Search detail tabs', () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

  test('keeps tab semantics and touch targets usable with tap input', async ({ page }, testInfo) => {
    await openSearch(page, 390, 844);

    const sourceTab = page.getByRole('tab', { name: '관계 원본', exact: true });
    const assistTab = page.getByRole('tab', { name: '판단 보조', exact: true });

    for (const tab of [sourceTab, assistTab]) {
      const box = await tab.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThanOrEqual(24);
      expect(box!.height).toBeGreaterThanOrEqual(24);
    }

    await sourceTab.tap();
    await expect(sourceTab).toHaveAttribute('aria-selected', 'true');
    await expect(sourceTab).toHaveAttribute('aria-controls', 'search-detail-panel-source');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('id', 'search-detail-panel-source');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'search-detail-tab-source');

    await assistTab.tap();
    await expect(assistTab).toHaveAttribute('aria-selected', 'true');
    await expect(assistTab).toHaveAttribute('aria-controls', 'search-detail-panel-assist');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('id', 'search-detail-panel-assist');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'search-detail-tab-assist');

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await page.screenshot({ path: testInfo.outputPath('search-detail-tabs-touch-mobile.png'), fullPage: false });
  });
});
