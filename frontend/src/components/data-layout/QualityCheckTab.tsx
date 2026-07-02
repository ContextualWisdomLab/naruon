import React from 'react';
import { toSafeReactText } from '@/lib/safe-text';
import {
  DataEvidenceSnapshotResponse,
  DataQualitySurfaceResponse,
  DataSurfaceStatus
} from './types';
import {
  formatCount,
  getSurfaceStatusLabel,
  getSurfaceStatusClass,
  getWriteBoundaryLabel
} from './utils';

interface QualityCheckTabProps {
  dataSurfaceStatus: DataSurfaceStatus;
  dataQualitySurface: DataQualitySurfaceResponse | null;
  dataEvidenceSnapshot: DataEvidenceSnapshotResponse | null;
}

function getEndpointStatusLabel(status: string): string {
  if (status === 'segment_backed') return '문단 근거 연결됨';
  if (status === 'node_only') return '노드 근거만 있음';
  return '근거 endpoint 없음';
}

export function QualityCheckTab({
  dataSurfaceStatus,
  dataQualitySurface,
  dataEvidenceSnapshot,
}: QualityCheckTabProps) {
  const [snapshotCopyStatus, setSnapshotCopyStatus] = React.useState<'idle' | 'copied' | 'unavailable'>('idle');
  const attachmentParseBreakdown = dataQualitySurface?.attachment_parse_breakdown ?? [];
  const contentGraphBreakdown = dataQualitySurface?.content_graph_breakdown ?? [];
  const knowledgeGraphBreakdown = dataQualitySurface?.knowledge_graph_breakdown ?? [];
  const contentEvidenceSamples = dataQualitySurface?.content_graph_evidence_samples ?? [];
  const knowledgeGraphEvidenceSamples = dataQualitySurface?.knowledge_graph_evidence_samples ?? [];
  const evidenceSnapshot = dataEvidenceSnapshot;
  const copyEvidenceSnapshot = React.useCallback(async () => {
    if (!evidenceSnapshot) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(JSON.stringify(evidenceSnapshot, null, 2));
      setSnapshotCopyStatus('copied');
    } catch {
      setSnapshotCopyStatus('unavailable');
    }
  }, [evidenceSnapshot]);

  return (
<div className="space-y-6">
              {evidenceSnapshot && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="flex flex-col gap-3 border-b border-border bg-secondary/30 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h2 className="font-bold text-lg">실사 스냅샷</h2>
                      <p className="mt-1 text-sm font-semibold text-muted-foreground">raw 본문/첨부 원문 제외 · 안정 ID 비노출</p>
                    </div>
                    <button
                      type="button"
                      onClick={copyEvidenceSnapshot}
                      className="w-fit rounded bg-secondary px-3 py-1.5 text-xs font-bold text-secondary-foreground hover:bg-secondary/80"
                    >
                      실사 스냅샷 JSON 복사
                    </button>
                  </div>
                  <dl className="grid gap-3 p-5 text-xs sm:grid-cols-4">
                    <div>
                      <dt className="font-black text-muted-foreground">검증 상태</dt>
                      <dd className="mt-1 text-sm font-bold">{getSurfaceStatusLabel(evidenceSnapshot.validation_status.status_code)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">parser family</dt>
                      <dd className="mt-1 text-sm font-bold">{formatCount(evidenceSnapshot.parser_manifest_summary.length)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">문단 샘플</dt>
                      <dd className="mt-1 text-sm font-bold">{formatCount(evidenceSnapshot.content_graph_evidence_samples.length)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">KG 샘플</dt>
                      <dd className="mt-1 text-sm font-bold">{formatCount(evidenceSnapshot.knowledge_graph_evidence_samples.length)}</dd>
                    </div>
                  </dl>
                  {snapshotCopyStatus !== 'idle' && (
                    <p className="border-t border-border px-5 py-3 text-xs font-bold text-muted-foreground">
                      {snapshotCopyStatus === 'copied' ? '스냅샷 JSON을 복사했습니다.' : '클립보드 복사를 사용할 수 없습니다.'}
                    </p>
                  )}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {(dataQualitySurface?.quality_checks.slice(0, 3) ?? []).map((check) => (
                  <div key={check.check_key} className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                    <p className="text-xs font-bold text-muted-foreground mb-1">{toSafeReactText(check.display_name)}</p>
                    <p className={`text-xl font-bold ${check.issue_count > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {formatCount(check.issue_count)} / {formatCount(check.total_count)}
                    </p>
                    <span className={`mt-3 inline-flex rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(check.status_code)}`}>
                      {getSurfaceStatusLabel(check.status_code)}
                    </span>
                    <div className="mt-4 flex gap-2 justify-end border-t border-border pt-3">
                      <button type="button" className="rounded bg-secondary px-3 py-1.5 text-xs font-bold text-secondary-foreground hover:bg-secondary/80">
                        품질 점검
                      </button>
                      <button type="button" className="rounded bg-red-50 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-100 border border-red-200">
                        격리
                      </button>
                    </div>
                  </div>
                ))}
                {dataSurfaceStatus === 'loading' && (
                  <div className="rounded-2xl border border-border bg-card p-5 text-sm font-semibold text-muted-foreground shadow-sm md:col-span-3">
                    품질 점검 근거를 확인하는 중입니다.
                  </div>
                )}
                {dataSurfaceStatus === 'error' && (
                  <div className="rounded-2xl border border-border bg-card p-5 text-sm font-bold text-red-700 shadow-sm md:col-span-3">
                    품질 점검 근거를 불러오지 못했습니다.
                  </div>
                )}
              </div>
              <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="p-5 border-b border-border bg-secondary/30">
                  <h2 className="font-bold text-lg">품질 문제 항목</h2>
                </div>
                <div className="grid gap-3 p-5">
                  {dataQualitySurface?.quality_checks.map((check) => (
                    <article key={check.check_key} className="rounded-xl border border-border bg-background p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="text-sm font-black">{toSafeReactText(check.display_name)}</h3>
                          <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(check.detail_text)}</p>
                          <p className="mt-1 text-xs font-semibold text-muted-foreground">원본 근거 연결됨</p>
                        </div>
                        <span className={`w-fit shrink-0 rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(check.status_code)}`}>
                          {getSurfaceStatusLabel(check.status_code)}
                        </span>
                      </div>
                      <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                        <div>
                          <dt className="font-black text-muted-foreground">이슈</dt>
                          <dd className="mt-1 text-sm font-bold">{formatCount(check.issue_count)}</dd>
                        </div>
                        <div>
                          <dt className="font-black text-muted-foreground">대상</dt>
                          <dd className="mt-1 text-sm font-bold">{formatCount(check.total_count)}</dd>
                        </div>
                        <div>
                          <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                          <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(check.provider_write_executed)}</dd>
                        </div>
                      </dl>
                    </article>
                  ))}
                </div>
              </div>
              {contentGraphBreakdown.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">DOM/문단 구조별 현황</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {contentGraphBreakdown.map((item) => (
                      <article key={`${item.source_kind}:${item.segment_kind}`} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.segment_kind)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">source {toSafeReactText(item.source_kind)}</p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            segment
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                          <div>
                            <dt className="font-black text-muted-foreground">건수</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.object_count)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                            <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              {knowledgeGraphBreakdown.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">KG edge 형식별 현황</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {knowledgeGraphBreakdown.map((item) => (
                      <article key={`${item.source_kind}:${item.edge_kind}`} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.edge_kind)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">source {toSafeReactText(item.source_kind)}</p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            edge
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                          <div>
                            <dt className="font-black text-muted-foreground">건수</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.object_count)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                            <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              {contentEvidenceSamples.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">문단 근거 샘플</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {contentEvidenceSamples.map((item) => (
                      <article key={item.sample_key} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.segment_kind)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">source {toSafeReactText(item.source_kind)}</p>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">{toSafeReactText(item.segment_path)}</p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            sample
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs">
                          <div>
                            <dt className="font-black text-muted-foreground">단어 수</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.word_count)}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              {knowledgeGraphEvidenceSamples.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">KG 근거 샘플</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {knowledgeGraphEvidenceSamples.map((item) => (
                      <article key={item.sample_key} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.edge_kind)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">source {toSafeReactText(item.source_kind)}</p>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">{toSafeReactText(item.edge_path)}</p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {getEndpointStatusLabel(item.endpoint_status)}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs">
                          <div>
                            <dt className="font-black text-muted-foreground">Endpoint</dt>
                            <dd className="mt-1 text-sm font-bold">{getEndpointStatusLabel(item.endpoint_status)}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              {attachmentParseBreakdown.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">첨부 parser 형식별 현황</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {attachmentParseBreakdown.map((item) => (
                      <article key={`${item.content_type}:${item.parse_status}`} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.display_name)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">원본 MIME {toSafeReactText(item.content_type)}</p>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">
                              Parse source {toSafeReactText(item.parse_content_type ?? item.content_type)}
                            </p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {toSafeReactText(item.parse_status)}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                          <div>
                            <dt className="font-black text-muted-foreground">건수</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.object_count)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">parser</dt>
                            <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.parser_key)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                            <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              )}
            </div>
  );
}
