/* @vitest-environment jsdom */
import React, { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { createRoot, type Root } from "react-dom/client";

import { CalendarCoordinationView } from "./CalendarCoordinationView";

describe("CalendarCoordinationView", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
  });

  it("renders date-correct proposal cards without inactive controls", () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(<CalendarCoordinationView />);
    });

    expect(container.textContent).toContain("회의 조율");
    expect(container.textContent).toContain("5월 23일 (토) 14:00 - 15:00");
    expect(container.textContent).toContain("5월 24일 (일) 10:00 - 11:00");
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });
});
