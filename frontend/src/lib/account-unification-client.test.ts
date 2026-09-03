import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFetchBackedNodeRequest } from "@/test/fetch-backed-node-request";

import {
  AccountUnificationError,
  passwordRegistrationConfig,
  registerAccountWithPassword,
} from "./account-unification-client";

const { dnsLookupMock, httpRequestMock, httpsRequestMock } = vi.hoisted(() => ({
  dnsLookupMock: vi.fn(),
  httpRequestMock: vi.fn(),
  httpsRequestMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({ lookup: dnsLookupMock }));
vi.mock("node:http", async () => {
  const actual = await vi.importActual<typeof import("node:http")>("node:http");
  return { ...actual, request: httpRequestMock };
});
vi.mock("node:https", () => ({ request: httpsRequestMock }));

const ORIGINAL_ENV = { ...process.env };

describe("account-unification password-registration client", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.ACCOUNT_UNIFICATION_INTERNAL_URL;
    delete process.env.ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN;
    dnsLookupMock.mockReset();
    dnsLookupMock.mockResolvedValue([{ address: "8.8.8.8", family: 4 }]);
    httpRequestMock.mockReset();
    httpsRequestMock.mockReset();
    httpRequestMock.mockImplementation(createFetchBackedNodeRequest());
    httpsRequestMock.mockImplementation(createFetchBackedNodeRequest());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    process.env = { ...ORIGINAL_ENV };
  });

  it("returns null (fail closed) when either env value is unset", () => {
    expect(passwordRegistrationConfig()).toBeNull();
    vi.stubEnv("ACCOUNT_UNIFICATION_INTERNAL_URL", "https://idp.internal.example");
    expect(passwordRegistrationConfig()).toBeNull();
  });

  it("accepts a public HTTPS internal URL", () => {
    vi.stubEnv("ACCOUNT_UNIFICATION_INTERNAL_URL", "https://idp.internal.example");
    vi.stubEnv("ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN", "token-1");
    const config = passwordRegistrationConfig();
    expect(config?.baseUrl.origin).toBe("https://idp.internal.example");
    expect(config?.token).toBe("token-1");
  });

  it("rejects a non-HTTPS internal URL in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("ACCOUNT_UNIFICATION_INTERNAL_URL", "http://idp.internal.example");
    vi.stubEnv("ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN", "token-1");
    expect(() => passwordRegistrationConfig()).toThrow(/https/);
  });

  it("rejects a private/loopback host outside the dev-loopback exception", () => {
    vi.stubEnv("ACCOUNT_UNIFICATION_INTERNAL_URL", "https://10.0.0.4");
    vi.stubEnv("ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN", "token-1");
    expect(() => passwordRegistrationConfig()).toThrow(/private\/loopback/);
  });

  it("allows the exact dev loopback outside production", () => {
    vi.stubEnv("ACCOUNT_UNIFICATION_INTERNAL_URL", "http://127.0.0.1:8099");
    vi.stubEnv("ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN", "token-1");
    const config = passwordRegistrationConfig();
    expect(config?.baseUrl.origin).toBe("http://127.0.0.1:8099");
  });

  it("creates an account through the pinned HTTPS client and returns its id/email", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("https://idp.internal.example/registration/accounts/password");
      expect(new Headers(init?.headers).get("authorization")).toBe("Bearer token-1");
      expect(JSON.parse(String(init?.body))).toEqual({
        email_address: "person@example.com",
        password: "correct horse battery staple 1!",
      });
      return Response.json(
        { account_id: "user-1", email_address: "person@example.com" },
        { status: 201 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await registerAccountWithPassword(
      { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
      { email_address: "person@example.com", password: "correct horse battery staple 1!" },
    );

    expect(result).toEqual({ account_id: "user-1", email_address: "person@example.com" });
    expect(httpsRequestMock).toHaveBeenCalledOnce();
    expect(httpRequestMock).not.toHaveBeenCalled();
  });

  it("uses the pinned HTTP client only for the exact development loopback", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { account_id: "user-1", email_address: "person@example.com" },
          { status: 201 },
        ),
      ),
    );

    await registerAccountWithPassword(
      { baseUrl: new URL("http://127.0.0.1:8099"), token: "token-1" },
      { email_address: "person@example.com", password: "correct horse battery staple 1!" },
    );

    expect(httpRequestMock).toHaveBeenCalledOnce();
    expect(httpsRequestMock).not.toHaveBeenCalled();
  });

  it("surfaces the upstream status and detail on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ detail: "email_already_registered" }, { status: 409 }),
      ),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject(
      new AccountUnificationError("account_unification_rejected", 409, "email_already_registered"),
    );
  });

  it("maps a transport failure to a generic 502 error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({ status: 502, message: "account_unification_unreachable" });
  });

  it("fails closed instead of following a redirect response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(null, {
          status: 307,
          headers: { Location: "https://attacker.example/registration/accounts/password" },
        }),
      ),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({ status: 502, message: "account_unification_unreachable" });
    expect(httpsRequestMock).toHaveBeenCalledOnce();
  });

  it("rejects a malformed success response shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ unexpected: true }, { status: 201 })),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({ status: 502, message: "account_unification_response_invalid" });
  });

  it("rejects an oversized response before parsing it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("x".repeat(64 * 1024 + 1), { status: 201 })),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({ status: 502, message: "account_unification_unreachable" });
  });
});
