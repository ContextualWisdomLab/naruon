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
  const semanticExtractionManifest = dataQualitySurface?.semantic_extraction_manifest ?? [];
  const semanticRelationEvidenceSamples = dataQualitySurface?.semantic_relation_evidence_samples ?? [];
  const acquisitionReadinessGate = dataQualitySurface?.acquisition_readiness_gate;
  const evidenceSnapshot = dataEvidenceSnapshot;
  const closeDecisionSummary = evidenceSnapshot?.diligence_close_decision_summary;
  const artifactReviewQueue = evidenceSnapshot?.diligence_close_artifact_review_queue ?? [];
  const ownerHandoffQueue = evidenceSnapshot?.diligence_close_owner_handoff_queue ?? [];
  const traceabilityMap = evidenceSnapshot?.diligence_close_traceability_map ?? [];
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
                  <dl className="grid gap-3 p-5 text-xs sm:grid-cols-3 lg:grid-cols-6">
                    <div>
                      <dt className="font-black text-muted-foreground">검증 상태</dt>
                      <dd className="mt-1 text-sm font-bold">{getSurfaceStatusLabel(evidenceSnapshot.validation_status.status_code)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">Digest</dt>
                      <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(evidenceSnapshot.snapshot_digest.slice(0, 12))}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">Algorithm</dt>
                      <dd className="mt-1 text-sm font-bold">{toSafeReactText(evidenceSnapshot.digest_algorithm)}</dd>
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
                  <div className="border-t border-border p-5">
                    <p className="text-xs font-black text-muted-foreground">Snapshot verification handoff</p>
                    <p className="mt-2 text-sm font-semibold leading-6 text-muted-foreground">{toSafeReactText(evidenceSnapshot.verification_handoff.handoff_text)}</p>
                    <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                      <div>
                        <dt className="font-black text-muted-foreground">Verifier command</dt>
                        <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(evidenceSnapshot.verification_handoff.verifier_command)}</dd>
                      </div>
                      <div>
                        <dt className="font-black text-muted-foreground">Accepted input</dt>
                        <dd className="mt-1 text-sm font-bold">{toSafeReactText(evidenceSnapshot.verification_handoff.accepted_input)}</dd>
                      </div>
                      <div>
                        <dt className="font-black text-muted-foreground">Algorithm</dt>
                        <dd className="mt-1 text-sm font-bold">{toSafeReactText(evidenceSnapshot.verification_handoff.digest_algorithm)}</dd>
                      </div>
                      <div>
                        <dt className="font-black text-muted-foreground">Excluded digest fields</dt>
                        <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(evidenceSnapshot.verification_handoff.excluded_digest_fields.join(', '))}</dd>
                      </div>
                      <div>
                        <dt className="font-black text-muted-foreground">Exit codes</dt>
                        <dd className="mt-1 break-all text-sm font-bold">
                          ok:{formatCount(evidenceSnapshot.verification_handoff.success_exit_code)} · {toSafeReactText(Object.entries(evidenceSnapshot.verification_handoff.failure_exit_codes).map(([code, exitCode]) => `${code}:${exitCode}`).join(', '))}
                        </dd>
                      </div>
                      <div>
                        <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                        <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(evidenceSnapshot.verification_handoff.provider_write_executed)}</dd>
                      </div>
                    </dl>
                  </div>
                  {evidenceSnapshot.evidence_packet_checklist.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Buyer diligence packet checklist</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {evidenceSnapshot.evidence_packet_checklist.map((item) => (
                          <article key={item.checklist_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(item.display_name)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.detail_text)}</p>
                              </div>
                              <span className={`w-fit shrink-0 rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(item.state_code)}`}>
                                {getSurfaceStatusLabel(item.state_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Artifact</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.required_artifact)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Source field</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.source_field)}</dd>
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
                  {evidenceSnapshot.data_room_package_manifest.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Data room package manifest</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {evidenceSnapshot.data_room_package_manifest.map((item) => (
                          <article key={item.manifest_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="break-all text-sm font-black">{toSafeReactText(item.file_name)}</h3>
                                <p className="mt-1 text-sm font-semibold text-muted-foreground">{toSafeReactText(item.display_name)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.detail_text)}</p>
                              </div>
                              <span className={`w-fit shrink-0 rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(item.state_code)}`}>
                                {getSurfaceStatusLabel(item.state_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Artifact type</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.artifact_type)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Source field</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.source_field)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Close required</dt>
                                <dd className="mt-1 text-sm font-bold">{item.required_for_close ? 'yes' : 'no'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Raw content</dt>
                                <dd className="mt-1 text-sm font-bold">raw content: {item.contains_raw_content ? 'yes' : 'no'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Stable IDs</dt>
                                <dd className="mt-1 text-sm font-bold">stable IDs: {item.contains_stable_identifiers ? 'yes' : 'no'}</dd>
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
                  {evidenceSnapshot.diligence_exception_register.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence exception register</p>
                      <div className="mt-3 grid gap-3">
                        {evidenceSnapshot.diligence_exception_register.map((item) => (
                          <article key={item.exception_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(item.display_name)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.detail_text)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.severity_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Check key</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.blocking_check_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Source field</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.source_field)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Artifact</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.related_artifact)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Blocks close</dt>
                                <dd className="mt-1 text-sm font-bold">blocks close: {item.blocks_close ? 'yes' : 'no'}</dd>
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
                  {evidenceSnapshot.diligence_risk_matrix.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence risk matrix</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {evidenceSnapshot.diligence_risk_matrix.map((item) => (
                          <article key={item.matrix_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(item.risk_label)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.buyer_implication)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.recommended_next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.severity_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Artifact</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.related_artifact)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Exception count</dt>
                                <dd className="mt-1 text-sm font-bold">{formatCount(item.exception_count)} exception(s)</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Blocks close</dt>
                                <dd className="mt-1 text-sm font-bold">blocks close: {item.blocks_close ? 'yes' : 'no'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                              </div>
                            </dl>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.representative_exception_keys.map((exceptionKey) => (
                                <span key={exceptionKey} className="rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                  {toSafeReactText(exceptionKey)}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  {closeDecisionSummary && closeDecisionSummary.total_proof_count > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence close decision summary</p>
                      <div className="mt-3 rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">
                              {toSafeReactText(closeDecisionSummary.decision_code)}
                            </h3>
                            <p className="mt-1 text-sm leading-6 text-muted-foreground">
                              {toSafeReactText(closeDecisionSummary.buyer_summary_text)}
                            </p>
                            <p className="mt-1 text-sm leading-6 text-muted-foreground">
                              {toSafeReactText(closeDecisionSummary.next_action_text)}
                            </p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {toSafeReactText(closeDecisionSummary.highest_severity)}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                          <div>
                            <dt className="font-black text-muted-foreground">Proofs</dt>
                            <dd className="mt-1 text-sm font-bold">
                              total {formatCount(closeDecisionSummary.total_proof_count)}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Blocked / ready</dt>
                            <dd className="mt-1 text-sm font-bold">
                              {formatCount(closeDecisionSummary.blocked_proof_count)} / {formatCount(closeDecisionSummary.ready_proof_count)}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Critical / high / medium</dt>
                            <dd className="mt-1 text-sm font-bold">
                              {formatCount(closeDecisionSummary.critical_blocker_count)} / {formatCount(closeDecisionSummary.high_blocker_count)} / {formatCount(closeDecisionSummary.medium_blocker_count)}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Required artifacts</dt>
                            <dd className="mt-1 text-sm font-bold">
                              {formatCount(closeDecisionSummary.required_artifact_count)}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Snapshot verification</dt>
                            <dd className="mt-1 text-sm font-bold">
                              {closeDecisionSummary.snapshot_verification_required ? 'required' : 'not required'}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                            <dd className="mt-1 text-sm font-bold">
                              {getWriteBoundaryLabel(closeDecisionSummary.provider_write_executed)}
                            </dd>
                          </div>
                        </dl>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {closeDecisionSummary.required_artifacts.map((artifact) => (
                            <span key={artifact} className="max-w-full break-all rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                              {toSafeReactText(artifact)}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  {artifactReviewQueue.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence close artifact review queue</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {artifactReviewQueue.map((item) => (
                          <article key={item.queue_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="break-all text-sm font-black">{toSafeReactText(item.required_proof_artifact)}</h3>
                                <p className="mt-1 text-sm font-semibold text-muted-foreground">{toSafeReactText(item.buyer_review_role)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.acceptance_summary)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.review_status)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Reviewer role</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.buyer_review_role)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Proof counts</dt>
                                <dd className="mt-1 text-sm font-bold">
                                  total {formatCount(item.proof_count)} · blocked {formatCount(item.blocked_proof_count)} · ready {formatCount(item.ready_proof_count)}
                                </dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Highest severity</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.highest_severity)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Review status</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.review_status)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Snapshot verification</dt>
                                <dd className="mt-1 text-sm font-bold">{item.snapshot_verification_required ? 'required' : 'not required'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                              </div>
                            </dl>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.owner_areas.map((ownerArea) => (
                                <span key={ownerArea} className="max-w-full break-all rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                  {toSafeReactText(ownerArea)}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  {ownerHandoffQueue.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence close owner handoff queue</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {ownerHandoffQueue.map((item) => (
                          <article key={item.handoff_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="break-all text-sm font-black">{toSafeReactText(item.owner_area)}</h3>
                                <p className="mt-1 text-sm font-semibold text-muted-foreground">{toSafeReactText(item.buyer_review_roles.join(', '))}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.acceptance_summary)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.handoff_status)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Reviewer roles</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.buyer_review_roles.join(', '))}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Proof counts</dt>
                                <dd className="mt-1 text-sm font-bold">
                                  total {formatCount(item.proof_count)} · blocked {formatCount(item.blocked_proof_count)} · ready {formatCount(item.ready_proof_count)}
                                </dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Highest severity</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.highest_severity)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Handoff status</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.handoff_status)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Snapshot verification</dt>
                                <dd className="mt-1 text-sm font-bold">{item.snapshot_verification_required ? 'required' : 'not required'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                              </div>
                            </dl>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.related_artifacts.map((artifact) => (
                                <span key={artifact} className="max-w-full break-all rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                  {toSafeReactText(artifact)}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  {traceabilityMap.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence close traceability map</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {traceabilityMap.map((item) => (
                          <article key={item.trace_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="break-all text-sm font-black">{toSafeReactText(item.data_room_artifact)}</h3>
                                <p className="mt-1 text-sm font-semibold text-muted-foreground">{toSafeReactText(item.buyer_review_roles.join(', '))}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.trace_summary)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.close_gate_status)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Source field</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.source_field)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Manifest key</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.manifest_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Trace keys</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.risk_key)} · {toSafeReactText(item.proof_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Review key</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.artifact_review_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Handoff key</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.owner_handoff_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Exception count</dt>
                                <dd className="mt-1 text-sm font-bold">{formatCount(item.exception_count)} exception(s)</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Reviewer roles</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.buyer_review_roles.join(', '))}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Snapshot verification</dt>
                                <dd className="mt-1 text-sm font-bold">{item.snapshot_verification_required ? 'required' : 'not required'}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Severity</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.severity_code)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(item.provider_write_executed)}</dd>
                              </div>
                            </dl>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.exception_keys.map((exceptionKey) => (
                                <span key={exceptionKey} className="max-w-full break-all rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                  {toSafeReactText(exceptionKey)}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  {evidenceSnapshot.diligence_close_proof_plan.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Diligence close proof plan</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {evidenceSnapshot.diligence_close_proof_plan.map((item) => (
                          <article key={item.proof_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(item.buyer_close_dependency)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.acceptance_criteria)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.verification_method)}</p>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.next_action)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                {toSafeReactText(item.close_gate_status)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Proof artifact</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.required_proof_artifact)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Related artifact</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(item.related_artifact)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Exception count</dt>
                                <dd className="mt-1 text-sm font-bold">{formatCount(item.exception_count)} exception(s)</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Severity</dt>
                                <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.severity_code)}</dd>
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
                  {snapshotCopyStatus !== 'idle' && (
                    <p className="border-t border-border px-5 py-3 text-xs font-bold text-muted-foreground">
                      {snapshotCopyStatus === 'copied' ? '스냅샷 JSON을 복사했습니다.' : '클립보드 복사를 사용할 수 없습니다.'}
                    </p>
                  )}
                </div>
              )}
              {acquisitionReadinessGate && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="flex flex-col gap-3 border-b border-border bg-secondary/30 p-5 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h2 className="font-bold text-lg">{toSafeReactText(acquisitionReadinessGate.display_name)}</h2>
                      <p className="mt-1 text-sm font-semibold text-muted-foreground">{toSafeReactText(acquisitionReadinessGate.detail_text)}</p>
                    </div>
                    <span className={`w-fit shrink-0 rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(acquisitionReadinessGate.state_code)}`}>
                      {getSurfaceStatusLabel(acquisitionReadinessGate.state_code)}
                    </span>
                  </div>
                  <dl className="grid gap-3 p-5 text-xs sm:grid-cols-2 lg:grid-cols-6">
                    <div>
                      <dt className="font-black text-muted-foreground">Readiness</dt>
                      <dd className="mt-1 text-xl font-black">{formatCount(acquisitionReadinessGate.readiness_score)}%</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">통과</dt>
                      <dd className="mt-1 text-sm font-bold">{formatCount(acquisitionReadinessGate.passed_checks)} / {formatCount(acquisitionReadinessGate.total_checks)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">Blocking</dt>
                      <dd className="mt-1 text-sm font-bold">{formatCount(acquisitionReadinessGate.issue_checks)}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">Evidence packet</dt>
                      <dd className="mt-1 text-sm font-bold">{acquisitionReadinessGate.evidence_packet_ready ? '증거 패킷 생성됨' : '증거 패킷 대기'}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">Snapshot verification</dt>
                      <dd className="mt-1 text-sm font-bold">{acquisitionReadinessGate.snapshot_verification_ready ? 'Snapshot verification ready' : 'Snapshot verification pending'}</dd>
                    </div>
                    <div>
                      <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                      <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(acquisitionReadinessGate.provider_write_executed)}</dd>
                    </div>
                  </dl>
                  <div className="border-t border-border p-5">
                    <p className="text-xs font-black text-muted-foreground">Acquisition decision summary</p>
                    <div className="mt-3 rounded-xl border border-border bg-background p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="text-sm font-black">{toSafeReactText(acquisitionReadinessGate.decision_summary.headline_text)}</h3>
                          <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(acquisitionReadinessGate.decision_summary.next_step_text)}</p>
                        </div>
                        <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                          {toSafeReactText(acquisitionReadinessGate.decision_summary.recommendation_code)} · {toSafeReactText(acquisitionReadinessGate.decision_summary.risk_level)}
                        </span>
                      </div>
                      <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-4">
                        <div>
                          <dt className="font-black text-muted-foreground">Target gaps</dt>
                          <dd className="mt-1 text-sm font-bold">{formatCount(acquisitionReadinessGate.decision_summary.target_gap_count)}</dd>
                        </div>
                        <div>
                          <dt className="font-black text-muted-foreground">Critical / high / medium</dt>
                          <dd className="mt-1 text-sm font-bold">
                            {formatCount(acquisitionReadinessGate.decision_summary.critical_action_count)} / {formatCount(acquisitionReadinessGate.decision_summary.high_action_count)} / {formatCount(acquisitionReadinessGate.decision_summary.medium_action_count)}
                          </dd>
                        </div>
                        <div>
                          <dt className="font-black text-muted-foreground">Summary key</dt>
                          <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(acquisitionReadinessGate.decision_summary.summary_key)}</dd>
                        </div>
                        <div>
                          <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                          <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(acquisitionReadinessGate.decision_summary.provider_write_executed)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>
                  {acquisitionReadinessGate.blocking_check_keys.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Blocking check keys</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {acquisitionReadinessGate.blocking_check_keys.map((checkKey) => (
                          <span key={checkKey} className="rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {toSafeReactText(checkKey)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {acquisitionReadinessGate.kpis.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Acquisition KPI targets</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {acquisitionReadinessGate.kpis.map((kpi) => (
                          <article key={kpi.kpi_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(kpi.display_name)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(kpi.guardrail_text)}</p>
                              </div>
                              <span className={`w-fit shrink-0 rounded-full px-2 py-1 text-xs font-bold ${getSurfaceStatusClass(kpi.status_code)}`}>
                                {getSurfaceStatusLabel(kpi.status_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Current / target</dt>
                                <dd className="mt-1 text-sm font-bold">{formatCount(kpi.current_percent)}% / {formatCount(kpi.target_percent)}%</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(kpi.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(kpi.provider_write_executed)}</dd>
                              </div>
                            </dl>
                            <p className="mt-3 text-xs font-bold text-muted-foreground">
                              {kpi.target_met ? 'Target met' : 'Target gap'} · {toSafeReactText(kpi.source_check_key)}
                            </p>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  {acquisitionReadinessGate.remediation_actions.length > 0 && (
                    <div className="border-t border-border p-5">
                      <p className="text-xs font-black text-muted-foreground">Remediation actions</p>
                      <div className="mt-3 grid gap-3">
                        {acquisitionReadinessGate.remediation_actions.map((action) => (
                          <article key={action.action_key} className="rounded-xl border border-border bg-background p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <h3 className="text-sm font-black">{toSafeReactText(action.display_name)}</h3>
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(action.recommended_next_step)}</p>
                                <p className="mt-1 text-xs font-semibold text-muted-foreground">{toSafeReactText(action.impact_text)}</p>
                              </div>
                              <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                                P{formatCount(action.priority_rank)} · {toSafeReactText(action.priority_code)}
                              </span>
                            </div>
                            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                              <div>
                                <dt className="font-black text-muted-foreground">Owner area</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(action.owner_area)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">Check key</dt>
                                <dd className="mt-1 break-all text-sm font-bold">{toSafeReactText(action.blocking_check_key)}</dd>
                              </div>
                              <div>
                                <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                                <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(action.provider_write_executed)}</dd>
                              </div>
                            </dl>
                          </article>
                        ))}
                      </div>
                    </div>
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
                    <h2 className="font-bold text-lg">문단 출처 근거 샘플</h2>
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
              {semanticExtractionManifest.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">Semantic KG readiness</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {semanticExtractionManifest.map((item) => (
                      <article key={item.manifest_key} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.display_name)}</h3>
                            <p className="mt-1 text-sm leading-6 text-muted-foreground">{toSafeReactText(item.detail_text)}</p>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">
                              required {toSafeReactText(item.required_evidence.join(', '))}
                            </p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {toSafeReactText(item.state_code)}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-4">
                          <div>
                            <dt className="font-black text-muted-foreground">Structural edges</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.structural_edge_count)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Semantic relations</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.semantic_relation_count)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Source-backed</dt>
                            <dd className="mt-1 text-sm font-bold">{formatCount(item.source_backed_relation_count)}</dd>
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
              {semanticRelationEvidenceSamples.length > 0 && (
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 border-b border-border bg-secondary/30">
                    <h2 className="font-bold text-lg">Semantic relation evidence</h2>
                  </div>
                  <div className="grid gap-3 p-5">
                    {semanticRelationEvidenceSamples.map((item) => (
                      <article key={item.sample_key} className="rounded-xl border border-border bg-background p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">{toSafeReactText(item.relationship_type)}</h3>
                            <p className="mt-1 break-all text-sm leading-6 text-muted-foreground">
                              action {toSafeReactText(item.next_action)}
                            </p>
                          </div>
                          <span className="w-fit shrink-0 rounded-full bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                            {toSafeReactText(item.source_scope)}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                          <div>
                            <dt className="font-black text-muted-foreground">Confidence</dt>
                            <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.confidence_bucket)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">Source scope</dt>
                            <dd className="mt-1 text-sm font-bold">{toSafeReactText(item.source_scope)}</dd>
                          </div>
                          <div>
                            <dt className="font-black text-muted-foreground">쓰기 경계</dt>
                            <dd className="mt-1 text-sm font-bold">{getWriteBoundaryLabel(false)}</dd>
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
