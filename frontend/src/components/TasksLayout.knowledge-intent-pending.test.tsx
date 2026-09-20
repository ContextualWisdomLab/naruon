/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  Plus: () => <svg aria-hidden="true" />,
  Loader2: () => <svg data-testid="loading-spinner" aria-hidden="true" />,
  Search: () => <svg aria-hidden="true" />,
  Filter: () => <svg aria-hidden="true" />,
  User: () => <svg aria-hidden="true" />,
  CalendarDays: () => <svg aria-hidden="true" />,
  Inbox: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  X: () => <svg aria-hidden="true" />,
}));

import { TasksLayout } from "./TasksLayout";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  };
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("TasksLayout knowledge intent pending identity", () => {
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
  });

  it("marks only the initiating knowledge action busy while keeping both actions mutually exclusive", async () => {
    const task = {
      id: "task-knowledge-1",
      title: "지식 메모",
      status: "open",
      priority: "normal",
      source_type: "self_sent_knowledge",
      source_email_id: "mail-knowledge-1",
      related_thread_id: null,
      updated_at: "2026-09-20T00:00:00Z",
    };
    const intent = {
      intent: "knowledge_materialization",
      status: "ready",
      task_id: task.id,
      source_type: "self_sent_knowledge",
      source_email_id: task.source_email_id,
      source_thread_id: null,
      source_id: "source-1",
      target_label: "Notes",
      target_path: "/notes/source-1.md",
      requires_if_match: true,
      provenance: "task",
      provider_write_executed: false,
      audit_event: "knowledge_materialization_intent_created",
    };
    const createResponse = deferred<ReturnType<typeof jsonResponse>>();
    const executeResponse = deferred<ReturnType<typeof jsonResponse>>();
    let intentRequestCount = 0;

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/tasks")) return Promise.resolve(jsonResponse([task]));
      if (url.endsWith("/api/webdav/knowledge-materialization-intent") && init?.method === "POST") {
        intentRequestCount += 1;
        return intentRequestCount === 1 ? createResponse.promise : executeResponse.promise;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<TasksLayout />);
    });
    await flushAsyncWork();

    const getCreateButton = () => container?.querySelector<HTMLButtonElement>(
      'button[aria-label="지식 메모 WebDAV 지식 노트 의도 생성"]',
    ) ?? null;
    const getExecuteButton = () => container?.querySelector<HTMLButtonElement>(
      'button[aria-label="지식 메모 WebDAV 지식 노트 실행 요청"]',
    ) ?? null;

    expect(getCreateButton()).not.toBeNull();
    expect(getExecuteButton()).not.toBeNull();

    await act(async () => {
      getCreateButton()?.click();
      await Promise.resolve();
    });

    expect(getCreateButton()?.disabled).toBe(true);
    expect(getExecuteButton()?.disabled).toBe(true);
    expect(getCreateButton()?.getAttribute("aria-busy")).toBe("true");
    expect(getExecuteButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getCreateButton()?.textContent).toContain("생성 중");
    expect(getExecuteButton()?.textContent).toContain("실행 요청");
    expect(getCreateButton()?.querySelector('[data-testid="loading-spinner"]')).not.toBeNull();
    expect(getExecuteButton()?.querySelector('[data-testid="loading-spinner"]')).toBeNull();

    const createRequest = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith("/api/webdav/knowledge-materialization-intent")
        && (init as RequestInit | undefined)?.method === "POST",
    );
    expect(JSON.parse(String((createRequest?.[1] as RequestInit | undefined)?.body))).toEqual({
      source_task_id: task.id,
    });

    await act(async () => {
      createResponse.resolve(jsonResponse(intent));
      await createResponse.promise;
    });
    await flushAsyncWork();

    expect(getCreateButton()?.disabled).toBe(false);
    expect(getExecuteButton()?.disabled).toBe(false);
    expect(getCreateButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getExecuteButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getCreateButton()?.textContent).toContain("의도 생성");
    expect(getExecuteButton()?.textContent).toContain("실행 요청");

    await act(async () => {
      getExecuteButton()?.click();
      await Promise.resolve();
    });

    expect(getCreateButton()?.disabled).toBe(true);
    expect(getExecuteButton()?.disabled).toBe(true);
    expect(getCreateButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getExecuteButton()?.getAttribute("aria-busy")).toBe("true");
    expect(getCreateButton()?.textContent).toContain("의도 생성");
    expect(getExecuteButton()?.textContent).toContain("실행 중");
    expect(getCreateButton()?.querySelector('[data-testid="loading-spinner"]')).toBeNull();
    expect(getExecuteButton()?.querySelector('[data-testid="loading-spinner"]')).not.toBeNull();

    const postRequests = fetchMock.mock.calls.filter(
      ([input, init]) => String(input).endsWith("/api/webdav/knowledge-materialization-intent")
        && (init as RequestInit | undefined)?.method === "POST",
    );
    expect(JSON.parse(String((postRequests[1]?.[1] as RequestInit | undefined)?.body))).toEqual({
      source_task_id: task.id,
      execute_provider: true,
    });

    await act(async () => {
      executeResponse.reject(new Error("provider unavailable"));
      try {
        await executeResponse.promise;
      } catch {
        // The component owns the error state; the test only needs settlement.
      }
    });
    await flushAsyncWork();

    expect(getCreateButton()?.disabled).toBe(false);
    expect(getExecuteButton()?.disabled).toBe(false);
    expect(getCreateButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getExecuteButton()?.getAttribute("aria-busy")).toBeNull();
    expect(getCreateButton()?.textContent).toContain("의도 생성");
    expect(getExecuteButton()?.textContent).toContain("실행 요청");
    expect(container.textContent).toContain("WebDAV/Notes 의도를 만들지 못했습니다.");
  });
});
