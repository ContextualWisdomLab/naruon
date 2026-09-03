import type { NextRequest } from "next/server";

/**
 * Rejects a cross-site state-changing request (`Sec-Fetch-Site: cross-site`,
 * or an `Origin`/`Referer` that does not match this deployment) the same
 * way `app/api/[...path]/route.ts`'s API proxy already does. `Content-Type:
 * text/plain` keeps a JSON body's `request.json()` call working while
 * staying a CORS-simple request, so the browser never sends a preflight a
 * same-origin-only route could rely on instead -- Origin/Referer checking is
 * the mitigation that still applies.
 */

const CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/;
const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function firstHeaderValue(value: string | null): string | null {
  return value?.split(",")[0]?.trim() || null;
}

function forwardedProtocol(request: NextRequest): string {
  const proto = firstHeaderValue(request.headers.get("x-forwarded-proto"));
  if (proto === "http" || proto === "https") return proto;
  return request.nextUrl.protocol.replace(":", "");
}

function requestOriginCandidates(request: NextRequest): Set<string> {
  const origins = new Set([request.nextUrl.origin]);
  const proto = forwardedProtocol(request);
  const hosts = [
    firstHeaderValue(request.headers.get("x-forwarded-host")),
    firstHeaderValue(request.headers.get("host")),
  ];

  for (const host of hosts) {
    if (!host || CONTROL_CHARACTER_PATTERN.test(host)) continue;
    try {
      origins.add(new URL(`${proto}://${host}`).origin);
    } catch {
      // Ignore malformed proxy host metadata and keep the stricter origin set.
    }
  }

  return origins;
}

export function sameOriginStateChangingRequest(request: NextRequest): boolean {
  if (!STATE_CHANGING_METHODS.has(request.method.toUpperCase())) return true;

  const fetchSite = request.headers.get("sec-fetch-site")?.trim().toLowerCase();
  if (fetchSite === "cross-site") return false;

  const origin = request.headers.get("origin");
  if (origin) {
    try {
      return requestOriginCandidates(request).has(new URL(origin).origin);
    } catch {
      return false;
    }
  }

  const referer = request.headers.get("referer");
  if (referer) {
    try {
      return requestOriginCandidates(request).has(new URL(referer).origin);
    } catch {
      return false;
    }
  }
  return false; // Fail securely if neither Origin nor Referer is present
}
