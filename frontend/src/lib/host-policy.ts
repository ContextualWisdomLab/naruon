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

export function normalizeHostname(value: URL | string): string {
  const hostname = typeof value === "string" ? value : value.hostname;
  return hostname
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .replace(/\.+$/, "")
    .toLowerCase();
}

export function isLoopbackHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1"
  );
}

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

export function isPrivateOrLoopbackHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  const mapped = ipv4MappedHostToDotted(hostname);
  const candidates = mapped ? [hostname, mapped] : [hostname];
  return candidates.some((candidate) =>
    PRIVATE_OR_LOCAL_HOST_PATTERNS.some((pattern) => pattern.test(candidate)),
  );
}
