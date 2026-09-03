import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFetchBackedNodeRequest } from "@/test/fetch-backed-node-request";

import { POST } from "./route";

const { postOidcTokenRequestMock } = vi.hoisted(() => ({
  postOidcTokenRequestMock: vi.fn<
    (endpoint: URL, body: URLSearchParams) => Promise<{ access_token?: unknown }>
  >(),
}));

const { registerAccountWithPasswordMock, passwordRegistrationConfigMock } = vi.hoisted(() => ({
  registerAccountWithPasswordMock: vi.fn(),
  passwordRegistrationConfigMock: vi.fn(),
}));

const { backendDnsLookupMock, httpsRequestMock } = vi.hoisted(() => ({
  backendDnsLookupMock: vi.fn(),
  httpsRequestMock: vi.fn(),
}));

vi.mock("@/lib/oidc-token-client", () => ({
  postOidcTokenRequest: postOidcTokenRequestMock,
}));

vi.mock("@/lib/account-unification-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/account-unification-client")>(
    "@/lib/account-unification-client",
  );
  return {
    ...actual,
    registerAccountWithPassword: registerAccountWithPasswordMock,
    passwordRegistrationConfig: passwordRegistrationConfigMock,
  };
});

vi.mock("node:dns/promises", () => ({
  lookup: backendDnsLookupMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

const ORIGINAL_ENV = { ...process.env };
const REGISTRATION_CONFIG = { baseUrl: new URL("https://idp.internal.example"), token: "reg-token" };

function postRequest(bodyJson: unknown) {
  return new NextRequest("https://app.example.com/auth/password/signup", {
    method: "POST",
    body: JSON.stringify(bodyJson),
    headers: { origin: "https://app.example.com" },
  });
}

describe("/auth/password/signup route", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://login.example.com/realms/naruon/");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "naruon-web");
    backendDnsLookupMock.mockReset();
    backendDnsLookupMock.mockResolvedValue([{ address: "8.8.8.8", family: 4 }]);
    httpsRequestMock.mockReset();
    httpsRequestMock.mockImplementation(createFetchBackedNodeRequest());
    postOidcTokenRequestMock.mockReset();
    registerAccountWithPasswordMock.mockReset();
    passwordRegistrationConfigMock.mockReset();
    passwordRegistrationConfigMock.mockReturnValue(REGISTRATION_CONFIG);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
  });

  it("creates a password account, then logs the new session straight in", async () => {
    registerAccountWithPasswordMock.mockResolvedValue({
      account_id: "user-1",
      email_address: "person@example.com",
    });
    postOidcTokenRequestMock.mockResolvedValue({
      access_token: "test-header.test-payload.test-signature",
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("https://api.naruon.net/api/auth/session");
      return Response.json({
        user_id: "user-1",
        organization_id: "org-acme",
        workspace_id: "workspace-acme",
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      postRequest({
        email: "person@example.com",
        password: "correct horse battery staple 1!",
        first_name: "New",
        return_to: "/settings",
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ return_to: "/settings" });
    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("naruon_session=");
    expect(setCookie).toContain("HttpOnly");
    expect(registerAccountWithPasswordMock).toHaveBeenCalledWith(REGISTRATION_CONFIG, {
      email_address: "person@example.com",
      password: "correct horse battery staple 1!",
      first_name: "New",
      last_name: undefined,
    });
    const [, tokenBody] = postOidcTokenRequestMock.mock.calls[0];
    expect(tokenBody.get("grant_type")).toBe("password");
    expect(tokenBody.get("username")).toBe("person@example.com");
  });

  it("fails closed with 503 when password signup is not configured", async () => {
    passwordRegistrationConfigMock.mockReturnValue(null);

    const response = await POST(
      postRequest({ email: "person@example.com", password: "correct horse battery staple 1!" }),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_unavailable",
    });
    expect(registerAccountWithPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects a missing email or password before contacting Keyverse", async () => {
    const response = await POST(postRequest({ email: "person@example.com" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_credentials_invalid",
    });
    expect(registerAccountWithPasswordMock).not.toHaveBeenCalled();
  });

  it("maps a duplicate-email conflict to 409 without logging the caller in", async () => {
    const { AccountUnificationError } = await import("@/lib/account-unification-client");
    registerAccountWithPasswordMock.mockRejectedValue(
      new AccountUnificationError("account_unification_rejected", 409, "email_already_registered"),
    );

    const response = await POST(
      postRequest({ email: "person@example.com", password: "correct horse battery staple 1!" }),
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_email_taken",
    });
    expect(postOidcTokenRequestMock).not.toHaveBeenCalled();
  });

  it("forwards a validation error's detail as the error code", async () => {
    const { AccountUnificationError } = await import("@/lib/account-unification-client");
    registerAccountWithPasswordMock.mockRejectedValue(
      new AccountUnificationError("account_unification_rejected", 422, "password_must_not_match_email"),
    );

    const response = await POST(
      postRequest({ email: "person@example.com", password: "correct horse battery staple 1!" }),
    );

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_must_not_match_email",
    });
  });

  it("maps a rate-limited registration response to 429", async () => {
    const { AccountUnificationError } = await import("@/lib/account-unification-client");
    registerAccountWithPasswordMock.mockRejectedValue(
      new AccountUnificationError("account_unification_rejected", 429),
    );

    const response = await POST(
      postRequest({ email: "person@example.com", password: "correct horse battery staple 1!" }),
    );

    expect(response.status).toBe(429);
  });

  it("collapses an unreachable or malformed upstream response to a generic 502", async () => {
    registerAccountWithPasswordMock.mockRejectedValue(new Error("network exploded"));

    const response = await POST(
      postRequest({ email: "person@example.com", password: "correct horse battery staple 1!" }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_failed",
    });
  });

  it("rejects a cross-site signup submission before touching account-unification", async () => {
    const request = new NextRequest("https://app.example.com/auth/password/signup", {
      method: "POST",
      body: JSON.stringify({
        email: "person@example.com",
        password: "correct horse battery staple 1!",
      }),
      headers: { origin: "https://attacker.example" },
    });

    const response = await POST(request);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error_code: "csrf_origin_rejected" });
    expect(registerAccountWithPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects (rather than silently dropping) an over-length first_name", async () => {
    const response = await POST(
      postRequest({
        email: "person@example.com",
        password: "correct horse battery staple 1!",
        first_name: "x".repeat(101),
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error_code: "password_signup_name_invalid" });
    expect(registerAccountWithPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects an oversized request body with 413 before parsing it", async () => {
    const request = new NextRequest("https://app.example.com/auth/password/signup", {
      method: "POST",
      body: JSON.stringify({
        email: "person@example.com",
        password: "correct horse battery staple 1!",
        first_name: "x".repeat(20_000),
      }),
      headers: { origin: "https://app.example.com" },
    });

    const response = await POST(request);

    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toEqual({ error_code: "password_signup_request_too_large" });
    expect(registerAccountWithPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects a signup submission with no Origin or Referer at all", async () => {
    const request = new NextRequest("https://app.example.com/auth/password/signup", {
      method: "POST",
      body: JSON.stringify({
        email: "person@example.com",
        password: "correct horse battery staple 1!",
      }),
    });

    const response = await POST(request);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error_code: "csrf_origin_rejected" });
  });
});
