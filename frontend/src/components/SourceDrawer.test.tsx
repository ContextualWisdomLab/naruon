/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  ExternalLink: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  X: () => <svg aria-hidden="true" />,
}));

import { SourceDrawer } from "./SourceDrawer";

describe("SourceDrawer", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
  });

  it("uses a mobile bottom sheet and a desktop right-side drawer", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(
        <SourceDrawer
          open
          title="검토 메일"
          sourceLabel="원본 메일"
          sourceType="mail"
          sourceId="message-22"
          summary="근거 요약"
          onClose={vi.fn()}
        />,
      );
    });

    const dialog = container.querySelector<HTMLElement>("[role='dialog']");
    expect(dialog).not.toBeNull();
    expect(Array.from(dialog?.classList ?? [])).toEqual(expect.arrayContaining([
      "max-sm:bottom-0",
      "max-sm:inset-x-0",
      "max-sm:h-[85vh]",
      "max-sm:w-full",
      "max-sm:rounded-t-3xl",
      "sm:right-0",
      "sm:top-0",
      "sm:h-full",
      "sm:max-w-[440px]",
    ]));
  });
});
