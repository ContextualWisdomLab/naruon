import React from 'react';
import { toSafeReactText } from '@/lib/safe-text';
import type { RepositoryAssetPreview } from './types';
import {
  getRepositoryAssetPreviewCopy,
  isRecognizedRepositoryAssetPreview,
} from './utils';

type RepositoryAssetPreviewPanelProps = {
  currentDetailText: string;
  preview: RepositoryAssetPreview | null;
  onRefreshPreview?: () => void;
};

/** Render recognized HWPX text, or an explicit next action when text is missing. */
export function RepositoryAssetPreviewPanel({
  currentDetailText,
  preview,
  onRefreshPreview,
}: RepositoryAssetPreviewPanelProps) {
  const copy = preview
    ? getRepositoryAssetPreviewCopy(preview)
    : {
        next_action_label: '미리보기를 확인하는 중입니다.',
        status_label: '미리보기 확인',
      };
  const recognized = isRecognizedRepositoryAssetPreview(preview);

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
      {preview?.preview_state === 'pending' ? (
        <button
          type="button"
          aria-label="인식 결과 다시 확인"
          onClick={onRefreshPreview}
          className="mt-3 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-black text-foreground"
        >
          다시 확인
        </button>
      ) : null}
      <p className="mt-3 break-words text-xs font-semibold text-muted-foreground">
        {toSafeReactText(currentDetailText)}
      </p>
    </section>
  );
}
