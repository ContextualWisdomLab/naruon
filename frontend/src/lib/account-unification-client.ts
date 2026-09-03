import { request as httpRequest, type IncomingMessage, type RequestOptions } from "node:http";
import { request as httpsRequest } from "node:https";
import { isIP } from "node:net";

import { isPrivateOrLoopbackHostname, normalizeHostname } from "@/lib/host-policy";
import {
  createPinnedOidcLookup as createPinnedServiceLookup,
  resolveOidcTokenAddresses as resolvePinnedServiceAddresses,
} from "@/lib/oidc-token-client";

/**
 * Server-side client for Keyverse's account-unification service — currently
 * only its scoped password-registration endpoint
 * (`POST /registration/accounts/password`), called from naruon's own signup
 * route so no Keycloak page is ever shown (see
 * docs/adr/0015-naruon-password-credential-issuance.md).
 *
 * The registration bearer token and submitted password cross this boundary,
 * so hostname validation alone is insufficient: the request resolves the
 * destination once, rejects any non-global DNS answer (except exact local
 * development loopback), and pins the socket lookup to those validated
 * addresses. Redirects are not followed.
 */

const REQUEST_TIMEOUT_MS = 15_000;
const RESPONSE_MAX_BYTES = 64 * 1024;

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

function responseHeaders(response: IncomingMessage): Headers {
  const headers = new Headers();
  for (let index = 0; index < response.rawHeaders.length; index += 2) {
    const name = response.rawHeaders[index];
    const value = response.rawHeaders[index + 1];
    if (name !== undefined && value !== undefined) headers.append(name, value);
  }
  return headers;
}

function collectPinnedResponse(
  target: URL,
  options: RequestOptions,
  encodedBody: string,
): Promise<Response> {
  const requester = target.protocol === "http:" ? httpRequest : httpsRequest;
  return new Promise((resolve, reject) => {
    const request = requester(options, (response) => {
      const status = response.statusCode ?? 0;
      if (status < 200 || status > 599) {
        response.destroy();
        reject(new Error("Account-unification returned an invalid HTTP status"));
        return;
      }

      const chunks: Buffer[] = [];
      let receivedBytes = 0;
      let settled = false;
      const rejectOnce = (error: Error) => {
        if (settled) return;
        settled = true;
        reject(error);
      };
      response.on("data", (chunk: Buffer | string) => {
        if (settled) return;
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        receivedBytes += buffer.length;
        if (receivedBytes > RESPONSE_MAX_BYTES) {
          const error = new Error("Account-unification response exceeded the size limit");
          request.destroy(error);
          rejectOnce(error);
          return;
        }
        chunks.push(buffer);
      });
      response.on("end", () => {
        if (settled) return;
        settled = true;
        resolve(
          new Response(Buffer.concat(chunks), {
            headers: responseHeaders(response),
            status,
            statusText: response.statusMessage ?? "",
          }),
        );
      });
      response.on("error", (error) => rejectOnce(error));
    });
    request.once("error", (error) => reject(error));
    request.end(encodedBody);
  });
}

async function postPinnedRegistration(target: URL, token: string, encodedBody: string): Promise<Response> {
  const addresses = await resolvePinnedServiceAddresses(target);
  const hostname = normalizeHostname(target);
  const options: RequestOptions = {
    method: "POST",
    agent: false,
    protocol: target.protocol,
    hostname,
    port: target.port || undefined,
    path: `${target.pathname}${target.search}`,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "Content-Length": String(Buffer.byteLength(encodedBody)),
      Host: target.host,
    },
    lookup: createPinnedServiceLookup(hostname, addresses),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  };
  if (target.protocol === "https:" && isIP(hostname) === 0) {
    options.servername = hostname;
  }
  return collectPinnedResponse(target, options, encodedBody);
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
    response = await postPinnedRegistration(target, config.token, JSON.stringify(body));
  } catch {
    throw new AccountUnificationError("account_unification_unreachable", 502);
  }
  if (response.status >= 300 && response.status < 400) {
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
