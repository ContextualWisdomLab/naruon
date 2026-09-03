import { NextRequest } from "next/server";

import {
  AccountUnificationError,
  passwordRegistrationConfig,
  registerAccountWithPassword,
} from "@/lib/account-unification-client";
import { sameOriginStateChangingRequest } from "@/lib/csrf-origin";

import {
  errorResponse,
  exchangePasswordForSessionResponse,
  normalizeCredential,
  readBoundedJson,
  RequestBodyTooLargeError,
  safeReturnTo,
  serverOidcConfig,
} from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const MAX_NAME_LENGTH = 100;

/**
 * `undefined` means "not supplied" (a genuinely optional field); any other
 * value must be a valid name or the request is rejected outright. An
 * over-length name must never be silently dropped -- `JSON.stringify` omits
 * an `undefined` field, so a caller providing a too-long name would
 * otherwise have it quietly vanish from the registration request instead of
 * being told to fix it.
 */
type NameValidation = { ok: true; value: string | undefined } | { ok: false };

function validateOptionalName(value: unknown): NameValidation {
  if (value === undefined || value === null || value === "") return { ok: true, value: undefined };
  if (typeof value !== "string") return { ok: false };
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > MAX_NAME_LENGTH) return { ok: false };
  return { ok: true, value: trimmed };
}

function statusForAccountUnificationError(error: AccountUnificationError): {
  errorCode: string;
  status: number;
} {
  if (error.status === 409) {
    return { errorCode: "password_signup_email_taken", status: 409 };
  }
  if (error.status === 422) {
    // The Keyverse/account-unification response body is an upstream contract,
    // not Naruon's public error namespace. Keep the product API stable and do
    // not let new validation strings or implementation details escape merely
    // because the upstream chose HTTP 422.
    return { errorCode: "password_signup_invalid", status: 422 };
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
  if (!sameOriginStateChangingRequest(request)) {
    return errorResponse("csrf_origin_rejected", 403);
  }

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
    body = await readBoundedJson(request);
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return errorResponse("password_signup_request_too_large", 413);
    }
    return errorResponse("password_signup_request_invalid");
  }

  const parsed = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const email = normalizeCredential(parsed.email);
  const password = normalizeCredential(parsed.password);
  const returnTo = safeReturnTo(parsed.return_to);
  if (!email || !password) {
    return errorResponse("password_signup_credentials_invalid");
  }
  const firstName = validateOptionalName(parsed.first_name);
  const lastName = validateOptionalName(parsed.last_name);
  if (!firstName.ok || !lastName.ok) {
    return errorResponse("password_signup_name_invalid");
  }

  try {
    await registerAccountWithPassword(registrationConfig, {
      email_address: email,
      password,
      first_name: firstName.value,
      last_name: lastName.value,
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
