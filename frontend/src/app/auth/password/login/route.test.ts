import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFetchBackedNodeRequest } from "@/test/fetch-backed-node-request";

import { POST } from "./route";

const { postOidcTokenRequestMock } = vi.hoisted(() => ({
  postOidcTokenRequestMock: vi.fn<
    (endpoint: URL, body: URLSearchParams) => Promise<{ access_token?: unknown }>
  >(),
}));

const { backendDnsLookupMock, httpsRequestMock } = vi.hoisted(() => ({
  backendDnsLookupMock: vi.fn(),
  httpsRequestMock: vi.fn(),
}));

vi.mock("@/lib/oidc-token-client", () => ({
  postOidcTokenRequest: postOidcTokenRequestMock,
}));

vi.mock("node:dns/promises", () => ({
  lookup: backendDnsLookupMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

const ORIGINAL_ENV = { ...process.env };

function postRequest(bodyJson: unknown) {
  return new NextRequest("https://app.example.com/auth/password/login", {
    method: "POST",
    body: JSON.stringify(bodyJson),
  });
}

describe("/auth/password/login route", () => {
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
  });

  it("exchanges a username/password for a Direct Access Grants token and sets only an HttpOnly session cookie", async () => {
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
      postRequest({ username: "person@example.com", password: "correct horse", return_to: "/settings" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ return_to: "/settings" });
    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("naruon_session=");
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Secure");
    expect(setCookie).not.toContain("correct horse");

    expect(postOidcTokenRequestMock).toHaveBeenCalledTimes(1);
    const [tokenEndpoint, tokenBody] = postOidcTokenRequestMock.mock.calls[0];
    expect(tokenEndpoint.href).toBe(
      "https://login.example.com/realms/naruon/protocol/openid-connect/token",
    );
    expect(tokenBody.get("grant_type")).toBe("password");
    expect(tokenBody.get("client_id")).toBe("naruon-web");
    expect(tokenBody.get("username")).toBe("person@example.com");
    expect(tokenBody.get("password")).toBe("correct horse");
  });

  it("rejects a missing username or password before contacting Keycloak", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(postRequest({ username: "person@example.com" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_login_credentials_invalid",
    });
    expect(postOidcTokenRequestMock).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("collapses a wrong password, unknown user, and a disabled grant into one generic error", async () => {
    postOidcTokenRequestMock.mockRejectedValue(new Error("OIDC token endpoint returned HTTP 401"));
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      postRequest({ username: "person@example.com", password: "wrong-password" }),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_login_invalid_credentials",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never persists a session cookie when the backend rejects the minted token", async () => {
    postOidcTokenRequestMock.mockResolvedValue({
      access_token: "test-header.test-payload.test-signature",
    });
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      postRequest({ username: "person@example.com", password: "correct horse" }),
    );

    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
