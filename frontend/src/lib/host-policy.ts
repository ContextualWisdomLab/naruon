const PRIVATE_OR_LOCAL_HOST_PATTERNS: readonly RegExp[] = [
  /^localhost$/,
  /^0\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^169\.254\.\d{1,3}\.\d{1,3}$/,
  /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/,
  /^192\.168\.\d{1,3}\.\d{1,3}$/,
  /^::$/,
  /^::1$/,
  /^fc[0-9a-f]{2}:[0-9a-f:]*$/,
  /^fd[0-9a-f]{2}:[0-9a-f:]*$/,
  /^fe[89ab][0-9a-f]:[0-9a-f:]*$/,
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

/**
 * Strictly parse dotted-quad IPv4 text: exactly four decimal octets 0-255
 * with no leading zeros. Returns canonical dotted text, or null when the
 * input uses a legacy numeric encoding (octal/hex components, out-of-range
 * octets) whose resolution differs across network stacks.
 */
function canonicalizeStrictIpv4Dotted(candidate: string): string | null {
  const parts = candidate.split(".");
  if (parts.length !== 4 || parts.some((part) => part === "")) return null;
  const octets: number[] = [];
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null;
    if (part.length > 1 && part.startsWith("0")) return null;
    const octet = Number.parseInt(part, 10);
    if (!(octet <= 255)) return null;
    octets.push(octet);
  }
  return octets.join(".");
}

/** Return whether text looks like a numeric IP literal instead of a DNS name. */
function isNumericHostText(hostname: string): boolean {
  return hostname
    .split(".")
    .every((part) => /^(?:\d+|0x[0-9a-f]+)$/.test(part));
}

/**
 * Return whether numeric text carries a legacy encoding (hex components,
 * leading zeros, out-of-range octets) that different resolvers map to
 * different addresses, so classification must fail closed.
 */
function hasAmbiguousNumericEncoding(hostname: string): boolean {
  return (
    isNumericHostText(hostname) &&
    canonicalizeStrictIpv4Dotted(hostname) === null
  );
}

function parseIpv6Hextets(text: string): number[] | null {
  if (text === "") return [];
  const hextets: number[] = [];
  for (const segment of text.split(":")) {
    if (!/^[0-9a-f]{1,4}$/.test(segment)) return null;
    hextets.push(Number.parseInt(segment, 16));
  }
  return hextets;
}

/** Emit the RFC 5952 canonical text for eight parsed IPv6 hextets. */
function formatCanonicalIpv6(hextets: number[]): string {
  let bestStart = -1;
  let bestLength = 0;
  let currentStart = -1;
  let currentLength = 0;
  for (let index = 0; index <= hextets.length; index += 1) {
    if (index < hextets.length && hextets[index] === 0) {
      if (currentLength === 0) currentStart = index;
      currentLength += 1;
      if (currentLength > bestLength) {
        bestLength = currentLength;
        bestStart = currentStart;
      }
    } else {
      currentStart = -1;
      currentLength = 0;
    }
  }
  if (bestLength < 2) bestStart = -1;
  const head = hextets
    .slice(0, bestStart >= 0 ? bestStart : hextets.length)
    .map((hextet) => hextet.toString(16))
    .join(":");
  if (bestStart < 0) return head;
  const tail = hextets
    .slice(bestStart + bestLength)
    .map((hextet) => hextet.toString(16))
    .join(":");
  return `${head}::${tail}`;
}

/**
 * Parse an IPv6 literal into its RFC 5952 canonical text, expanding `::`
 * and converting embedded dotted-quad tails (RFC 4291 section 2.2) to hex
 * hextets. Returns null when the literal is not valid IPv6 text.
 */
function canonicalizeIpv6Literal(literal: string): string | null {
  if (!literal.includes(":")) return null;
  const zoneSeparator = literal.indexOf("%");
  const text = zoneSeparator >= 0 ? literal.slice(0, zoneSeparator) : literal;
  const tailStart = text.lastIndexOf(":") + 1;
  const tail = text.slice(tailStart);
  let expandedText = text;
  if (tail.includes(".")) {
    const canonicalTail = canonicalizeStrictIpv4Dotted(tail);
    if (canonicalTail === null) return null;
    const [first, second, third, fourth] = canonicalTail.split(".").map(Number);
    expandedText = `${text.slice(0, tailStart)}${(
      (first << 8) |
      second
    ).toString(16)}:${((third << 8) | fourth).toString(16)}`;
  }
  const doubleColonParts = expandedText.split("::");
  if (doubleColonParts.length > 2) return null;
  let hextets: number[] | null;
  if (doubleColonParts.length === 2) {
    const left = parseIpv6Hextets(doubleColonParts[0]);
    const right = parseIpv6Hextets(doubleColonParts[1]);
    if (left === null || right === null) return null;
    const missing = 8 - left.length - right.length;
    if (missing < 1) return null;
    hextets = [...left, ...new Array<number>(missing).fill(0), ...right];
  } else {
    hextets = parseIpv6Hextets(expandedText);
    if (hextets !== null && hextets.length !== 8) return null;
  }
  if (hextets === null) return null;
  return formatCanonicalIpv6(hextets);
}

/**
 * Return whether an IPv6-shaped hostname embeds a dotted-quad tail written
 * with a legacy numeric encoding. Such text cannot be resolved safely, so
 * callers must fail closed instead of trusting the raw spelling.
 */
function hasAmbiguousNumericTail(literal: string): boolean {
  const tail = literal.slice(literal.lastIndexOf(":") + 1);
  return tail.includes(".") && hasAmbiguousNumericEncoding(tail);
}

/** Return whether a hostname is one of Naruon's exact loopback endpoints. */
export function isLoopbackHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  if (hostname.includes(":")) {
    return canonicalizeIpv6Literal(hostname) === "::1";
  }
  return hostname === "localhost" || hostname === "127.0.0.1";
}

/** Return whether a hostname uses the IPv4-mapped IPv6 prefix. */
export function isIpv4MappedHostname(value: URL | string): boolean {
  const hostname = normalizeHostname(value);
  if (!hostname.includes(":")) return false;
  const canonical = canonicalizeIpv6Literal(hostname);
  return canonical !== null && canonical.startsWith("::ffff:");
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
  const matchesPolicy = (candidate: string) =>
    PRIVATE_OR_LOCAL_HOST_PATTERNS.some((pattern) => pattern.test(candidate));
  if (hostname.includes(":")) {
    const canonical = canonicalizeIpv6Literal(hostname);
    if (canonical !== null) {
      const mapped = ipv4MappedHostToDotted(canonical);
      return (
        matchesPolicy(canonical) || (mapped !== null && matchesPolicy(mapped))
      );
    }
    // Unparseable IPv6 text cannot resolve to any address, but a legacy
    // numeric encoding inside an otherwise literal-shaped host can resolve
    // differently across stacks; fail closed on the latter.
    return hasAmbiguousNumericTail(hostname);
  }
  if (isNumericHostText(hostname)) {
    const canonical = canonicalizeStrictIpv4Dotted(hostname);
    // Valid dotted quads compare canonically; legacy numeric forms such as
    // octal components or bare integers must fail closed because resolvers
    // disagree on their meaning.
    return canonical === null ? true : matchesPolicy(canonical);
  }
  return matchesPolicy(hostname);
}
