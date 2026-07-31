const PRIVATE_BACKEND_HOST_PATTERNS: readonly RegExp[] = [
  /^localhost$/,
  /^127\./,
  /^0\./,
  /^10\./,
  /^192\.168\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^169\.254\./,
  /^::1$/,
  /^::$/,
  /^fc[0-9a-f]{2}:/,
  /^fd[0-9a-f]{2}:/,
  /^fe[89ab][0-9a-f]:/,
];

function normalizeHost(parsed: URL): string {
  return parsed.hostname.replace(/^\[/, "").replace(/\]$/, "").toLowerCase();
}

function ipv4MappedHostToDotted(host: string): string | null {
  if (!host.startsWith("::ffff:")) return null;
  const suffix = host.slice("::ffff:".length);
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(suffix)) return suffix;
  const [highHex, lowHex] = suffix.split(":");
  if (
    !highHex ||
    !lowHex ||
    !/^[0-9a-f]{1,4}$/.test(highHex) ||
    !/^[0-9a-f]{1,4}$/.test(lowHex)
  ) {
    return null;
  }
  const high = Number.parseInt(highHex, 16);
  const low = Number.parseInt(lowHex, 16);
  if (!Number.isFinite(high) || !Number.isFinite(low)) return null;
  const bytes = [high >> 8, high & 255, low >> 8, low & 255];
  return bytes.join(".");
}

function hostCandidates(parsed: URL): string[] {
  const host = normalizeHost(parsed);
  const mapped = ipv4MappedHostToDotted(host);
  return mapped ? [host, mapped] : [host];
}

function isPrivateBackendHost(parsed: URL): boolean {
  return hostCandidates(parsed).some((host) =>
    PRIVATE_BACKEND_HOST_PATTERNS.some((pattern) => pattern.test(host)),
  );
}

function isAllowedComposeBackendUrl(parsed: URL): boolean {
  const host = normalizeHost(parsed);
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
  if (!normalizeHost(parsed)) {
    throw new Error("BACKEND_INTERNAL_URL must include a hostname");
  }
  if (isPrivateBackendHost(parsed)) {
    throw new Error(
      `BACKEND_INTERNAL_URL host ${normalizeHost(parsed)} is in a private/loopback/link-local range`,
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
