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
   * Reserves the login window synchronously while the initiating browser event
   * still carries transient user activation. The reserved window starts at
   * `about:blank`; after server-side login initialization returns the trusted
   * authorization URL, startOidcLogin navigates this same window to Keyverse.
   * Return `null` (as a popup-blocked browser would) to use the top-level
   * navigation fallback instead.
   */
  openPopup?: (url: string, windowName: string) => Window | null;
}

/** BroadcastChannel payload the popup's `/auth/callback` page sends back once it completes. */
export interface OidcPopupResultMessage {
  source: 'naruon-oidc';
  /** Identifies which startOidcLogin() call this result belongs to. */
  flowId: string;
  status: 'success' | 'error';
  returnTo?: string;
  message?: string;
}

/**
 * Same-origin channel used instead of window.opener/postMessage, so the
 * popup can be opened with its opener severed (CWE-1021: an un-severed
 * opener lets the cross-origin authorization page navigate this tab).
 */
const OIDC_POPUP_CHANNEL = 'naruon-oidc-popup';

/**
 * Prefix for the popup's window.open() target name. The `/auth/callback`
 * page reads its own window.name back to learn whether it is running inside
 * this specific popup flow -- this works even with opener severed, and
 * (unlike a shared localStorage flag) carries no risk of two simultaneous
 * login attempts in different tabs clobbering each other's state.
 */
export const OIDC_POPUP_WINDOW_NAME_PREFIX = 'naruon-oidc-login-';

/** True when running inside the popup startOidcLogin opened for `flowId`. */
export function isOidcPopupFlow(): { isPopup: boolean; flowId: string | null } {
  if (typeof window === 'undefined' || !window.name.startsWith(OIDC_POPUP_WINDOW_NAME_PREFIX)) {
    return { isPopup: false, flowId: null };
  }
  return { isPopup: true, flowId: window.name.slice(OIDC_POPUP_WINDOW_NAME_PREFIX.length) };
}

/** Sends the popup's result back to whichever tab is waiting on this flowId. */
export function broadcastOidcPopupResult(message: OidcPopupResultMessage) {
  const channel = new BroadcastChannel(OIDC_POPUP_CHANNEL);
  channel.postMessage(message);
  channel.close();
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

/** Unique per-attempt id correlating a popup's result back to its starting call. */
function randomFlowId() {
  requireBrowserStorage();
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
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

function defaultOpenPopup(url: string, windowName: string): Window | null {
  if (typeof window.open !== 'function') return null;
  try {
    const popup = window.open(url, windowName, 'width=460,height=680');
    if (popup) {
      try {
        // Sever the reverse-tabnabbing vector (CWE-1021): without this, the
        // cross-origin authorization page could reach back into this tab via
        // window.opener (e.g. opener.location = ...). Completion is signalled
        // over BroadcastChannel below, which needs no opener relationship at
        // all, so severing it here costs nothing.
        popup.opener = null;
      } catch {
        // Best-effort; some environments restrict cross-window property
        // writes. The popup still functions, just without this hardening.
      }
    }
    return popup;
  } catch {
    return null;
  }
}

/** Close a reserved login window without making cleanup failure user-visible. */
function closeReservedPopup(popup: Window) {
  try {
    if (!popup.closed) popup.close();
  } catch {
    // Login initialization failure is the primary error; popup cleanup is best effort.
  }
}

/** Resolves once the matching-flowId popup result arrives, or rejects if it's closed first. */
function waitForPopupCompletion(popup: Window, flowId: string): Promise<{ returnTo: string }> {
  return new Promise((resolve, reject) => {
    const channel = new BroadcastChannel(OIDC_POPUP_CHANNEL);
    const cleanup = () => {
      window.clearInterval(closedPoll);
      channel.close();
    };
    channel.onmessage = (event: MessageEvent) => {
      const data = event.data as Partial<OidcPopupResultMessage> | null;
      if (!data || data.source !== 'naruon-oidc' || data.flowId !== flowId) return;
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
  });
}

/**
 * Starts an OIDC login. The popup is reserved before any asynchronous server
 * initialization so browser transient user activation is not lost while the
 * authorization URL is being prepared. Once the URL arrives, the same opener-
 * severed window is navigated to Keyverse. If popup reservation is blocked,
 * the flow falls back to the previous full top-level redirect.
 */
export async function startOidcLogin(options: OidcLoginOptions = {}): Promise<{ returnTo: string }> {
  requireBrowserStorage();
  if (!getOidcBrowserConfig()) {
    throw new OidcSessionError('OIDC browser configuration is missing');
  }

  const returnTo = options.returnTo ?? window.location.pathname;
  const flowId = randomFlowId();
  const openPopup = options.openPopup ?? defaultOpenPopup;
  const popup = openPopup('about:blank', `${OIDC_POPUP_WINDOW_NAME_PREFIX}${flowId}`);

  if (!popup) {
    const authorizationUrl = await requestServerOidcLogin(returnTo);
    const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
    navigate(authorizationUrl);
    return new Promise(() => {
      // Top-level navigation is about to unload this page; nothing left to resolve.
    });
  }

  let authorizationUrl: string;
  try {
    authorizationUrl = await requestServerOidcLogin(returnTo);
  } catch (error) {
    closeReservedPopup(popup);
    throw error;
  }

  try {
    // Assigning the reserved window's Location is permitted while it is still
    // the same-origin about:blank page. Reflect.set also keeps injected test
    // windows lightweight without weakening the browser path.
    if (!Reflect.set(popup, 'location', authorizationUrl)) {
      throw new Error('window location assignment was rejected');
    }
  } catch {
    closeReservedPopup(popup);
    throw new OidcSessionError('OIDC login window could not be navigated');
  }

  popup.focus();
  return waitForPopupCompletion(popup, flowId);
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
