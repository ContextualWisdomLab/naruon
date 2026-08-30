/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { CalendarSidebarRight } from "./CalendarSidebarRight";
import type { CalendarDetailEvent } from "./types";

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("CalendarSidebarRight", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) {
      act(() => root?.unmount());
    }
    root = null;
    container?.remove();
    container = null;
  });

  it("renders correctly with no event", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CalendarSidebarRight selectedDetailEvent={null} />);
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("표시 중인 일정 없음");

    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(5);

    const deleteBtn = container.querySelector('button[aria-label="일정 삭제"]');
    expect((deleteBtn as HTMLButtonElement)?.disabled).toBe(true);

    const copyBtn = container.querySelector('button[aria-label="일정 복사"]');
    expect((copyBtn as HTMLButtonElement)?.disabled).toBe(true);

    const editBtn = container.querySelector('button[aria-label="일정 수정"]');
    expect((editBtn as HTMLButtonElement)?.disabled).toBe(true);
  });

  it("renders correctly with an event", async () => {
    const mockEvent: CalendarDetailEvent = {
      id: "1",
      calendarId: "cal-1",
      title: "Meeting",
      badgeLabel: "Work",
      badgeClassName: "bg-blue-100",
      dotClassName: "bg-blue-500",
      time: "10:00",
      duration: "1h",
      location: "Room A",
      description: "Discuss project",
    };

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CalendarSidebarRight selectedDetailEvent={mockEvent} />);
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("Meeting (Naruon 2.0)");
    expect(container.textContent).toContain("Room A");

    const deleteBtn = container.querySelector('button[aria-label="Meeting 일정 삭제"]');
    expect((deleteBtn as HTMLButtonElement)?.disabled).toBe(false);

    const copyBtn = container.querySelector('button[aria-label="Meeting 일정 복사"]');
    expect((copyBtn as HTMLButtonElement)?.disabled).toBe(false);

    const editBtn = container.querySelector('button[aria-label="Meeting 일정 수정"]');
    expect((editBtn as HTMLButtonElement)?.disabled).toBe(false);
  });
});
