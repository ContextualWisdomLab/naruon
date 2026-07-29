import {
  isPrivateOrLoopbackHostname,
  normalizeHostname,
} from "@/lib/host-policy";

function isAllowedComposeBackendUrl(parsed: URL): boolean {
  const host = normalizeHostname(parsed);
  return (
    process.env.ALLOW_DOCKER_BACKEND_INTERNAL_URL === "1" &&
    parsed.protocol === "http:" &&
    (host === "backend" || host === "127.0.0.1" || host === "localhost") &&
    parsed.port === "8000" &&
    (parsed.pathname === "" || parsed.pathname === "/")
  );
}

export function parseBackendInternalUrl(raw: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(
      `BACKEND_INTERNAL_URL is not a valid URL: ${JSON.stringify(raw)}`,
    );
  }
  if (isAllowedComposeBackendUrl(parsed)) return parsed;
  if (parsed.protocol !== "https:") {
    throw new Error(
      `BACKEND_INTERNAL_URL must use https:// in split deployments, got ${parsed.protocol}//`,
    );
  }
  if (!normalizeHostname(parsed)) {
    throw new Error("BACKEND_INTERNAL_URL must include a hostname");
  }
  if (isPrivateOrLoopbackHostname(parsed)) {
    throw new Error(
      `BACKEND_INTERNAL_URL host ${normalizeHostname(parsed)} is in a private/loopback/link-local range`,
    );
  }
  return parsed;
}

export function backendApiBaseUrl(): URL {
  const raw = process.env.BACKEND_INTERNAL_URL?.trim();
  if (raw) return parseBackendInternalUrl(raw);
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "BACKEND_INTERNAL_URL must be set in production runtime. " +
        "Set it to the backend public HTTPS origin or use the exact Compose opt-in.",
    );
  }
  return new URL("http://127.0.0.1:8000");
}

export function trustedBackendOrigin(): URL {
  const configured = backendApiBaseUrl();
  const hostname = normalizeHostname(configured);
  const hasRootPath = configured.pathname === "" || configured.pathname === "/";
  if (
    !hostname ||
    configured.username ||
    configured.password ||
    configured.search ||
    configured.hash ||
    !hasRootPath
  ) {
    throw new Error(
      "BACKEND_INTERNAL_URL must be an origin without credentials, path, query, or fragment",
    );
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
        "Backend HTTP is limited to the exact development loopback or opted-in Compose host",
      );
    }
    if (hostname === "backend") return new URL("http://backend:8000");
    if (hostname === "localhost") return new URL("http://localhost:8000");
    return new URL("http://127.0.0.1:8000");
  }

  if (configured.protocol !== "https:") {
    throw new Error("Backend requests require HTTPS");
  }
  const encodedHostname = hostname.includes(":")
    ? `[${hostname}]`
    : encodeURIComponent(hostname);
  const encodedPort = configured.port
    ? `:${encodeURIComponent(configured.port)}`
    : "";
  return new URL(`https://${encodedHostname}${encodedPort}`);
}
