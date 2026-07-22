import { NextRequest, NextResponse } from "next/server";

import { backendApiBaseUrl } from "@/lib/backend-url";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
};

// Signup happens before any session exists, so this is a plain anonymous
// relay: the browser talks same-origin, the server forwards to the backend's
// public /api/auth/register, and no cookie or bearer material is involved.
export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error_code: "invalid_registration_request" },
      { status: 400, headers: NO_STORE_HEADERS },
    );
  }

  const target = backendApiBaseUrl();
  target.pathname = "/api/auth/register";
  target.search = "";

  try {
    const backendResponse = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const payload = await backendResponse.json().catch(() => ({}));
    return NextResponse.json(payload, {
      status: backendResponse.status,
      headers: NO_STORE_HEADERS,
    });
  } catch {
    return NextResponse.json(
      { detail: { error_code: "registration_unavailable" } },
      { status: 503, headers: NO_STORE_HEADERS },
    );
  }
}
