import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

const ORIGINAL_ENV = { ...process.env };

describe("/auth/oidc-config route", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.NEXT_PUBLIC_OIDC_ISSUER_URL;
    delete process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
    delete process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI;
    delete process.env.NEXT_PUBLIC_OIDC_SCOPE;
    delete process.env.NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT;
    delete process.env.NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    process.env = { ...ORIGINAL_ENV };
  });

  it("reports the browser OIDC identity from runtime env without a rebuild", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://login.example.com/realms/naruon/");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "naruon-web");
    vi.stubEnv("NEXT_PUBLIC_OIDC_SCOPE", "openid");

    const response = await GET(new NextRequest("https://app.example.com/auth/oidc-config"));

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const body = await response.json();
    expect(body).toEqual({
      configured: true,
      issuer_url: "https://login.example.com/realms/naruon",
      client_id: "naruon-web",
      redirect_uri: "https://app.example.com/auth/callback",
      scope: "openid",
      authorization_endpoint:
        "https://login.example.com/realms/naruon/protocol/openid-connect/auth",
      end_session_endpoint:
        "https://login.example.com/realms/naruon/protocol/openid-connect/logout",
    });
  });

  it("never exposes the token endpoint, whose override may be container-internal", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://login.example.com/realms/naruon");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "naruon-web");
    vi.stubEnv("NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT", "http://keyverse:8080/realms/cwl/token");

    const response = await GET(new NextRequest("https://app.example.com/auth/oidc-config"));

    const body = (await response.json()) as Record<string, unknown>;
    expect(body.configured).toBe(true);
    expect(JSON.stringify(body)).not.toContain("keyverse:8080");
    expect(body).not.toHaveProperty("token_endpoint");
  });

  it("reports configured=false instead of an error when the runtime env is empty", async () => {
    const response = await GET(new NextRequest("https://app.example.com/auth/oidc-config"));

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({ configured: false });
  });
});
