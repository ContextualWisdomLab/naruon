export interface OidcBrowserConfig {
  issuerUrl: string;
  clientId: string;
  redirectUri: string;
  scope: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  endSessionEndpoint: string;
}

export interface OidcLoginOptions {
  returnTo?: string;
  /** Fallback top-level navigation, used only when a popup cannot be opened. */
  navigate?: (url: string) => void;
  /**
   * Opens the Keycloak authorization URL. Defaults to a small `window.open`
   * popup so the user's naruon tab never navigates away; return `null` (as a
   * popup-blocked browser would) to fall back to `navigate`.
   */
  openPopup?: (url: string) => Window | null;
}

/** postMessage payload the popup's `/auth/callback` page sends back to the opener. */
export interface OidcPopupResultMessage {
  source: 'naruon-oidc';
  status: 'success' | 'error';
  returnTo?: string;
  message?: string;
}

export interface OidcLogoutOptions {
  postLogoutRedirectUri?: string;
  navigate?: (url: string) => void;
}

const DEFAULT_OIDC_SCOPE = 'openid profile email';
const LEGACY_OIDC_STORAGE_KEYS = [
  'naruon_oidc_state',
  'naruon_oidc_pkce_verifier',
  'naruon_oidc_return_to',
];

export class OidcSessionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'OidcSessionError';
  }
}

async function requestServerOidcLogin(returnTo: string) {
  const response = await fetch('/auth/oidc/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ return_to: returnTo }),
  });
  if (!response.ok) {
    throw new OidcSessionError('OIDC login initialization failed');
  }
  const body = await response.json() as { authorization_url?: unknown };
  const authorizationUrl = typeof body.authorization_url === 'string' ? body.authorization_url : '';
  if (!authorizationUrl) {
    throw new OidcSessionError('OIDC login response did not include an authorization URL');
  }
  return authorizationUrl;
}

async function completeServerOidcCallback(search: string) {
  const response = await fetch('/auth/oidc/callback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ search }),
  });
  if (!response.ok) {
    throw new OidcSessionError('OIDC callback exchange failed');
  }
  const body = await response.json() as { return_to?: unknown };
  return typeof body.return_to === 'string' && body.return_to ? body.return_to : '/';
}

async function clearPersistedOidcSession() {
  const response = await fetch('/auth/session', {
    method: 'DELETE',
    credentials: 'same-origin',
  });
  if (!response.ok) {
    throw new OidcSessionError('OIDC session clear failed');
  }
}

