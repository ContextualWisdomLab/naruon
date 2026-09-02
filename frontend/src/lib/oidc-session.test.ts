/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildOidcAuthorizationUrl,
  clearOidcTransientState,
  clearOidcSession,
  completeOidcRedirect,
  getOidcBrowserConfig,
  startOidcLogin,
} from './oidc-session';

function installCrypto() {
  const cryptoMock = {
    getRandomValues: (bytes: Uint8Array) => {
      bytes.fill(7);
      return bytes;
    },
    subtle: {
      digest: vi.fn(async () => new Uint8Array([1, 2, 3, 4]).buffer),
    },
  };
  Object.defineProperty(window, 'crypto', {
    configurable: true,
    value: cryptoMock,
  });
}

describe('oidc-session', () => {
  beforeEach(() => {
    installCrypto();
    vi.stubEnv('NEXT_PUBLIC_OIDC_ISSUER_URL', 'https://login.example.com/realms/naruon/');
    vi.stubEnv('NEXT_PUBLIC_OIDC_CLIENT_ID', 'naruon-web');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('derives Keycloak endpoints from public OIDC settings', () => {
    const config = getOidcBrowserConfig('https://app.example.com');

    expect(config).toMatchObject({
      issuerUrl: 'https://login.example.com/realms/naruon',
      clientId: 'naruon-web',
      redirectUri: 'https://app.example.com/auth/callback',
      authorizationEndpoint: 'https://login.example.com/realms/naruon/protocol/openid-connect/auth',
      tokenEndpoint: 'https://login.example.com/realms/naruon/protocol/openid-connect/token',
      endSessionEndpoint: 'https://login.example.com/realms/naruon/protocol/openid-connect/logout',
    });
  });

  it('falls back to a top-level redirect when the login popup is blocked', async () => {
    const assignedUrls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(input).toBe('/auth/oidc/login');
      expect(init).toMatchObject({
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ return_to: '/settings' }),
      });
      return new Response(JSON.stringify({
        authorization_url: 'https://login.example.com/realms/naruon/protocol/openid-connect/auth?state=server-state',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }));

    // A blocked popup (returns null), matching how real browsers behave.
    void startOidcLogin({
      returnTo: '/settings',
      openPopup: () => null,
      navigate: (url) => assignedUrls.push(url),
    });
    await vi.waitFor(() => expect(assignedUrls).toHaveLength(1));

    expect(sessionStorage.getItem('naruon_oidc_state')).toBeNull();
    expect(sessionStorage.getItem('naruon_oidc_pkce_verifier')).toBeNull();
    expect(sessionStorage.getItem('naruon_oidc_return_to')).toBeNull();
    const authorizationUrl = new URL(assignedUrls[0]);
    expect(authorizationUrl.origin).toBe('https://login.example.com');
    expect(authorizationUrl.searchParams.get('state')).toBe('server-state');
  });

  it('opens the authorization URL in a popup and resolves once it posts back success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      authorization_url: 'https://login.example.com/realms/naruon/protocol/openid-connect/auth?state=server-state',
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));

    const fakePopup = { closed: false, focus: vi.fn() } as unknown as Window;
    const openedUrls: string[] = [];

    const loginPromise = startOidcLogin({
      returnTo: '/settings',
      openPopup: (url) => {
        openedUrls.push(url);
        return fakePopup;
      },
    });

    await vi.waitFor(() => expect(openedUrls).toHaveLength(1));
    window.dispatchEvent(new MessageEvent('message', {
      origin: window.location.origin,
      source: fakePopup,
      data: { source: 'naruon-oidc', status: 'success', returnTo: '/security' },
    }));

    await expect(loginPromise).resolves.toEqual({ returnTo: '/security' });
  });

  it('rejects when the login popup is closed before it posts back a result', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      authorization_url: 'https://login.example.com/realms/naruon/protocol/openid-connect/auth',
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));

    const fakePopup = { closed: false, focus: vi.fn() } as unknown as Window;
    const loginPromise = startOidcLogin({
      returnTo: '/settings',
      openPopup: () => fakePopup,
    });

    // Attach the rejection assertion before advancing timers so the promise
    // is never briefly unhandled once the popup-closed poll fires.
    const assertion = expect(loginPromise).rejects.toThrow('OIDC login window was closed before completing');
    (fakePopup as { closed: boolean }).closed = true;
    await vi.advanceTimersByTimeAsync(500);
    await assertion;
    vi.useRealTimers();
  });

  it('completes OIDC callback through the server-side cookie exchange route', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(input).toBe('/auth/oidc/callback');
      expect(init).toMatchObject({
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search: '?code=auth-code&state=state-123' }),
      });
      return new Response(JSON.stringify({ return_to: '/security' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }));

    const result = await completeOidcRedirect('?code=auth-code&state=state-123');

    expect(result.returnTo).toBe('/security');
    expect(sessionStorage.getItem('naruon_oidc_state')).toBeNull();
  });

  it('clears the server session state and redirects to the provider logout endpoint', async () => {
    sessionStorage.setItem('naruon_oidc_state', 'state-123');
    const assignedUrls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ authenticated: false }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })));

    await clearOidcSession({
      postLogoutRedirectUri: 'https://app.example.com',
      navigate: (url) => assignedUrls.push(url),
    });

    expect(sessionStorage.getItem('naruon_oidc_state')).toBeNull();
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/auth/session', {
      method: 'DELETE',
      credentials: 'same-origin',
    });
    const logoutUrl = new URL(assignedUrls[0]);
    expect(logoutUrl.toString()).toContain('/protocol/openid-connect/logout');
    expect(logoutUrl.searchParams.get('client_id')).toBe('naruon-web');
    expect(logoutUrl.searchParams.get('post_logout_redirect_uri')).toBe('https://app.example.com');
  });

  it('builds an authorization URL directly for deterministic callers', async () => {
    const config = getOidcBrowserConfig('https://app.example.com');
    expect(config).toBeTruthy();

    const authorizationUrl = await buildOidcAuthorizationUrl(config!, 'state-123', 'verifier-123');

    expect(new URL(authorizationUrl).searchParams.get('state')).toBe('state-123');
  });

  it('clears transient OIDC state from sessionStorage', () => {
    sessionStorage.setItem('naruon_oidc_state', 'state-123');
    sessionStorage.setItem('naruon_oidc_pkce_verifier', 'verifier-123');
    sessionStorage.setItem('naruon_oidc_return_to', '/settings');

    clearOidcTransientState();

    expect(sessionStorage.getItem('naruon_oidc_state')).toBeNull();
    expect(sessionStorage.getItem('naruon_oidc_pkce_verifier')).toBeNull();
    expect(sessionStorage.getItem('naruon_oidc_return_to')).toBeNull();
  });

  it('safely handles environments without browser storage', () => {
    vi.stubGlobal('window', undefined);

    expect(() => clearOidcTransientState()).not.toThrow();
  });
});
