import React from 'react';
import { toSafeReactText } from '@/lib/safe-text';
import type { RepositoryAssetPreview } from './types';
import {
  getInkspanEditHandoffUnavailableReason,
  getRepositoryAssetPreviewCopy,
  isRecognizedRepositoryAssetPreview,
} from './utils';

type RepositoryAssetPreviewPanelProps = {
  currentDetailText: string;
  preview: RepositoryAssetPreview | null;
  fileName?: string;
};

/** Render recognized HWPX text, or an explicit next action when text is missing. */
export function RepositoryAssetPreviewPanel({
  currentDetailText,
  preview,
  fileName,
}: RepositoryAssetPreviewPanelProps) {
  const copy = preview
    ? getRepositoryAssetPreviewCopy(preview)
    : {
        next_action_label: '미리보기를 확인하는 중입니다.',
        status_label: '미리보기 확인',
      };
  const recognized = isRecognizedRepositoryAssetPreview(preview);
  const editHandoff = preview?.edit_handoff ?? null;
  const handoffFileName = toSafeReactText(fileName || '선택한 파일');

  return (
    <section aria-label="선택한 자산 본문 미리보기" className="mt-5 border-t border-border pt-4">
      <p className="text-xs font-black text-muted-foreground">{copy.status_label}</p>
      {recognized ? (
        <ol data-preview-paragraphs className="mt-3 grid gap-3">
          {preview.paragraph_texts.map((paragraph, index) => (
            <li
              key={`${preview.asset_key}:${index}`}
              className="whitespace-pre-wrap break-words text-sm font-semibold text-foreground"
            >
              {toSafeReactText(paragraph)}
            </li>
          ))}
        </ol>
      ) : (
        <p role="status" className="mt-2 text-sm font-semibold text-muted-foreground">
          {copy.next_action_label}
        </p>
      )}
      {editHandoff ? (
        <div className="mt-4 space-y-2">
          <button
            type="button"
            disabled
            aria-disabled="true"
            aria-label={`${handoffFileName} Inkspan에서 편집`}
            aria-describedby="inkspan-edit-handoff-status"
            className="rounded-xl border border-border bg-muted px-3 py-2 text-sm font-semibold text-muted-foreground"
          >
            Inkspan에서 편집
          </button>
          <p
            id="inkspan-edit-handoff-status"
            role="status"
            className="text-sm font-semibold text-muted-foreground"
          >
            {getInkspanEditHandoffUnavailableReason(editHandoff.error_code)}
          </p>
        </div>
      ) : null}
      <p className="mt-3 break-words text-xs font-semibold text-muted-foreground">
        {toSafeReactText(currentDetailText)}
      </p>
    </section>
  );
}