function envValue(name: string): string | null {
  const value = process.env[name]?.trim();
  return value ? value : null;
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function defaultBrowserOrigin() {
  if (typeof window === 'undefined') return '';
  return window.location.origin;
}

function defaultRedirectUri(origin: string) {
  return origin ? `${origin}/auth/callback` : '/auth/callback';
}

export function getOidcBrowserConfig(origin = defaultBrowserOrigin()): OidcBrowserConfig | null {
  const issuerUrl = envValue('NEXT_PUBLIC_OIDC_ISSUER_URL');
  const clientId = envValue('NEXT_PUBLIC_OIDC_CLIENT_ID');
  if (!issuerUrl || !clientId) return null;

  const normalizedIssuer = trimTrailingSlash(issuerUrl);
  const keycloakEndpointBase = `${normalizedIssuer}/protocol/openid-connect`;
  return {
    issuerUrl: normalizedIssuer,
    clientId,
    redirectUri: envValue('NEXT_PUBLIC_OIDC_REDIRECT_URI') ?? defaultRedirectUri(origin),
    scope: envValue('NEXT_PUBLIC_OIDC_SCOPE') ?? DEFAULT_OIDC_SCOPE,
    authorizationEndpoint: envValue('NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT') ?? `${keycloakEndpointBase}/auth`,
    tokenEndpoint: envValue('NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT') ?? `${keycloakEndpointBase}/token`,
    endSessionEndpoint: envValue('NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT') ?? `${keycloakEndpointBase}/logout`,
  };
}

function requireBrowserStorage() {
  if (typeof window === 'undefined') {
    throw new OidcSessionError('OIDC browser session storage is unavailable');
  }
}

function base64UrlEncode(bytes: Uint8Array) {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function pkceChallenge(verifier: string) {
  requireBrowserStorage();
  const encoded = new TextEncoder().encode(verifier);
  const digest = await window.crypto.subtle.digest('SHA-256', encoded);
  return base64UrlEncode(new Uint8Array(digest));
}

export async function buildOidcAuthorizationUrl(config: OidcBrowserConfig, state: string, verifier: string) {
  const challenge = await pkceChallenge(verifier);
  const authorizationUrl = new URL(config.authorizationEndpoint);
  authorizationUrl.searchParams.set('response_type', 'code');
  authorizationUrl.searchParams.set('client_id', config.clientId);
  authorizationUrl.searchParams.set('redirect_uri', config.redirectUri);
  authorizationUrl.searchParams.set('scope', config.scope);
  authorizationUrl.searchParams.set('state', state);
  authorizationUrl.searchParams.set('code_challenge', challenge);
  authorizationUrl.searchParams.set('code_challenge_method', 'S256');
  return authorizationUrl.toString();
}

function defaultOpenPopup(url: string): Window | null {
  if (typeof window.open !== 'function') return null;
  try {
    return window.open(url, 'naruon-oidc-login', 'width=460,height=680,noopener=false');
  } catch {
    return null;
  }
}

/** Resolves once the popup posts back a result, or rejects if it's closed first. */
function waitForPopupCompletion(popup: Window): Promise<{ returnTo: string }> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearInterval(closedPoll);
      window.removeEventListener('message', onMessage);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== popup) return;
      const data = event.data as Partial<OidcPopupResultMessage> | null;
      if (!data || data.source !== 'naruon-oidc') return;
      cleanup();
      if (data.status === 'success') {
        resolve({ returnTo: typeof data.returnTo === 'string' && data.returnTo ? data.returnTo : '/' });
      } else {
        reject(new OidcSessionError(data.message ?? 'OIDC login failed'));
      }
    };
    const closedPoll = window.setInterval(() => {
      if (popup.closed) {
        cleanup();
        reject(new OidcSessionError('OIDC login window was closed before completing'));
      }
    }, 500);
    window.addEventListener('message', onMessage);
  });
}

/**
 * Starts an OIDC login. By default this opens Keycloak's authorization URL in
 * a popup so naruon's own tab/page never navigates away — only the credential
 * ceremony itself runs on Keyverse's origin, which WebAuthn requires anyway.
 * If the popup is blocked, this falls back to the previous full top-level
 * redirect (and the returned promise never resolves, since the page unloads).
 */
export async function startOidcLogin(options: OidcLoginOptions = {}): Promise<{ returnTo: string }> {
  requireBrowserStorage();
  if (!getOidcBrowserConfig()) {
    throw new OidcSessionError('OIDC browser configuration is missing');
  }

  const authorizationUrl = await requestServerOidcLogin(
    options.returnTo ?? window.location.pathname,
  );
  const openPopup = options.openPopup ?? defaultOpenPopup;
  const popup = openPopup(authorizationUrl);
  if (!popup) {
    const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
    navigate(authorizationUrl);
    return new Promise(() => {
      // Top-level navigation is about to unload this page; nothing left to resolve.
    });
  }
  popup.focus();
  return waitForPopupCompletion(popup);
}

export async function completeOidcRedirect(search = window.location.search) {
  requireBrowserStorage();
  if (!getOidcBrowserConfig()) {
    throw new OidcSessionError('OIDC browser configuration is missing');
  }

  const returnTo = await completeServerOidcCallback(search);
  return { returnTo };
}

export function clearOidcTransientState() {
  if (typeof window === 'undefined') return;
  LEGACY_OIDC_STORAGE_KEYS.forEach((key) => {
    window.sessionStorage.removeItem(key);
  });
}

export async function clearOidcSession(options: OidcLogoutOptions = {}) {
  requireBrowserStorage();
  const config = getOidcBrowserConfig();
  await clearPersistedOidcSession();
  clearOidcTransientState();

  if (!config) return;
  const postLogoutRedirectUri = options.postLogoutRedirectUri ?? window.location.origin;
  const logoutUrl = new URL(config.endSessionEndpoint);
  logoutUrl.searchParams.set('client_id', config.clientId);
  logoutUrl.searchParams.set('post_logout_redirect_uri', postLogoutRedirectUri);
  const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
  navigate(logoutUrl.toString());
}
