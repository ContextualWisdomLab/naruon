import { Readable } from "node:stream";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createPinnedBackendLookup,
  fetchTrustedBackend,
  resolveBackendAddresses,
  type BackendDnsLookup,
} from "./backend-request";

const { httpsRequestMock, systemLookupMock } = vi.hoisted(() => ({
  httpsRequestMock: vi.fn(),
  systemLookupMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({
  lookup: systemLookupMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

const ORIGINAL_ENV = { ...process.env };

describe("backend destination pinning", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    httpsRequestMock.mockReset();
    systemLookupMock.mockReset();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.ALLOW_DOCKER_BACKEND_INTERNAL_URL;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
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

  it("returns only prevalidated addresses and rejects another hostname", async () => {
    const pinnedLookup = createPinnedBackendLookup(
      "api.naruon.net",
      [{ address: "8.8.8.8", family: 4 }],
    );
    const invokeLookup = pinnedLookup as unknown as (
      hostname: string,
      options: { all: false; family: number },
      callback: (
        error: Error | null,
        address: string,
        family: number,
      ) => void,
    ) => void;

    await expect(
      new Promise<{ address: string; family: number }>((resolve, reject) => {
        invokeLookup(
          "api.naruon.net",
          { all: false, family: 0 },
          (error, address, family) => {
            if (error) reject(error);
            else resolve({ address, family });
          },
        );
      }),
    ).resolves.toEqual({ address: "8.8.8.8", family: 4 });

    await expect(
      new Promise<void>((resolve, reject) => {
        invokeLookup(
          "attacker.example",
          { all: false, family: 0 },
          (error) => {
            if (error) reject(error);
            else resolve();
          },
        );
      }),
    ).rejects.toThrow("unexpected hostname");
  });

  it("normalizes bracketed IPv6 hostnames in the pinned lookup", async () => {
    const pinnedLookup = createPinnedBackendLookup(
      "2001:4860:4860::8888",
      [{ address: "2001:4860:4860::8888", family: 6 }],
    );
    const invokeLookup = pinnedLookup as unknown as (
      hostname: string,
      options: { all: false; family: number },
      callback: (
        error: Error | null,
        address: string,
        family: number,
      ) => void,
    ) => void;

    await expect(
      new Promise<{ address: string; family: number }>((resolve, reject) => {
        invokeLookup(
          "[2001:4860:4860::8888]",
          { all: false, family: 6 },
          (error, address, family) => {
            if (error) reject(error);
            else resolve({ address, family });
          },
        );
      }),
    ).resolves.toEqual({
      address: "2001:4860:4860::8888",
      family: 6,
    });
  });

  it("wires validated DNS answers into a one-shot HTTPS request", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    const requestEnd = vi.fn();
    const requestOnce = vi.fn();
    httpsRequestMock.mockImplementation((_target, _options, callback) => {
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
    const target = new URL("https://api.naruon.net/api/tasks");

    const response = await fetchTrustedBackend(target, {
      headers: { Accept: "application/json" },
      redirect: "manual",
    });

    expect(systemLookupMock).toHaveBeenCalledWith("api.naruon.net", {
      all: true,
      verbatim: true,
    });
    expect(httpsRequestMock).toHaveBeenCalledOnce();
    const [fetchedTarget, requestOptions] = httpsRequestMock.mock.calls[0] as [
      URL,
      {
        agent: boolean;
        headers: Record<string, string>;
        lookup: ReturnType<typeof createPinnedBackendLookup>;
        method: string;
        servername: string;
      },
    ];
    expect(fetchedTarget).toBe(target);
    expect(requestOptions).toMatchObject({
      agent: false,
      headers: { accept: "application/json" },
      method: "GET",
      servername: "api.naruon.net",
    });
    expect(requestEnd).toHaveBeenCalledWith();
    expect(requestOnce).toHaveBeenCalledWith("error", expect.any(Function));
    expect(response.status).toBe(204);
    expect(response.headers.get("x-backend")).toBe("pinned");

    const invokeLookup = requestOptions.lookup as unknown as (
      hostname: string,
      options: { all: false; family: number },
      callback: (
        error: Error | null,
        address: string,
        family: number,
      ) => void,
    ) => void;
    await expect(
      new Promise<{ address: string; family: number }>((resolve, reject) => {
        invokeLookup(
          "api.naruon.net",
          { all: false, family: 0 },
          (error, address, family) => {
            if (error) reject(error);
            else resolve({ address, family });
          },
        );
      }),
    ).resolves.toEqual({ address: "8.8.8.8", family: 4 });
  });

  it("forwards an ArrayBuffer body and streams the backend response", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    const requestEnd = vi.fn();
    httpsRequestMock.mockImplementation((_target, _options, callback) => {
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
