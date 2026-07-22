import { NextRequest, NextResponse } from "next/server";

import { OIDC_NO_STORE_HEADERS, serverOidcConfig } from "../oidc/shared";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function GET(request: NextRequest) {
  const config = serverOidcConfig(request.nextUrl.origin);
  if (!config) {
    return NextResponse.json(
      { configured: false },
      { headers: OIDC_NO_STORE_HEADERS },
    );
  }

  // token_endpoint is intentionally omitted: the code exchange runs in the
  // server routes, and its override may point at a container-internal address
  // that must not leak to browsers.
  return NextResponse.json(
    {
      configured: true,
      issuer_url: config.issuerUrl,
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      scope: config.scope,
      authorization_endpoint: config.authorizationEndpoint,
      end_session_endpoint: config.endSessionEndpoint,
    },
    { headers: OIDC_NO_STORE_HEADERS },
  );
}
