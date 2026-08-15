import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { DocumentRepositoryTab } from './DocumentRepositoryTab';

const workspaceDocument = {
  asset_key: 'workspace-document-1',
  asset_type: 'workspace_document',
  display_name: '운영 계약.md',
  source_label: '로컬 문서',
  state_code: 'ready',
  detail_text: '검토 가능한 문서 근거',
  content_chars: 128,
  captured_at: '2026-08-15T09:00:00+09:00',
  evidence_source: 'workspace_document',
  thread_key: 'thread-1',
  provider_write_executed: false,
};

function renderRepository(activeDocumentAction: string | null) {
  return renderToStaticMarkup(
    <DocumentRepositoryTab
      {...({
        writebackStatus: 'idle',
        writebackResult: null,
        requestWebdavWritebackIntent: () => undefined,
        isWritebackLoading: false,
        canRequestWebdavWriteback: true,
        selectedWebdavAccount: {
          source_id: 'webdav-1',
          display_label: '업무 문서',
          writeback_enabled: true,
        },
        isWebdavSourceLoading: false,
        setSelectedWebdavSourceId: () => undefined,
        uniqueThreadStatus: 'idle',
        uniqueThreadResult: null,
        requestUniqueThreadIntent: () => undefined,
        isUniqueThreadLoading: false,
        connectorEvents: [],
        dataSurfaceStatus: 'ready',
        dataQualitySurface: null,
        embeddingStage: null,
        emailRepository: null,
        attachmentRepository: null,
        handleEmailImportFileChange: () => undefined,
        requestEmailFileImport: () => undefined,
        isEmailImportLoading: false,
        emailImportFiles: [],
        emailImportStatus: 'idle',
        emailImportResult: null,
        handleDocumentFileChange: () => undefined,
        requestDocumentUpload: () => undefined,
        isDocumentActionLoading: true,
        activeDocumentAction,
        documentUploadFiles: [],
        documentActionStatus: 'loading',
        documentActionResult: null,
        webdavAccountStatus: 'ready',
        webdavAccounts: [{
          source_id: 'webdav-1',
          display_label: '업무 문서',
          writeback_enabled: true,
        }],
        webdavAccountMap: new Map(),
        projectFolders: [],
        selectedRepositoryAssetKey: workspaceDocument.asset_key,
        setSelectedRepositoryAssetKey: () => undefined,
        repositoryAssets: [workspaceDocument],
        selectedWorkspaceDocument: workspaceDocument,
        requestDocumentAction: () => undefined,
      } as never)}
    />,
  );
}

function getActionButtonTag(markup: string, action: string) {
  const match = markup.match(
    new RegExp(`<button[^>]*data-document-action="${action}"[^>]*>`),
  );
  if (!match) {
    throw new Error(`missing rendered button for ${action}`);
  }
  return match[0];
}

describe('DocumentRepositoryTab action busy identity', () => {
  it('marks only the initiating document action as busy', () => {
    const markup = renderRepository('reparse');

    expect(getActionButtonTag(markup, 'reparse')).toContain('aria-busy="true"');
    expect(getActionButtonTag(markup, 'embedding-regeneration-intent')).toContain('aria-busy="false"');
    expect(getActionButtonTag(markup, 'hwp-conversion-intent')).toContain('aria-busy="false"');
    expect(getActionButtonTag(markup, 'webdav-materialization-intent')).toContain('aria-busy="false"');
    expect(getActionButtonTag(markup, 'upload')).toContain('aria-busy="false"');
  });
});
