/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { DecisionPointCard } from "./DecisionPointCard";
import {
  EVIDENCE_MISSING_LABEL,
  EXECUTION_BLOCKED_LABEL,
  EXECUTION_INTENT_ONLY_LABEL,
  LOW_CONFIDENCE_LABEL,
  MISSING_CONFIDENCE_LABEL,
} from "@/lib/confidence";

describe("DecisionPointCard analysis contract", () => {
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

  function renderCard(ui: React.ReactElement) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(ui);
    });
    return container;
  }

  it("normalizes 1 and 1.01 to the same 100% scale and does not show 1%", () => {
    const first = renderCard(
      <DecisionPointCard title="판단 포인트" showConfidence confidence={1}>
        합성 결과
      </DecisionPointCard>,
    );
    expect(first.textContent).toContain("신뢰도 100%");
    expect(first.textContent).not.toContain("신뢰도 1%");

    act(() => {
      root?.render(
        <DecisionPointCard title="판단 포인트" showConfidence confidence={1.01}>
          합성 결과
        </DecisionPointCard>,
      );
    });
    expect(first.textContent).toContain("신뢰도 100%");
    expect(first.textContent).not.toContain("신뢰도 1%");
  });

  it("keeps 0, 0.5, and 50 on one display scale", () => {
    const node = renderCard(
      <DecisionPointCard title="판단 포인트" showConfidence confidence={0}>
        합성 결과
      </DecisionPointCard>,
    );
    expect(node.textContent).toContain("신뢰도 0%");
    expect(node.textContent).toContain(LOW_CONFIDENCE_LABEL);

    act(() => {
      root?.render(
        <DecisionPointCard title="판단 포인트" showConfidence confidence={0.5}>
          합성 결과
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain("신뢰도 50%");
    expect(node.textContent).not.toContain(LOW_CONFIDENCE_LABEL);

    act(() => {
      root?.render(
        <DecisionPointCard title="판단 포인트" showConfidence confidence={50}>
          합성 결과
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain("신뢰도 50%");
  });

  it("shows 신뢰도 미제공, empty, error, and low-confidence as distinct states", () => {
    const node = renderCard(
      <DecisionPointCard title="맥락 종합" showConfidence>
        합성 결과
      </DecisionPointCard>,
    );
    expect(node.textContent).toContain(MISSING_CONFIDENCE_LABEL);
    expect(node.querySelector('[data-analysis-state="ready"]')).not.toBeNull();

    act(() => {
      root?.render(
        <DecisionPointCard title="맥락 종합" empty emptyMessage="맥락 종합이 없습니다.">
          hidden
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain("맥락 종합이 없습니다.");
    expect(node.querySelector('[role="alert"]')).toBeNull();
    expect(node.querySelector('[data-analysis-state="empty"]')).not.toBeNull();

    act(() => {
      root?.render(
        <DecisionPointCard title="맥락 종합" error="맥락 종합을 생성하지 못했습니다.">
          hidden
        </DecisionPointCard>,
      );
    });
    expect(node.querySelector('[role="alert"]')?.textContent).toContain(
      "맥락 종합을 생성하지 못했습니다.",
    );
    expect(node.textContent).not.toContain("맥락 종합이 없습니다.");
    expect(node.querySelector('[data-analysis-state="error"]')).not.toBeNull();

    act(() => {
      root?.render(
        <DecisionPointCard title="맥락 종합" showConfidence confidence={0.42}>
          낮은 확신 합성
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain("신뢰도 42%");
    expect(node.textContent).toContain(LOW_CONFIDENCE_LABEL);
    expect(node.querySelector('[data-confidence-state="low"]')).not.toBeNull();
  });

  it("shows 근거 없음 when evidence is missing and blocked or intent-only when no next action", () => {
    const node = renderCard(
      <DecisionPointCard title="판단 포인트" evidenceMissing>
        판단
      </DecisionPointCard>,
    );
    expect(node.textContent).toContain(EVIDENCE_MISSING_LABEL);
    expect(node.querySelector('[data-evidence-state="missing"]')).not.toBeNull();

    act(() => {
      root?.render(
        <DecisionPointCard
          title="실행 항목"
          empty
          emptyMessage="실행 항목이 없습니다."
          executionState="blocked"
        >
          hidden
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain("실행 항목이 없습니다.");
    expect(node.textContent).toContain(EXECUTION_BLOCKED_LABEL);
    expect(node.querySelector('[data-execution-state="blocked"]')).not.toBeNull();

    act(() => {
      root?.render(
        <DecisionPointCard title="실행 항목" executionState="intent-only">
          일정 반영 의도
        </DecisionPointCard>,
      );
    });
    expect(node.textContent).toContain(EXECUTION_INTENT_ONLY_LABEL);
    expect(node.querySelector('[data-execution-state="intent-only"]')).not.toBeNull();
  });
});
