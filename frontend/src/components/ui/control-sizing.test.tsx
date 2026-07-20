/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { Button } from "./button";
import { Input } from "./input";
import { Textarea } from "./textarea";

describe("brand control sizing", () => {
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

  it("uses guide-aligned default control heights and radii", () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <>
          <Button>버튼</Button>
          <Input aria-label="메일" />
          <Textarea aria-label="답장" />
        </>,
      );
    });

    expect(container.querySelector("button")?.className).toContain("h-10");
    expect(container.querySelector("input")?.className).toContain("h-10");
    expect(container.querySelector("textarea")?.className).toContain("min-h-24");
  });
});
