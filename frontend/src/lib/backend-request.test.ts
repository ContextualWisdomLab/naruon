import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Agent } from "undici";

import {
  createPinnedBackendLookup,
  fetchTrustedBackend,
  resolveBackendAddresses,
  type BackendDnsLookup,
} from "./backend-request";

const { systemLookupMock } = vi.hoisted(() => ({
  systemLookupMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({
  lookup: systemLookupMock,
}));

const ORIGINAL_ENV = { ...process.env };

describe("backend destination pinning", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
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

  it("wires validated DNS answers into the fetch dispatcher", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    systemLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    const expectedResponse = new Response(null, { status: 204 });
    const fetchMock = vi.fn().mockResolvedValue(expectedResponse);
    vi.stubGlobal("fetch", fetchMock);
    const target = new URL("https://api.naruon.net/api/tasks");

    await expect(
      fetchTrustedBackend(target, { redirect: "manual" }),
    ).resolves.toBe(expectedResponse);

    expect(systemLookupMock).toHaveBeenCalledWith("api.naruon.net", {
      all: true,
      verbatim: true,
    });
    expect(fetchMock).toHaveBeenCalledOnce();
    const [fetchedTarget, requestInit] = fetchMock.mock.calls[0] as [
      URL,
      RequestInit & { dispatcher: Agent },
    ];
    expect(fetchedTarget).toBe(target);
    expect(requestInit.redirect).toBe("manual");
    expect(requestInit.dispatcher).toBeInstanceOf(Agent);
  });
});
