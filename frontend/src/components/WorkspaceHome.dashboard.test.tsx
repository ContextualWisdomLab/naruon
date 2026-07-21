/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/EmailList", () => ({
  EmailList: () => <section aria-label="mock email list">mock email list</section>,
}));

vi.mock("@/components/EmailDetail", () => ({
  EmailDetail: () => <section aria-label="mock email detail">mock email detail</section>,
}));

vi.mock("@/components/ui/resizable", () => ({
  ResizablePanelGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ResizablePanel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ResizableHandle: () => <div />,
}));

vi.mock("@/components/mobile-workspace-panels", () => ({
  MobileCalendarPanel: () => <section>mock calendar</section>,
  MobileSearchPanel: () => <section>mock search</section>,
}));

vi.mock("next/dynamic", () => ({
  default: () => function MockDynamic() {
    return <div>mock graph</div>;
  },
}));

vi.mock("lucide-react", () => ({
  CalendarDays: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Inbox: () => <svg aria-hidden="true" />,
  Network: () => <svg aria-hidden="true" />,
  Send: () => <svg aria-hidden="true" />,
  Settings: () => <svg aria-hidden="true" />,
  Sparkles: () => <svg aria-hidden="true" />,
}));

import { WorkspaceHome } from "./WorkspaceHome";

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForCondition(condition: () => boolean) {
  for (let index = 0; index < 20; index += 1) {
    if (condition()) return;
    await flushAsyncWork();
  }
  throw new Error("waitForCondition timed out after 20 attempts");
}

function emptySourceEvidenceResponse(url: string) {
  if (
    url.endsWith("/api/calendar/writeback-sources") ||
    url.endsWith("/api/webdav/folders")
  ) {
    return Promise.resolve({
      ok: true,
      json: async () => ([]),
    });
  }
  return null;
}

function emptyCalendarCandidateSearchResponse(url: string) {
  if (url.endsWith("/api/search")) {
    return Promise.resolve({
      ok: true,
      json: async () => ({ results: [] }),
    });
  }
  return null;
}

function accountsConfigResponse(url: string, overrides: Record<string, unknown> = {}) {
  if (url.endsWith("/api/accounts/config")) {
    return Promise.resolve({
      ok: true,
      json: async () => ({
        user_id: "default",
        smtp_server: "smtp.example.com",
        smtp_port: 587,
        smtp_username: "sender@example.com",
        has_smtp_password: true,
        imap_server: "imap.example.com",
        imap_port: 993,
        imap_username: "inbox@example.com",
        has_imap_password: true,
        pop3_server: null,
        pop3_port: null,
        pop3_username: null,
        has_pop3_password: false,
        oauth_client_id: null,
        oauth_redirect_uri: null,
        has_oauth_client_secret: false,
        has_openai_api_key: true,
        ...overrides,
      }),
    });
  }
  return null;
}

