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

const PRIVATE_OIDC_HOST_PATTERNS: readonly RegExp[] = [
  /^0\./,
  /^10\./,
  /^127\./,
  /^169\.254\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^192\.168\./,
  /^::$/,
  /^::1$/,
  /^fc[0-9a-f]{2}:/,
  /^fd[0-9a-f]{2}:/,
  /^fe[89ab][0-9a-f]:/,
];
const OIDC_CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/;

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

function normalizedHostname(url: URL): string {
  return url.hostname.replace(/^\[/, "").replace(/\]$/, "").toLowerCase();
}

function isLoopbackHostname(hostname: string): boolean {
  return (
    hostname === "localhost" || hostname === "::1" || /^127\./.test(hostname)
  );
}

function trustedOidcTokenEndpoint(config: {
  issuerUrl: string;
  tokenEndpoint: string;
}): URL {
  const issuer = new URL(config.issuerUrl);
  const endpoint = new URL(config.tokenEndpoint);
  const hostname = normalizedHostname(endpoint);
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
  if (endpoint.protocol === "http:") {
    if (!isLoopback || process.env.NODE_ENV === "production") {
      throw new Error(
        "OIDC token endpoint HTTP is limited to development loopback",
      );
    }
  } else if (endpoint.protocol === "https:") {
    if (
      isLoopback ||
      hostname.endsWith(".internal") ||
      hostname.endsWith(".local") ||
      PRIVATE_OIDC_HOST_PATTERNS.some((pattern) => pattern.test(hostname))
    ) {
      throw new Error("OIDC token endpoint must not target a private host");
    }
  } else {
    throw new Error("OIDC token endpoint requires HTTPS");
  }

  const safePath = endpoint.pathname
    .split("/")
    .map((segment) => {
      const decoded = decodeURIComponent(segment);
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

function trustedBackendSessionUrl(): URL {
  const configured = backendApiBaseUrl();
  const hostname = normalizedHostname(configured);
  const hasRootPath = configured.pathname === "" || configured.pathname === "/";
  if (
    !hostname ||
    configured.username ||
    configured.password ||
    configured.search ||
    configured.hash ||
    !hasRootPath
  ) {
    throw new Error("BACKEND_INTERNAL_URL must be a trusted origin");
  }

  if (configured.protocol === "http:") {
    const isExactLocalBackend =
      configured.port === "8000" &&
      (hostname === "127.0.0.1" || hostname === "localhost");
    const isExactComposeBackend =
      process.env.ALLOW_DOCKER_BACKEND_INTERNAL_URL === "1" &&
      configured.port === "8000" &&
      hostname === "backend";
    if (
      (!isExactLocalBackend || process.env.NODE_ENV === "production") &&
      !isExactComposeBackend
    ) {
      throw new Error(
        "Backend HTTP is limited to a trusted loopback or Compose host",
      );
    }
    const origin =
      hostname === "backend"
        ? "http://backend:8000"
        : hostname === "localhost"
          ? "http://localhost:8000"
          : "http://127.0.0.1:8000";
    return new URL("/api/auth/session", origin);
  }
  if (configured.protocol !== "https:") {
    throw new Error("Backend requests require HTTPS");
  }
  const encodedPort = configured.port
    ? `:${encodeURIComponent(configured.port)}`
    : "";
  const encodedHostname = hostname.includes(":")
    ? `[${hostname}]`
    : encodeURIComponent(hostname);
  return new URL(
    "/api/auth/session",
    `https://${encodedHostname}${encodedPort}`,
  );
}

async function backendAcceptsSessionToken(token: string) {
  try {
    const target = trustedBackendSessionUrl();
    const response = await fetch(target, {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });
    if (!response.ok) return false;
    const body = (await response.json()) as {
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
    const tokenResponse = await fetch(trustedOidcTokenEndpoint(config), {
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
