import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

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
  });

  afterEach(() => {
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
    expect(fetchMock).toHaveBeenCalledTimes(2);
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
});
