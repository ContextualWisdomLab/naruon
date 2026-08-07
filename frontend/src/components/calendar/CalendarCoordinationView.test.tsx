/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { CalendarCoordinationView } from "./CalendarCoordinationView";

describe("CalendarCoordinationView", () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  afterEach(() => {
    if (root && container) {
      act(() => {
        root!.unmount();
      });
      container.remove();
    }
    container = null;
    root = null;
  });

  it("renders buttons with distinct accessible names including date and attendance", () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root!.render(<CalendarCoordinationView />);
    });

    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(2);

    // Assert focus class
    buttons.forEach((btn) => {
      expect(btn.className).toContain("focus-visible:ring-2");
    });

    // Check sr-only span content within buttons to ensure computed accessible name contains it
    const button1 = buttons[0];
    const button2 = buttons[1];

    expect(button1.textContent).toContain("1안 제안하기:");
    expect(button1.textContent).toContain("5월 23일 (목) 14:00 - 15:00");
    expect(button1.textContent).toContain("모든 참석자 참석 가능");

    expect(button2.textContent).toContain("2안 제안하기:");
    expect(button2.textContent).toContain("5월 24일 (금) 10:00 - 11:00");
    expect(button2.textContent).toContain("1명(김개발) 불참 예상");

    // Check aria-hidden on decorative elements
    const ariaHiddenElements = container.querySelectorAll('[aria-hidden="true"]');
    // There are 2 option badges (1안, 2안) + 2 propose labels (제안하기) = 4
    expect(ariaHiddenElements).toHaveLength(4);

    // verify option labels are aria-hidden
    expect(Array.from(ariaHiddenElements).some(el => el.textContent === '1안')).toBe(true);
    expect(Array.from(ariaHiddenElements).some(el => el.textContent === '2안')).toBe(true);

    // verify propose labels are aria-hidden
    const proposeLabels = Array.from(ariaHiddenElements).filter(el => el.textContent === '제안하기');
    expect(proposeLabels).toHaveLength(2);
  });
});
