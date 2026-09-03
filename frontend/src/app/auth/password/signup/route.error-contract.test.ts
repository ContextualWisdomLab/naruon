import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const { registerAccountWithPasswordMock, passwordRegistrationConfigMock } = vi.hoisted(() => ({
  registerAccountWithPasswordMock: vi.fn(),
  passwordRegistrationConfigMock: vi.fn(),
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

const ORIGINAL_ENV = { ...process.env };

function postRequest() {
  return new NextRequest("https://app.example.com/auth/password/signup", {
    method: "POST",
    body: JSON.stringify({
      email: "person@example.com",
      password: "correct horse battery staple 1!",
    }),
    headers: { origin: "https://app.example.com" },
  });
}

describe("password signup public error contract", () => {
  beforeEach(() => {
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER_URL", "https://login.example.com/realms/naruon/");
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "naruon-web");
    passwordRegistrationConfigMock.mockReset();
    passwordRegistrationConfigMock.mockReturnValue({
      baseUrl: new URL("https://idp.example.com"),
      token: "registration-token",
    });
    registerAccountWithPasswordMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    process.env = { ...ORIGINAL_ENV };
  });

  it("does not publish an unknown upstream 422 detail as a Naruon error code", async () => {
    const { AccountUnificationError } = await import("@/lib/account-unification-client");
    registerAccountWithPasswordMock.mockRejectedValue(
      new AccountUnificationError(
        "account_unification_rejected",
        422,
        "internal_policy_rule_changed",
      ),
    );

    const response = await POST(postRequest());

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_invalid",
    });
  });
});
