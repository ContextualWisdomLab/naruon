import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AccountUnificationError,
  passwordRegistrationConfig,
  registerAccountWithPassword,
} from "./account-unification-client";

const ORIGINAL_ENV = { ...process.env };

describe("account-unification password-registration client", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.ACCOUNT_UNIFICATION_INTERNAL_URL;
    delete process.env.ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
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

  it("creates an account and returns its id/email on success", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("https://idp.internal.example/registration/accounts/password");
      expect(new Headers(init?.headers).get("authorization")).toBe("Bearer token-1");
      // A 307/308 preserves the POST body -- fetch must not be allowed to
      // silently forward the password to a redirect's Location.
      expect(init?.redirect).toBe("error");
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

  it("fails closed instead of following a redirect response (fetch throws per redirect: 'error')", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        // This is the real contract for redirect: "error" (a TypeError,
        // same shape as any other network failure) -- simulated here since
        // undici/jsdom's fetch doesn't run a real redirect in this test.
        if (init?.redirect === "error") {
          throw new TypeError("fetch failed");
        }
        return Response.json({ account_id: "user-1", email_address: "person@example.com" }, { status: 201 });
      }),
    );

    await expect(
      registerAccountWithPassword(
        { baseUrl: new URL("https://idp.internal.example"), token: "token-1" },
        { email_address: "person@example.com", password: "correct horse battery staple 1!" },
      ),
    ).rejects.toMatchObject({ status: 502, message: "account_unification_unreachable" });
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
});
