/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

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
  Checkbox: (props: React.InputHTMLAttributes<HTMLInputElement>) => (
    <input type="checkbox" {...props} />
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
    <textarea {...props} />
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("lucide-react", () => ({
  MessagesSquare: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  ExternalLink: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  Info: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
  X: () => <svg aria-hidden="true" />,
}));

import { EmailDetail } from "./EmailDetail";

type TestEmail = {
  id: number;
  message_id: string;
  thread_id: string | null;
  sender: string;
  recipients: string;
  subject: string;
  date: string;
  body: string;
};

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function waitForCondition(condition: () => boolean) {
  for (let index = 0; index < 20; index += 1) {
    if (condition()) return;
    await flushAsyncWork();
  }
  throw new Error("Condition did not become true before the test timeout.");
}

describe("EmailDetail conversation memoization", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) {
      act(() => root?.unmount());
    }
    root = null;
    container?.remove();
    container = null;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not rerender unchanged thread messages when reply draft text changes", async () => {
    const selectedEmail: TestEmail = {
      id: 41,
      message_id: "<selected@example.com>",
      thread_id: "memo-thread",
      sender: "selected@example.com",
      recipients: "user@example.com",
      subject: "Memoization proof",
      date: "2026-08-16T08:00:00Z",
      body: "Selected message body",
    };
    const siblingEmail: TestEmail = {
      ...selectedEmail,
      id: 42,
      message_id: "<sibling@example.com>",
      sender: "sibling@example.com",
      date: "2026-08-16T08:05:00Z",
      body: "Sibling message body",
    };

    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/41")) {
        return Promise.resolve(jsonResponse(selectedEmail));
      }
      if (url.endsWith("/api/emails/thread/memo-thread")) {
        return Promise.resolve(jsonResponse({ thread: [selectedEmail, siblingEmail] }));
      }
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(
          jsonResponse({ summary: "Memoization acceptance context", action_items: [] }),
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const dateFormattingSpy = vi
      .spyOn(Date.prototype, "toLocaleString")
      .mockReturnValue("formatted date");

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<EmailDetail emailId={41} />);
    });
    await waitForCondition(() =>
      container?.textContent?.includes("Sibling message body") ?? false,
    );
    await flushAsyncWork();

    const callsBeforeDraftEdit = dateFormattingSpy.mock.calls.length;
    const draftTextarea = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="답장 초안"]',
    );
    expect(draftTextarea).not.toBeNull();

    const nativeValueSetter = Object.getOwnPropertyDescriptor(
      HTMLTextAreaElement.prototype,
      "value",
    )?.set;
    expect(nativeValueSetter).toBeDefined();

    await act(async () => {
      nativeValueSetter?.call(draftTextarea, "Unrelated draft edit");
      draftTextarea?.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await flushAsyncWork();

    expect(draftTextarea?.value).toBe("Unrelated draft edit");
    expect(dateFormattingSpy.mock.calls.length - callsBeforeDraftEdit).toBe(1);
  });
});
