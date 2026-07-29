import { lookup as systemLookup } from "node:dns/promises";
import {
  BlockList,
  isIP,
  type LookupFunction,
} from "node:net";
import { Agent, type Dispatcher } from "undici";

import { trustedBackendOrigin } from "@/lib/backend-url";
import { normalizeHostname } from "@/lib/host-policy";

const BACKEND_DNS_TIMEOUT_MS = 5_000;

type AddressFamily = 4 | 6;
type BackendDestinationKind = "compose" | "loopback" | "public";

export interface BackendResolvedAddress {
  address: string;
  family: AddressFamily;
}

export type BackendDnsLookup = (
  hostname: string,
  options: { all: true; verbatim: true },
) => Promise<readonly { address: string; family: number }[]>;

type DispatcherRequestInit = RequestInit & {
  dispatcher: Dispatcher;
};

const NON_GLOBAL_ADDRESSES = new BlockList();

for (const [network, prefix] of [
  ["0.0.0.0", 8],
  ["10.0.0.0", 8],
  ["100.64.0.0", 10],
  ["127.0.0.0", 8],
  ["169.254.0.0", 16],
  ["172.16.0.0", 12],
  ["192.0.0.0", 24],
  ["192.0.2.0", 24],
  ["192.88.99.0", 24],
  ["192.168.0.0", 16],
  ["198.18.0.0", 15],
  ["198.51.100.0", 24],
  ["203.0.113.0", 24],
  ["224.0.0.0", 4],
  ["240.0.0.0", 4],
] as const) {
  NON_GLOBAL_ADDRESSES.addSubnet(network, prefix, "ipv4");
}

for (const [network, prefix] of [
  ["::", 96],
  ["64:ff9b::", 96],
  ["64:ff9b:1::", 48],
  ["100::", 64],
  ["2001::", 23],
  ["2001:db8::", 32],
  ["2002::", 16],
  ["3fff::", 20],
  ["5f00::", 16],
  ["fc00::", 7],
  ["fe80::", 10],
  ["fec0::", 10],
  ["ff00::", 8],
] as const) {
  NON_GLOBAL_ADDRESSES.addSubnet(network, prefix, "ipv6");
}

const COMPOSE_ADDRESSES = new BlockList();

for (const [network, prefix] of [
  ["10.0.0.0", 8],
  ["127.0.0.0", 8],
  ["172.16.0.0", 12],
  ["192.168.0.0", 16],
] as const) {
  COMPOSE_ADDRESSES.addSubnet(network, prefix, "ipv4");
}

for (const [network, prefix] of [
  ["::1", 128],
  ["fc00::", 7],
] as const) {
  COMPOSE_ADDRESSES.addSubnet(network, prefix, "ipv6");
}

function isIpv4MappedIpv6(address: string): boolean {
  const normalized = address.toLowerCase();
  return (
    normalized.startsWith("::ffff:") ||
    normalized.startsWith("0:0:0:0:0:ffff:")
  );
}

function isLoopbackAddress(address: string, family: AddressFamily): boolean {
  if (family === 4) return address.startsWith("127.");
  return address === "::1";
}

function destinationKind(target: URL): BackendDestinationKind {
  const hostname = normalizeHostname(target);
  if (target.protocol === "https:") return "public";
  if (
    target.protocol === "http:" &&
    target.port === "8000" &&
    (hostname === "127.0.0.1" || hostname === "localhost")
  ) {
    return "loopback";
  }
  if (
    target.protocol === "http:" &&
    target.port === "8000" &&
    hostname === "backend" &&
    process.env.ALLOW_DOCKER_BACKEND_INTERNAL_URL === "1"
  ) {
    return "compose";
  }
  throw new Error("Backend request target is outside the trusted origin policy");
}

