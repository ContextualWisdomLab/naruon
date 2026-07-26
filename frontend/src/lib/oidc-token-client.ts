import { lookup as systemLookup } from "node:dns/promises";
import {
  request as httpRequest,
} from "node:http";
import {
  request as httpsRequest,
  type RequestOptions,
} from "node:https";
import {
  BlockList,
  isIP,
  type LookupFunction,
} from "node:net";

const OIDC_DNS_TIMEOUT_MS = 5_000;
const OIDC_REQUEST_TIMEOUT_MS = 15_000;
const OIDC_RESPONSE_MAX_BYTES = 1024 * 1024;

type AddressFamily = 4 | 6;

export interface OidcResolvedAddress {
  address: string;
  family: AddressFamily;
}

export type OidcDnsLookup = (
  hostname: string,
  options: { all: true; verbatim: true },
) => Promise<readonly { address: string; family: number }[]>;

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

function normalizedHostname(url: URL): string {
  return url.hostname
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .replace(/\.+$/, "")
    .toLowerCase();
}

function isLoopbackAddress(address: string): boolean {
  if (isIP(address) === 4) {
    return NON_GLOBAL_ADDRESSES.check(address, "ipv4") && address.startsWith("127.");
  }
  return address === "::1";
}

function validateResolvedAddress(
  address: string,
  { allowLoopback }: { allowLoopback: boolean },
): OidcResolvedAddress {
  const family = isIP(address);
  if (family !== 4 && family !== 6) {
    throw new Error("OIDC token endpoint resolved to an invalid IP address");
  }
  if (family === 6 && address.toLowerCase().startsWith("::ffff:")) {
    throw new Error(
      "OIDC token endpoint must resolve only to globally routable addresses",
    );
  }
  if (allowLoopback) {
    if (!isLoopbackAddress(address)) {
      throw new Error(
        "Development HTTP OIDC token endpoints must resolve only to loopback addresses",
      );
    }
    return { address, family };
  }
  const type = family === 4 ? "ipv4" : "ipv6";
  if (NON_GLOBAL_ADDRESSES.check(address, type)) {
    throw new Error(
      "OIDC token endpoint must resolve only to globally routable addresses",
    );
  }
  return { address, family };
}

function deduplicateAddresses(
  addresses: readonly OidcResolvedAddress[],
): OidcResolvedAddress[] {
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
          () => reject(new Error("OIDC token endpoint DNS resolution timed out")),
          OIDC_DNS_TIMEOUT_MS,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function resolveOidcTokenAddresses(
  endpoint: URL,
  dnsLookup: OidcDnsLookup = systemLookup,
): Promise<OidcResolvedAddress[]> {
  const hostname = normalizedHostname(endpoint);
  const allowLoopback =
    endpoint.protocol === "http:" &&
    process.env.NODE_ENV !== "production" &&
    (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1");
  const literalFamily = isIP(hostname);
  if (literalFamily === 4 || literalFamily === 6) {
    return [validateResolvedAddress(hostname, { allowLoopback })];
  }

  const resolved = await withDnsTimeout(
    dnsLookup(hostname, { all: true, verbatim: true }),
  );
  if (resolved.length === 0) {
    throw new Error("OIDC token endpoint did not resolve to an IP address");
  }
  const addresses = resolved.map(({ address }) =>
    validateResolvedAddress(address, { allowLoopback }),
  );
  return deduplicateAddresses(addresses);
}

export function createPinnedOidcLookup(
  expectedHostname: string,
  addresses: readonly OidcResolvedAddress[],
): LookupFunction {
  if (addresses.length === 0) {
    throw new Error("OIDC token endpoint requires a pinned IP address");
  }

  return ((hostname: string, options: unknown, callback: (...args: unknown[]) => void) => {
    if (
      hostname.replace(/\.+$/, "").toLowerCase() !==
      expectedHostname.replace(/\.+$/, "").toLowerCase()
    ) {
      callback(new Error("OIDC pinned lookup rejected an unexpected hostname"));
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
      callback(new Error("OIDC token endpoint has no address in the requested family"));
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

function collectJsonResponse(
  endpoint: URL,
  requestOptions: RequestOptions,
  body: string,
): Promise<{ access_token?: unknown }> {
  const requester = endpoint.protocol === "http:" ? httpRequest : httpsRequest;
  return new Promise((resolve, reject) => {
    const request = requester(endpoint, requestOptions, (response) => {
      const statusCode = response.statusCode ?? 0;
      const chunks: Buffer[] = [];
      let receivedBytes = 0;
      response.on("data", (chunk: Buffer | string) => {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        receivedBytes += buffer.length;
        if (receivedBytes > OIDC_RESPONSE_MAX_BYTES) {
          request.destroy(new Error("OIDC token response exceeded the size limit"));
          return;
        }
        chunks.push(buffer);
      });
      response.on("end", () => {
        if (statusCode < 200 || statusCode >= 300) {
          reject(new Error(`OIDC token endpoint returned HTTP ${statusCode}`));
          return;
        }
        try {
          resolve(
            JSON.parse(Buffer.concat(chunks).toString("utf8")) as {
              access_token?: unknown;
            },
          );
        } catch (error) {
          reject(new Error("OIDC token endpoint returned invalid JSON", { cause: error }));
        }
      });
      response.on("error", reject);
    });
    request.setTimeout(OIDC_REQUEST_TIMEOUT_MS, () => {
      request.destroy(new Error("OIDC token endpoint request timed out"));
    });
    request.on("error", reject);
    request.end(body);
  });
}

export async function postOidcTokenRequest(
  endpoint: URL,
  body: URLSearchParams,
): Promise<{ access_token?: unknown }> {
  if (endpoint.protocol !== "http:" && endpoint.protocol !== "https:") {
    throw new Error("OIDC token endpoint requires HTTP(S)");
  }
  const addresses = await resolveOidcTokenAddresses(endpoint);
  const hostname = normalizedHostname(endpoint);
  const encodedBody = body.toString();
  const requestOptions: RequestOptions = {
    method: "POST",
    agent: false,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
      "Content-Length": String(Buffer.byteLength(encodedBody)),
    },
    lookup: createPinnedOidcLookup(hostname, addresses),
  };
  if (endpoint.protocol === "https:" && isIP(hostname) === 0) {
    requestOptions.servername = hostname;
  }
  return collectJsonResponse(endpoint, requestOptions, encodedBody);
}
