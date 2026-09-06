/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MailAttachmentPreview } from "./MailAttachmentPreview";
import type { MailAttachmentRef } from "@/lib/email-threading";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function flushAsyncWork() {
  for (let index = 0; index < 5; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

const recognizedAttachment: MailAttachmentRef = {
  asset_key: "asset_mail_hwpx_recognized",
  file_name: "decision.hwpx",
  parser_family: "hwpx",
};

describe("MailAttachmentPreview", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.unstubAllGlobals();
  });

  function renderPreview(attachments: MailAttachmentRef[]) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(<MailAttachmentPreview attachments={attachments} />);
    });
  }

  it("opens recognized HWPX ordered paragraphs from the selected mail attachment", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/data/repository-assets/asset_mail_hwpx_recognized/preview")) {
        return Promise.resolve(jsonResponse({
          asset_key: "asset_mail_hwpx_recognized",
          asset_type: "email_attachment",
          preview_state: "recognized",
          parser_family: "hwpx",
          paragraph_texts: ["Quarterly decision record", "Approve the next action."],
          preview_text: "Quarterly decision record\n\nApprove the next action.",
          next_action: "read_recognized_text",
          error_code: null,
          provider_write_executed: false,
        }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPreview([recognizedAttachment]);

    const openButton = Array.from(container?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent?.includes("decision.hwpx"),
    );
    expect(openButton).toBeDefined();
    expect(container?.textContent).toContain("첨부에서 파일을 선택하면 인식된 본문을 읽습니다");

    await act(async () => {
      openButton?.click();
    });
    await flushAsyncWork();

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain(
      "/api/data/repository-assets/asset_mail_hwpx_recognized/preview",
    );
    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("Quarterly decision record");
    expect(panel?.textContent).toContain("Approve the next action.");
    expect(panel?.textContent).toContain("인식된 본문");
    expect(container?.textContent).not.toContain("본문이 없습니다");
    expect(container?.textContent).not.toContain("asset_mail_hwpx_recognized");
    expect(container?.textContent).not.toContain("99");
  });

  it("tells the buyer to wait when mail HWPX recognition is still pending", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/data/repository-assets/asset_mail_hwpx_pending/preview")) {
        return Promise.resolve(jsonResponse({
          asset_key: "asset_mail_hwpx_pending",
          asset_type: "email_attachment",
          preview_state: "pending",
          parser_family: "hwpx",
          paragraph_texts: [],
          preview_text: null,
          next_action: "wait_for_recognition",
          error_code: "hwpx_recognition_pending",
          provider_write_executed: false,
        }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    renderPreview([{
      asset_key: "asset_mail_hwpx_pending",
      file_name: "pending.hwpx",
      parser_family: "hwpx",
    }]);

    await act(async () => {
      Array.from(container?.querySelectorAll("button") ?? []).find(
        (button) => button.textContent?.includes("pending.hwpx"),
      )?.click();
    });
    await flushAsyncWork();

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("인식이 끝날 때까지 기다리거나 다른 파일을 선택하세요");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
    expect(container?.textContent).not.toContain("본문이 없습니다");
  });

  it("tells the buyer to choose another file when mail HWPX preview failed", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/data/repository-assets/asset_mail_hwpx_failed/preview")) {
        return Promise.resolve(jsonResponse({
          asset_key: "asset_mail_hwpx_failed",
          asset_type: "email_attachment",
          preview_state: "failed",
          parser_family: "hwpx",
          paragraph_texts: [],
          preview_text: null,
          next_action: "choose_another_file",
          error_code: "hwpx_recognition_failed",
          provider_write_executed: false,
        }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    renderPreview([{
      asset_key: "asset_mail_hwpx_failed",
      file_name: "failed.hwpx",
      parser_family: "hwpx",
    }]);

    await act(async () => {
      Array.from(container?.querySelectorAll("button") ?? []).find(
        (button) => button.textContent?.includes("failed.hwpx"),
      )?.click();
    });
    await flushAsyncWork();

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("이 파일의 본문을 읽을 수 없습니다. 다른 파일을 선택하세요");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
  });

  it("fails closed on unmatched preview 404 without leaking existence", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/data/repository-assets/asset_missing_mail_preview/preview")) {
        return Promise.resolve(jsonResponse({
          detail: { error_code: "repository_asset_not_found" },
        }, 404));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    renderPreview([{
      asset_key: "asset_missing_mail_preview",
      file_name: "missing.hwpx",
      parser_family: "hwpx",
    }]);

    await act(async () => {
      Array.from(container?.querySelectorAll("button") ?? []).find(
        (button) => button.textContent?.includes("missing.hwpx"),
      )?.click();
    });
    await flushAsyncWork();

    const panel = container?.querySelector('[aria-label="선택한 자산 본문 미리보기"]');
    expect(panel?.textContent).toContain("미리보기를 열 수 없습니다. 다른 파일을 선택하세요");
    expect(panel?.querySelector("[data-preview-paragraphs]")).toBeNull();
    expect(container?.textContent).not.toContain("repository_asset_not_found");
    expect(container?.textContent).not.toContain("본문이 없습니다");
  });

  it("keeps the latest recognized preview when an older pending response arrives late", async () => {
    let resolveFirst!: (response: Response) => void;
    let resolveSecond!: (response: Response) => void;
    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const secondResponse = new Promise<Response>((resolve) => {
      resolveSecond = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(firstResponse)
      .mockReturnValueOnce(secondResponse);
    vi.stubGlobal("fetch", fetchMock);

    renderPreview([recognizedAttachment]);
    const openButton = Array.from(container?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent?.includes("decision.hwpx"),
    );
    expect(openButton).toBeDefined();

    await act(async () => {
      openButton?.click();
    });
    await act(async () => {
      openButton?.click();
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveSecond(jsonResponse({
        asset_key: "asset_mail_hwpx_recognized",
        asset_type: "email_attachment",
        preview_state: "recognized",
        parser_family: "hwpx",
        paragraph_texts: ["Latest recognized paragraph"],
        preview_text: "Latest recognized paragraph",
        next_action: "read_recognized_text",
        error_code: null,
        provider_write_executed: false,
      }));
    });
    await flushAsyncWork();
    expect(container?.textContent).toContain("Latest recognized paragraph");

    await act(async () => {
      resolveFirst(jsonResponse({
        asset_key: "asset_mail_hwpx_recognized",
        asset_type: "email_attachment",
        preview_state: "pending",
        parser_family: "hwpx",
        paragraph_texts: [],
        preview_text: null,
        next_action: "wait_for_recognition",
        error_code: "hwpx_recognition_pending",
        provider_write_executed: false,
      }));
    });
    await flushAsyncWork();

    expect(container?.textContent).toContain("Latest recognized paragraph");
    expect(container?.textContent).not.toContain("인식이 끝날 때까지 기다리거나 다른 파일을 선택하세요");
  });

  it("renders nothing when the selected mail has no attachments", () => {
    renderPreview([]);
    expect(container?.querySelector('[aria-label="메일 첨부 파일"]')).toBeNull();
    expect(container?.textContent).toBe("");
  });
});
