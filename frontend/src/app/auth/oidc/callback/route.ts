import { NextRequest, NextResponse } from "next/server";

import { fetchTrustedBackendSession } from "@/lib/backend-session-probe";
import {
  isIpv4MappedHostname,
  isLoopbackHostname,
  isPrivateOrLoopbackHostname,
  normalizeHostname,
} from "@/lib/host-policy";
import {
  buildExpiredSessionCookieOptions,
  buildSessionCookieOptions,
  normalizeSessionToken,
} from "@/lib/session-cookie";
import { postOidcTokenRequest } from "@/lib/oidc-token-client";

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

const OIDC_CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/;
const OIDC_ALLOWED_HOSTS_ENV = "OIDC_ALLOWED_HOSTS";
type OidcTokenExchangeFailureReason =
  | "configuration_rejected"
  | "dns_or_transport_rejected"
  | "access_token_missing_or_invalid"
  | "backend_session_rejected";

function errorResponse(errorCode: string, status = 400) {
  return NextResponse.json(
    { error_code: errorCode },
    { status, headers: OIDC_NO_STORE_HEADERS },
  );
}

function recordOidcTokenExchangeFailure(
  reason: OidcTokenExchangeFailureReason,
): void {
  console.warn("oidc_token_exchange_failed", { reason });
}

function searchParamsFromBodySearch(value: unknown) {
  const search = typeof value === "string" ? value.trim() : "";
  return new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
}

function assertAllowedOidcHostname(hostname: string): void {
  const configuredHosts = process.env[OIDC_ALLOWED_HOSTS_ENV]?.trim();
  if (!configuredHosts) {
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        `${OIDC_ALLOWED_HOSTS_ENV} is required for production OIDC token exchange`,
      );
    }
    return;
  }
  const allowedHosts = new Set(
    configuredHosts
      .split(",")
      .map((host) =>
        host
          .trim()
          .replace(/^\[/, "")
          .replace(/\]$/, "")
          .replace(/\.+$/, "")
          .toLowerCase(),
      )
      .filter(Boolean),
  );
  if (!allowedHosts.has(hostname)) {
    throw new Error(
      `OIDC token endpoint host must be listed in ${OIDC_ALLOWED_HOSTS_ENV}`,
    );
  }
}

function trustedOidcTokenEndpoint(config: {
  issuerUrl: string;
  tokenEndpoint: string;
}): URL {
  const issuer = new URL(config.issuerUrl);
  const endpoint = new URL(config.tokenEndpoint);
  const hostname = normalizeHostname(endpoint);
  if (
    !hostname ||
    endpoint.username ||
    endpoint.password ||
    endpoint.search ||
    endpoint.hash ||
    issuer.username ||
    issuer.password ||
    issuer.search ||
    issuer.hash ||
    endpoint.origin !== issuer.origin
  ) {
    throw new Error(
      "OIDC token endpoint must be on the configured issuer origin",
    );
  }

  const isLoopback = isLoopbackHostname(hostname);
  assertAllowedOidcHostname(hostname);
  if (endpoint.protocol === "http:") {
    if (!isLoopback || process.env.NODE_ENV === "production") {
      throw new Error(
        "OIDC token endpoint HTTP is limited to development loopback",
      );
    }
  } else if (endpoint.protocol === "https:") {
    if (
      isLoopback ||
      isIpv4MappedHostname(hostname) ||
      hostname.endsWith(".internal") ||
      hostname.endsWith(".local") ||
      isPrivateOrLoopbackHostname(hostname)
    ) {
      throw new Error("OIDC token endpoint must not target a private host");
    }
  } else {
    throw new Error("OIDC token endpoint requires HTTPS");
  }

  const safePath = endpoint.pathname
    .split("/")
    .map((segment) => {
      let decoded: string;
      try {
        decoded = decodeURIComponent(segment);
      } catch {
        throw new Error("OIDC token endpoint path is invalid");
      }
      if (
        decoded === "." ||
        decoded === ".." ||
        OIDC_CONTROL_CHARACTER_PATTERN.test(decoded)
      ) {
        throw new Error("OIDC token endpoint path is invalid");
      }
      return encodeURIComponent(decoded);
    })
    .join("/");
  const encodedPort = endpoint.port
    ? `:${encodeURIComponent(endpoint.port)}`
    : "";
  const encodedHostname = hostname.includes(":")
    ? `[${hostname}]`
    : encodeURIComponent(hostname);
  if (endpoint.protocol === "http:") {
    const loopbackOrigin =
      hostname === "localhost"
        ? `http://localhost${encodedPort}`
        : hostname === "::1"
          ? `http://[::1]${encodedPort}`
          : `http://${encodeURIComponent(hostname)}${encodedPort}`;
    return new URL(safePath, loopbackOrigin);
  }
  return new URL(
    safePath,
    `https://${encodedHostname}${encodedPort}`,
  );
}

async function backendAcceptsSessionToken(token: string) {
  const body = await fetchTrustedBackendSession(token);
  if (!body || typeof body !== "object") return false;
  const session = body as {
    user_id?: unknown;
    organization_id?: unknown;
    workspace_id?: unknown;
  };
  return (
    typeof session.user_id === "string" &&
    typeof session.organization_id === "string" &&
    typeof session.workspace_id === "string"
  );
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