describe("WorkspaceHome Today dashboard", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    const mountedRoot = root;
    if (mountedRoot) {
      act(() => mountedRoot.unmount());
    }
    root = null;
    container?.remove();
    container = null;
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("loads pending sent-mail replies through signed session headers", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      fetchCalls.push({ url, init });
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 301,
                subject: "벤더 계약 답변 요청",
                sender: "Seongho <user@naruon.ai>",
                date: "2026-05-17T09:00:00Z",
                snippet: "계약 검토 회신 기한이 지나 작업 보드와 연결해야 합니다.",
                requires_reply: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 101,
                subject: "고객 계약 승인 대기",
                sender: "legal@example.com",
                date: "2026-05-17T09:00:00Z",
                snippet: "오늘 승인해야 하는 계약 검토 요청",
                unread: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([]),
        });
      }
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("벤더 계약 답변 요청") ?? false);

    expect(container.textContent).toContain("답변 대기 메일");
    expect(container.textContent).toContain("계약 검토 회신 기한");
    const pendingCall = fetchCalls.find((call) => call.url.endsWith("/api/emails/pending-replies?limit=3"));
    expect(pendingCall).toBeDefined();
    expect(pendingCall?.init?.credentials).toBe("same-origin");
    const headers = pendingCall?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(headers["X-User-Id"]).toBeUndefined();
    expect(headers["X-Organization-Id"]).toBeUndefined();
    expect(headers["X-Dev-Auth-Token"]).toBeUndefined();
  });

  it("creates overdue reply follow-up tasks from the Today dashboard with signed headers", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    const publicIdentityHeaders = [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ];
    const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      fetchCalls.push({ url, init });
      if (url.endsWith("/api/tasks/reply-sla-escalations")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            evaluated: 2,
            created: 1,
            policy: { overdue_hours: 48 },
            tasks: [],
          }),
        });
      }
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 301,
                subject: "벤더 계약 답변 요청",
                sender: "Seongho <user@naruon.ai>",
                date: "2026-05-17T09:00:00Z",
                snippet: "계약 검토 회신 기한이 지나 작업 보드와 연결해야 합니다.",
                requires_reply: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([]),
        });
      }
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("벤더 계약 답변 요청") ?? false);

    const escalationButton = container.querySelector<HTMLButtonElement>(
      'button[aria-label="홈에서 보낸 메일 미답변 팔로업 작업 생성"]',
    );
    expect(escalationButton).not.toBeNull();
    await act(async () => {
      escalationButton?.click();
    });
    await waitForCondition(() => container?.textContent?.includes("1개 팔로업 작업 생성") ?? false);

    const escalationCall = fetchCalls.find((call) => call.url.endsWith("/api/tasks/reply-sla-escalations"));
    expect(escalationCall).toBeDefined();
    expect(escalationCall?.init?.method).toBe("POST");
    expect(escalationCall?.init?.credentials).toBe("same-origin");
    expect(JSON.parse(String(escalationCall?.init?.body))).toEqual({ overdue_hours: 48 });
    const headers = escalationCall?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    for (const headerName of publicIdentityHeaders) {
      expect(Object.keys(headers).some((key) => key.toLowerCase() === headerName)).toBe(false);
    }
    expect(container.textContent).toContain("1개 팔로업 작업 생성, 2개 답변 대기 확인");
  });

  it("routes Today dashboard task calendar and quick actions to implemented workspaces", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 101,
                subject: "고객 계약 승인 대기",
                sender: "legal@example.com",
                date: "2026-05-17T09:00:00Z",
                snippet: "오늘 승인해야 하는 계약 검토 요청",
                unread: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              id: "task-home-route",
              title: "계약 승인 확인",
              status: "open",
              priority: "high",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
          ]),
        });
      }
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("계약 승인 확인") ?? false);

    const linkHrefByText = (label: string) =>
      Array.from(container?.querySelectorAll<HTMLAnchorElement>("a") ?? [])
        .find((link) => link.textContent?.includes(label))
        ?.getAttribute("href");

    expect(linkHrefByText("작업 바로가기")).toBe("/tasks");
    expect(linkHrefByText("전체 작업 보기")).toBe("/tasks");
    expect(linkHrefByText("일정 조율하기")).toBe("/calendar");
    expect(linkHrefByText("열기")).toBe("/mail?id=101");
    expect(
      Array.from(container?.querySelectorAll("button") ?? [])
        .some((button) => button.textContent?.includes("보류")),
    ).toBe(false);

    const quickActions = container.querySelector<HTMLElement>('[aria-label="홈 빠른 실행"]');
    expect(quickActions).not.toBeNull();
    expect(Array.from(quickActions?.querySelectorAll("button") ?? [])).toHaveLength(0);
    expect(linkHrefByText("메일함 열기")).toBe("/mail");
    expect(linkHrefByText("보낸 메일 답변 추적")).toBe("/mail?folder=sent");
    expect(linkHrefByText("일정 후보 검토")).toBe("/calendar");
    expect(linkHrefByText("실행 항목 보드")).toBe("/tasks");
    expect(linkHrefByText("프로젝트 의사결정")).toBe("/projects");
    expect(linkHrefByText("AI 허브")).toBe("/ai-hub");
    expect(linkHrefByText("데이터 품질 점검")).toBe("/data");
    expect(linkHrefByText("보안 감사 로그")).toBe("/security");
  });

  it("marks a Today dashboard task done through the signed task API", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      fetchCalls.push({ url, init });
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/tasks/task-home-toggle")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "task-home-toggle",
            title: "계약 승인 확인",
            status: "done",
            priority: "high",
            created_at: "2026-05-17T09:00:00Z",
            updated_at: "2026-05-17T10:00:00Z",
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              id: "task-home-toggle",
              title: "계약 승인 확인",
              status: "open",
              priority: "high",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
          ]),
        });
      }
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("계약 승인 확인") ?? false);

    const taskCheckbox = container.querySelector<HTMLInputElement>(
      'input[aria-label="계약 승인 확인 작업 선택"]',
    );
    expect(taskCheckbox).not.toBeNull();
    expect(taskCheckbox?.checked).toBe(false);

    await act(async () => {
      taskCheckbox?.click();
    });
    await waitForCondition(() => container?.textContent?.includes("계약 승인 확인 작업을 완료 처리했습니다.") ?? false);

    const patchCall = fetchCalls.find((call) => call.url.endsWith("/api/tasks/task-home-toggle"));
    expect(patchCall?.init?.method).toBe("PATCH");
    expect(patchCall?.init?.credentials).toBe("same-origin");
    expect(JSON.parse(String(patchCall?.init?.body))).toEqual({ status: "done" });
    const headers = patchCall?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    for (const headerName of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(Object.keys(headers).some((key) => key.toLowerCase() === headerName)).toBe(false);
    }
  });

  it("keeps Today dashboard task update feedback keyed per task", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/tasks/task-alpha")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "task-alpha",
            title: "계약 승인 확인",
            status: "done",
            priority: "high",
            created_at: "2026-05-17T09:00:00Z",
            updated_at: "2026-05-17T10:00:00Z",
          }),
        });
      }
      if (url.endsWith("/api/tasks/task-beta")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "task-beta",
            title: "회의록 공유",
            status: "done",
            priority: "normal",
            created_at: "2026-05-17T09:00:00Z",
            updated_at: "2026-05-17T10:00:00Z",
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              id: "task-alpha",
              title: "계약 승인 확인",
              status: "open",
              priority: "high",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
            {
              id: "task-beta",
              title: "회의록 공유",
              status: "open",
              priority: "normal",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
          ]),
        });
      }
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("회의록 공유") ?? false);

    const contractCheckbox = container.querySelector<HTMLInputElement>(
      'input[aria-label="계약 승인 확인 작업 선택"]',
    );
    const notesCheckbox = container.querySelector<HTMLInputElement>(
      'input[aria-label="회의록 공유 작업 선택"]',
    );
    expect(contractCheckbox).not.toBeNull();
    expect(notesCheckbox).not.toBeNull();

    await act(async () => {
      contractCheckbox?.click();
      notesCheckbox?.click();
    });
    await waitForCondition(() => (
      (container?.textContent?.includes("계약 승인 확인 작업을 완료 처리했습니다.") ?? false)
      && (container?.textContent?.includes("회의록 공유 작업을 완료 처리했습니다.") ?? false)
    ));
  });

  it("backs Today dashboard operating metrics with source evidence instead of fixed fixture numbers", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    const publicIdentityHeaders = [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ];
    const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      fetchCalls.push({ url, init });
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 101,
                subject: "고객 계약 승인 대기",
                sender: "legal@example.com",
                date: "2026-05-17T09:00:00Z",
                snippet: "오늘 승인해야 하는 계약 검토 요청",
                unread: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              id: "task-source-open",
              title: "<script>계약 승인 확인</script>",
              status: "open",
              priority: "high",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
            {
              id: "task-source-done",
              title: "첨부 근거 정리",
              status: "done",
              priority: "low",
              created_at: "2026-05-17T09:00:00Z",
              updated_at: "2026-05-17T09:00:00Z",
            },
          ]),
        });
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              source_id: "caldav-primary",
              provider: "Primary CalDAV",
              protocol: "caldav",
              capabilities: ["read", "write"],
              writeback_enabled: true,
              etag: "etag-home-1",
            },
            {
              source_id: "calendar-readonly",
              provider: "Read-only Calendar",
              protocol: "local",
              capabilities: ["read"],
              writeback_enabled: false,
            },
          ]),
        });
      }
      if (url.endsWith("/api/webdav/folders")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              folder_uid: "folder-roadmap",
              project_name: "Naruon Roadmap",
              webdav_path: "/Projects/Naruon_Roadmap",
            },
          ]),
        });
      }
      if (url.endsWith("/api/search")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            results: [
              {
                id: 601,
                subject: "엔터프라이즈 데모 일정 조율",
                sender: "sales@example.com",
                date: "2026-05-18T11:00:00Z",
                snippet: "고객 데모 후보 시간을 확정해야 합니다.",
              },
            ],
          }),
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("고객 계약 승인 대기") ?? false);

    expect(container.textContent).toContain("일정 원본");
    expect(container.textContent).toContain("2");
    expect(container.textContent).toContain("1개 일정 반영 가능");
    expect(container.textContent).toContain("일정 원본 1");
    expect(container.textContent).toContain("충돌 토큰 있음");
    expect(container.textContent).toContain("프로젝트 원본");
    expect(container.textContent).toContain("1개 WebDAV 폴더");
    expect(container.textContent).toContain("작업 완료율");
    expect(container.textContent).toContain("50%");
    expect(container.textContent).toContain("1/2 완료");
    expect(container.textContent).toContain("계약 승인 확인");
    expect(container.textContent).toContain("일정 조율 후보 1건");
    expect(container.textContent).toContain("엔터프라이즈 데모 일정 조율");
    expect(container.textContent).toContain("고객 데모 후보 시간을 확정해야 합니다.");
    expect(container.textContent).not.toContain("오늘 일정");
    expect(container.textContent).not.toContain("진행 중 프로젝트");
    expect(container.textContent).not.toContain("이번 주 목표 진행률");
    expect(container.textContent).not.toContain("회의 2건 예정");
    expect(container.textContent).not.toContain("일정 충돌 알림");
    expect(container.textContent).not.toContain("68%");
    expect(container.textContent).not.toContain("어제 대비");
    expect(container.textContent).not.toContain("<script>");
    expect(container.textContent).not.toContain("caldav-primary");
    expect(container.textContent).not.toContain("calendar-readonly");
    expect(container.textContent).not.toContain("Primary CalDAV");
    expect(container.textContent).not.toContain("Read-only Calendar");

    const calendarSourceCall = fetchCalls.find((call) => call.url.endsWith("/api/calendar/writeback-sources"));
    const projectFolderCall = fetchCalls.find((call) => call.url.endsWith("/api/webdav/folders"));
    const calendarCandidateCall = fetchCalls.find((call) => call.url.endsWith("/api/search"));
    expect(calendarCandidateCall?.init?.method).toBe("POST");
    expect(JSON.parse(String(calendarCandidateCall?.init?.body))).toEqual({
      query: "일정 충돌 일정 조율 회의 후보",
      limit: 3,
    });
    for (const sourceCall of [calendarSourceCall, projectFolderCall, calendarCandidateCall]) {
      expect(sourceCall).toBeDefined();
      expect(sourceCall?.init?.credentials).toBe("same-origin");
      const headers = sourceCall?.init?.headers as Record<string, string>;
      expect(headers.Authorization).toBeUndefined();
      for (const headerName of publicIdentityHeaders) {
        expect(Object.keys(headers).some((key) => key.toLowerCase() === headerName)).toBe(false);
      }
    }
  });

  it("shows an explicit source evidence error instead of a false empty calendar state", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ emails: [] }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 101,
                subject: "고객 계약 승인 대기",
                sender: "legal@example.com",
                date: "2026-05-17T09:00:00Z",
                snippet: "오늘 승인해야 하는 계약 검토 요청",
                unread: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([]),
        });
      }
      if (url.endsWith("/api/calendar/writeback-sources") || url.endsWith("/api/webdav/folders")) {
        return Promise.reject(new Error("source registry unavailable"));
      }
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("일정 원본 목록 확인에 실패했습니다.") ?? false);

    expect(container.textContent).toContain("일정 원본 확인 필요");
    expect(container.textContent).toContain("오류");
    expect(container.textContent).toContain("일정 원본 목록 응답을 확인할 수 없습니다.");
    expect(container.textContent).not.toContain("연결된 일정 원본이 없습니다.");
  });

  it("renders the calendar startup view as a data-backed today surface", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              {
                id: 501,
                subject: "견적 회신 대기",
                sender: "김파트너 <partner@example.com>",
                date: "2026-07-20T09:00:00Z",
                snippet: "발송 후 48시간 무응답",
                requires_reply: true,
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              id: "task-uid-1",
              title: "출시 일정 확정",
              status: "open",
              priority: "high",
              created_at: "2026-07-20T01:00:00Z",
              updated_at: "2026-07-20T01:00:00Z",
            },
          ]),
        });
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            {
              source_id: "opaque-source-1",
              provider: "fastmail",
              protocol: "caldav",
              owner_id: "owner",
              organization_id: "org",
              capabilities: ["read", "write", "etag"],
              writeback_enabled: true,
              etag: "W/\"1\"",
            },
          ]),
        });
      }
      if (url.endsWith("/api/webdav/folders")) {
        return Promise.resolve({ ok: true, json: async () => ([]) });
      }
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="calendar" />);
    });
    await waitForCondition(() => container?.textContent?.includes("출시 일정 확정") ?? false);

    // Calendar-first Home is a real dashboard, not a redirect card.
    const calendarCta = Array.from(container.querySelectorAll("a")).find(
      (link) => link.textContent?.includes("일정 관리 열기"),
    );
    expect(calendarCta?.getAttribute("href")).toBe("/calendar");
    expect(container.textContent).toContain("일정 원본 연결 상태");
    expect(container.textContent).toContain("CalDAV 원본");
    expect(container.textContent).toContain("일정 반영");
    expect(container.textContent).toContain("김파트너");
    expect(container.textContent).toContain("견적 회신 대기");
    expect(container.textContent).toContain("출시 일정 확정");
    // Empty search candidates render as a calm empty state, and the source
    // event feed is honestly labelled pending (no server events API yet).
    expect(container.textContent).toContain("일정 후보가 없습니다");
    expect(container.textContent).toContain("원본 이벤트 표시는 연동 후 제공");
    // Opaque source ids never render as visible text.
    expect(container.textContent).not.toContain("opaque-source-1");
  });

  it("leads with onboarding when no mailbox is connected", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({ ok: true, json: async () => ([]) });
      }
      const accountsResponse = accountsConfigResponse(url, {
        imap_server: null,
        imap_username: null,
        has_imap_password: false,
        smtp_server: null,
        has_smtp_password: false,
        has_openai_api_key: false,
      });
      if (accountsResponse) return accountsResponse;
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("메일 워크스페이스 시작하기") ?? false);

    expect(container.textContent).toContain("메일 계정 연결");
    expect(container.textContent).toContain("LLM API Key 등록");
    expect(container.textContent).toContain("메일 데이터 가져오기");
    const linkHrefByText = (label: string) =>
      Array.from(container?.querySelectorAll("a") ?? []).find((link) => link.textContent?.includes(label))?.getAttribute("href");
    expect(linkHrefByText("메일 계정 연결하기")).toBe("/settings#accounts");
    expect(linkHrefByText("LLM API Key 등록하기")).toBe("/settings#ai-models");
  });

  it("hides onboarding once the mailbox and data are connected", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/emails")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [
              { id: 1, subject: "동기화된 메일", sender: "peer@example.com", date: "2026-07-20T09:00:00Z", snippet: "본문", unread: false },
            ],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({ ok: true, json: async () => ([]) });
      }
      const accountsResponse = accountsConfigResponse(url);
      if (accountsResponse) return accountsResponse;
      const sourceEvidenceResponse = emptySourceEvidenceResponse(url);
      if (sourceEvidenceResponse) return sourceEvidenceResponse;
      const calendarCandidateResponse = emptyCalendarCandidateSearchResponse(url);
      if (calendarCandidateResponse) return calendarCandidateResponse;
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
    await waitForCondition(() => container?.textContent?.includes("동기화된 메일") ?? false);

    expect(container.textContent).not.toContain("메일 워크스페이스 시작하기");
  });
});
