import {
  SurfaceStatusCode,
  QualityStatusCode,
  WebdavAccount,
  WebdavAccountLookup,
  WebdavWritebackIntentResponse,
  DataQualitySurfaceResponse,
  RepositoryAssetPreview,
  RepositoryAssetPreviewNextAction,
  RepositoryAssetPreviewState,
} from './types';

export function getApiErrorStatus(error: unknown) {
  const shapedError = error as { status?: unknown; response?: { status?: unknown } } | null;
  if (typeof shapedError?.status === 'number') return shapedError.status;
  if (typeof shapedError?.response?.status === 'number') return shapedError.response.status;
  return null;
}

export function getSafeErrorSummary(error: unknown) {
  const status = getApiErrorStatus(error);
  const errorName = error instanceof Error ? error.name : typeof error;
  return { status, error_name: errorName.slice(0, 40) };
}

export function formatCount(value: number) {
  return new Intl.NumberFormat('ko-KR').format(value);
}

export function formatDataTimestamp(value: string | null | undefined) {
  if (!value) return '기록 없음';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '기록 없음';
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

export function getSurfaceStatusLabel(status: SurfaceStatusCode | QualityStatusCode) {
  switch (status) {
    case 'ready':
    case 'pass':
      return '정상';
    case 'running':
      return '진행 중';
    case 'needs_attention':
      return '점검 필요';
    case 'pending':
      return '대기';
    case 'no_source':
      return '원본 없음';
    default:
      return '대기';
  }
}

export function getWriteBoundaryLabel(providerWriteExecuted: boolean) {
  return providerWriteExecuted ? '외부 쓰기 실행됨' : '의도만 기록';
}

export function getAssetEvidenceLabel(asset: DataQualitySurfaceResponse['repository_assets'][number]) {
  if (asset.asset_type === 'workspace_document') return '워크스페이스 문서 근거';
  if (asset.content_chars === 0) return '본문 추출 대기';
  return '원본 메일/스레드 근거 연결';
}

export function getDocumentTypeForFile(file: File) {
  const filename = file.name.toLowerCase();
  if (filename.endsWith('.md') || filename.endsWith('.markdown')) return 'text/markdown';
  if (filename.endsWith('.hwp')) return 'application/x-hwp';
  return file.type || 'text/plain';
}

export function isTextDocumentUploadType(documentType: string) {
  return documentType.startsWith('text/');
}

export function getSourceReadinessLabel(account: { writeback_enabled: boolean; etag?: string | null }) {
  if (!account.writeback_enabled) return '읽기 전용';
  return account.etag ? '쓰기 가능 · 충돌 검사용 ETag 준비' : '쓰기 가능 · ETag 확인 필요';
}

export function getWebdavAccountLabel(account: WebdavAccount, index: number) {
  const label = account.display_label.trim();
  if (!label || label.includes(account.source_id) || /^WebDAV source/i.test(label)) {
    return `WebDAV 저장소 ${index + 1}`;
  }
  return label;
}

export function getWritebackTargetLabel(
  result: WebdavWritebackIntentResponse,
  accountMap: WebdavAccountLookup,
) {
  const mapped = result.source_id ? accountMap.get(result.source_id) : undefined;
  if (mapped) {
    return getWebdavAccountLabel(mapped.account, mapped.index);
  }

  const label = result.target_label?.trim();
  if (!label || (result.source_id && label.includes(result.source_id)) || /^WebDAV source/i.test(label)) {
    return '선택된 원본';
  }
  return label;
}

/** Return buyer-visible status and next-action copy for one preview state. */
export function getRepositoryAssetPreviewCopy(
  preview: Pick<RepositoryAssetPreview, 'preview_state' | 'next_action'>,
) {
  const nextAction = preview.next_action;
  switch (preview.preview_state) {
    case 'recognized':
      return {
        next_action_label: getRepositoryAssetPreviewNextActionLabel(nextAction),
        status_label: '인식된 본문',
      };
    case 'pending':
      return {
        next_action_label: '인식이 끝날 때까지 기다리거나 다른 파일을 선택하세요.',
        status_label: '인식 대기',
      };
    case 'failed':
      return {
        next_action_label: '이 파일의 본문을 읽을 수 없습니다. 다른 파일을 선택하세요.',
        status_label: '인식 실패',
      };
    case 'unavailable':
      return {
        next_action_label: '미리보기를 열 수 없습니다. 다른 파일을 선택하세요.',
        status_label: '미리보기 없음',
      };
    default: {
      const exhaustive: never = preview.preview_state;
      return exhaustive;
    }
  }
}

/** Return the exact next action a buyer should take for a preview result. */
export function getRepositoryAssetPreviewNextActionLabel(
  nextAction: RepositoryAssetPreviewNextAction,
) {
  switch (nextAction) {
    case 'read_recognized_text':
      return '인식된 본문을 읽으세요.';
    case 'wait_for_recognition':
      return '인식이 끝날 때까지 기다리거나 다른 파일을 선택하세요.';
    case 'choose_another_file':
      return '이 파일의 본문을 읽을 수 없습니다. 다른 파일을 선택하세요.';
    default: {
      const exhaustive: never = nextAction;
      return exhaustive;
    }
  }
}

/** True only when preview contains recognized paragraph text, never empty content. */
export function isRecognizedRepositoryAssetPreview(
  preview: RepositoryAssetPreview | null | undefined,
): preview is RepositoryAssetPreview & { preview_state: Extract<RepositoryAssetPreviewState, 'recognized'> } {
  return preview?.preview_state === 'recognized' && preview.paragraph_texts.length > 0;
}

export function getSurfaceStatusClass(status: SurfaceStatusCode | QualityStatusCode) {
  switch (status) {
    case 'ready':
    case 'pass':
      return 'bg-emerald-100 text-emerald-700';
    case 'running':
      return 'bg-blue-100 text-blue-700';
    case 'needs_attention':
      return 'bg-amber-100 text-amber-800';
    case 'no_source':
      return 'bg-slate-100 text-slate-700';
    case 'pending':
    default:
      return 'bg-secondary text-muted-foreground';
  }
}
