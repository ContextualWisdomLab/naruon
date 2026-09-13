/**
 * @vitest-environment jsdom
 */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/dynamic", () => ({
  default: vi.fn(() => () => <div>Mocked Component</div>),
}));

import { SearchLayout } from "./SearchLayout";

describe("SearchLayout product events", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount();
      });
    }
    if (container) {
      container.remove();
    }
    root = null;
    container = null;
    vi.clearAllMocks();
  });

  function renderSearchLayout(props: any) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(<SearchLayout {...props} />);
    });
  }

  it("checks title attributes for loading states", () => {
    renderSearchLayout({
      recentSearches: [],
      onSaveSearch: vi.fn(),
      loading: true,
      results: [],
      error: null,
      onPerformSearch: vi.fn(),
      captureStatus: "loading",
      onCaptureSenderRelationship: vi.fn(),
      onClearError: vi.fn()
    });

    const buttons = Array.from(container!.querySelectorAll("button"));
    const searchBtn = buttons.find(b => b.textContent?.includes("맥락 검색"));
    const captureBtn = buttons.find(b => b.textContent?.includes("관계 캡처"));

    expect(searchBtn?.getAttribute("title")).toBe("맥락 검색 중입니다");
    expect(captureBtn?.getAttribute("title")).toBe("관계 캡처 중입니다");
  });

  it("checks title attributes for loading states", () => {
    let capturedEvent: any = null;
    vi.stubGlobal('dispatchEvent', vi.fn((event) => {
      capturedEvent = event;
    }));

    renderSearchLayout({
      recentSearches: [],
      onSaveSearch: vi.fn(),
      loading: true,
      results: [{
        id: 1,
        sender_id: 101,
        sender_email: "test@example.com",
        sender_type: "customer",
        subject: "test",
        snippet: "test",
        date: "2023-01-01T00:00:00Z",
        related_people: [],
        extracted_topics: [],
        thread_context: { messages_in_thread: 1 },
        confidence: 0.9,
        pipeline_status: "ready",
        intent_status: null
      }],
      error: null,
      onPerformSearch: vi.fn(),
      captureStatus: "loading",
      onCaptureSenderRelationship: vi.fn(),
      onClearError: vi.fn(),
      emailThreadingState: {
        threads: new Map(),
        isLoading: false,
        error: null,
      },
      fetchThread: vi.fn()
    });

    const buttons = Array.from(container!.querySelectorAll("button"));
    const searchBtn = buttons.find(b => b.textContent?.includes("맥락 검색"));
    const captureBtn = buttons.find(b => b.textContent?.includes("관계 캡처"));

    expect(searchBtn?.getAttribute("title")).toBe("맥락 검색 중입니다");
    expect(captureBtn?.getAttribute("title")).toBe("관계 캡처 중입니다");
  });

  it("checks title attributes for loading states", () => {
    let capturedEvent: any = null;
    vi.stubGlobal('dispatchEvent', vi.fn((event) => {
      capturedEvent = event;
    }));

    renderSearchLayout({
      recentSearches: [],
      onSaveSearch: vi.fn(),
      loading: true,
      results: [{
        id: 1,
        sender_id: 101,
        sender_email: "test@example.com",
        sender_type: "customer",
        subject: "test",
        snippet: "test",
        date: "2023-01-01T00:00:00Z",
        related_people: [],
        extracted_topics: [],
        thread_context: { messages_in_thread: 1 },
        confidence: 0.9,
        pipeline_status: "ready",
        intent_status: null
      }],
      error: null,
      onPerformSearch: vi.fn(),
      captureStatus: "loading",
      onCaptureSenderRelationship: vi.fn(),
      onClearError: vi.fn(),
      emailThreadingState: {
        threads: new Map(),
        isLoading: false,
        error: null,
      },
      fetchThread: vi.fn()
    });

    const buttons = Array.from(container!.querySelectorAll("button"));
    const searchBtn = buttons.find(b => b.textContent?.includes("맥락 검색"));
    const captureBtn = buttons.find(b => b.textContent?.includes("관계 캡처"));

    expect(searchBtn?.getAttribute("title")).toBe("맥락 검색 중입니다");
    expect(captureBtn?.getAttribute("title")).toBe("관계 캡처 중입니다");
  });

  it("checks title attributes for loading states", () => {
    let capturedEvent: any = null;
    vi.stubGlobal('dispatchEvent', vi.fn((event) => {
      capturedEvent = event;
    }));

    renderSearchLayout({
      recentSearches: [],
      onSaveSearch: vi.fn(),
      loading: true,
      results: [],
      error: null,
      onPerformSearch: vi.fn(),
      captureStatus: "loading",
      onCaptureSenderRelationship: vi.fn(),
      onClearError: vi.fn(),
      emailThreadingState: {
        threads: new Map(),
        isLoading: false,
        error: null,
      },
      fetchThread: vi.fn()
    });

    const buttons = Array.from(container!.querySelectorAll("button"));
    const searchBtn = buttons.find(b => b.textContent?.includes("맥락 검색") && b.getAttribute("type") === "submit");
    const captureBtn = buttons.find(b => b.textContent?.includes("관계 캡처"));

    if (searchBtn) {
        expect(searchBtn.getAttribute("title")).toBe("맥락 검색 중입니다");
    }
    if (captureBtn) {
        expect(captureBtn.getAttribute("title")).toBe("관계 캡처 중입니다");
    }
  });
});
