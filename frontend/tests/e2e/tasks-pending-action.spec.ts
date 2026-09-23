import { expect, test, type Page, type Route } from '@playwright/test';

import { mockDashboardApi } from './helpers';

type IntentRelease = () => void;

function createIntentGate() {
  let releaseCreate!: IntentRelease;
  let releaseExecute!: IntentRelease;
  const createGate = new Promise<void>((resolve) => {
    releaseCreate = resolve;
  });
  const executeGate = new Promise<void>((resolve) => {
    releaseExecute = resolve;
  });
  return { createGate, executeGate, releaseCreate, releaseExecute };
}

async function fulfillIntent(route: Route, providerWriteExecuted: boolean) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      intent: 'knowledge_materialization',
      status: 'intent_ready',
      task_id: 'task-self-knowledge',
      source_type: 'self_sent_knowledge',
      source_email_id: 'self-note@example.com',
      source_thread_id: null,
      source_id: 'webdav_src_primary',
      target_label: 'Notes',
      target_path: '/notes/task-self-knowledge.md',
      requires_if_match: true,
      provenance: 'task',
      provider_write_executed: providerWriteExecuted,
      audit_event: 'knowledge_materialization_intent_created',
    }),
  });
}

async function preparePendingIntentPage(page: Page) {
  const gate = createIntentGate();
  const requestBodies: Record<string, unknown>[] = [];
  let requestCount = 0;

  await mockDashboardApi(page);
  await page.route('**/api/webdav/knowledge-materialization-intent', async (route) => {
    requestCount += 1;
    const body = route.request().postDataJSON() as Record<string, unknown>;
    requestBodies.push(body);
    if (requestCount === 1) {
      await gate.createGate;
      await fulfillIntent(route, false);
      return;
    }
    await gate.executeGate;
    await fulfillIntent(route, true);
  });

  await page.goto('/tasks');
  await expect(page.getByRole('heading', { name: '실행 항목 추적', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: '나에게 보낸 지식 메일 WebDAV 의도' })).toBeVisible();

  return { gate, requestBodies };
}

async function expectCreatePending(page: Page) {
  const createButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 의도 생성',
    exact: true,
  });
  const executeButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 실행 요청',
    exact: true,
  });

  await expect(createButton).toBeDisabled();
  await expect(executeButton).toBeDisabled();
  await expect(createButton).toHaveAttribute('aria-busy', 'true');
  await expect(executeButton).not.toHaveAttribute('aria-busy');
  await expect(createButton).toContainText('생성 중');
  await expect(executeButton).toContainText('실행 요청');
}

async function expectExecutePending(page: Page) {
  const createButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 의도 생성',
    exact: true,
  });
  const executeButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 실행 요청',
    exact: true,
  });

  await expect(createButton).toBeDisabled();
  await expect(executeButton).toBeDisabled();
  await expect(createButton).not.toHaveAttribute('aria-busy');
  await expect(executeButton).toHaveAttribute('aria-busy', 'true');
  await expect(createButton).toContainText('의도 생성');
  await expect(executeButton).toContainText('실행 중');
}

test('keeps Tasks create and execute pending identity distinct in a real browser', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 1024 });
  const { gate, requestBodies } = await preparePendingIntentPage(page);

  const createButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 의도 생성',
    exact: true,
  });
  const executeButton = page.getByRole('button', {
    name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 실행 요청',
    exact: true,
  });

  await createButton.click();
  await expectCreatePending(page);
  expect(requestBodies[0]).toEqual({ source_task_id: 'task-self-knowledge' });
  await page.screenshot({ path: testInfo.outputPath('tasks-knowledge-create-pending-desktop.png'), fullPage: false });

  gate.releaseCreate();
  await expect(page.getByText('WebDAV/Notes 의도 준비', { exact: true })).toBeVisible();
  await expect(createButton).toBeEnabled();
  await expect(executeButton).toBeEnabled();

  await executeButton.click();
  await expectExecutePending(page);
  expect(requestBodies[1]).toEqual({
    source_task_id: 'task-self-knowledge',
    execute_provider: true,
  });
  await page.screenshot({ path: testInfo.outputPath('tasks-knowledge-execute-pending-desktop.png'), fullPage: false });

  gate.releaseExecute();
  await expect(page.getByText('외부 쓰기 실행됨', { exact: true })).toBeVisible();
  await expect(createButton).toBeEnabled();
  await expect(executeButton).toBeEnabled();
});

test.describe('mobile touch pending identity', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  test('keeps the touched Tasks action as the only aria-busy control', async ({ page }, testInfo) => {
    const { gate } = await preparePendingIntentPage(page);
    const createButton = page.getByRole('button', {
      name: '나에게 보낸 지식 메모 정리 WebDAV 지식 노트 의도 생성',
      exact: true,
    });

    await createButton.tap();
    await expectCreatePending(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await page.screenshot({ path: testInfo.outputPath('tasks-knowledge-create-pending-mobile-touch.png'), fullPage: false });

    gate.releaseCreate();
    await expect(page.getByText('WebDAV/Notes 의도 준비', { exact: true })).toBeVisible();
  });
});
