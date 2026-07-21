/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import {
  EmailSourceLineagePanel,
  type EmailSourceLineage,
} from "./EmailSourceLineagePanel";

const SHA256 = "a".repeat(64);

function lineage(
  productionTime: EmailSourceLineage["production_time"],
): EmailSourceLineage {
  return {
    schema_version: 1,
    source_kind: "rfc822",
    source_filename: "260101-customer-message.eml",
    raw_content_sha256: SHA256,
    production_time: productionTime,
    message_identity: {
      selected_source: "embedded_message_id",
      embedded_status: "embedded",
    },
  };
}

describe("EmailSourceLineagePanel", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
  });

  function render(value: EmailSourceLineage, displayedDate?: string) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(
        <EmailSourceLineagePanel lineage={value} displayedDate={displayedDate} />,
      );
    });
  }

  it("shows the embedded Date as production evidence and preserves precedence", () => {
    render(
      lineage({
        selected_value: "2026-01-02T03:04:05Z",
        selected_source: "embedded_date_header",
        embedded_status: "parsed",
        evidence_precedence: [
          "embedded_metadata",
          "explicit_filename_date",
          "filesystem_created_at",
          "filesystem_modified_at",
        ],
      }),
      "2026-07-20T00:00:00Z",
    );

    expect(container?.querySelector('section[aria-label="원본 계보"]')).not.toBeNull();
    expect(container?.textContent).toContain("내장 Date 헤더 확인");
    expect(container?.textContent).toContain("내장 Date 헤더");
    expect(container?.textContent).toContain("260101-customer-message.eml");
    expect(container?.textContent).toContain(SHA256);
    expect(container?.textContent).not.toContain("저장용 fallback");

    const lineageEyebrow = Array.from(container?.querySelectorAll("p") ?? []).find(
      (element) => element.textContent === "Data lineage",
    );
    expect(lineageEyebrow?.classList.contains("dark:text-sky-300")).toBe(true);

    const statusBadge = Array.from(container?.querySelectorAll("span") ?? []).find(
      (element) => element.textContent === "내장 Date 헤더 확인",
    );
    expect(statusBadge?.classList.contains("dark:text-sky-300")).toBe(true);

    const precedence = container?.querySelector(
      'ol[aria-label="생산 시점 증거 우선순위"]',
    )?.textContent;
    expect(precedence).toContain("1. 내장 메타데이터");
    expect(precedence).toContain("2. 명시적 파일명 날짜 (검토 필요)");
    expect(precedence).toContain("3. 파일시스템 생성일");
    expect(precedence).toContain("4. 파일시스템 수정일");
  });

  it("labels the display timestamp and filename date as non-production evidence", () => {
    const value = lineage({
      selected_value: null,
      selected_source: null,
      embedded_status: "invalid",
      evidence_precedence: [
        "embedded_metadata",
        "explicit_filename_date",
        "filesystem_created_at",
        "filesystem_modified_at",
      ],
    });
    value.message_identity = {
      selected_source: "raw_content_sha256",
      embedded_status: "invalid",
    };

    render(value, "2026-07-20T00:00:00Z");

    expect(container?.textContent).toContain("내장 Date 헤더 해석 불가");
    expect(container?.textContent).toContain("확정된 내장 생산 시점 없음");
    expect(container?.textContent).toContain("저장용 fallback이며 생산일 근거가 아닙니다");
    expect(container?.textContent).toContain("파일명 날짜도 자동 승격하지 않습니다");
    expect(container?.textContent).toContain("원본 바이트 SHA-256");

    const fallbackWarning = Array.from(container?.querySelectorAll("p") ?? []).find(
      (element) => element.textContent?.includes("저장용 fallback"),
    );
    expect(fallbackWarning?.classList.contains("dark:text-amber-200")).toBe(true);
  });

  it("does not confirm internally inconsistent embedded evidence", () => {
    const value = lineage({
      selected_value: null,
      selected_source: null,
      embedded_status: "parsed",
      evidence_precedence: [
        "embedded_metadata",
        "explicit_filename_date",
        "filesystem_created_at",
        "filesystem_modified_at",
      ],
    });
    value.message_identity = {
      selected_source: "embedded_message_id",
      embedded_status: "invalid",
    };

    render(value);

    expect(container?.textContent).not.toContain("내장 Date 헤더 확인");
    expect(container?.textContent).toContain("내장 Date 헤더 근거 불완전");
    expect(container?.textContent).not.toContain("내장 Message-ID");
    expect(container?.textContent).toContain("Message-ID 근거 불완전");
  });
});
