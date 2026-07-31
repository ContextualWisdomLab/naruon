import { NextRequest, NextResponse } from "next/server";

import { backendApiBaseUrl } from "@/lib/backend-url";
import {
  buildExpiredSessionCookieOptions,
  buildSessionCookieOptions,
  normalizeSessionToken,
} from "@/lib/session-cookie";

import {
  OIDC_NO_STORE_HEADERS,
  OIDC_PKCE_COOKIE_NAME,
  decodeOidcStateCookie,
  expiredOidcStateCookieOptions,
  serverOidcConfig,
} from "../shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

function errorResponse(errorCode: string, status = 400) {
  return NextResponse.json(
    { error_code: errorCode },
    { status, headers: OIDC_NO_STORE_HEADERS },
  );
}

function searchParamsFromBodySearch(value: unknown) {
  const search = typeof value === "string" ? value.trim() : "";
  return new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
}

async function backendAcceptsSessionToken(token: string) {
  const target = backendApiBaseUrl();
  target.pathname = "/api/auth/session";
  target.search = "";
  try {
    const response = await fetch(target, {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });
    if (!response.ok) return false;
    const body = await response.json() as {
      user_id?: unknown;
      organization_id?: unknown;
      workspace_id?: unknown;
    };
    return (
      typeof body.user_id === "string" &&
      typeof body.organization_id === "string" &&
      typeof body.workspace_id === "string"
    );
  } catch {
    return false;
  }
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
  let accessToken: string | null = null;
  try {
    const tokenResponse = await fetch(config.tokenEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: tokenBody,
      cache: "no-store",
    });
    if (!tokenResponse.ok) {
      return errorResponse("oidc_token_exchange_failed", 502);
    }
    const tokenJson = await tokenResponse.json() as { access_token?: unknown };
    accessToken = normalizeSessionToken(tokenJson.access_token);
  } catch {
    return errorResponse("oidc_token_exchange_failed", 502);
  }

  if (!accessToken || !(await backendAcceptsSessionToken(accessToken))) {
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
