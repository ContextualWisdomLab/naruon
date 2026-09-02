/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  Search: () => <svg aria-hidden="true" />,
  Mail: () => <svg aria-hidden="true" />,
  CalendarDays: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  Sparkles: () => <svg aria-hidden="true" />,
  Network: () => <svg aria-hidden="true" />,
  Clock: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  CornerDownRight: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
  X: () => <svg aria-hidden="true" />,
}));

vi.mock("vis-network", () => ({
  Network: vi.fn(function MockNetwork() {
    return { destroy: vi.fn(), fit: vi.fn() };
  }),
}));

import { SearchLayout } from "./SearchLayout";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  };
}

async function flushAsyncWork() {
  for (let index = 0; index < 6; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

let root: Root | null = null;
let container: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root?.unmount());
  root = null;
  container?.remove();
  container = null;
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("explains that automatic relationship capture abstained when validated evidence is unavailable", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/search")) {
      return Promise.resolve(
        jsonResponse({
          results: [
            {
              id: 91,
              source_message_id: "<unavailable@example.com>",
              subject: "관계 근거 확인",
              sender: "보낸 사람",
              date: "2026-09-02T05:00:00Z",
              snippet: "검증된 관계 분류가 없는 경우",
              thread_id: "thread-unavailable",
              reply_count: 1,
              score: 0.7,
            },
          ],
        }),
      );
    }
    if (url.endsWith("/api/search/answer")) {
      return Promise.resolve(jsonResponse({ answer: null, citations: [], provenance: null }));
    }
    if (url.includes("/api/ontology/relationships/capture-source")) {
      return Promise.resolve(
        jsonResponse(
          {
            detail:
              "Automatic sender classification is unavailable until validated relationship evidence is configured.",
          },
          false,
          503,
        ),
      );
    }
    if (url.includes("/api/ontology/relationships")) {
      return Promise.resolve(jsonResponse([]));
    }
    if (url.endsWith("/api/network/graph")) {
      return Promise.resolve(jsonResponse({ nodes: [], edges: [] }));
    }
    return Promise.resolve(jsonResponse({}, false, 404));
  });
  vi.stubGlobal("fetch", fetchMock);

  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(<SearchLayout />);
  });
  await flushAsyncWork();

  expect(container.textContent).toContain(
    "검증된 관계 분류 근거가 있을 때만 관계를 저장합니다.",
  );

  const captureButton = Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent?.includes("검증된 관계 캡처"),
  );
  expect(captureButton).toBeDefined();

  await act(async () => {
    captureButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await flushAsyncWork();

  expect(container.textContent).toContain(
    "검증된 관계 분류 근거가 없어 저장하지 않았습니다.",
  );
  expect(container.textContent).not.toContain("발신자 관계 캡처에 실패했습니다.");
});