function validateResolvedAddress(
  address: string,
  kind: BackendDestinationKind,
): BackendResolvedAddress {
  const family = isIP(address);
  if (family !== 4 && family !== 6) {
    throw new Error("Backend origin resolved to an invalid IP address");
  }
  if (family === 6 && isIpv4MappedIpv6(address)) {
    throw new Error(
      "Backend origin must not resolve to an IPv4-mapped IPv6 address",
    );
  }
  if (kind === "loopback") {
    if (!isLoopbackAddress(address, family)) {
      throw new Error(
        "Development backend origin must resolve only to loopback addresses",
      );
    }
    return { address, family };
  }

  const addressType = family === 4 ? "ipv4" : "ipv6";
  if (kind === "compose") {
    if (!COMPOSE_ADDRESSES.check(address, addressType)) {
      throw new Error(
        "Compose backend origin must resolve only to private or loopback addresses",
      );
    }
    return { address, family };
  }
  if (NON_GLOBAL_ADDRESSES.check(address, addressType)) {
    throw new Error(
      "Public backend origin must resolve only to globally routable addresses",
    );
  }
  return { address, family };
}

function deduplicateAddresses(
  addresses: readonly BackendResolvedAddress[],
): BackendResolvedAddress[] {
  const seen = new Set<string>();
  return addresses.filter(({ address, family }) => {
    const key = `${family}:${address}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function withDnsTimeout<T>(operation: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      operation,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("Backend origin DNS resolution timed out")),
          BACKEND_DNS_TIMEOUT_MS,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function resolveBackendAddresses(
  target: URL,
  dnsLookup: BackendDnsLookup = systemLookup,
): Promise<BackendResolvedAddress[]> {
  const kind = destinationKind(target);
  const hostname = normalizeHostname(target);
  const literalFamily = isIP(hostname);
  if (literalFamily === 4 || literalFamily === 6) {
    return [validateResolvedAddress(hostname, kind)];
  }

  const resolved = await withDnsTimeout(
    dnsLookup(hostname, { all: true, verbatim: true }),
  );
  if (resolved.length === 0) {
    throw new Error("Backend origin did not resolve to an IP address");
  }
  return deduplicateAddresses(
    resolved.map(({ address }) => validateResolvedAddress(address, kind)),
  );
}

export function createPinnedBackendLookup(
  expectedHostname: string,
  addresses: readonly BackendResolvedAddress[],
): LookupFunction {
  if (addresses.length === 0) {
    throw new Error("Backend origin requires a pinned IP address");
  }

  return ((
    hostname: string,
    options: unknown,
    callback: (...args: unknown[]) => void,
  ) => {
    if (
      hostname.replace(/\.+$/, "").toLowerCase() !==
      expectedHostname.replace(/\.+$/, "").toLowerCase()
    ) {
      callback(new Error("Backend pinned lookup rejected an unexpected hostname"));
      return;
    }
    const requestedFamily =
      typeof options === "object" &&
      options !== null &&
      "family" in options &&
      (options.family === 4 || options.family === 6)
        ? options.family
        : 0;
    const eligible = addresses.filter(
      ({ family }) => requestedFamily === 0 || family === requestedFamily,
    );
    if (eligible.length === 0) {
      callback(new Error("Backend origin has no address in the requested family"));
      return;
    }
    const wantsAll =
      typeof options === "object" &&
      options !== null &&
      "all" in options &&
      options.all === true;
    if (wantsAll) {
      callback(null, eligible);
      return;
    }
    callback(null, eligible[0].address, eligible[0].family);
  }) as LookupFunction;
}

function assertTrustedTarget(target: URL): void {
  const trustedOrigin = trustedBackendOrigin();
  if (
    target.origin !== trustedOrigin.origin ||
    target.username ||
    target.password ||
    target.hash
  ) {
    throw new Error("Backend request target does not match the trusted origin");
  }
}

export async function fetchTrustedBackend(
  target: URL,
  init: RequestInit = {},
): Promise<Response> {
  assertTrustedTarget(target);
  const addresses = await resolveBackendAddresses(target);
  const hostname = normalizeHostname(target);
  const dispatcher = new Agent({
    connect: {
      lookup: createPinnedBackendLookup(hostname, addresses),
    },
  });

  try {
    const requestInit: DispatcherRequestInit = {
      ...init,
      dispatcher,
    };
    // The target origin and every DNS answer were validated above, and this
    // per-request dispatcher can connect only to the resulting pinned IPs.
    const response = await globalThis.fetch(target, requestInit);
    return response;
  } finally {
    void dispatcher.close().catch(() => undefined);
  }
}
