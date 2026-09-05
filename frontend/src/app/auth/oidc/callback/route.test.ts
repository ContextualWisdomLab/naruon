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

function oidcStateCookie(state: string, verifier: string, returnTo: string) {
  const payload = Buffer.from(JSON.stringify({
    state,
    verifier,
    return_to: returnTo,
  })).toString("base64url");
  return `naruon_oidc_pkce=${payload}`;
}

describe("/auth/oidc/callback route", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://login.example.com/realms/naruon/");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "naruon-web");
    vi.stubEnv("NEXT_PUBLIC_OIDC_REDIRECT_URI", "https://app.example.com/auth/callback");
    backendDnsLookupMock.mockReset();
    backendDnsLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    httpsRequestMock.mockReset();
    httpsRequestMock.mockImplementation(createFetchBackedNodeRequest());
    postOidcTokenRequestMock.mockReset();
    postOidcTokenRequestMock.mockResolvedValue({
      access_token: "test-header.test-payload.test-signature",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
  });

  it("exchanges the callback code server-side and sets only HttpOnly cookies", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "https://login.example.com/realms/naruon/protocol/openid-connect/token") {
        expect(init?.method).toBe("POST");
        expect(String(init?.body)).toContain("code=auth-code");
        expect(String(init?.body)).toContain("code_verifier=verifier-123");
        return Response.json({ access_token: "test-header.test-payload.test-signature" });
      }
      if (url === "https://api.naruon.net/api/auth/session") {
        expect(new Headers(init?.headers).get("authorization")).toBe("Bearer test-header.test-payload.test-signature");
        return Response.json({
          user_id: "user-1",
          organization_id: "org-acme",
          workspace_id: "workspace-acme",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(new NextRequest("https://app.example.com/auth/oidc/callback", {
      method: "POST",
      headers: {
        Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
      },
      body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
    }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ return_to: "/security" });
    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("naruon_session=");
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Secure");
    expect(setCookie).toContain("naruon_oidc_pkce=");
    expect(setCookie).toContain("Max-Age=0");
    expect(setCookie).not.toContain("verifier-123");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(httpsRequestMock.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      agent: false,
      method: "GET",
      servername: "api.naruon.net",
      signal: expect.any(AbortSignal),
    }));
    expect(postOidcTokenRequestMock).toHaveBeenCalledTimes(1);
    const [tokenEndpoint, tokenBody] = postOidcTokenRequestMock.mock.calls[0];
    expect(tokenEndpoint.href).toBe(
      "https://login.example.com/realms/naruon/protocol/openid-connect/token",
    );
    expect(tokenBody.get("code")).toBe("auth-code");
    expect(tokenBody.get("code_verifier")).toBe("verifier-123");
  });

  it("rejects callbacks without matching server-side state", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(new NextRequest("https://app.example.com/auth/oidc/callback", {
      method: "POST",
      headers: {
        Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
      },
      body: JSON.stringify({ search: "?code=auth-code&state=attacker-state" }),
    }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error_code: "oidc_callback_state_invalid",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([
    "http://169.254.169.254/token",
    "https://evil.example/token",
    "https://login.example.com@169.254.169.254/token",
  ])(
    "rejects untrusted OIDC token endpoint %s before fetching",
    async (tokenEndpoint) => {
      vi.stubEnv("NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT", tokenEndpoint);
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const response = await POST(
        new NextRequest("https://app.example.com/auth/oidc/callback", {
          method: "POST",
          headers: {
            Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
          },
          body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
        }),
      );

      expect(response.status).toBe(502);
      await expect(response.json()).resolves.toEqual({
        error_code: "oidc_token_exchange_failed",
      });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("rejects IPv4-mapped IPv6 OIDC token endpoints before fetching", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_ISSUER_URL",
      "https://[::ffff:127.0.0.1]/realms/naruon",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "https://[::ffff:127.0.0.1]/realms/naruon/token",
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error_code: "oidc_token_exchange_failed",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects trailing-dot private OIDC hosts before fetching", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_ISSUER_URL",
      "https://service.local./realms/naruon",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "https://service.local./realms/naruon/token",
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error_code: "oidc_token_exchange_failed",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("allows an exact loopback OIDC issuer only outside production", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_ISSUER_URL",
      "http://127.0.0.1:8080/realms/naruon",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "http://127.0.0.1:8080/realms/naruon/protocol/openid-connect/token",
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (
        url ===
        "http://127.0.0.1:8080/realms/naruon/protocol/openid-connect/token"
      ) {
        return Response.json({
          access_token: "test-header.test-payload.test-signature",
        });
      }
      if (url === "https://api.naruon.net/api/auth/session") {
        return Response.json({
          user_id: "user-1",
          organization_id: "org-acme",
          workspace_id: "workspace-acme",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("http://localhost:3000/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(postOidcTokenRequestMock).toHaveBeenCalledTimes(1);
  });

  it("preserves a validated global IPv6 OIDC issuer authority", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_ISSUER_URL",
      "https://[2001:4860:4860::8888]/realms/naruon",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "https://[2001:4860:4860::8888]/realms/naruon/token",
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "https://[2001:4860:4860::8888]/realms/naruon/token") {
        return Response.json({
          access_token: "test-header.test-payload.test-signature",
        });
      }
      if (url === "https://api.naruon.net/api/auth/session") {
        return Response.json({
          user_id: "user-1",
          organization_id: "org-acme",
          workspace_id: "workspace-acme",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(postOidcTokenRequestMock).toHaveBeenCalledTimes(1);
  });

  it("rejects loopback OIDC token endpoints in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("OIDC_ALLOWED_HOSTS", "127.0.0.1");
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_ISSUER_URL",
      "http://127.0.0.1:8080/realms/naruon",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "http://127.0.0.1:8080/realms/naruon/protocol/openid-connect/token",
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(502);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(postOidcTokenRequestMock).not.toHaveBeenCalled();
  });

  it("requires an exact server-only OIDC host allowlist in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const warnMock = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(502);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(postOidcTokenRequestMock).not.toHaveBeenCalled();
    expect(warnMock).toHaveBeenCalledWith(
      "oidc_token_exchange_failed",
      { reason: "configuration_rejected" },
    );
  });

  it("uses the pinned token client for an allowlisted production issuer", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("OIDC_ALLOWED_HOSTS", "login.example.com");
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
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("state-123", "verifier-123", "/security"),
        },
        body: JSON.stringify({ search: "?code=auth-code&state=state-123" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(postOidcTokenRequestMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns configuration error if the endpoint has invalid URI encoding", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://auth.example.com");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "test-client");
    vi.stubEnv("NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT", "https://auth.example.com/auth");
    vi.stubEnv("NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT", "https://auth.example.com/token/%2");

    const req = new NextRequest("http://localhost:3000/auth/callback", {
      method: "POST",
      headers: { cookie: `naruon_oidc_pkce=eyJzdGF0ZSI6InRlc3Qtc3RhdGUiLCJ2ZXJpZmllciI6InRlc3QtdmVyaWZpZXIiLCJyZXR1cm5fdG8iOiIvIn0` },
      body: JSON.stringify({ search: "?code=test-code&state=test-state" }),
    });
    const response = await POST(req);
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error_code: "oidc_token_exchange_failed" });
  });
});
