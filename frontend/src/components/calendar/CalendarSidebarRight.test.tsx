/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
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

const mockEvent: CalendarDetailEvent = {
  id: "1",
  calendarId: "cal-1",
  dayIndex: 1,
  title: "Meeting",
  source: "CalDAV",
  badgeLabel: "Work",
  badgeClassName: "bg-blue-100",
  dotClassName: "bg-blue-500",
  time: "10:00",
  duration: "1h",
  location: "Room A",
  description: "Discuss project",
  monthClassName: "bg-blue-50",
};

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
      root?.render(
        <CalendarSidebarRight
          selectedDetailEvent={null}
          isWritebackDisabled={false}
          onRequestUpdate={vi.fn()}
        />,
      );
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("표시 중인 일정 없음");

    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(1);
    const editBtn = container.querySelector('button[aria-label="일정 수정 점검"]');
    expect((editBtn as HTMLButtonElement)?.disabled).toBe(true);
  });

  it("requests an update only when the selected event is writable", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    const onRequestUpdate = vi.fn();
    await act(async () => {
      root?.render(
        <CalendarSidebarRight
          selectedDetailEvent={mockEvent}
          isWritebackDisabled={false}
          onRequestUpdate={onRequestUpdate}
        />,
      );
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("Meeting (Naruon 2.0)");
    expect(container.textContent).toContain("Room A");

    const editBtn = container.querySelector('button[aria-label="Meeting 일정 수정 점검"]') as HTMLButtonElement;
    expect(editBtn.disabled).toBe(false);
    await act(async () => {
      editBtn.click();
    });
    expect(onRequestUpdate).toHaveBeenCalledOnce();

    await act(async () => {
      root?.render(
        <CalendarSidebarRight
          selectedDetailEvent={mockEvent}
          isWritebackDisabled
          onRequestUpdate={onRequestUpdate}
        />,
      );
    });
    await flushAsyncWork();

    const disabledEditBtn = container.querySelector('button[aria-label="Meeting 일정 수정 점검"]') as HTMLButtonElement;
    expect(disabledEditBtn.disabled).toBe(true);
    await act(async () => {
      disabledEditBtn.click();
    });
    expect(onRequestUpdate).toHaveBeenCalledOnce();
  });
});
