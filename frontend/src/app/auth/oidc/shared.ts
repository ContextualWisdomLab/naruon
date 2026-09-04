import { createHash, randomBytes } from "node:crypto";
import { NextResponse } from "next/server";

import { fetchTrustedBackendSession } from "@/lib/backend-session-probe";
import {
  isIpv4MappedHostname,
  isLoopbackHostname,
  isPrivateOrLoopbackHostname,
  normalizeHostname,
} from "@/lib/host-policy";

export const OIDC_PKCE_COOKIE_NAME = "naruon_oidc_pkce";

export const OIDC_NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
};

const OIDC_CONTROL_CHARACTER_PATTERN = /[\x00-\x1f\x7f]/;
const OIDC_ALLOWED_HOSTS_ENV = "OIDC_ALLOWED_HOSTS";

/** Failure reasons logged without credentials or tokens for OIDC code exchange. */
export type OidcTokenExchangeFailureReason =
  | "configuration_rejected"
  | "dns_or_transport_rejected"
  | "access_token_missing_or_invalid"
  | "backend_session_rejected";

export function errorResponse(errorCode: string, status = 400) {
  return NextResponse.json(
    { error_code: errorCode },
    { status, headers: OIDC_NO_STORE_HEADERS },
  );
}

export function recordOidcTokenExchangeFailure(
  reason: OidcTokenExchangeFailureReason,
): void {
  console.warn("oidc_token_exchange_failed", { reason });
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

/**
 * Validates that a configured OIDC token endpoint is on the issuer's own
 * origin, HTTPS (or loopback HTTP outside production), and not a private/
 * internal host before an authorization-code exchange can reach it.
 */
export function trustedOidcTokenEndpoint(config: {
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

/** True only when the backend recognizes the access token and returns full session claims. */
export async function backendAcceptsSessionToken(token: string) {
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

const DEFAULT_OIDC_SCOPE = "openid profile email";
const OIDC_COOKIE_MAX_AGE_SECONDS = 10 * 60;

export interface ServerOidcConfig {
  issuerUrl: string;
  clientId: string;
  redirectUri: string;
  scope: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
}

export interface OidcStateCookiePayload {
  state: string;
  verifier: string;
  return_to: string;
}

function envValue(name: string): string | null {
  const value = process.env[name]?.trim();
  return value ? value : null;
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

export function serverOidcConfig(origin: string): ServerOidcConfig | null {
  const issuerUrl = envValue("NEXT_PUBLIC_OIDC_ISSUER_URL");
  const clientId = envValue("NEXT_PUBLIC_OIDC_CLIENT_ID");
  if (!issuerUrl || !clientId) return null;

  const normalizedIssuer = trimTrailingSlash(issuerUrl);
  const keycloakEndpointBase = `${normalizedIssuer}/protocol/openid-connect`;
  return {
    issuerUrl: normalizedIssuer,
    clientId,
    redirectUri: envValue("NEXT_PUBLIC_OIDC_REDIRECT_URI") ?? `${origin}/auth/callback`,
    scope: envValue("NEXT_PUBLIC_OIDC_SCOPE") ?? DEFAULT_OIDC_SCOPE,
    authorizationEndpoint:
      envValue("NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT") ?? `${keycloakEndpointBase}/auth`,
    tokenEndpoint:
      envValue("NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT") ?? `${keycloakEndpointBase}/token`,
  };
}

export function safeReturnTo(value: unknown) {
  const candidate = typeof value === "string" ? value.trim() : "";
  if (!candidate) return "/";

  try {
    const decodedCandidate = decodeURIComponent(candidate);
    if (
      !candidate.startsWith("/") ||
      candidate.startsWith("//") ||
      decodedCandidate.startsWith("//") ||
      /[\u0000-\u001f\u007f\\]/.test(candidate) ||
      /[\u0000-\u001f\u007f\\]/.test(decodedCandidate)
    ) {
      return "/";
    }

    const url = new URL(candidate, "http://localhost");
    if (url.origin !== "http://localhost") return "/";

    const safePath = url.pathname + url.search + url.hash;
    const decodedSafePath = decodeURIComponent(safePath);

    if (
      !safePath.startsWith("/") ||
      safePath.startsWith("//") ||
      decodedSafePath.startsWith("//") ||
      /[\u0000-\u001f\u007f\\]/.test(decodedSafePath)
    ) {
      return "/";
    }

    return safePath;
  } catch {
    return "/";
  }
}

export function randomUrlSafeString(byteLength: number) {
  return randomBytes(byteLength).toString("base64url");
}

export function pkceChallenge(verifier: string) {
  return createHash("sha256").update(verifier, "ascii").digest("base64url");
}

export function encodeOidcStateCookie(payload: OidcStateCookiePayload) {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

export function decodeOidcStateCookie(value: string | undefined): OidcStateCookiePayload | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as {
      state?: unknown;
      verifier?: unknown;
      return_to?: unknown;
    };
    if (
      typeof parsed.state !== "string" ||
      typeof parsed.verifier !== "string" ||
      typeof parsed.return_to !== "string" ||
      !parsed.state ||
      !parsed.verifier
    ) {
      return null;
    }
    return {
      state: parsed.state,
      verifier: parsed.verifier,
      return_to: safeReturnTo(parsed.return_to),
    };
  } catch {
    return null;
  }
}

export function oidcStateCookieOptions(value: string) {
  return {
    name: OIDC_PKCE_COOKIE_NAME,
    value,
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/auth",
    maxAge: OIDC_COOKIE_MAX_AGE_SECONDS,
  };
}

export function expiredOidcStateCookieOptions() {
  return {
    name: OIDC_PKCE_COOKIE_NAME,
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/auth",
    maxAge: 0,
  };
}
