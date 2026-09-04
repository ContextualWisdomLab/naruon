import { expect, test, type BrowserContext, type Page } from '@playwright/test';

interface AuthHarness {
  setAuthenticated(value: boolean): void;
  setAuthorizationTarget(target: 'callback' | 'hold'): void;
}

async function installAuthHarness(context: BrowserContext): Promise<AuthHarness> {
  let authenticated = false;
  let authorizationTarget: 'callback' | 'hold' = 'callback';

  await context.route('**/api/**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error_code: 'e2e_unavailable' }),
    });
  });

  await context.route('**/auth/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        claims: authenticated
          ? {
              userId: 'e2e-user',
              organizationId: 'e2e-org',
              workspaceId: 'e2e-workspace',
            }
          : {},
      }),
    });
  });

  await context.route('**/auth/oidc/login', async (route) => {
    const requestUrl = new URL(route.request().url());
    const target = authorizationTarget === 'callback'
      ? `${requestUrl.origin}/auth/callback?code=e2e-code&state=e2e-state`
      : `${requestUrl.origin}/auth/e2e-login-hold`;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ authorization_url: target }),
    });
  });

  await context.route('**/auth/oidc/callback', async (route) => {
    authenticated = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ return_to: '/settings' }),
    });
  });

  return {
    setAuthenticated(value: boolean) {
      authenticated = value;
    },
    setAuthorizationTarget(target: 'callback' | 'hold') {
      authorizationTarget = target;
    },
  };
}

async function openSsoSettings(page: Page) {
  await page.goto('/settings');
  await page.getByRole('button', { name: '개발자' }).first().click();
  const loginButton = page.getByRole('button', { name: 'Keyverse SSO로 로그인', exact: true });
  await expect(loginButton).toBeEnabled();
  return loginButton;
}

test('Keyverse SSO popup completes through BroadcastChannel and closes without navigating the app tab', async ({ context, page }) => {
  const harness = await installAuthHarness(context);
  harness.setAuthenticated(false);
  harness.setAuthorizationTarget('callback');
  const loginButton = await openSsoSettings(page);

  const popupOpened = context.waitForEvent('page');
  await loginButton.click();
  const popup = await popupOpened;

  await expect.poll(() => popup.isClosed()).toBe(true);
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByText(/서명된 세션 연결됨/)).toBeVisible();
});

test('closing the reserved Keyverse popup fails visibly instead of silently leaving login pending', async ({ context, page }) => {
  const harness = await installAuthHarness(context);
  harness.setAuthorizationTarget('hold');
  const loginButton = await openSsoSettings(page);

  const popupOpened = context.waitForEvent('page');
  await loginButton.click();
  const popup = await popupOpened;
  await popup.close();

  await expect(page.getByRole('alert')).toContainText('OIDC login window was closed before completing');
  await expect(page).toHaveURL(/\/settings$/);
});

test('popup blocking falls back to the same tab and completes the callback without closing the app page', async ({ context, page }) => {
  const harness = await installAuthHarness(context);
  harness.setAuthenticated(false);
  harness.setAuthorizationTarget('callback');
  await page.addInitScript(() => {
    Object.defineProperty(window, 'open', {
      configurable: true,
      value: () => null,
    });
  });
  const loginButton = await openSsoSettings(page);

  await loginButton.click();

  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByText(/서명된 세션 연결됨/)).toBeVisible();
  expect(context.pages()).toHaveLength(1);
});
