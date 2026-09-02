import { NextRequest, NextResponse } from "next/server";

import { buildSessionCookieOptions, normalizeSessionToken } from "@/lib/session-cookie";
import { postOidcTokenRequest } from "@/lib/oidc-token-client";

import {
  OIDC_NO_STORE_HEADERS,
  backendAcceptsSessionToken,
  errorResponse,
  recordOidcTokenExchangeFailure,
  safeReturnTo,
  serverOidcConfig,
  trustedOidcTokenEndpoint,
} from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

// Generous enough for any real email/passphrase; bounds the request body so
// a caller cannot force an oversized synchronous parse/allocation.
const MAX_CREDENTIAL_LENGTH = 256;

function normalizeCredential(value: unknown): string | null {
  if (typeof value !== "string") return null;
  if (!value || value.length > MAX_CREDENTIAL_LENGTH) return null;
  return value;
}

/**
 * naruon's own login form calls this route directly — no redirect to, or
 * page rendered by, Keyverse/Keycloak. It performs the OAuth2 Resource Owner
 * Password Credentials grant (Keycloak's "Direct Access Grants") server-side
 * against Keycloak's token endpoint: the password exists only in this
 * request's memory for the single call below and is never logged, cached,
 * or persisted. See docs/adr/0015-naruon-owned-password-form.md for why this
 * mechanism was chosen over a Keycloak-rendered (even reskinned) page, and
 * the passwordless-vs-password tradeoff it accepts.
 */
export async function POST(request: NextRequest) {
  const config = serverOidcConfig(request.nextUrl.origin);
  if (!config) {
    return errorResponse("oidc_browser_configuration_missing", 503);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse("password_login_request_invalid");
  }

  const parsed = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const username = normalizeCredential(parsed.username);
  const password = normalizeCredential(parsed.password);
  const returnTo = safeReturnTo(parsed.return_to);
  if (!username || !password) {
    return errorResponse("password_login_credentials_invalid");
  }

  const tokenBody = new URLSearchParams({
    grant_type: "password",
    client_id: config.clientId,
    scope: config.scope,
    username,
    password,
  });

  let tokenEndpoint: URL;
  try {
    tokenEndpoint = trustedOidcTokenEndpoint(config);
  } catch {
    recordOidcTokenExchangeFailure("configuration_rejected");
    return errorResponse("password_login_failed", 502);
  }

  let accessToken: string | null = null;
  try {
    const tokenJson = await postOidcTokenRequest(tokenEndpoint, tokenBody);
    accessToken = normalizeSessionToken(tokenJson.access_token);
  } catch {
    // Keycloak rejects a wrong password, an unknown user, or a client
    // without Direct Access Grants enabled all as a non-2xx response, which
    // postOidcTokenRequest turns into a rejection here. Collapsing every
    // case to one generic message avoids leaking which one it was.
    recordOidcTokenExchangeFailure("invalid_credentials");
    return errorResponse("password_login_invalid_credentials", 401);
  }

  if (!accessToken) {
    recordOidcTokenExchangeFailure("access_token_missing_or_invalid");
  }
  const backendAccepted = accessToken ? await backendAcceptsSessionToken(accessToken) : false;
  if (!accessToken || !backendAccepted) {
    if (accessToken && !backendAccepted) {
      recordOidcTokenExchangeFailure("backend_session_rejected");
    }
    return errorResponse("password_login_invalid_credentials", 401);
  }

  const response = NextResponse.json(
    { return_to: returnTo },
    { headers: OIDC_NO_STORE_HEADERS },
  );
  response.cookies.set(buildSessionCookieOptions(accessToken));
  return response;
}
