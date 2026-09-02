import { NextRequest } from "next/server";

import {
  errorResponse,
  exchangePasswordForSessionResponse,
  normalizeCredential,
  safeReturnTo,
  serverOidcConfig,
} from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

/**
 * naruon's own login form calls this route directly — no redirect to, or
 * page rendered by, Keyverse/Keycloak. It performs the OAuth2 Resource Owner
 * Password Credentials grant (Keycloak's "Direct Access Grants") server-side
 * against Keycloak's token endpoint via `exchangePasswordForSessionResponse`:
 * the password exists only in this request's memory for the single call
 * inside it and is never logged, cached, or persisted. See
 * docs/adr/0005-naruon-owned-password-login-form.md for why this mechanism
 * was chosen over a Keycloak-rendered (even reskinned) page, and the
 * passwordless-vs-password tradeoff it accepts.
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

  return exchangePasswordForSessionResponse(config, username, password, returnTo);
}
