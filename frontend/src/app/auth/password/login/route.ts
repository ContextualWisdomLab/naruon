import { NextRequest } from "next/server";

import { sameOriginStateChangingRequest } from "@/lib/csrf-origin";

import {
  errorResponse,
  exchangePasswordForSessionResponse,
  normalizeCredential,
  readBoundedJson,
  RequestBodyTooLargeError,
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
 * inside it and is never logged, cached, or persisted.
 *
 * **THIS MECHANISM MUST NOT SHIP AS THE GA AUTHENTICATION PATH.** RFC 9700
 * §2.4 (BCP 240, Jan 2025) states the Resource Owner Password Credentials
 * grant MUST NOT be used; RFC 10017 §7.3 (OAuth 2.0 for Browser-Based
 * Applications, BCP, Aug 2026) independently repeats that prohibition for
 * browser-based apps specifically and requires a redirect-based flow such as
 * Authorization Code instead. A product-owner risk acceptance documents an
 * organizational deviation, not standards compliance — it does not make
 * `grant_type=password` conforming. This route exists as transitional
 * evidence for the product requirement (naruon-owned UI, Keyverse as
 * identity backend, zero Keycloak-rendered HTML), not as an approved
 * mechanism; PR #1532 that introduces it was returned to Draft over this
 * exact finding. Do not remove this route or its tests when repairing this
 * — preserve it as evidence for the successor mechanism — but do not wire it
 * into a production login flow, feature-flag it on, or treat its presence
 * here as license to merge. See docs/adr/0005-naruon-owned-password-login-form.md
 * ("Standards finding" and "Current decision" sections) for the full
 * reasoning, the security repairs in this route worth preserving regardless
 * of mechanism, and what a compliant successor needs from Keyverse before
 * this can become Ready.
 */
export async function POST(request: NextRequest) {
  if (!sameOriginStateChangingRequest(request)) {
    return errorResponse("csrf_origin_rejected", 403);
  }

  const config = serverOidcConfig(request.nextUrl.origin);
  if (!config) {
    return errorResponse("oidc_browser_configuration_missing", 503);
  }

  let body: unknown;
  try {
    body = await readBoundedJson(request);
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return errorResponse("password_login_request_too_large", 413);
    }
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
