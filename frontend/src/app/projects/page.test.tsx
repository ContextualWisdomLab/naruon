/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <a href={href} {...props}>{children}</a>,
}));

vi.mock("lucide-react", () => ({
  CalendarDays: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Clock: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  FolderOpen: () => <svg aria-hidden="true" />,
  GitBranch: () => <svg aria-hidden="true" />,
  ListChecks: () => <svg aria-hidden="true" />,
  Network: () => <svg aria-hidden="true" />,
  Search: () => <svg aria-hidden="true" />,
  User: () => <svg aria-hidden="true" />,
}));

import ProjectsPage from "./page";

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return Promise.resolve({
    ok,
    status,
    statusText: ok ? "OK" : "Server Error",
    json: () => Promise.resolve(body),
  } as Response);
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("ProjectsPage", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("loads project folders and ticket tasks through signed APIs", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBeNull();
      expect(headers.get("X-User-Id")).toBeNull();
      expect(headers.get("X-Organization-Id")).toBeNull();

      const path = String(input);
      if (path === "/auth/session") {
        return jsonResponse({
          authenticated: true,
          claims: {
            userId: "alice",
            organizationId: "org-acme",
            workspaceId: "workspace-org-acme",
          },
        });
      }
      if (path === "/api/webdav/folders") {
        return jsonResponse([
          {
            folder_uid: "webdav_folder_roadmap",
            project_name: "Naruon Roadmap 2026",
            webdav_path: "/Projects/Naruon_Roadmap_2026",
            owner_user_id: "alice",
            organization_id: "org-acme",
          },
          {
            folder_uid: "webdav_folder_rival",
            project_name: "Rival Project",
            webdav_path: "/Projects/Rival_Project",
            owner_user_id: "mallory",
            organization_id: "org-rival",
          },
        ]);
      }
      if (path === "/api/tasks") {
        return jsonResponse([
          {
            id: "task-q2-owner",
            title: "리소스 배정 검토 회의",
            status: "blocked",
            priority: "urgent",
            source_type: "email",
            source_email_id: "<q2@example.com>",
            related_thread_id: "thread-q2",
            created_at: "2026-05-19T00:00:00Z",
            updated_at: "2026-05-21T00:00:00Z",
          },
          {
            id: "task-webdav-evidence",
            title: "첨부파일 WebDAV 폴더 정리",
            status: "done",
            priority: "low",
            source_type: "webdav",
            source_email_id: "<q2@example.com>",
            related_thread_id: "thread-q2",
            created_at: "2026-05-19T00:00:00Z",
            updated_at: "2026-05-24T00:00:00Z",
          },
        ]);
      }
      if (path === "/api/projects/candidates") {
        return jsonResponse({ candidates: [] });
      }
      return jsonResponse({}, false, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<ProjectsPage />);
    });
    await flushAsyncWork();

    expect(fetchMock).toHaveBeenCalledWith("/api/webdav/folders", expect.objectContaining({ headers: expect.any(Object) }));
    expect(fetchMock).toHaveBeenCalledWith("/api/tasks", expect.objectContaining({ headers: expect.any(Object) }));
    expect(container.textContent).toContain("Naruon Roadmap 2026");
    expect(container.textContent).not.toContain("Rival Project");
    expect(container.textContent).not.toContain("webdav_folder_roadmap");
    expect(container.textContent).not.toContain("/Projects/Naruon_Roadmap_2026");
    expect(container.textContent).toContain("외부 저장소 쓰기는 별도 승인 전까지 실행하지 않습니다");
    expect(container.textContent).toContain("WebDAV 폴더 근거");
    expect(container.textContent).toContain("리소스 배정 검토 회의");
    expect(container.textContent).toContain("스레드 근거 연결됨");
    expect(container.textContent).not.toContain("thread-q2");
    expect(container.textContent).not.toContain("<q2@example.com>");
    expect(container.textContent).toContain("프로젝트 액션");
    expect(container.textContent).toContain("새 프로젝트");
    expect(container.textContent).toContain("마일스톤 추가");
    expect(container.textContent).toContain("의사결정 추가");
    expect(container.textContent).toContain("관련 문서/메일 연결");
    expect(container.textContent).not.toContain("Naruon 2.0 런칭");
  });

  it("renders the semantic project graph command center with paragraph citations", async () => {
    const citation = {
      content_segment_uid: "segment-alpha-1",
      source_kind: "email_body",
      source_record_uid: "<alpha@example.com>",
      heading_path: "Project kickoff",
      segment_path: "/document[1]/paragraph[1]",
      ordinal_index: 1,
      safe_text_excerpt: "결제 화면은 카드 승인 실패 시 재시도 안내를 반드시 보여줘야 합니다.",
    };
    const candidate = {
      candidate_uid: "project_candidate:alpha",
      project_uid: "project_candidate:alpha",
      title: "Project: Alpha Checkout",
      status_code: "needs_review",
      score: 0.87,
      object_count: 6,
      requirement_count: 1,
      issue_count: 1,
      milestone_count: 1,
      deliverable_count: 1,
      participant_count: 1,
      source_segment_count: 1,
      representative_object_uids: ["requirement:alpha-payment-retry"],
      citation_bundle: [citation],
      updated_at: "2026-07-02T00:00:00Z",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/auth/session") {
        return jsonResponse({
          authenticated: true,
          claims: {
            userId: "alice",
            organizationId: "org-acme",
            workspaceId: "workspace-org-acme",
          },
        });
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/tasks") return jsonResponse([]);
      if (path === "/api/projects/candidates") {
        return jsonResponse({ candidates: [candidate] });
      }
      if (path === "/api/projects/project_candidate%3Aalpha/traceability") {
        return jsonResponse({
          project_uid: "project_candidate:alpha",
          candidate,
          objects: [
            {
              object_uid: "requirement:alpha-payment-retry",
              object_type: "requirement",
              title: "카드 승인 실패 재시도 안내",
              summary: "결제 화면은 승인 실패 사용자가 다시 시도할 수 있는 안내를 제공해야 합니다.",
              status_code: "needs_review",
              confidence: 0.92,
              source_segment_uids: ["segment-alpha-1"],
              citation_bundle: [citation],
              attributes: {},
            },
            {
              object_uid: "issue:alpha-pg-timeout",
              object_type: "issue",
              title: "PG timeout risk",
              summary: "PG 응답 지연 시 결제 재시도 UX가 필요합니다.",
              status_code: "open",
              confidence: 0.81,
              source_segment_uids: ["segment-alpha-1"],
              citation_bundle: [citation],
              attributes: {},
            },
          ],
          edges: [
            {
              edge_uid: "edge:segment-alpha-1:requirement:alpha-payment-retry",
              source_uid: "segment-alpha-1",
              target_uid: "requirement:alpha-payment-retry",
              edge_type: "evidences",
              confidence: 0.92,
              source_segment_uids: ["segment-alpha-1"],
              citation_bundle: [citation],
            },
          ],
        });
      }
      return jsonResponse({}, false, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<ProjectsPage />);
    });
    await flushAsyncWork();
    await flushAsyncWork();

    expect(fetchMock).toHaveBeenCalledWith("/api/projects/candidates", expect.objectContaining({ headers: expect.any(Object) }));
    expect(fetchMock).toHaveBeenCalledWith("/api/projects/project_candidate%3Aalpha/traceability", expect.objectContaining({ headers: expect.any(Object) }));
    expect(container.textContent).toContain("Project: Alpha Checkout");
    expect(container.textContent).toContain("프로젝트 지식그래프");
    expect(container.textContent).toContain("Traceability Map");
    expect(container.textContent).toContain("Evidence Inspector");
    expect(container.textContent).toContain("문단 citation 경계 확인됨");
    expect(container.textContent).toContain("문단 KG 근거");
    expect(container.textContent).toContain("카드 승인 실패 재시도 안내");
    expect(container.textContent).toContain("결제 화면은 카드 승인 실패");
    expect(container.textContent).toContain("1 citations");
    expect(container.textContent).not.toContain("segment-alpha-1");
    expect(container.textContent).not.toContain("<alpha@example.com>");
  });

  it("renders an actionable fallback when project evidence fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse({ detail: "failed" }, false, 500)));

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<ProjectsPage />);
    });
    await flushAsyncWork();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain("프로젝트 근거를 불러오지 못했습니다");
    expect(
      Array.from(container.querySelectorAll('a[href="/data"]')).some((link) => link.textContent?.includes("원본 연결") || link.textContent?.includes("새 프로젝트")),
    ).toBe(true);
    expect(container.textContent).toContain("원본 연결 작업 대기열");
  });
});
