import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST, PUT } from "./route";

const ORIGINAL_ENV = { ...process.env };
const SIGNED_SESSION_TOKEN = "signed.session.token";

describe("/api runtime proxy route", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    process.env = { ...ORIGINAL_ENV };
  });

  it("proxies signed requests without forwarding public identity headers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: URL | RequestInfo, init?: RequestInit) => {
        const headers = init?.headers as Headers;
        return Response.json({
          target_url: String(input),
          auth_header: headers.get("authorization"),
          cookie_header: headers.get("cookie"),
          user_header: headers.get("x-user-id"),
          request_body: await new Response(init?.body).text(),
        });
      }),
    );

    const request = new NextRequest(
      "https://frontend.naruon.net/api/tasks?limit=1",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer attacker-controlled-token",
          Cookie: `naruon_session=${SIGNED_SESSION_TOKEN}`,
          Origin: "https://frontend.naruon.net",
          "Content-Type": "application/json",
          "X-User-Id": "public-user-id",
        },
        body: JSON.stringify({ state: "open" }),
      },
    );

    const response = await POST(request, {
      params: Promise.resolve({ path: ["tasks"] }),
    });

    await expect(response.json()).resolves.toEqual({
      target_url: "https://api.naruon.net/api/tasks?limit=1",
      auth_header: "Bearer signed.session.token",
      cookie_header: null,
      user_header: null,
      request_body: '{"state":"open"}',
    });
  });

  it("rejects unsupported query parameters before proxying", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest(
      "https://frontend.naruon.net/api/tasks?filename=../../../../etc/passwd",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${SIGNED_SESSION_TOKEN}`,
          Origin: "https://frontend.naruon.net",
        },
        body: "{}",
      },
    );

    const response = await POST(request, {
      params: Promise.resolve({ path: ["tasks"] }),
    });

    expect(response.status).toBe(400);
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    await expect(response.json()).resolves.toEqual({
      error_code: "invalid_proxy_query",
      message: "Unsupported query parameter: filename",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects cross-site state-changing requests before proxying", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest(
      "https://frontend.naruon.net/api/accounts/config",
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${SIGNED_SESSION_TOKEN}`,
          Origin: "https://evil.example",
        },
        body: "{}",
      },
    );

    const response = await PUT(request, {
      params: Promise.resolve({ path: ["accounts", "config"] }),
    });

    expect(response.status).toBe(403);
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    await expect(response.json()).resolves.toEqual({
      error_code: "csrf_origin_rejected",
      message: "Cross-site state-changing API requests are not allowed",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepts browser same-origin state changes when the runtime URL is internal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: URL | RequestInfo, init?: RequestInit) => {
        const headers = init?.headers as Headers;
        return Response.json({
          target_url: String(input),
          auth_header: headers.get("authorization"),
          request_body: await new Response(init?.body).text(),
        });
      }),
    );

    const request = new NextRequest(
      "http://internal-frontend:3000/api/search",
      {
        method: "POST",
        headers: {
          Cookie: `naruon_session=${SIGNED_SESSION_TOKEN}`,
          Host: "127.0.0.1:3000",
          Origin: "http://127.0.0.1:3000",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: "일정 충돌 일정 조율 회의 후보", limit: 3 }),
      },
    );

    const response = await POST(request, {
      params: Promise.resolve({ path: ["search"] }),
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      target_url: "https://api.naruon.net/api/search",
      auth_header: "Bearer signed.session.token",
      request_body: '{"query":"일정 충돌 일정 조율 회의 후보","limit":3}',
    });
  });

  it("rejects cross-site fetch metadata before proxying", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest(
      "https://frontend.naruon.net/api/accounts/config",
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${SIGNED_SESSION_TOKEN}`,
          "Sec-Fetch-Site": "cross-site",
        },
        body: "{}",
      },
    );

    const response = await PUT(request, {
      params: Promise.resolve({ path: ["accounts", "config"] }),
    });

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error_code: "csrf_origin_rejected",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("re-encodes allowed query parameters instead of copying the raw search string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: URL | RequestInfo) =>
        Response.json({ target_url: String(input) }),
      ),
    );

    const request = new NextRequest(
      "https://frontend.naruon.net/api/ontology/relationships?source_message_id=%3Cabc@example.com%3E&source_thread_id=thread/one",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${SIGNED_SESSION_TOKEN}`,
          Origin: "https://frontend.naruon.net",
        },
        body: "{}",
      },
    );

    const response = await POST(request, {
      params: Promise.resolve({ path: ["ontology", "relationships"] }),
    });

    await expect(response.json()).resolves.toEqual({
      target_url:
        "https://api.naruon.net/api/ontology/relationships?source_message_id=%3Cabc%40example.com%3E&source_thread_id=thread%2Fone",
    });
  });

  it("rejects state-changing requests when both Origin and Referer are absent", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest(
      "https://frontend.naruon.net/api/accounts/config",
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${SIGNED_SESSION_TOKEN}`,
          // Both Origin and Referer are intentionally omitted
        },
        body: "{}",
      },
    );

    const response = await PUT(request, {
      params: Promise.resolve({ path: ["accounts", "config"] }),
    });

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error_code: "csrf_origin_rejected",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
