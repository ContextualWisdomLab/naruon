import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("/auth/register/submit route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("relays the anonymous signup to the backend without credentials", async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ email_address: "new.user@example.com" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const response = await POST(
      new NextRequest("https://app.example.com/auth/register/submit", {
        method: "POST",
        body: JSON.stringify({
          email_address: "new.user@example.com",
          initial_password: "bootstrap-pass-1",
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [target, init] = fetchSpy.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(target)).toContain("/api/auth/register");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(await response.json()).toEqual({
      email_address: "new.user@example.com",
    });
  });

  it("passes backend error statuses through verbatim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: { error_code: "email_already_registered" } }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const response = await POST(
      new NextRequest("https://app.example.com/auth/register/submit", {
        method: "POST",
        body: JSON.stringify({
          email_address: "dup@example.com",
          initial_password: "bootstrap-pass-1",
        }),
      }),
    );

    expect(response.status).toBe(409);
    expect((await response.json()).detail.error_code).toBe(
      "email_already_registered",
    );
  });

  it("maps a backend outage to registration_unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );

    const response = await POST(
      new NextRequest("https://app.example.com/auth/register/submit", {
        method: "POST",
        body: JSON.stringify({
          email_address: "new.user@example.com",
          initial_password: "bootstrap-pass-1",
        }),
      }),
    );

    expect(response.status).toBe(503);
    expect((await response.json()).detail.error_code).toBe(
      "registration_unavailable",
    );
  });

  it("rejects a non-JSON body", async () => {
    const response = await POST(
      new NextRequest("https://app.example.com/auth/register/submit", {
        method: "POST",
        body: "not json",
      }),
    );

    expect(response.status).toBe(400);
  });
});
