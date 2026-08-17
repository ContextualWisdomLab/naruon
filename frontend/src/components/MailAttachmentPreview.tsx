import React, { useState } from 'react';
import { apiClient } from '@/lib/api-client';
import type { MailAttachmentRef } from '@/lib/email-threading';
import { toMailDisplayText } from '@/lib/mail-text';
import { RepositoryAssetPreviewPanel } from '@/components/data-layout/RepositoryAssetPreviewPanel';
import type { RepositoryAssetPreview, RepositoryAssetPreviewNextAction } from '@/components/data-layout/types';
import { getApiErrorStatus } from '@/components/data-layout/utils';

type MailAttachmentPreviewProps = {
  attachments: MailAttachmentRef[];
};

function unavailablePreview(assetKey: string): RepositoryAssetPreview {
  return {
    asset_key: assetKey,
    asset_type: 'email_attachment',
    preview_state: 'unavailable',
    parser_family: null,
    paragraph_texts: [],
    preview_text: null,
    next_action: 'choose_another_file' satisfies RepositoryAssetPreviewNextAction,
    error_code: 'repository_asset_not_found',
    provider_write_executed: false,
  };
}

/** Open one mail attachment through the existing read-only repository preview. */
export function MailAttachmentPreview({ attachments }: MailAttachmentPreviewProps) {
  const [selectedAssetKey, setSelectedAssetKey] = useState<string | null>(null);
  const [previewByKey, setPreviewByKey] = useState<Record<string, RepositoryAssetPreview>>({});

  if (attachments.length === 0) {
    return null;
  }

  const selectedAttachment = attachments.find((attachment) => attachment.asset_key === selectedAssetKey) ?? null;
  const selectedPreview = selectedAttachment
    ? previewByKey[selectedAttachment.asset_key] ?? null
    : null;

  const openAttachment = async (attachment: MailAttachmentRef) => {
    setSelectedAssetKey(attachment.asset_key);
    try {
      const preview = await apiClient.get<RepositoryAssetPreview>(
        `/api/data/repository-assets/${encodeURIComponent(attachment.asset_key)}/preview`,
      );
      setPreviewByKey((current) => ({ ...current, [attachment.asset_key]: preview }));
    } catch (error: unknown) {
      setPreviewByKey((current) => {
        const existing = current[attachment.asset_key];
        if (existing?.preview_state === 'recognized') {
          return current;
        }
        return { ...current, [attachment.asset_key]: unavailablePreview(attachment.asset_key) };
      });
      void getApiErrorStatus(error);
    }
  };

  return (
    <section aria-label="메일 첨부 파일" className="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div>
        <h3 className="text-sm font-bold text-foreground">첨부 파일</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          첨부에서 파일을 선택하면 인식된 본문을 읽습니다. 인식이 끝나지 않았으면 기다리거나 다른 파일을 선택하세요.
        </p>
      </div>
      <ul className="grid gap-2">
        {attachments.map((attachment) => {
          const selected = selectedAssetKey === attachment.asset_key;
          return (
            <li key={attachment.asset_key}>
              <button
                type="button"
                aria-pressed={selected}
                aria-label={`${toMailDisplayText(attachment.file_name, '첨부 파일')} 인식된 본문 열기`}
                onClick={() => void openAttachment(attachment)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                  selected ? 'border-primary bg-primary/5 text-foreground' : 'border-border bg-background text-foreground hover:border-primary/40'
                }`}
              >
                {toMailDisplayText(attachment.file_name, '첨부 파일')}
              </button>
            </li>
          );
        })}
      </ul>
      {selectedAttachment ? (
        <RepositoryAssetPreviewPanel
          currentDetailText={selectedAttachment.file_name}
          preview={selectedPreview}
        />
      ) : null}
    </section>
  );
}
