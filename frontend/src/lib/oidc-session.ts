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
  navigate?: (url: string) => void;
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

type PublicOidcEnvName =
  | 'NEXT_PUBLIC_OIDC_ISSUER_URL'
  | 'NEXT_PUBLIC_OIDC_CLIENT_ID'
  | 'NEXT_PUBLIC_OIDC_REDIRECT_URI'
  | 'NEXT_PUBLIC_OIDC_SCOPE'
  | 'NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT'
  | 'NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT'
  | 'NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT';

function envValue(name: PublicOidcEnvName): string | null {
  // NEXT_PUBLIC_* values only reach the browser bundle through STATIC
  // `process.env.NEXT_PUBLIC_X` member accesses — Next.js never inlines
  // dynamic `process.env[name]` lookups, which silently disables browser
  // OIDC in every deployment. Keep each access literal.
  let raw: string | undefined;
  switch (name) {
    case 'NEXT_PUBLIC_OIDC_ISSUER_URL':
      raw = process.env.NEXT_PUBLIC_OIDC_ISSUER_URL;
      break;
    case 'NEXT_PUBLIC_OIDC_CLIENT_ID':
      raw = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
      break;
    case 'NEXT_PUBLIC_OIDC_REDIRECT_URI':
      raw = process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI;
      break;
    case 'NEXT_PUBLIC_OIDC_SCOPE':
      raw = process.env.NEXT_PUBLIC_OIDC_SCOPE;
      break;
    case 'NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT':
      raw = process.env.NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT;
      break;
    case 'NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT':
      raw = process.env.NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT;
      break;
    case 'NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT':
      raw = process.env.NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT;
      break;
  }
  const value = raw?.trim();
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

interface RuntimeOidcConfigPayload {
  configured?: unknown;
  issuer_url?: unknown;
  client_id?: unknown;
  redirect_uri?: unknown;
  scope?: unknown;
  authorization_endpoint?: unknown;
  end_session_endpoint?: unknown;
}

function stringField(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function runtimeConfigFromPayload(payload: RuntimeOidcConfigPayload, origin: string): OidcBrowserConfig | null {
  if (payload.configured !== true) return null;
  const issuerUrl = stringField(payload.issuer_url);
  const clientId = stringField(payload.client_id);
  if (!issuerUrl || !clientId) return null;

  const normalizedIssuer = trimTrailingSlash(issuerUrl);
  const keycloakEndpointBase = `${normalizedIssuer}/protocol/openid-connect`;
  return {
    issuerUrl: normalizedIssuer,
    clientId,
    redirectUri: stringField(payload.redirect_uri) ?? defaultRedirectUri(origin),
    scope: stringField(payload.scope) ?? DEFAULT_OIDC_SCOPE,
    authorizationEndpoint:
      stringField(payload.authorization_endpoint) ?? `${keycloakEndpointBase}/auth`,
    // The runtime route never exposes the token endpoint (its override may be
    // container-internal); the browser-facing derivation is only a placeholder
    // because the code exchange runs in the server routes.
    tokenEndpoint: `${keycloakEndpointBase}/token`,
    endSessionEndpoint:
      stringField(payload.end_session_endpoint) ?? `${keycloakEndpointBase}/logout`,
  };
}

// Build-time inlined values win when present; otherwise the frontend server
// reports its runtime env through /auth/oidc-config, so one prebuilt image
// works for every deployment without NEXT_PUBLIC_* build args.
export async function resolveOidcBrowserConfig(): Promise<OidcBrowserConfig | null> {
  const inlined = getOidcBrowserConfig();
  if (inlined) return inlined;

  try {
    const response = await fetch('/auth/oidc-config', {
      cache: 'no-store',
      credentials: 'same-origin',
    });
    if (!response.ok) return null;
    const payload = await response.json() as RuntimeOidcConfigPayload;
    return runtimeConfigFromPayload(payload, defaultBrowserOrigin());
  } catch {
    return null;
  }
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

export async function startOidcLogin(options: OidcLoginOptions = {}) {
  requireBrowserStorage();
  if (!(await resolveOidcBrowserConfig())) {
    throw new OidcSessionError('OIDC browser configuration is missing');
  }

  const authorizationUrl = await requestServerOidcLogin(
    options.returnTo ?? window.location.pathname,
  );
  const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
  navigate(authorizationUrl);
}

export async function completeOidcRedirect(search = window.location.search) {
  requireBrowserStorage();
  if (!(await resolveOidcBrowserConfig())) {
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
  const config = await resolveOidcBrowserConfig();
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
