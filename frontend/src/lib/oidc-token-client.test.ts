import { afterEach, describe, expect, it, vi } from "vitest";
import { createServer } from "node:http";

import {
  createPinnedOidcLookup,
  postOidcTokenRequest,
  resolveOidcTokenAddresses,
  type OidcDnsLookup,
} from "./oidc-token-client";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("OIDC token destination pinning", () => {
  it("accepts and deduplicates only globally routable DNS results", async () => {
    const dnsLookup = vi.fn<OidcDnsLookup>().mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);

    await expect(
      resolveOidcTokenAddresses(
        new URL("https://login.example.com/token"),
        dnsLookup,
      ),
    ).resolves.toEqual([
      { address: "8.8.8.8", family: 4 },
      { address: "2001:4860:4860::8888", family: 6 },
    ]);
    expect(dnsLookup).toHaveBeenCalledOnce();
  });

  it.each([
    "127.0.0.1",
    "10.0.0.8",
    "100.64.0.1",
    "169.254.169.254",
    "192.168.1.10",
    "::1",
    "::ffff:127.0.0.1",
    "fc00::1",
    "fe80::1",
  ])("rejects non-global DNS answer %s", async (address) => {
    const family = address.includes(":") ? 6 : 4;
    const dnsLookup = vi
      .fn<OidcDnsLookup>()
      .mockResolvedValue([{ address, family }]);

    await expect(
      resolveOidcTokenAddresses(
        new URL("https://login.example.com/token"),
        dnsLookup,
      ),
    ).rejects.toThrow("globally routable");
  });

  it("rejects the whole destination when one DNS answer is private", async () => {
    const dnsLookup = vi.fn<OidcDnsLookup>().mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "127.0.0.1", family: 4 },
    ]);

    await expect(
      resolveOidcTokenAddresses(
        new URL("https://login.example.com/token"),
        dnsLookup,
      ),
    ).rejects.toThrow("globally routable");
  });

  it("allows exact development loopback HTTP but rejects it in production", async () => {
    vi.stubEnv("NODE_ENV", "development");
    await expect(
      resolveOidcTokenAddresses(new URL("http://127.0.0.1:8080/token")),
    ).resolves.toEqual([{ address: "127.0.0.1", family: 4 }]);

    vi.stubEnv("NODE_ENV", "production");
    await expect(
      resolveOidcTokenAddresses(new URL("http://127.0.0.1:8080/token")),
    ).rejects.toThrow("globally routable");
  });

  it("rejects a non-loopback DNS answer for development localhost HTTP", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const dnsLookup = vi
      .fn<OidcDnsLookup>()
      .mockResolvedValue([{ address: "8.8.8.8", family: 4 }]);

    await expect(
      resolveOidcTokenAddresses(
        new URL("http://localhost:8080/token"),
        dnsLookup,
      ),
    ).rejects.toThrow("only to loopback");
  });

  it("returns only the prevalidated address without another DNS lookup", async () => {
    const pinnedLookup = createPinnedOidcLookup(
      "login.example.com",
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

    const result = await new Promise<{ address: string; family: number }>(
      (resolve, reject) => {
        invokeLookup(
          "login.example.com",
          { all: false, family: 0 },
          (error, address, family) => {
            if (error) {
              reject(error);
              return;
            }
            resolve({ address, family });
          },
        );
      },
    );

    expect(result).toEqual({ address: "8.8.8.8", family: 4 });
  });

  it("refuses to reuse pinned addresses for a different hostname", async () => {
    const pinnedLookup = createPinnedOidcLookup(
      "login.example.com",
      [{ address: "8.8.8.8", family: 4 }],
    );
    const invokeLookup = pinnedLookup as unknown as (
      hostname: string,
      options: { all: false; family: number },
      callback: (error: Error | null) => void,
    ) => void;

    await expect(
      new Promise<void>((resolve, reject) => {
        invokeLookup(
          "attacker.example",
          { all: false, family: 0 },
          (error) => {
            if (error) {
              reject(error);
              return;
            }
            resolve();
          },
        );
      }),
    ).rejects.toThrow("unexpected hostname");
  });

  it("posts through the pinned native client without following redirects", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const server = createServer((request, response) => {
      expect(request.method).toBe("POST");
      expect(request.headers.host).toMatch(/^127\.0\.0\.1:/);
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ access_token: "signed-token" }));
    });
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", () => resolve());
    });
    const address = server.address();
    if (!address || typeof address === "string") {
      server.close();
      throw new Error("test server did not expose a TCP port");
    }

    try {
      await expect(
        postOidcTokenRequest(
          new URL(`http://127.0.0.1:${address.port}/token`),
          new URLSearchParams({ code: "auth-code" }),
        ),
      ).resolves.toEqual({ access_token: "signed-token" });
    } finally {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        });
      });
    }
  });
});
