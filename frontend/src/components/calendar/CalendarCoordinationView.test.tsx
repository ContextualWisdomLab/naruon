/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { CalendarCoordinationView } from "./CalendarCoordinationView";
import { calendarCoordinationProposals } from "./constants";
import { formatCoordinationProposalLabel } from "./helpers";

describe("CalendarCoordinationView", () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  afterEach(() => {
    root?.unmount();
    container?.remove();
    root = null;
    container = null;
  });

  it("renders date, weekday, and aria-label from the same proposal instants", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(<CalendarCoordinationView />);
    });

    const buttons = Array.from(container.querySelectorAll("button"));
    expect(buttons).toHaveLength(calendarCoordinationProposals.length);

    calendarCoordinationProposals.forEach((proposal, index) => {
      const slotLabel = formatCoordinationProposalLabel(proposal.startsAt, proposal.endsAt);
      const button = buttons[index];
      expect(button.textContent).toContain(slotLabel);
      expect(button.getAttribute("aria-label")).toBe(
        `${proposal.rankLabel} 제안하기: ${slotLabel}, ${proposal.availability}`,
      );
    });
    expect(container.textContent).not.toContain("5월 23일 (목)");
    expect(container.textContent).not.toContain("5월 24일 (금)");
  });
});
