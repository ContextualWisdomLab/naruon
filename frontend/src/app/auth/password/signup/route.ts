import { NextRequest } from "next/server";

import {
  AccountUnificationError,
  passwordRegistrationConfig,
  registerAccountWithPassword,
} from "@/lib/account-unification-client";

import {
  errorResponse,
  exchangePasswordForSessionResponse,
  normalizeCredential,
  safeReturnTo,
  serverOidcConfig,
} from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const MAX_NAME_LENGTH = 100;

function normalizeOptionalName(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > MAX_NAME_LENGTH) return undefined;
  return trimmed;
}

function statusForAccountUnificationError(error: AccountUnificationError): {
  errorCode: string;
  status: number;
} {
  if (error.status === 409) {
    return { errorCode: "password_signup_email_taken", status: 409 };
  }
  if (error.status === 422) {
    return { errorCode: error.detail ?? "password_signup_invalid", status: 422 };
  }
  if (error.status === 429) {
    return { errorCode: "password_signup_rate_limited", status: 429 };
  }
  if (error.status === 503) {
    return { errorCode: "password_signup_unavailable", status: 503 };
  }
  return { errorCode: "password_signup_failed", status: 502 };
}

/**
 * naruon's own signup form calls this route directly — no redirect to, or
 * page rendered by, Keyverse/Keycloak. It creates the account with an
 * immediately usable password credential through Keyverse's scoped
 * account-unification password-registration endpoint, then logs the new
 * account straight in via the same Direct Access Grants exchange the login
 * route uses (`exchangePasswordForSessionResponse`), so signup ends with a
 * working session, not a second manual login step. See
 * docs/adr/0005-naruon-owned-password-login-form.md and
 * docs/adr/0015-naruon-password-credential-issuance.md (keyverse) for why
 * this exists and what it deliberately defers (email verification, CAPTCHA,
 * abuse hardening beyond a per-peer rate limit).
 */
export async function POST(request: NextRequest) {
  const oidcConfig = serverOidcConfig(request.nextUrl.origin);
  if (!oidcConfig) {
    return errorResponse("oidc_browser_configuration_missing", 503);
  }
  const registrationConfig = passwordRegistrationConfig();
  if (!registrationConfig) {
    return errorResponse("password_signup_unavailable", 503);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse("password_signup_request_invalid");
  }

  const parsed = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const email = normalizeCredential(parsed.email);
  const password = normalizeCredential(parsed.password);
  const returnTo = safeReturnTo(parsed.return_to);
  if (!email || !password) {
    return errorResponse("password_signup_credentials_invalid");
  }

  try {
    await registerAccountWithPassword(registrationConfig, {
      email_address: email,
      password,
      first_name: normalizeOptionalName(parsed.first_name),
      last_name: normalizeOptionalName(parsed.last_name),
    });
  } catch (error) {
    if (error instanceof AccountUnificationError) {
      const { errorCode, status } = statusForAccountUnificationError(error);
      return errorResponse(errorCode, status);
    }
    return errorResponse("password_signup_failed", 502);
  }

  // The account now has a usable password credential — reuse the login
  // exchange so the response the caller gets back already carries a signed
  // naruon session, not just a "go log in now" instruction.
  return exchangePasswordForSessionResponse(oidcConfig, email, password, returnTo);
}
