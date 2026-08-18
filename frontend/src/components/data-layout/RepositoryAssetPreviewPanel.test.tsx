/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { RepositoryAssetPreviewPanel } from "./RepositoryAssetPreviewPanel";
import type { RepositoryAssetPreview } from "./types";

function recognizedPreview(): RepositoryAssetPreview {
  return {
    asset_key: "asset_hwpx_recognized",
    asset_type: "email_attachment",
    preview_state: "recognized",
    parser_family: "hwpx",
    paragraph_texts: ["Quarterly decision record", "Approve the next action."],
    preview_text: "Quarterly decision record\n\nApprove the next action.",
    next_action: "read_recognized_text",
    error_code: null,
    provider_write_executed: false,
  };
}

function pendingPreview(): RepositoryAssetPreview {
  return {
    asset_key: "asset_hwpx_pending",
    asset_type: "email_attachment",
    preview_state: "pending",
    parser_family: "hwpx",
    paragraph_texts: [],
    preview_text: null,
    next_action: "wait_for_recognition",
    error_code: "hwpx_recognition_pending",
    provider_write_executed: false,
  };
}

function failedPreview(): RepositoryAssetPreview {
  return {
    asset_key: "asset_hwpx_failed",
    asset_type: "email_attachment",
    preview_state: "failed",
    parser_family: "hwpx",
    paragraph_texts: [],
    preview_text: null,
    next_action: "choose_another_file",
    error_code: "hwpx_recognition_failed",
    provider_write_executed: false,
  };
}

function unavailablePreview(): RepositoryAssetPreview {
  return {
    asset_key: "asset_unknown_preview",
    asset_type: "email_attachment",
    preview_state: "unavailable",
    parser_family: null,
    paragraph_texts: [],
    preview_text: null,
    next_action: "choose_another_file",
    error_code: "repository_asset_not_found",
    provider_write_executed: false,
  };
}

describe("RepositoryAssetPreviewPanel", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
  });

  function renderPanel(props: React.ComponentProps<typeof RepositoryAssetPreviewPanel>) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(<RepositoryAssetPreviewPanel {...props} />);
    });
  }

  it("shows recognized HWPX ordered paragraph text in the attachment view", () => {
    renderPanel({
      currentDetailText: "content and thread evidence ready",
      preview: recognizedPreview(),
    });

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("Quarterly decision record");
    expect(panel?.textContent).toContain("Approve the next action.");
    expect(panel?.textContent).not.toContain("본문이 없습니다");
    expect(container?.textContent).toContain("content and thread evidence ready");
  });

  it("tells the buyer to wait when HWPX recognition is still pending", () => {
    renderPanel({
      currentDetailText: "content extraction pending, canonical thread pending",
      preview: pendingPreview(),
    });

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("인식이 끝날 때까지 기다리거나 다른 파일을 선택하세요");
    expect(panel?.textContent).not.toContain("UEsDBAo");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
    expect(container?.textContent).toContain("content extraction pending, canonical thread pending");
    const refresh = panel?.querySelector('[aria-label="인식 결과 다시 확인"]');
    expect(refresh).not.toBeNull();
  });

  it("tells the buyer to choose another file when HWPX recognition failed", () => {
    renderPanel({
      currentDetailText: "content extraction pending",
      preview: failedPreview(),
    });

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("이 파일의 본문을 읽을 수 없습니다. 다른 파일을 선택하세요");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
    expect(container?.textContent).toContain("content extraction pending");
  });

  it("fails closed on unmatched preview 404 without replacing current content", () => {
    renderPanel({
      currentDetailText: "document status: uploaded",
      preview: unavailablePreview(),
    });

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("미리보기를 열 수 없습니다. 다른 파일을 선택하세요");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
    expect(container?.textContent).toContain("document status: uploaded");
    expect(container?.textContent).not.toContain("본문이 없습니다");
  });
});
