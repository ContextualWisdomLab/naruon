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
  for (let index = 0; index < 30; index += 1) {
    if (condition()) return;
    await flushAsyncWork();
  }
  throw new Error("waitForCondition timed out after 30 attempts");
}

function supportResponse(url: string) {
  if (url.endsWith("/api/calendar/writeback-sources") || url.endsWith("/api/webdav/folders")) {
    return Promise.resolve({ ok: true, json: async () => [] });
  }
  if (url.endsWith("/api/search")) {
    return Promise.resolve({ ok: true, json: async () => ({ results: [] }) });
  }
  return null;
}

describe("WorkspaceHome dashboard successor contracts", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    const mountedRoot = root;
    if (mountedRoot) act(() => mountedRoot.unmount());
    root = null;
    container?.remove();
    container = null;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  async function renderDashboard() {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(<WorkspaceHome forcedStartupView="dashboard" />);
    });
  }

  it.each([401, 403])("routes a %i core response to login recovery instead of retry", async (status) => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const support = supportResponse(url);
      if (support) return support;
      if (
        url.endsWith("/api/emails")
        || url.endsWith("/api/emails/pending-replies?limit=3")
        || url.endsWith("/api/tasks")
      ) {
        return Promise.resolve({ ok: false, status });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    await renderDashboard();
    await waitForCondition(() => container?.textContent?.includes("로그인이 필요합니다.") ?? false);

    expect(container?.textContent).toContain("세션이 만료됐거나 이 작업공간에 접근할 수 없습니다.");
    expect(container?.querySelector('a[href="/settings"]')?.textContent).toContain("로그인 설정 열기");
    expect(container?.querySelector('[role="alert"] button')).toBeNull();
  });

  it("fails closed when a successful mail response omits the emails array", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const support = supportResponse(url);
      if (support) return support;
      if (url.endsWith("/api/emails")) return Promise.resolve({ ok: true, json: async () => ({}) });
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/tasks")) return Promise.resolve({ ok: true, json: async () => [] });
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    await renderDashboard();
    await waitForCondition(() => container?.textContent?.includes("최근 메일을 확인하지 못했습니다.") ?? false);

    expect(container?.textContent).not.toContain("수신된 메일이 없습니다.");
  });

  it("publishes ready source data without waiting for an unrelated stalled core read", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const support = supportResponse(url);
      if (support) return support;
      if (url.endsWith("/api/emails")) return new Promise(() => undefined);
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            emails: [{
              id: 501,
              subject: "독립적으로 확인된 답변 대기",
              sender: "customer@example.com",
              date: "2026-09-05T00:00:00Z",
              snippet: "메일 목록 응답과 무관하게 표시되어야 합니다.",
            }],
          }),
        });
      }
      if (url.endsWith("/api/tasks")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{
            id: "task-independent-ready",
            title: "독립적으로 확인된 작업",
            status: "open",
            priority: "normal",
            created_at: "2026-09-05T00:00:00Z",
            updated_at: "2026-09-05T00:00:00Z",
          }],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    await renderDashboard();
    await waitForCondition(() => container?.textContent?.includes("독립적으로 확인된 답변 대기") ?? false);

    expect(container?.textContent).toContain("독립적으로 확인된 작업");
    expect(container?.textContent).toContain("메일을 불러오는 중...");
  });

  it("bounds a stalled dashboard read with the native timeout signal", async () => {
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    const timeoutController = new AbortController();
    const timeoutSpy = vi.spyOn(AbortSignal, "timeout").mockReturnValue(timeoutController.signal);
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const support = supportResponse(url);
      if (support) return support;
      if (url.endsWith("/api/emails")) {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("timed out", "AbortError")),
            { once: true },
          );
        });
      }
      if (url.endsWith("/api/emails/pending-replies?limit=3")) {
        return Promise.resolve({ ok: true, json: async () => ({ emails: [] }) });
      }
      if (url.endsWith("/api/tasks")) return Promise.resolve({ ok: true, json: async () => [] });
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    await renderDashboard();
    expect(timeoutSpy).toHaveBeenCalledWith(15_000);
    await act(async () => timeoutController.abort());
    await waitForCondition(() => container?.textContent?.includes("최근 메일을 확인하지 못했습니다.") ?? false);

    expect(container?.textContent).not.toContain("메일을 불러오는 중...");
  });
});
