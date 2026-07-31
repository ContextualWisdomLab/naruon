import { lookup as systemLookup } from "node:dns/promises";
import {
  request as httpRequest,
  type ClientRequest,
  type IncomingMessage,
  type RequestOptions,
} from "node:http";
import { request as httpsRequest } from "node:https";
import { BlockList, isIP } from "node:net";
import { Readable } from "node:stream";

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

const IPV4_MAPPED_IPV6_ADDRESSES = new BlockList();
IPV4_MAPPED_IPV6_ADDRESSES.addSubnet("::ffff:0:0", 96, "ipv6");

function isIpv4MappedIpv6(address: string): boolean {
  return IPV4_MAPPED_IPV6_ADDRESSES.check(address, "ipv6");
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
  throw new Error(
    "Backend request target is outside the trusted origin policy",
  );
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

function outgoingHeaders(
  headersInit: HeadersInit | undefined,
): Record<string, string> {
  const headers: Record<string, string> = {};
  new Headers(headersInit).forEach((value, name) => {
    headers[name] = value;
  });
  return headers;
}

function incomingHeaders(response: IncomingMessage): Headers {
  const headers = new Headers();
  for (let index = 0; index < response.rawHeaders.length; index += 2) {
    const name = response.rawHeaders[index];
    const value = response.rawHeaders[index + 1];
    if (name !== undefined && value !== undefined) {
      headers.append(name, value);
    }
  }
  return headers;
}

function hasNullResponseBody(method: string, status: number): boolean {
  return (
    method === "HEAD" || status === 204 || status === 205 || status === 304
  );
}

function endRequest(
  request: ClientRequest,
  body: BodyInit | null | undefined,
): void {
  if (body === null || body === undefined) {
    request.end();
    return;
  }
  if (typeof body === "string" || body instanceof URLSearchParams) {
    request.end(body.toString());
    return;
  }
  if (body instanceof ArrayBuffer) {
    request.end(new Uint8Array(body));
    return;
  }
  if (ArrayBuffer.isView(body)) {
    request.end(new Uint8Array(body.buffer, body.byteOffset, body.byteLength));
    return;
  }
  throw new TypeError(
    "Trusted backend requests support only buffered request bodies",
  );
}

function performPinnedRequest(
  target: URL,
  init: RequestInit,
  address: BackendResolvedAddress,
): Promise<Response> {
  if (init.redirect !== undefined && init.redirect !== "manual") {
    throw new Error("Trusted backend redirects must be handled manually");
  }

  const method = (init.method ?? "GET").toUpperCase();
  const headers = outgoingHeaders(init.headers);
  // Never let a caller select a different virtual host on the pinned backend.
  headers.host = target.host;
  const requestOptions: RequestOptions = {
    agent: false,
    family: address.family,
    headers,
    hostname: address.address,
    method,
    path: `${target.pathname}${target.search}`,
    port: target.port || undefined,
    protocol: target.protocol,
    signal: init.signal ?? undefined,
  };

  return new Promise<Response>((resolve, reject) => {
    const handleResponse = (response: IncomingMessage) => {
      const status = response.statusCode;
      if (status === undefined || status < 200 || status > 599) {
        response.destroy();
        reject(new Error("Backend returned an invalid HTTP status"));
        return;
      }

      let body: BodyInit | null = null;
      if (hasNullResponseBody(method, status)) {
        response.resume();
      } else {
        body = Readable.toWeb(response) as ReadableStream<Uint8Array>;
      }
      resolve(
        new Response(body, {
          headers: incomingHeaders(response),
          status,
          statusText: response.statusMessage ?? "",
        }),
      );
    };

    const request =
      target.protocol === "https:"
        ? httpsRequest(
            {
              ...requestOptions,
              servername: isIP(normalizeHostname(target))
                ? undefined
                : normalizeHostname(target),
            },
            handleResponse,
          )
        : httpRequest(requestOptions, handleResponse);
    request.once("error", reject);

    try {
      endRequest(request, init.body);
    } catch (error) {
      request.destroy();
      reject(error);
    }
  });
}

export async function fetchTrustedBackend(
  target: URL,
  init: RequestInit = {},
): Promise<Response> {
  assertTrustedTarget(target);
  const addresses = await resolveBackendAddresses(target);
  const address =
    addresses.find(({ family }) => family === 4) ?? addresses[0]!;
  // Connect directly to the validated literal address. Host and SNI retain the
  // configured authority, while no second DNS lookup or URL-derived hostname
  // can redirect the socket.
  return performPinnedRequest(target, init, address);
}
