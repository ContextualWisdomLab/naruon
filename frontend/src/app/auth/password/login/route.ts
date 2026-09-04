import { NextRequest } from "next/server";

import { sameOriginStateChangingRequest } from "@/lib/csrf-origin";

import { errorResponse } from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

/**
 * Keep the Naruon-owned password-login surface fail-closed until Keyverse
 * publishes an immutable, standards-compliant headless authentication/session
 * contract. RFC 9700 §2.4 and RFC 10017 §7.3 prohibit the Resource Owner
 * Password Credentials grant, so this route must not parse a password or
 * forward one to an OAuth token endpoint as a substitute for that contract.
 *
 * The same-origin check remains first so cross-site state-changing requests are
 * rejected independently of capability availability. The existing
 * Authorization Code + PKCE Keyverse SSO path is unaffected.
 */
export async function POST(request: NextRequest) {
  if (!sameOriginStateChangingRequest(request)) {
    return errorResponse("csrf_origin_rejected", 403);
  }

  return errorResponse("password_login_unavailable", 503);
}
