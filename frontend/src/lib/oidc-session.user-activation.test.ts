/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OIDC_POPUP_WINDOW_NAME_PREFIX, startOidcLogin } from './oidc-session';

function installCrypto() {
  const cryptoMock = {
    getRandomValues: (bytes: Uint8Array) => {
      bytes.fill(11);
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

describe('OIDC popup user-activation boundary', () => {
  beforeEach(() => {
    installCrypto();
    vi.stubEnv('NEXT_PUBLIC_OIDC_ISSUER_URL', 'https://login.example.com/realms/naruon/');
    vi.stubEnv('NEXT_PUBLIC_OIDC_CLIENT_ID', 'naruon-web');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('reserves the popup before awaiting server-side login initialization', async () => {
    let resolveLoginResponse!: (response: Response) => void;
    const loginResponse = new Promise<Response>((resolve) => {
      resolveLoginResponse = resolve;
    });
    vi.stubGlobal('fetch', vi.fn(() => loginResponse));

    const openPopup = vi.fn(() => null);
    const navigate = vi.fn();

    void startOidcLogin({
      returnTo: '/settings',
      openPopup,
      navigate,
    });

    // A popup must be reserved synchronously while the initiating click still
    // carries transient user activation. Network initialization may finish
    // after that browser activation window has expired.
    const popupCallsBeforeServerResolution = openPopup.mock.calls.length;

    resolveLoginResponse(new Response(JSON.stringify({
      authorization_url: 'https://login.example.com/realms/naruon/protocol/openid-connect/auth?state=server-state',
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));

    expect(popupCallsBeforeServerResolution).toBe(1);
    expect(openPopup).toHaveBeenCalledWith(
      'about:blank',
      expect.stringMatching(new RegExp(`^${OIDC_POPUP_WINDOW_NAME_PREFIX}.+`)),
    );
  });
});
