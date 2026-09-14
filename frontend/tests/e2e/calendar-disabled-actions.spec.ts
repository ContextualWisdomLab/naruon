import { expect, test } from '@playwright/test';

import { mockDashboardApi } from './helpers';

const CALENDAR_TOGGLE_LABELS = [
  '김나루 (나) 캘린더 표시 토글',
  'Naruon PM 팀 캘린더 표시 토글',
  '제품 개발팀 캘린더 표시 토글',
  '마케팅팀 캘린더 표시 토글',
  '회사 공용 캘린더 표시 토글',
  '공휴일 캘린더 표시 토글',
] as const;

const EMPTY_ACTION_LABELS = ['일정 삭제', '일정 복사', '일정 수정'] as const;
const SELECTED_ACTION_LABELS = [
  '출시 회의 일정 삭제',
  '출시 회의 일정 복사',
  '출시 회의 일정 수정',
] as const;

const UNSUPPORTED_ACTION_REASON = '삭제·복사·수정은 이 상세 패널에서 지원하지 않습니다.';

test('keeps Calendar detail controls honest and accessible across selected and empty states', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'The event-detail sidebar is an xl desktop surface.');

  await page.setViewportSize({ width: 1440, height: 1024 });
  await mockDashboardApi(page);
  await page.goto('/calendar');

  await expect(page.getByRole('heading', { name: '출시 회의', exact: true })).toBeVisible();
  await expect(page.getByText('09:30', { exact: true })).toBeVisible();
  await expect(page.getByText('1시간 30분', { exact: true })).toBeVisible();
  await expect(page.getByText('2026.05.23 (목)', { exact: false })).toHaveCount(0);
  await expect(page.getByText('참석자 6명', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Naruon_2.0_런칭계획.pptx', { exact: true })).toHaveCount(0);
  await expect(page.getByText('출시_체크리스트.xlsx', { exact: true })).toHaveCount(0);
  await expect(page.getByText(/\(Naruon 2\.0\)/u)).toHaveCount(0);
  await expect(page.getByRole('button', { name: '닫기', exact: true })).toHaveCount(0);

  const reason = page.locator('#calendar-action-disabled-reason');
  await expect(reason).toHaveText(UNSUPPORTED_ACTION_REASON);
  await expect(reason).toBeVisible();

  for (const label of SELECTED_ACTION_LABELS) {
    const button = page.getByRole('button', { name: label, exact: true });
    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute('aria-describedby', 'calendar-action-disabled-reason');
  }

  const selectedLocationButton = page.getByRole('button', {
    name: '회의실 A (4층) 위치 보기',
    exact: true,
  });
  await expect(selectedLocationButton).toBeDisabled();
  await expect(selectedLocationButton).toHaveAttribute(
    'aria-describedby',
    'calendar-location-action-disabled-reason',
  );
  await expect(page.locator('#calendar-location-action-disabled-reason')).toHaveText(
    '위치 보기는 이 상세 패널에서 지원하지 않습니다.',
  );

  await page.screenshot({
    path: testInfo.outputPath('calendar-selected-event-integrity-desktop.png'),
    fullPage: false,
  });

  for (const label of CALENDAR_TOGGLE_LABELS) {
    const toggle = page.getByRole('checkbox', { name: label, exact: true });
    await expect(toggle).toBeVisible();
    if (await toggle.isChecked()) await toggle.uncheck();
  }

  await expect(reason).toHaveText(UNSUPPORTED_ACTION_REASON);
  await expect(reason).toBeVisible();

  for (const label of EMPTY_ACTION_LABELS) {
    const button = page.getByRole('button', { name: label, exact: true });
    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute('aria-describedby', 'calendar-action-disabled-reason');
    await expect(button).not.toHaveAttribute('title', /.+/u);
    const programmaticFocusAccepted = await button.evaluate((element) => {
      element.focus();
      return document.activeElement === element;
    });
    expect(programmaticFocusAccepted).toBe(false);
  }

  const locationSummary = page.locator('#calendar-location-summary');
  await expect(locationSummary).toHaveText('장소 없음');
  const locationButton = page.getByRole('button', { name: '장소 위치 보기', exact: true });
  await expect(locationButton).toBeDisabled();
  await expect(locationButton).toHaveAttribute('aria-describedby', 'calendar-location-summary');
  await expect(locationButton).not.toHaveAttribute('title', /.+/u);

  await expect(page.getByText('2026.05.23 (목)', { exact: false })).toHaveCount(0);
  await expect(page.getByText('참석자 6명', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Naruon_2.0_런칭계획.pptx', { exact: true })).toHaveCount(0);
  await expect(page.getByText('출시_체크리스트.xlsx', { exact: true })).toHaveCount(0);

  await reason.scrollIntoViewIfNeeded();
  const reasonBox = await reason.boundingBox();
  expect(reasonBox).not.toBeNull();
  expect(reasonBox!.x).toBeGreaterThanOrEqual(0);
  expect(reasonBox!.x + reasonBox!.width).toBeLessThanOrEqual(1440);
  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(horizontalOverflow).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: testInfo.outputPath('calendar-disabled-actions-desktop.png'),
    fullPage: false,
  });

  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(reason).toBeHidden();
  await expect(page.getByRole('button', { name: '일정 삭제', exact: true })).toBeHidden();
  const tabletOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(tabletOverflow).toBeLessThanOrEqual(1);
});
