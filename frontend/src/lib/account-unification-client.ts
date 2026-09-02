import { isPrivateOrLoopbackHostname, normalizeHostname } from "@/lib/host-policy";

/**
 * Server-side client for Keyverse's account-unification service — currently
 * only its scoped password-registration endpoint
 * (`POST /registration/accounts/password`), called from naruon's own signup
 * route so no Keycloak page is ever shown (see
 * docs/adr/0015-naruon-password-credential-issuance.md).
 *
 * ponytail: unlike oidc-token-client.ts / backend-request.ts, this uses plain
 * `fetch` rather than DNS-pinned node:https — account-unification is an
 * operator-deployed internal service naruon already trusts the same way it
 * trusts its own backend, not a boundary this slice needed to harden further.
 * Upgrade to the shared DNS-pinning machinery if that trust boundary ever
 * changes (e.g. account-unification becomes reachable across a less-trusted
 * network).
 */

const REQUEST_TIMEOUT_MS = 15_000;

export class AccountUnificationError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: string | null = null,
  ) {
    super(message);
    this.name = "AccountUnificationError";
  }
}

function parseAccountUnificationUrl(raw: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(
      `ACCOUNT_UNIFICATION_INTERNAL_URL is not a valid URL: ${JSON.stringify(raw)}`,
    );
  }
  const hostname = normalizeHostname(parsed);
  const isDevLoopback =
    process.env.NODE_ENV !== "production" &&
    parsed.protocol === "http:" &&
    (hostname === "127.0.0.1" || hostname === "localhost");
  if (isDevLoopback) return parsed;
  if (parsed.protocol !== "https:") {
    throw new Error(
      `ACCOUNT_UNIFICATION_INTERNAL_URL must use https:// in production, got ${parsed.protocol}//`,
    );
  }
  if (!hostname) {
    throw new Error("ACCOUNT_UNIFICATION_INTERNAL_URL must include a hostname");
  }
  if (isPrivateOrLoopbackHostname(parsed)) {
    throw new Error(
      `ACCOUNT_UNIFICATION_INTERNAL_URL host ${hostname} is in a private/loopback/link-local range`,
    );
  }
  return parsed;
}

/**
 * Returns `null` when the deployment has not configured naruon-owned
 * password signup — callers must fail closed (503), never open, exactly
 * like Keyverse's own registration surfaces do when unconfigured.
 */
export function passwordRegistrationConfig(): { baseUrl: URL; token: string } | null {
  const rawUrl = process.env.ACCOUNT_UNIFICATION_INTERNAL_URL?.trim();
  const token = process.env.ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN?.trim();
  if (!rawUrl || !token) return null;
  return { baseUrl: parseAccountUnificationUrl(rawUrl), token };
}

export interface PasswordRegistrationAccount {
  account_id: string;
  email_address: string;
}

/**
 * Calls account-unification's scoped password-registration endpoint.
 * Never logs the password; only a fixed reason/status surfaces on failure.
 */
export async function registerAccountWithPassword(
  config: { baseUrl: URL; token: string },
  body: { email_address: string; password: string; first_name?: string | null; last_name?: string | null },
): Promise<PasswordRegistrationAccount> {
  const target = new URL("/registration/accounts/password", config.baseUrl);
  let response: Response;
  try {
    response = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.token}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    throw new AccountUnificationError("account_unification_unreachable", 502);
  }
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    const detail =
      parsed && typeof parsed === "object" && typeof (parsed as { detail?: unknown }).detail === "string"
        ? (parsed as { detail: string }).detail
        : null;
    throw new AccountUnificationError("account_unification_rejected", response.status, detail);
  }
  const result = parsed as Partial<PasswordRegistrationAccount> | null;
  if (!result || typeof result.account_id !== "string" || typeof result.email_address !== "string") {
    throw new AccountUnificationError("account_unification_response_invalid", 502, null);
  }
  return { account_id: result.account_id, email_address: result.email_address };
}
