import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFetchBackedNodeRequest } from "@/test/fetch-backed-node-request";

const { backendDnsLookupMock, httpsRequestMock } = vi.hoisted(() => ({
  backendDnsLookupMock: vi.fn(),
  httpsRequestMock: vi.fn(),
}));

vi.mock("node:dns/promises", () => ({
  lookup: backendDnsLookupMock,
}));

vi.mock("node:https", () => ({
  request: httpsRequestMock,
}));

import { GET, POST, PUT } from "./route";

const ORIGINAL_ENV = { ...process.env };
const SIGNED_SESSION_TOKEN = "signed.session.token";

describe("/api runtime proxy route", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    process.env = { ...ORIGINAL_ENV };
    vi.stubEnv("BACKEND_INTERNAL_URL", "https://api.naruon.net");
    backendDnsLookupMock.mockReset();
    backendDnsLookupMock.mockResolvedValue([
      { address: "8.8.8.8", family: 4 },
    ]);
    httpsRequestMock.mockReset();
    httpsRequestMock.mockImplementation(createFetchBackedNodeRequest());
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
    expect(httpsRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agent: false,
        family: 4,
        hostname: "8.8.8.8",
        path: "/api/tasks?limit=1",
        servername: "api.naruon.net",
      }),
      expect.any(Function),
    );
  });

  it("rejects a backend hostname that resolves to the metadata network", async () => {
    backendDnsLookupMock.mockResolvedValue([
      { address: "169.254.169.254", family: 4 },
    ]);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const response = await GET(
      new NextRequest("https://frontend.naruon.net/api/tasks"),
      {
        params: Promise.resolve({ path: ["tasks"] }),
      },
    );

    expect(response.status).toBe(503);
    expect(backendDnsLookupMock).toHaveBeenCalledWith("api.naruon.net", {
      all: true,
      verbatim: true,
    });
    expect(fetchMock).not.toHaveBeenCalled();
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
  it.each([".", "..", "\u0000admin"])(
    "rejects path segment %j before URL normalization can escape the API prefix",
    async (segment) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const response = await POST(
        new NextRequest("https://frontend.naruon.net/api/placeholder", {
          method: "POST",
          headers: { Origin: "https://frontend.naruon.net" },
          body: "{}",
        }),
        { params: Promise.resolve({ path: [segment, "admin"] }) },
      );

      expect(response.status).toBe(400);
      await expect(response.json()).resolves.toMatchObject({
        error_code: "invalid_proxy_path",
      });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("fails closed when the backend configuration is not a bare trusted origin", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubEnv(
      "BACKEND_INTERNAL_URL",
      "https://api.naruon.net/untrusted/base?next=http://169.254.169.254",
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://frontend.naruon.net/api/tasks", {
        method: "POST",
        headers: { Origin: "https://frontend.naruon.net" },
        body: "{}",
      }),
      { params: Promise.resolve({ path: ["tasks"] }) },
    );

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith(
      "proxy_target_configuration_failed",
      { error_type: "Error" },
    );
  });

  it("returns secure no-store headers when the backend fetch fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("backend unavailable\r\nforged_event=true");
    }));

    const response = await GET(
      new NextRequest("https://frontend.naruon.net/api/tasks"),
      { params: Promise.resolve({ path: ["tasks"] }) },
    );

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(consoleError).toHaveBeenCalledWith("proxy_fetch_failed", {
      error_type: "Error",
    });
    expect(consoleError.mock.calls.flat().join(" ")).not.toContain("forged_event");
  });

  it("keeps encoded authority-like path input on the configured backend host", async () => {
    const fetchMock = vi.fn(async (input: URL | RequestInfo) =>
      Response.json({ target_url: String(input) }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("https://frontend.naruon.net/api/placeholder", {
        method: "POST",
        headers: { Origin: "https://frontend.naruon.net" },
        body: "{}",
      }),
      { params: Promise.resolve({ path: ["//169.254.169.254", "metadata"] }) },
    );

    await expect(response.json()).resolves.toEqual({
      target_url: "https://api.naruon.net/api/%2F%2F169.254.169.254/metadata",
    });
  });

  it("preserves a validated global IPv6 backend authority", async () => {
    vi.stubEnv(
      "BACKEND_INTERNAL_URL",
      "https://[2001:4860:4860::8888]:8443",
    );
    const fetchMock = vi.fn(async (input: URL | RequestInfo) =>
      Response.json({ target_url: String(input) }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("https://frontend.naruon.net/api/tasks"),
      { params: Promise.resolve({ path: ["tasks"] }) },
    );

    await expect(response.json()).resolves.toEqual({
      target_url: "https://[2001:4860:4860::8888]:8443/api/tasks",
    });
  });
});
