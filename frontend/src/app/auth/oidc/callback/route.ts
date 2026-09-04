import { NextRequest, NextResponse } from "next/server";

import {
  buildExpiredSessionCookieOptions,
  buildSessionCookieOptions,
  normalizeSessionToken,
} from "@/lib/session-cookie";
import { postOidcTokenRequest } from "@/lib/oidc-token-client";

import {
  OIDC_NO_STORE_HEADERS,
  OIDC_PKCE_COOKIE_NAME,
  backendAcceptsSessionToken,
  decodeOidcStateCookie,
  errorResponse,
  expiredOidcStateCookieOptions,
  recordOidcTokenExchangeFailure,
  serverOidcConfig,
  trustedOidcTokenEndpoint,
} from "../shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

function searchParamsFromBodySearch(value: unknown) {
  const search = typeof value === "string" ? value.trim() : "";
  return new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
}

export async function POST(request: NextRequest) {
  const config = serverOidcConfig(request.nextUrl.origin);
  if (!config) {
    return errorResponse("oidc_browser_configuration_missing", 503);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse("oidc_callback_request_invalid");
  }

  const params = searchParamsFromBodySearch(
    body && typeof body === "object"
      ? (body as { search?: unknown }).search
      : null,
  );
  if (params.get("error")) {
    return errorResponse("oidc_provider_error");
  }

  const code = params.get("code");
  const state = params.get("state");
  const stateCookie = decodeOidcStateCookie(
    request.cookies.get(OIDC_PKCE_COOKIE_NAME)?.value,
  );
  if (!code || !state || !stateCookie || state !== stateCookie.state) {
    return errorResponse("oidc_callback_state_invalid");
  }

  const tokenBody = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.clientId,
    code,
    code_verifier: stateCookie.verifier,
    redirect_uri: config.redirectUri,
  });
  let tokenEndpoint: URL;
  try {
    tokenEndpoint = trustedOidcTokenEndpoint(config);
  } catch {
    recordOidcTokenExchangeFailure("configuration_rejected");
    return errorResponse("oidc_token_exchange_failed", 502);
  }

  let accessToken: string | null = null;
  try {
    const tokenJson = await postOidcTokenRequest(tokenEndpoint, tokenBody);
    accessToken = normalizeSessionToken(tokenJson.access_token);
  } catch {
    recordOidcTokenExchangeFailure("dns_or_transport_rejected");
    return errorResponse("oidc_token_exchange_failed", 502);
  }

  if (!accessToken) {
    recordOidcTokenExchangeFailure("access_token_missing_or_invalid");
  }
  const backendAccepted =
    accessToken ? await backendAcceptsSessionToken(accessToken) : false;
  if (!accessToken || !backendAccepted) {
    if (accessToken && !backendAccepted) {
      recordOidcTokenExchangeFailure("backend_session_rejected");
    }
    const response = errorResponse("invalid_session_token", 401);
    response.cookies.set(expiredOidcStateCookieOptions());
    response.cookies.set(buildExpiredSessionCookieOptions());
    return response;
  }

  const response = NextResponse.json(
    { return_to: stateCookie.return_to },
    { headers: OIDC_NO_STORE_HEADERS },
  );
  response.cookies.set(buildSessionCookieOptions(accessToken));
  response.cookies.set(expiredOidcStateCookieOptions());
  return response;
}
