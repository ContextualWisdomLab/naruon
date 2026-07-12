"use client";

import { useEffect, useMemo, useState } from 'react';
import {
  AlertOctagon,
  CheckCircle2,
  Database,
  Lock,
  RefreshCw,
  ScrollText,
  Share2,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import { apiClient } from '@/lib/api-client';

type SecurityTab = '보안 대시보드' | '접근 권한' | '감사 로그' | '외부 공유' | '정책';
type ScopeKind = 'organization' | 'personal';

type PolicyDecisionSummary = {
  resource_label: string;
  resource_type: string;
  allowed: boolean;
  reason: string;
  evidence_label: string;
};

type GovernanceSource = {
  source_type: 'caldav_source' | 'carddav_source' | 'webdav_repository';
  source_label: string;
  scope_kind: ScopeKind;
  capabilities: string[];
  writeback_enabled: boolean;
  policy_decision: PolicyDecisionSummary;
  last_observed_at: string | null;
};

type ConnectorEvidence = {
  state_code: string;
  evidence_label: string;
  observed_at: string;
};

type DurableAuditEvidence = {
  actor_role: string;
  scope_kind: ScopeKind;
  event_action: string;
  resource_type: string;
  evidence_label: string;
  observed_at: string;
};

type ExternalShareReview = {
  source_type: GovernanceSource['source_type'];
  review_label: string;
  exposure_level: 'internal' | 'external_writeback';
  decision_reason: string;
};

type PolicyOrderStep = {
  display_name: string;
  evidence_label: string;
};

type SecurityAccessSurface = {
  scope_kind: ScopeKind;
  viewer: {
    role: string;
    scope_kind: ScopeKind;
  };
  sources: GovernanceSource[];
  connector_events: ConnectorEvidence[];
  durable_audit_events: DurableAuditEvidence[];
  policy_decisions: PolicyDecisionSummary[];
  external_share_reviews: ExternalShareReview[];
  policy_order: PolicyOrderStep[];
};

const tabs: SecurityTab[] = ['보안 대시보드', '접근 권한', '감사 로그', '외부 공유', '정책'];

const reasonLabels: Record<string, string> = {
  allowed: '허용',
  organization_denied: '조직 차단',
  data_region_denied: '리전 차단',
  consent_denied: '동의 차단',
  ownership_denied: '소유권 차단',
  rbac_denied: 'RBAC 차단',
};

function reasonLabel(reason: string) {
  return reasonLabels[reason] ?? reason;
}

function sourceTypeLabel(sourceType: GovernanceSource['source_type'] | string) {
  switch (sourceType) {
    case 'caldav_source':
      return 'CalDAV 일정 원본';
    case 'carddav_source':
      return 'CardDAV 연락처 원본';
    case 'webdav_repository':
      return 'WebDAV 저장소';
    case 'provider_secret':
      return '제공자 secret';
    case 'llm_provider':
      return 'LLM 제공자';
    default:
      return '보안 리소스';
  }
}

function sourceDisplayLabel(source: GovernanceSource, index: number) {
  const label = source.source_label.trim();
  if (!label || /repository|source/i.test(label)) {
    return `${sourceTypeLabel(source.source_type)} ${index + 1}`;
  }
  return label;
}

function capabilityLabel(capability: string) {
  switch (capability) {
    case 'read':
      return '읽기';
    case 'write':
      return '쓰기';
    case 'etag':
      return '충돌 검사';
    default:
      return '원본 기능';
  }
}

function scopeLabel(scopeKind: ScopeKind) {
  return scopeKind === 'organization' ? '조직 스코프' : '개인 스코프';
}

function roleLabel(role: string) {
  switch (role) {
    case 'tenant_admin':
      return '테넌트 관리자';
    case 'organization_admin':
      return '조직 관리자';
    case 'platform_admin':
      return '플랫폼 관리자';
    case 'member':
      return '멤버';
    default:
      return '서명 세션 사용자';
  }
}

function evidenceLabel(evidenceLabelValue: string) {
  if (/webdav/i.test(evidenceLabelValue)) return 'WebDAV 원본 근거';
  if (/calendar/i.test(evidenceLabelValue)) return '일정 원본 근거';
  if (/policy|access_policy/i.test(evidenceLabelValue)) return '정책 엔진 근거';
  if (/auth|session/i.test(evidenceLabelValue)) return '서명 세션 근거';
  if (/llm|provider/i.test(evidenceLabelValue)) return '제공자 설정 근거';
  if (/connector|runner/i.test(evidenceLabelValue)) return 'connector 관측 근거';
  return '서버 근거';
}

function subjectParticle(label: string) {
  const lastChar = label.trim().at(-1);
  if (!lastChar) return '가';
  const code = lastChar.charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return '가';
  return (code - 0xac00) % 28 === 0 ? '가' : '이';
}

function connectorStateLabel(stateCode: string) {
  switch (stateCode) {
    case 'heartbeat':
      return '하트비트 수신';
    case 'connected':
      return '연결됨';
    case 'disconnected':
      return '연결 종료';
    default:
      return '관측됨';
  }
}

function auditActionLabel(action: string) {
  switch (action) {
    case 'update':
      return '설정 변경';
    case 'create':
      return '생성';
    case 'delete':
      return '삭제';
    default:
      return '감사 이벤트';
  }
}

function exposureLabel(exposure: ExternalShareReview['exposure_level']) {
  return exposure === 'external_writeback' ? '외부 쓰기 검토' : '내부 공유';
}

function shareReviewLabel(review: ExternalShareReview) {
  if (/writeback boundary/i.test(review.review_label)) {
    return `${sourceTypeLabel(review.source_type)} 쓰기 경계`;
  }
  return review.review_label;
}

function policyStepLabel(step: PolicyOrderStep) {
  if (/signed session/i.test(step.display_name)) return '서명 세션 식별';
  if (/organization and workspace/i.test(step.display_name)) return '조직과 워크스페이스 스코프';
  if (/data-region/i.test(step.display_name)) return '데이터 리전 차단';
  if (/consent/i.test(step.display_name)) return '동의와 원본 기능 차단';
  if (/owner|delegated/i.test(step.display_name)) return '소유자 또는 위임 관리자 경계';
  if (/rbac/i.test(step.display_name)) return 'ABAC 차단 후 RBAC 허용';
  return step.display_name;
}

function decisionResourceLabel(decision: PolicyDecisionSummary) {
  if (/webdav/i.test(decision.resource_label)) return 'WebDAV 저장소';
  if (/provider secret/i.test(decision.resource_label)) return '교차 조직 제공자 secret';
  return decision.resource_label;
}

function DecisionPill({ decision }: { decision: PolicyDecisionSummary }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold ${
        decision.allowed
          ? 'bg-emerald-100 text-emerald-700'
          : 'bg-red-100 text-red-700'
      }`}
    >
      {decision.allowed ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
      {reasonLabel(decision.reason)}
    </span>
  );
}

function LoadingPanel() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
      보안 거버넌스 데이터를 불러오는 중입니다.
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  void message;
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
      서명 세션 보안 표면을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" className="rounded-lg border border-dashed border-border bg-background p-5 text-sm text-muted-foreground">
      현재 signed-session 스코프에서 확인된 {label}{subjectParticle(label)} 없습니다.
    </div>
  );
}

function SummaryCard({
  title,
  value,
  detail,
  icon,
}: {
  title: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold text-muted-foreground">{title}</p>
          <p className="mt-2 text-xl font-bold">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
        </div>
        <div className="rounded-lg bg-secondary p-2 text-primary">{icon}</div>
      </div>
    </article>
  );
}

function DashboardTab({ data }: { data: SecurityAccessSurface }) {
  const allowedCount = data.policy_decisions.filter((decision) => decision.allowed).length;
  const deniedCount = data.policy_decisions.length - allowedCount;
  const writebackReady = data.sources.filter((source) => source.writeback_enabled).length;
  const externalWritebackReviewCount = data.external_share_reviews.filter(
    (review) => review.exposure_level === 'external_writeback',
  ).length;

  return (
    <section aria-label="보안 거버넌스 대시보드" className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <SummaryCard
          title="접근 판정"
          value={`${allowedCount}/${data.policy_decisions.length}`}
          detail={`deny ${deniedCount}건, ABAC가 RBAC보다 먼저 적용됩니다.`}
          icon={<ShieldCheck className="size-5" />}
        />
        <SummaryCard
          title="연결 원본"
          value={`${data.sources.length}개`}
          detail={`쓰기 의도 가능 ${writebackReady}개, 소유자 스코프 확인`}
          icon={<Database className="size-5" />}
        />
        <SummaryCard
          title="Connector 근거"
          value={`${data.connector_events.length}건`}
          detail="워크스페이스 스코프 확인"
          icon={<ScrollText className="size-5" />}
        />
        <SummaryCard
          title="외부 쓰기"
          value={`${externalWritebackReviewCount}건`}
          detail="실행 없이 검토 큐 근거만 표시합니다."
          icon={<Lock className="size-5" />}
        />
      </div>

      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-bold">현재 관리자 경계</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {roleLabel(data.viewer.role)} / {scopeLabel(data.scope_kind)}
            </p>
          </div>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold text-muted-foreground">
            감사 근거 기록됨
          </span>
        </div>
        {data.policy_decisions.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="접근 판정" />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {data.policy_decisions.slice(0, 4).map((decision, index) => (
              <div key={`${decision.resource_type}-${index}`} className="rounded-lg border border-border bg-background p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="min-w-0 truncate text-sm font-bold">{decisionResourceLabel(decision)}</p>
                  <DecisionPill decision={decision} />
                </div>
                <p className="mt-2 truncate text-xs font-semibold text-muted-foreground">{evidenceLabel(decision.evidence_label)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function AccessTab({ data }: { data: SecurityAccessSurface }) {
  return (
    <section aria-label="접근 권한 소스 거버넌스" className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
        <h2 className="text-base font-bold">원본 연결 RBAC / ABAC</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              WebDAV, CalDAV, CardDAV source registry를 signed-session 스코프로 판정합니다.
            </p>
          </div>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold text-muted-foreground">
            외부 쓰기 실행 안 함
          </span>
        </div>
        {data.sources.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="연결 원본" />
          </div>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-1 gap-3 md:hidden">
              {data.sources.map((source, index) => (
                <article key={`${source.source_type}-${index}`} className="rounded-lg border border-border bg-background p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold">{sourceDisplayLabel(source, index)}</h3>
                      <p className="mt-1 text-xs font-semibold text-muted-foreground">{sourceTypeLabel(source.source_type)}</p>
                    </div>
                    <DecisionPill decision={source.policy_decision} />
                  </div>
                  <dl className="mt-3 grid grid-cols-1 gap-2 text-xs">
                    <div className="flex items-center justify-between gap-3">
                      <dt className="font-bold text-muted-foreground">원본 위치</dt>
                      <dd className="text-right font-semibold">서버에서 검증됨</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt className="font-bold text-muted-foreground">소유 경계</dt>
                      <dd className="text-right">{scopeLabel(source.scope_kind)}</dd>
                    </div>
                    <div>
                      <dt className="font-bold text-muted-foreground">기능</dt>
                      <dd className="mt-2 flex flex-wrap gap-1">
                        {source.capabilities.map((capability) => (
                          <span key={capability} className="rounded-md bg-secondary px-2 py-1 text-xs font-bold">
                            {capabilityLabel(capability)}
                          </span>
                        ))}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
            <div className="mt-4 hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-border bg-secondary/50 text-xs text-muted-foreground">
                  <tr>
                    <th className="p-3 font-bold">원본</th>
                    <th className="p-3 font-bold">원본 위치</th>
                    <th className="p-3 font-bold">소유 경계</th>
                    <th className="p-3 font-bold">기능</th>
                    <th className="p-3 font-bold">판정</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.sources.map((source, index) => (
                    <tr key={`${source.source_type}-${index}`} className="bg-background">
                      <td className="p-3">
                        <p className="font-bold">{sourceDisplayLabel(source, index)}</p>
                        <p className="mt-1 text-xs font-semibold text-muted-foreground">{sourceTypeLabel(source.source_type)}</p>
                      </td>
                      <td className="p-3 text-xs font-semibold">서버에서 검증됨</td>
                      <td className="p-3">
                        <p>{scopeLabel(source.scope_kind)}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{source.writeback_enabled ? '쓰기 의도 가능' : '읽기 전용'}</p>
                      </td>
                      <td className="p-3">
                        <div className="flex flex-wrap gap-1">
                          {source.capabilities.map((capability) => (
                            <span key={capability} className="rounded-md bg-secondary px-2 py-1 text-xs font-bold">
                              {capabilityLabel(capability)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="p-3"><DecisionPill decision={source.policy_decision} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function AuditTab({ data }: { data: SecurityAccessSurface }) {
  return (
    <section aria-label="보안 감사 로그" className="space-y-5">
        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-base font-bold">지속 감사 근거</h2>
          <p className="mt-1 text-sm text-muted-foreground">
          조직과 워크스페이스 경계 내에서 발생한 감사 이벤트만 표시합니다. 내부 식별자는 서버에만 보관합니다.
          </p>
        <div className="mt-4 rounded-lg border border-border bg-background p-3">
          <p className="text-xs font-bold text-muted-foreground">감사 조회 상태</p>
          <p className="mt-1 text-sm font-bold">감사 근거 기록됨</p>
        </div>
        {data.durable_audit_events.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="감사 이벤트" />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            {data.durable_audit_events.map((event, index) => (
              <article key={`${event.resource_type}-${event.observed_at}-${index}`} className="rounded-lg border border-border bg-background p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-sm font-bold">{auditActionLabel(event.event_action)} / {sourceTypeLabel(event.resource_type)}</h3>
                    <p className="mt-1 text-xs font-semibold text-muted-foreground">{scopeLabel(event.scope_kind)}</p>
                  </div>
                  <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold">{roleLabel(event.actor_role)}</span>
                </div>
                <dl className="mt-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                  <div>
                    <dt className="font-bold text-muted-foreground">이벤트 근거</dt>
                    <dd className="font-semibold">서버 감사 로그</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-muted-foreground">행위자</dt>
                    <dd className="font-semibold">{roleLabel(event.actor_role)}</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-muted-foreground">워크스페이스</dt>
                    <dd className="font-semibold">스코프 확인됨</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-muted-foreground">근거</dt>
                    <dd className="font-semibold">{evidenceLabel(event.evidence_label)}</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-muted-foreground">observed_at</dt>
                    <dd className="break-all font-mono">{event.observed_at}</dd>
                  </div>
                </dl>
                <p className="mt-3 break-words text-sm text-muted-foreground">보안 설정 변경이 서버 감사 근거로 기록되었습니다.</p>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-bold">Connector 근거</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          outbound connector가 남긴 workspace-scoped 운영 신호입니다.
        </p>
        {data.connector_events.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="connector 근거" />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {data.connector_events.map((event, index) => (
              <div key={`${event.state_code}-${event.observed_at}-${index}`} className="rounded-lg border border-border bg-background p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-bold">서버 관측 이벤트</p>
                  <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold">{connectorStateLabel(event.state_code)}</span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{evidenceLabel(event.evidence_label)}로 connector 상태가 관측되었습니다.</p>
                <p className="mt-2 font-mono text-xs text-muted-foreground">{event.observed_at}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SharingTab({ data }: { data: SecurityAccessSurface }) {
  return (
    <section aria-label="외부 공유와 writeback 검토" className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-bold">외부 공유 / 쓰기 경계</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          고객 소유 원본으로 나가는 쓰기 가능성만 검토하며 실제 외부 쓰기는 실행하지 않습니다.
        </p>
        {data.external_share_reviews.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="외부 공유 검토 항목" />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {data.external_share_reviews.map((review, index) => (
              <article key={`${review.source_type}-${index}`} className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-bold">{shareReviewLabel(review)}</h3>
                    <p className="mt-1 text-xs font-semibold text-muted-foreground">{sourceTypeLabel(review.source_type)}</p>
                  </div>
                  <span className="rounded-md bg-secondary px-2 py-1 text-xs font-bold">
                    {exposureLabel(review.exposure_level)}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md bg-red-50 px-2 py-1 font-bold text-red-700">
                    {reasonLabel(review.decision_reason)}
                  </span>
                  <span className="rounded-md bg-secondary px-2 py-1 font-bold">
                    외부 쓰기 실행 안 함
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function PolicyTab({ data }: { data: SecurityAccessSurface }) {
  return (
    <section aria-label="정책 엔진 판정 순서" className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-bold">차단 우선 정책 순서</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          NIST ABAC 모델과 OWASP deny-by-default 원칙에 맞춰 속성 차단을 역할 허용보다 먼저 평가합니다.
        </p>
        {data.policy_order.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="정책 판정 순서" />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {data.policy_order.map((step, index) => (
              <div key={`${step.display_name}-${index}`} className="rounded-lg border border-border bg-background p-3">
                <div className="flex items-center gap-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold">{policyStepLabel(step)}</p>
                    <p className="mt-1 truncate text-xs font-semibold text-muted-foreground">{evidenceLabel(step.evidence_label)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-bold">판정 샘플</h2>
        {data.policy_decisions.length === 0 ? (
          <div className="mt-4">
            <EmptyState label="정책 판정 샘플" />
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-border bg-secondary/50 text-xs text-muted-foreground">
                <tr>
                  <th className="p-3 font-bold">리소스</th>
                  <th className="p-3 font-bold">유형</th>
                  <th className="p-3 font-bold">판정</th>
                  <th className="p-3 font-bold">근거</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.policy_decisions.map((decision, index) => (
                  <tr key={`${decision.resource_type}-${index}`} className="bg-background">
                    <td className="p-3 font-bold">{decisionResourceLabel(decision)}</td>
                    <td className="p-3 text-xs font-semibold">{sourceTypeLabel(decision.resource_type)}</td>
                    <td className="p-3"><DecisionPill decision={decision} /></td>
                    <td className="p-3 text-xs font-semibold text-muted-foreground">{evidenceLabel(decision.evidence_label)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

export function SecurityLayout() {
  const [activeTab, setActiveTab] = useState<SecurityTab>('접근 권한');
  const [data, setData] = useState<SecurityAccessSurface | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .get<SecurityAccessSurface>('/api/security/access-surface')
      .then((surface) => {
        if (!mounted) return;
        setData(surface);
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'unknown error');
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const content = useMemo(() => {
    if (loading) return <LoadingPanel />;
    if (error) return <ErrorPanel message={error} />;
    if (!data) return <EmptyState label="보안 거버넌스 데이터" />;
    if (activeTab === '보안 대시보드') return <DashboardTab data={data} />;
    if (activeTab === '접근 권한') return <AccessTab data={data} />;
    if (activeTab === '감사 로그') return <AuditTab data={data} />;
    if (activeTab === '외부 공유') return <SharingTab data={data} />;
    return <PolicyTab data={data} />;
  }, [activeTab, data, error, loading]);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-x-hidden bg-background text-foreground">
      <header className="flex h-20 shrink-0 items-center overflow-hidden border-b border-border bg-card px-4 md:px-8">
        <h1 className="flex shrink-0 items-center gap-3 text-xl font-bold md:text-2xl">
          <ShieldCheck className="size-6 text-primary" />
          <span className="hidden sm:inline">보안과 관리자</span>
        </h1>
        <p className="sr-only">관리자 경계</p>
        <div className="ml-4 flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1 md:ml-8">
          {tabs.map((tab) => (
            <button type="button"
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`shrink-0 whitespace-nowrap rounded-md px-3 py-2 text-sm font-bold transition-colors md:px-4 ${
                activeTab === tab
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </header>

      <main className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-8">
        <div className="mx-auto max-w-6xl space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold text-muted-foreground">보안 거버넌스</p>
              <h2 className="mt-1 text-lg font-bold">접근 권한, 감사 근거, 쓰기 경계</h2>
            </div>
            <button
              type="button"
              disabled={loading}
              aria-busy={loading}
              onClick={() => {
                setLoading(true);
                setError(null);
                apiClient
                  .get<SecurityAccessSurface>('/api/security/access-surface')
                  .then(setData)
                  .catch((err: unknown) => setError(err instanceof Error ? err.message : 'unknown error'))
                  .finally(() => setLoading(false));
              }}
              className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-bold hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              {loading ? '새로고침 중' : '새로고침'}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-2 text-sm font-bold">
                <AlertOctagon className="size-4 text-red-600" /> 차단 우선
              </div>
              <p className="mt-1 text-xs text-muted-foreground">조직, 리전, 동의, 소유권 차단이 RBAC 허용보다 먼저 적용됩니다.</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-2 text-sm font-bold">
                <Share2 className="size-4 text-primary" /> 원본 소유권
              </div>
              <p className="mt-1 text-xs text-muted-foreground">WebDAV/CalDAV 원본은 고객 시스템이며 Naruon은 용량 제공자가 아닙니다.</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-2 text-sm font-bold">
                <Lock className="size-4 text-primary" /> 서명 세션 전용
              </div>
              <p className="mt-1 text-xs text-muted-foreground">브라우저는 bearer session으로만 보안 API를 호출합니다.</p>
            </div>
          </div>
          {content}
        </div>
      </main>
    </div>
  );
}
