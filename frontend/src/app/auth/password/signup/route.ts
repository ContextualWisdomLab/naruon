import { NextRequest } from "next/server";

import { sameOriginStateChangingRequest } from "@/lib/csrf-origin";

import { errorResponse } from "../../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

/**
 * Keep password signup fail-closed until Keyverse publishes the immutable
 * account-creation and authentication/session contract required by ADR-0005.
 * The current Keyverse owner lane has disabled its password-registration path
 * while the replacement design is unresolved, and Naruon must not recreate
 * identity authority or fall back to OAuth Resource Owner Password Credentials.
 *
 * Do not parse or forward submitted credentials while the capability is
 * unavailable. Same-origin rejection remains independent and precedes the
 * capability response.
 */
export async function POST(request: NextRequest) {
  if (!sameOriginStateChangingRequest(request)) {
    return errorResponse("csrf_origin_rejected", 403);
  }

  return errorResponse("password_signup_unavailable", 503);
}
