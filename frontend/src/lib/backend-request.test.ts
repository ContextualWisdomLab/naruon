import { Readable } from "node:stream";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchTrustedBackend,
  resolveBackendAddresses,
  type BackendDnsLookup,
} from "./backend-request";

const { httpRequestMock, httpsRequestMock, systemLookupMock } = vi.hoisted(() => ({
  httpRequestMock: vi.fn(),
  httpsRequestMock: vi.fn(),
  systemLookupMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({
  lookup: systemLookupMock,
}));

vi.mock("node:http", () => ({
  request: httpRequestMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

const ORIGINAL_ENV = { ...process.env };

describe("backend destination pinning", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    httpRequestMock.mockReset();
    httpsRequestMock.mockReset();
    systemLookupMock.mockReset();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.ALLOW_DOCKER_BACKEND_INTERNAL_URL;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    process.env = { ...ORIGINAL_ENV };
  });

  it("accepts and deduplicates only globally routable public DNS results", async () => {
    const dnsLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);

    await expect(
      resolveBackendAddresses(
        new URL("https://api.naruon.net/api/tasks"),
        dnsLookup,
      ),
    ).resolves.toEqual([
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    expect(dnsLookup).toHaveBeenCalledWith("api.naruon.net", {
      all: true,
      verbatim: true,
    });
  });

  it.each([
    "127.0.0.1",
    "10.0.0.8",
    "100.64.0.1",
    "169.254.169.254",
    "192.168.1.10",
    "::1",
    "::ffff:127.0.0.1",
    "0:0:0:0:0:ffff:7f00:1",
    "0::ffff:7f00:1",
    "0:0::ffff:7f00:1",
    "::FFFF:7F00:1",
    "fc00::1",
    "fe80::1",
  ])("rejects non-global public DNS answer %s", async (address) => {
    const dnsLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address, family: address.includes(":") ? 6 : 4 },
    ]);

    await expect(
      resolveBackendAddresses(
        new URL("https://api.naruon.net/api/tasks"),
        dnsLookup,
      ),
    ).rejects.toThrow(
      address.toLowerCase().includes("ffff:")
        ? "IPv4-mapped IPv6"
        : "globally routable",
    );
  });

  it("rejects the entire public destination when one answer is private", async () => {
    const dnsLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "169.254.169.254", family: 4 },
    ]);

    await expect(
      resolveBackendAddresses(
        new URL("https://api.naruon.net/api/tasks"),
        dnsLookup,
      ),
    ).rejects.toThrow("globally routable");
  });

  it("allows only loopback answers for the exact development backend", async () => {
    const loopbackLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address: "127.0.0.1", family: 4 },
      { address: "::1", family: 6 },
    ]);

    await expect(
      resolveBackendAddresses(
        new URL("http://localhost:8000/api/tasks"),
        loopbackLookup,
      ),
    ).resolves.toEqual([
      { address: "127.0.0.1", family: 4 },
      { address: "::1", family: 6 },
    ]);

    const publicLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    await expect(
      resolveBackendAddresses(
        new URL("http://localhost:8000/api/tasks"),
        publicLookup,
      ),
    ).rejects.toThrow("only to loopback");
  });

  it("allows private Compose answers but rejects metadata and public addresses", async () => {
    vi.stubEnv("ALLOW_DOCKER_BACKEND_INTERNAL_URL", "1");
    const privateLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
      { address: "172.18.0.4", family: 4 },
      { address: "fd00::4", family: 6 },
    ]);

    await expect(
      resolveBackendAddresses(
        new URL("http://backend:8000/api/tasks"),
        privateLookup,
      ),
    ).resolves.toEqual([
      { address: "172.18.0.4", family: 4 },
      { address: "fd00::4", family: 6 },
    ]);

    for (const address of ["169.254.169.254", "8.8.8.8", "fe80::1"]) {
      const dnsLookup = vi.fn<BackendDnsLookup>().mockResolvedValue([
        { address, family: address.includes(":") ? 6 : 4 },
      ]);
      await expect(
        resolveBackendAddresses(
          new URL("http://backend:8000/api/tasks"),
          dnsLookup,
        ),
      ).rejects.toThrow("private or loopback");
    }
  });

  it("rejects invalid destinations, empty DNS answers, and malformed addresses", async () => {
    const dnsLookup = vi.fn<BackendDnsLookup>();

    await expect(
      resolveBackendAddresses(
        new URL("http://localhost:9000/api/tasks"),
        dnsLookup,
      ),
    ).rejects.toThrow("outside the trusted origin policy");
    expect(dnsLookup).not.toHaveBeenCalled();

    dnsLookup.mockResolvedValueOnce([]);
    await expect(
      resolveBackendAddresses(
        new URL("https://api.naruon.net/api/tasks"),
        dnsLookup,
      ),
    ).rejects.toThrow("did not resolve");

    dnsLookup.mockResolvedValueOnce([{ address: "not-an-ip", family: 4 }]);
    await expect(
      resolveBackendAddresses(
        new URL("https://api.naruon.net/api/tasks"),
        dnsLookup,
      ),
    ).rejects.toThrow("invalid IP address");
  });

  it("fails closed when backend DNS resolution times out", async () => {
    vi.useFakeTimers();
    const pendingLookup = vi
      .fn<BackendDnsLookup>()
      .mockReturnValue(new Promise(() => undefined));
    const resolution = resolveBackendAddresses(
      new URL("https://api.naruon.net/api/tasks"),
      pendingLookup,
    );
    const rejection = expect(resolution).rejects.toThrow(
      "DNS resolution timed out",
    );

    await vi.advanceTimersByTimeAsync(5_000);
    await rejection;
  });

  it.each([
    "https://other.example/api/tasks",
    "https://user@api.naruon.net/api/tasks",
    "https://user:secret@api.naruon.net/api/tasks",
    "https://api.naruon.net/api/tasks#fragment",
  ])("rejects a request target outside the configured origin: %s", async (url) => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");

    await expect(fetchTrustedBackend(new URL(url))).rejects.toThrow(
      "does not match the trusted origin",
    );
    expect(systemLookupMock).not.toHaveBeenCalled();
    expect(httpsRequestMock).not.toHaveBeenCalled();
  });

  it("wires validated DNS answers into a one-shot HTTPS request", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net:8443");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    const requestEnd = vi.fn();
    const requestOnce = vi.fn();
    httpsRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([]) as Readable & {
        rawHeaders: string[];
        statusCode: number;
        statusMessage: string;
      };
      incoming.rawHeaders = ["X-Backend", "pinned"];
      incoming.statusCode = 204;
      incoming.statusMessage = "No Content";
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: requestEnd,
        once: requestOnce,
      };
    });
    const target = new URL(
      "https://api.naruon.net:8443/api/tasks?state=ready",
    );

    const response = await fetchTrustedBackend(target, {
      headers: {
        Accept: "application/json",
        Host: "attacker.example",
      },
      redirect: "manual",
    });

    expect(systemLookupMock).toHaveBeenCalledWith("api.naruon.net", {
      all: true,
      verbatim: true,
    });
    expect(httpsRequestMock).toHaveBeenCalledOnce();
    const [requestOptions] = httpsRequestMock.mock.calls[0] as [
      {
        agent: boolean;
        family: number;
        headers: Record<string, string>;
        hostname: string;
        method: string;
        path: string;
        port: string;
        protocol: string;
        servername: string;
      },
    ];
    expect(requestOptions).toMatchObject({
      agent: false,
      family: 4,
      headers: {
        accept: "application/json",
        host: "api.naruon.net:8443",
      },
      hostname: "8.8.8.8",
      method: "GET",
      path: "/api/tasks?state=ready",
      port: "8443",
      protocol: "https:",
      servername: "api.naruon.net",
    });
    expect(requestEnd).toHaveBeenCalledWith();
    expect(requestOnce).toHaveBeenCalledWith("error", expect.any(Function));
    expect(response.status).toBe(204);
    expect(response.headers.get("x-backend")).toBe("pinned");

  });

  it("uses a validated IPv6 literal when no IPv4 answer exists", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    httpsRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([]) as Readable & {
        rawHeaders: string[];
        statusCode: number;
        statusMessage: string;
      };
      incoming.rawHeaders = [];
      incoming.statusCode = 204;
      incoming.statusMessage = "No Content";
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: vi.fn(),
        once: vi.fn(),
      };
    });

    await fetchTrustedBackend(
      new URL("https://api.naruon.net/api/tasks"),
      { redirect: "manual" },
    );

    expect(httpsRequestMock.mock.calls[0]?.[0]).toMatchObject({
      family: 6,
      headers: { host: "api.naruon.net" },
      hostname: "2001:4860:4860::8888",
      path: "/api/tasks",
      protocol: "https:",
      servername: "api.naruon.net",
    });
  });

  it("uses the HTTP transport for Compose and preserves an empty status text", async () => {
    vi.stubEnv("ALLOW_DOCKER_BACKEND_INTERNAL_URL", "1");
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend:8000");
    systemLookupMock.mockResolvedValue([
      { address: "172.18.0.4", family: 4 },
    ]);
    const requestEnd = vi.fn();
    httpRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([]) as Readable & {
        rawHeaders: string[];
        statusCode: number;
        statusMessage?: string;
      };
      incoming.rawHeaders = ["X-Backend", "loopback", "Dangling"];
      incoming.statusCode = 205;
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: requestEnd,
        once: vi.fn(),
      };
    });

    const response = await fetchTrustedBackend(
      new URL("http://backend:8000/api/tasks"),
      {
        body: new URLSearchParams({ state: "ready" }),
        method: "POST",
        redirect: "manual",
      },
    );

    expect(httpRequestMock).toHaveBeenCalledOnce();
    expect(httpsRequestMock).not.toHaveBeenCalled();
    expect(httpRequestMock.mock.calls[0]?.[0]).toMatchObject({
      family: 4,
      headers: { host: "backend:8000" },
      hostname: "172.18.0.4",
      path: "/api/tasks",
      port: "8000",
      protocol: "http:",
    });
    expect(requestEnd).toHaveBeenCalledWith("state=ready");
    expect(response.status).toBe(205);
    expect(response.statusText).toBe("");
    expect(response.headers.get("x-backend")).toBe("loopback");
    expect(response.headers.has("dangling")).toBe(false);
  });

  it("forwards an ArrayBuffer body and streams the backend response", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    const requestEnd = vi.fn();
    httpsRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([Buffer.from("created")]) as Readable & {
        rawHeaders: string[];
        statusCode: number;
        statusMessage: string;
      };
      incoming.rawHeaders = ["Content-Type", "text/plain"];
      incoming.statusCode = 201;
      incoming.statusMessage = "Created";
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: requestEnd,
        once: vi.fn(),
      };
    });
    const body = new TextEncoder().encode("payload").buffer;

    const response = await fetchTrustedBackend(
      new URL("https://api.naruon.net/api/tasks"),
      { body, method: "POST", redirect: "manual" },
    );

    expect(requestEnd).toHaveBeenCalledOnce();
    expect(
      new TextDecoder().decode(requestEnd.mock.calls[0][0] as Uint8Array),
    ).toBe("payload");
    expect(response.status).toBe(201);
    await expect(response.text()).resolves.toBe("created");
  });

  it("forwards string, null, and typed-array bodies without coercing bytes", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    const requestEnd = vi.fn();
    httpsRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([]) as Readable & {
        rawHeaders: string[];
        statusCode: number;
        statusMessage: string;
      };
      incoming.rawHeaders = [];
      incoming.statusCode = 204;
      incoming.statusMessage = "No Content";
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: requestEnd,
        once: vi.fn(),
      };
    });

    await fetchTrustedBackend(
      new URL("https://api.naruon.net/api/string"),
      {
        body: "payload",
        method: "POST",
        redirect: "manual",
      },
    );
    await fetchTrustedBackend(new URL("https://api.naruon.net/api/null"), {
      body: null,
      method: "POST",
      redirect: "manual",
    });
    const view = new Uint16Array([0x1234, 0x5678]);
    await fetchTrustedBackend(new URL("https://api.naruon.net/api/view"), {
      body: view,
      method: "POST",
      redirect: "manual",
    });

    expect(requestEnd.mock.calls[0]).toEqual(["payload"]);
    expect(requestEnd.mock.calls[1]).toEqual([]);
    expect(requestEnd.mock.calls[2][0]).toEqual(
      new Uint8Array(view.buffer, view.byteOffset, view.byteLength),
    );
  });

  it("rejects unsupported bodies and destroys the unopened request", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    const requestDestroy = vi.fn();
    const requestEnd = vi.fn();
    httpsRequestMock.mockReturnValue({
      destroy: requestDestroy,
      end: requestEnd,
      once: vi.fn(),
    });

    await expect(
      fetchTrustedBackend(new URL("https://api.naruon.net/api/tasks"), {
        body: new Blob(["streaming"]),
        method: "POST",
        redirect: "manual",
      }),
    ).rejects.toThrow("only buffered request bodies");
    expect(requestDestroy).toHaveBeenCalledOnce();
    expect(requestEnd).not.toHaveBeenCalled();
  });

  it("rejects an invalid backend HTTP response status", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    const responseDestroy = vi.fn();
    httpsRequestMock.mockImplementation((_options, callback) => {
      const incoming = Readable.from([]) as Readable & {
        destroy: () => void;
        rawHeaders: string[];
        statusCode?: number;
      };
      incoming.destroy = responseDestroy;
      incoming.rawHeaders = [];
      callback(incoming);
      return {
        destroy: vi.fn(),
        end: vi.fn(),
        once: vi.fn(),
      };
    });

    await expect(
      fetchTrustedBackend(new URL("https://api.naruon.net/api/tasks"), {
        redirect: "manual",
      }),
    ).rejects.toThrow("invalid HTTP status");
    expect(responseDestroy).toHaveBeenCalledOnce();
  });

  it("rejects automatic redirect modes before opening a socket", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    httpsRequestMock.mockClear();

    await expect(
      fetchTrustedBackend(new URL("https://api.naruon.net/api/tasks"), {
        redirect: "follow",
      }),
    ).rejects.toThrow("handled manually");
    expect(httpsRequestMock).not.toHaveBeenCalled();
  });
});
