import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { POST } from "./route";

function request(body: BodyInit, origin?: string) {
  const headers = new Headers();
  if (origin) headers.set("origin", origin);
  return new NextRequest("https://app.example.com/auth/password/signup", {
    method: "POST",
    body,
    headers,
  });
}

describe("/auth/password/signup route", () => {
  it("fails closed without creating an account while the Keyverse contract is unavailable", async () => {
    const response = await POST(
      request(
        JSON.stringify({
          email: "person@example.com",
          password: "correct horse battery staple 1!",
          first_name: "New",
        }),
        "https://app.example.com",
      ),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_unavailable",
    });
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("does not parse credential bodies while the capability is unavailable", async () => {
    const response = await POST(request("{not-json", "https://app.example.com"));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error_code: "password_signup_unavailable",
    });
  });

  it("rejects a cross-site submission before capability evaluation", async () => {
    const response = await POST(
      request(
        JSON.stringify({ email: "person@example.com", password: "secret" }),
        "https://attacker.example",
      ),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error_code: "csrf_origin_rejected" });
  });

  it("rejects a submission with neither Origin nor Referer", async () => {
    const response = await POST(
      request(JSON.stringify({ email: "person@example.com", password: "secret" })),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error_code: "csrf_origin_rejected" });
  });
});
