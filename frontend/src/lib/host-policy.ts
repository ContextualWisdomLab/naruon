const PRIVATE_OR_LOCAL_HOST_PATTERNS: readonly RegExp[] = [
  /^localhost$/,
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

/** Normalize a URL hostname for exact host-policy comparisons. */
export function normalizeHostname(value: URL | string): string {
  const hostname = typeof value === "string" ? value : value.hostname;
  return hostname
    .replace(/\.+$/, "")
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .toLowerCase();
}

/** Return whether a hostname is one of Naruon's exact loopback endpoints. */
export function isLoopbackHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1"
  );
}

/** Return whether a hostname uses the IPv4-mapped IPv6 prefix. */
export function isIpv4MappedHostname(value: URL | string): boolean {
  return normalizeHostname(value).startsWith("::ffff:");
}

function ipv4MappedHostToDotted(hostname: string): string | null {
  if (!hostname.startsWith("::ffff:")) return null;
  const suffix = hostname.slice("::ffff:".length);
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
  return [high >> 8, high & 255, low >> 8, low & 255].join(".");
}

/** Return whether a hostname is private, link-local, unspecified, or loopback. */
export function isPrivateOrLoopbackHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  const mapped = ipv4MappedHostToDotted(hostname);
  const candidates = mapped ? [hostname, mapped] : [hostname];
  return candidates.some((candidate) =>
    PRIVATE_OR_LOCAL_HOST_PATTERNS.some((pattern) => pattern.test(candidate)),
  );
}
