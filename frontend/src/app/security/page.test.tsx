/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <a href={href} {...props}>{children}</a>,
}));

vi.mock("lucide-react", () => ({
  AlertOctagon: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Database: () => <svg aria-hidden="true" />,
  Lock: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  ScrollText: () => <svg aria-hidden="true" />,
  Share2: () => <svg aria-hidden="true" />,
  ShieldCheck: () => <svg aria-hidden="true" />,
  XCircle: () => <svg aria-hidden="true" />,
}));

import SecurityPage from "./page";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => body,
  };
}

const securitySurface = {
  scope_kind: "organization",
  viewer: {
    role: "tenant_admin",
    scope_kind: "organization",
  },
  sources: [
    {
      source_type: "webdav_repository",
      source_label: "WebDAV repository",
      scope_kind: "organization",
      capabilities: ["read", "write", "etag"],
      writeback_enabled: true,
      last_observed_at: "2026-05-28T04:00:00Z",
      policy_decision: {
        resource_label: "WebDAV repository",
        resource_type: "webdav_repository",
        allowed: true,
        reason: "allowed",
        evidence_label: "webdav_source_evidence",
      },
    },
  ],
  connector_events: [
    {
      state_code: "heartbeat",
      evidence_label: "connector_observation_evidence",
      observed_at: "2026-05-28T04:00:00Z",
    },
  ],
  durable_audit_events: [
    {
      actor_role: "tenant_admin",
      scope_kind: "organization",
      event_action: "update",
      resource_type: "llm_provider",
      evidence_label: "server_audit_evidence",
      observed_at: "2026-05-28T04:02:00Z",
    },
  ],
  policy_decisions: [
    {
      resource_label: "WebDAV repository",
      resource_type: "webdav_repository",
      allowed: true,
      reason: "allowed",
      evidence_label: "webdav_source_evidence",
    },
    {
      resource_label: "Cross-organization provider secret",
      resource_type: "provider_secret",
      allowed: false,
      reason: "organization_denied",
      evidence_label: "policy_engine_evidence",
    },
  ],
  external_share_reviews: [
    {
      source_type: "webdav_repository",
      review_label: "WebDAV repository writeback boundary",
      exposure_level: "external_writeback",
      decision_reason: "allowed",
    },
  ],
  policy_order: [
    {
      display_name: "Signed session identity",
      evidence_label: "signed_session_evidence",
    },
    {
      display_name: "RBAC allow after ABAC denies",
      evidence_label: "policy_engine_evidence",
    },
  ],
};

function mockSecurityFetch(surface: typeof securitySurface = securitySurface) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    void init;
    if (String(input) === "/api/security/access-surface") {
      return jsonResponse(surface);
    }
    throw new Error(`Unhandled fetch: ${String(input)}`);
  });
}

async function renderSecurityPage() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<SecurityPage />);
    await Promise.resolve();
    await Promise.resolve();
  });
  return { container, root };
}

describe("SecurityPage", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("fetches signed security governance and renders source-backed access data", async () => {
    const fetchMock = mockSecurityFetch();
    vi.stubGlobal("fetch", fetchMock);

    ({ container, root } = await renderSecurityPage());

    expect(container.querySelector("h1")?.textContent).toContain("보안과 관리자");
    expect(container.textContent).toContain("원본 연결 RBAC / ABAC");
    expect(container.textContent).toContain("WebDAV 저장소 1");
    expect(container.textContent).toContain("서버에서 검증됨");
    expect(container.textContent).toContain("쓰기 의도 가능");
    expect(container.textContent).not.toContain("webdav_src_primary");
    expect(container.textContent).not.toContain("files.acme.example");
    expect(container.textContent).not.toContain("provider_write_executed=false");
    expect(container.textContent).not.toContain("곧 제공됩니다");
    expect(container.textContent).not.toContain("비정상 로그인 시도");

    const accessCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/security/access-surface");
    expect(accessCall).toBeDefined();
    const [, init] = accessCall ?? [];
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
  });

  it("renders audit sharing and policy tabs without inert placeholders", async () => {
    vi.stubGlobal("fetch", mockSecurityFetch());
    ({ container, root } = await renderSecurityPage());

    for (const tabName of ["감사 로그", "외부 공유", "정책"]) {
      const tab = Array.from(container.querySelectorAll("button")).find((button) =>
        button.textContent?.includes(tabName),
      );
      expect(tab).toBeDefined();
      await act(async () => {
        tab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      expect(container.textContent).not.toContain("곧 제공됩니다");
      if (tabName === "감사 로그") {
        expect(container.textContent).toContain("지속 감사 근거");
        expect(container.textContent).toContain("설정 변경 / LLM 제공자");
        expect(container.textContent).toContain("서버 감사 로그");
        expect(container.textContent).toContain("Connector 근거");
        expect(container.textContent).not.toContain("audit_evt_provider_update");
        expect(container.textContent).not.toContain("llm_provider:provider_primary");
        expect(container.textContent).not.toContain("connector_evt_heartbeat");
        expect(container.textContent).not.toContain("outbound connector heartbeat");
        expect(container.textContent).not.toContain("workspace-org-acme");
      }
      if (tabName === "외부 공유") {
        expect(container.textContent).toContain("WebDAV 저장소 쓰기 경계");
        expect(container.textContent).toContain("외부 쓰기 검토");
        expect(container.textContent).toContain("외부 쓰기 실행 안 함");
        expect(container.textContent).not.toContain("webdav_src_primary");
        expect(container.textContent).not.toContain("external_writeback");
        expect(container.textContent).not.toContain("provider_write_executed");
      }
      if (tabName === "정책") {
        expect(container.textContent).toContain("차단 우선 정책 순서");
        expect(container.textContent).toContain("ABAC 차단 후 RBAC 허용");
        expect(container.textContent).toContain("교차 조직 제공자 secret");
        expect(container.textContent).not.toContain("Cross-organization provider secret");
        expect(container.textContent).not.toContain("services.access_policy.evaluate_access");
      }
    }
  });

  it("keeps sparse security sections visible and source-backed instead of blank", async () => {
    const sparseSurface = {
      ...securitySurface,
      policy_decisions: [],
      policy_order: [],
      external_share_reviews: [
        ...securitySurface.external_share_reviews,
        {
          source_type: "caldav_source",
          review_label: "Calendar writeback boundary",
          exposure_level: "external_writeback",
          decision_reason: "consent_denied",
        },
      ],
    };
    vi.stubGlobal("fetch", mockSecurityFetch(sparseSurface));
    ({ container, root } = await renderSecurityPage());

    const dashboardTab = Array.from(container.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("보안 대시보드"),
    );
    expect(dashboardTab).toBeDefined();
    await act(async () => {
      dashboardTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("외부 쓰기");
    expect(container.textContent).toContain("2건");
    expect(container.textContent).toContain("현재 signed-session 스코프에서 확인된 접근 판정이 없습니다.");
    expect(container.querySelector('[role="status"]')?.textContent).toContain("접근 판정");

    const policyTab = Array.from(container.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("정책"),
    );
    expect(policyTab).toBeDefined();
    await act(async () => {
      policyTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("현재 signed-session 스코프에서 확인된 정책 판정 순서가 없습니다.");
    expect(container.textContent).toContain("현재 signed-session 스코프에서 확인된 정책 판정 샘플이 없습니다.");
    expect(container.textContent).not.toContain("곧 제공됩니다");
  });
});
