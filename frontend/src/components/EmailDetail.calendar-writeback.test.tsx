/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/ui/separator", () => ({ Separator: () => <hr /> }));
vi.mock("@/components/ui/avatar", () => ({
  Avatar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AvatarFallback: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("@/components/ui/checkbox", () => ({
  Checkbox: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input type="checkbox" {...props} />,
}));
vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));
vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} />,
}));
vi.mock("@/components/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));
vi.mock("lucide-react", () => ({
  MessagesSquare: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
}));
vi.mock("@/components/DecisionPointCard", () => ({
  DecisionPointCard: ({
    children,
    footerActions,
    title,
  }: {
    children?: React.ReactNode;
    footerActions?: React.ReactNode;
    title: string;
  }) => (
    <section aria-label={title}>
      {children}
      {footerActions}
    </section>
  ),
}));
vi.mock("@/components/SourceDrawer", () => ({ SourceDrawer: () => null }));

import { EmailDetail } from "./EmailDetail";
import {
  clearRecordedProductEvents,
  getRecordedProductEvents,
} from "@/lib/product-events";

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const EMAIL = {
  id: 30,
  message_id: "<calendar-source@example.com>",
  thread_id: null,
  sender: "sender@example.com",
  recipients: "user@example.com",
  subject: "Calendar source",
  date: "2026-05-18T10:00:00Z",
  body: "Coordinate the meeting",
  schedule_conflict: true,
  attachments: ["proposal.pdf"],
};

const SOURCES = [
  {
    source_id: "caldav_source_primary",
    provider: "Fastmail",
    protocol: "caldav",
    owner_id: "owner_primary",
    organization_id: null,
    capabilities: ["read", "write", "etag"],
    writeback_enabled: true,
    etag: "etag-primary",
  },
  {
    source_id: "caldav_source_secondary",
    provider: "Nextcloud",
    protocol: "caldav",
    owner_id: "owner_secondary",
    organization_id: null,
    capabilities: ["read", "write", "etag"],
    writeback_enabled: true,
    etag: "etag-secondary",
  },
];

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function intentResponse(sourceId: string) {
  return {
    workspace_id: "workspace_primary",
    target_source_id: sourceId,
    protocol: "caldav",
    writeback_mode: "customer_owned",
    requires_if_match: false,
    if_match: null,
    provenance: { source_provider: sourceId === SOURCES[0].source_id ? "Fastmail" : "Nextcloud" },
    audit_event: "calendar_writeback_intent_created",
    provider_write_executed: false,
    status: "intent_created",
    runner_request_id: null,
    provider_status: null,
    error_code: null,
  };
}

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

function findButton(container: HTMLElement, label: string) {
  return Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find((button) =>
    button.textContent?.includes(label),
  );
}

function selectCalendarSource(container: HTMLElement, sourceId: string) {
  const sourceSelect = container.querySelector<HTMLSelectElement>('select[aria-label="일정 원본 선택"]');
  expect(sourceSelect).not.toBeNull();
  act(() => {
    if (!sourceSelect) return;
    sourceSelect.value = sourceId;
    sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
  });
  return sourceSelect;
}

describe("EmailDetail calendar writeback boundary", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.unstubAllGlobals();
    clearRecordedProductEvents();
  });

  async function renderWithFetch(fetchMock: ReturnType<typeof vi.fn>) {
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(<EmailDetail emailId={EMAIL.id} />);
    });
    await flushAsyncWork();
    return container;
  }

  it("requires an explicit server-authorized source and sends its opaque identifier", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/emails/${EMAIL.id}`)) return Promise.resolve(jsonResponse(EMAIL));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: ["Review the meeting"] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) return Promise.resolve(jsonResponse(SOURCES));
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        const payload = JSON.parse(String(init.body)) as { target_source_id?: string };
        return Promise.resolve(jsonResponse(intentResponse(String(payload.target_source_id))));
      }
      return Promise.resolve(jsonResponse({}));
    });

    const rendered = await renderWithFetch(fetchMock);
    const attachmentRegion = rendered.querySelector('[role="region"][aria-label="첨부파일"]');
    expect(attachmentRegion).not.toBeNull();

    const sourceSelect = rendered.querySelector<HTMLSelectElement>('select[aria-label="일정 원본 선택"]');
    expect(sourceSelect?.value).toBe("");
    const scheduleButton = findButton(rendered, "일정 조율");
    expect(scheduleButton?.disabled).toBe(true);

    selectCalendarSource(rendered, SOURCES[1].source_id);
    expect(scheduleButton?.disabled).toBe(false);
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/calendar/writeback-intent",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          action: "create",
          summary: "Review the meeting",
          target_source_id: SOURCES[1].source_id,
        }),
      }),
    );
    expect(rendered.textContent).toContain("1개 일정 반영 의도를 Nextcloud 원본에 요청했습니다.");
  });

  it("keeps scheduling disabled with no action items and while a request is pending", async () => {
    const writeback = deferred<Response>();
    let includeActionItem = false;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/emails/${EMAIL.id}`)) return Promise.resolve(jsonResponse(EMAIL));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({
          summary: "Summary",
          action_items: includeActionItem ? ["Review the meeting"] : [],
        }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) return Promise.resolve(jsonResponse(SOURCES));
      if (url.endsWith("/api/calendar/writeback-intent")) return writeback.promise;
      return Promise.resolve(jsonResponse({}));
    });

    let rendered = await renderWithFetch(fetchMock);
    selectCalendarSource(rendered, SOURCES[0].source_id);
    expect(findButton(rendered, "일정 조율")?.disabled).toBe(true);

    act(() => root?.unmount());
    root = null;
    rendered.remove();
    container = null;
    includeActionItem = true;
    rendered = await renderWithFetch(fetchMock);
    selectCalendarSource(rendered, SOURCES[0].source_id);
    const scheduleButton = findButton(rendered, "일정 조율");
    expect(scheduleButton?.disabled).toBe(false);

    await act(async () => {
      scheduleButton?.click();
      await Promise.resolve();
    });
    expect(scheduleButton?.disabled).toBe(true);
    expect(scheduleButton?.textContent).toContain("조율 중");

    await act(async () => {
      writeback.resolve(jsonResponse(intentResponse(SOURCES[0].source_id)));
      await writeback.promise;
    });
    await flushAsyncWork();
  });

  it("clears the confirmed source and requires reconfirmation after a source conflict", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/emails/${EMAIL.id}`)) return Promise.resolve(jsonResponse(EMAIL));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: ["Review the meeting"] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) return Promise.resolve(jsonResponse(SOURCES));
      if (url.endsWith("/api/calendar/writeback-intent")) {
        return Promise.resolve(jsonResponse({ detail: "source conflict" }, 409));
      }
      return Promise.resolve(jsonResponse({}));
    });

    const rendered = await renderWithFetch(fetchMock);
    const sourceSelect = selectCalendarSource(rendered, SOURCES[0].source_id);
    const scheduleButton = findButton(rendered, "일정 조율");
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(sourceSelect?.value).toBe("");
    expect(scheduleButton?.disabled).toBe(true);
    expect(rendered.textContent).toContain("원본 일정이 변경되었습니다. 일정 원본을 다시 선택해 주세요.");
  });

  it("reports partial intent failures without inventing a provider event identifier", async () => {
    const actionItems = ["Review the meeting", "Send the agenda"];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/emails/${EMAIL.id}`)) return Promise.resolve(jsonResponse(EMAIL));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: actionItems }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) return Promise.resolve(jsonResponse(SOURCES));
      if (url.endsWith("/api/calendar/writeback-intent")) {
        const payload = JSON.parse(String(init?.body)) as { summary?: string };
        return payload.summary === actionItems[0]
          ? Promise.resolve(jsonResponse(intentResponse(SOURCES[0].source_id)))
          : Promise.resolve(jsonResponse({ detail: "failed" }, 500));
      }
      return Promise.resolve(jsonResponse({}));
    });

    const rendered = await renderWithFetch(fetchMock);
    selectCalendarSource(rendered, SOURCES[0].source_id);
    const scheduleButton = findButton(rendered, "일정 조율");
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(rendered.textContent).toContain("1개 성공, 1개 실패");
    const calendarEvent = getRecordedProductEvents().find((event) => event.name === "calendar_reflected");
    expect(calendarEvent?.payload.calendar_event_id).toBeNull();
    expect(calendarEvent?.payload.conflict_state).toBe("warning");
    expect(calendarEvent?.payload.provider_write_executed).toBe(false);
  });
});
