import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

function oidcStateCookie(state: string, verifier: string, returnTo: string) {
  const payload = Buffer.from(
    JSON.stringify({ state, verifier, return_to: returnTo }),
  ).toString("base64url");
  return `naruon_oidc_pkce=${payload}`;
}

describe("OIDC malformed token endpoint configuration", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("fails closed without leaking an expected configuration warning", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://auth.example.com");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "test-client");
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_REDIRECT_URI",
      "https://app.example.com/auth/oidc/callback",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT",
      "https://auth.example.com/auth",
    );
    vi.stubEnv(
      "NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT",
      "https://auth.example.com/token/%2",
    );
    const warnMock = vi.spyOn(console, "warn").mockImplementation(() => {});

    const response = await POST(
      new NextRequest("https://app.example.com/auth/oidc/callback", {
        method: "POST",
        headers: {
          Cookie: oidcStateCookie("test-state", "test-verifier", "/"),
        },
        body: JSON.stringify({ search: "?code=test-code&state=test-state" }),
      }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error_code: "oidc_token_exchange_failed",
    });
    expect(warnMock).toHaveBeenCalledWith("oidc_token_exchange_failed", {
      reason: "configuration_rejected",
    });
  });
});
