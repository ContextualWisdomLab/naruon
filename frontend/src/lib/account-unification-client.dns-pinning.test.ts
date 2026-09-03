import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFetchBackedNodeRequest } from "@/test/fetch-backed-node-request";

import { registerAccountWithPassword } from "./account-unification-client";

const { dnsLookupMock, httpsRequestMock } = vi.hoisted(() => ({
  dnsLookupMock: vi.fn(),
  httpsRequestMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({
  lookup: dnsLookupMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

const ORIGINAL_ENV = { ...process.env };

describe("account-unification destination pinning", () => {
  beforeEach(() => {
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("NODE_ENV", "production");
    dnsLookupMock.mockReset();
    dnsLookupMock.mockResolvedValue([{ address: "8.8.8.8", family: 4 }]);
    httpsRequestMock.mockReset();
    httpsRequestMock.mockImplementation(createFetchBackedNodeRequest());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
  });

  it("connects through the DNS result validated before the password-bearing request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { account_id: "user-1", email_address: "person@example.com" },
          { status: 201 },
        ),
      ),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.example.com"), token: "registration-token" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).resolves.toEqual({
      account_id: "user-1",
      email_address: "person@example.com",
    });

    expect(dnsLookupMock).toHaveBeenCalledWith("idp.example.com", {
      all: true,
      verbatim: true,
    });
    expect(httpsRequestMock).toHaveBeenCalledOnce();

    const [requestOptions] = httpsRequestMock.mock.calls[0] as [{
      lookup?: (
        hostname: string,
        options: { all: false; family: number },
        callback: (error: Error | null, address?: string, family?: number) => void,
      ) => void;
    }];
    expect(requestOptions.lookup).toBeTypeOf("function");

    await expect(
      new Promise<{ address: string; family: number }>((resolve, reject) => {
        requestOptions.lookup!(
          "idp.example.com",
          { all: false, family: 0 },
          (error, address, family) => {
            if (error) {
              reject(error);
              return;
            }
            resolve({ address: address!, family: family! });
          },
        );
      }),
    ).resolves.toEqual({ address: "8.8.8.8", family: 4 });
  });

  it("fails before sending the password when DNS returns any non-global address", async () => {
    dnsLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
      { address: "169.254.169.254", family: 4 },
    ]);
    vi.stubGlobal("fetch", vi.fn());

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.example.com"), token: "registration-token" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({
      status: 502,
      message: "account_unification_unreachable",
    });

    expect(httpsRequestMock).not.toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
