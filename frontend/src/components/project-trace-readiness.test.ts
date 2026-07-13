import { describe, expect, it } from 'vitest';

import {
  buildAutomationBrief,
  buildProjectControlReadinessLayer,
  buildProjectReportDraftLayer,
  groupProjectTraceObjects,
  type ProjectTraceObject,
} from './project-trace-readiness';

const citation = {
  content_segment_uid: 'segment-alpha-1',
  source_kind: 'email_body',
  source_record_uid: '<alpha@example.com>',
  heading_path: 'Project kickoff',
  segment_path: '/document[1]/paragraph[1]',
  ordinal_index: 1,
  safe_text_excerpt: '결제 화면은 카드 승인 실패 시 재시도 안내를 반드시 보여줘야 합니다.',
};

function traceObject(objectType: string, title = `${objectType} title`, citationCount = 1): ProjectTraceObject {
  return {
    object_uid: `${objectType}:alpha`,
    object_type: objectType,
    title,
    summary: `${title} summary`,
    status_code: 'open',
    confidence: 0.8,
    source_segment_uids: ['segment-alpha-1'],
    citation_bundle: Array.from({ length: citationCount }, (_, index) => ({
      ...citation,
      content_segment_uid: `segment-alpha-${index + 1}`,
      ordinal_index: index + 1,
    })),
    attributes: {},
  };
}

describe('project trace readiness helpers', () => {
  it('groups trace objects by type while preserving repeated object order', () => {
    const firstIssue = traceObject('issue', 'First issue');
    const milestone = traceObject('milestone', 'Milestone');
    const secondIssue = traceObject('issue', 'Second issue');

    const grouped = groupProjectTraceObjects([firstIssue, milestone, secondIssue]);

    expect(grouped.get('issue')).toEqual([firstIssue, secondIssue]);
    expect(grouped.get('milestone')).toEqual([milestone]);
    expect(groupProjectTraceObjects([]).size).toBe(0);
  });

  it('builds automation, report, and control readiness layers from complete evidence', () => {
    const grouped = groupProjectTraceObjects([
      traceObject('requirement', '카드 승인 실패 재시도 안내', 2),
      traceObject('feature', '재시도 CTA', 1),
      traceObject('deliverable', 'QA 산출물', 1),
      traceObject('issue', 'PG timeout risk', 1),
      traceObject('milestone', '7월 결제 UX 베타 동결', 1),
      traceObject('wbs_item', '결제 재시도 UX 작업 패키지', 1),
      traceObject('participant', 'PM owner', 1),
      traceObject('report_delta', '주간 보고: 결제 재시도 리스크', 1),
      traceObject('wiki_projection', 'Alpha Checkout 위키 초안', 1),
      traceObject('data_requirement', '결제 실패 사유 데이터 요건', 1),
      traceObject('erd_candidate', 'PaymentAttempt ERD 후보', 1),
      traceObject('infra_requirement', 'PG timeout 관측 인프라', 1),
    ]);

    const automation = buildAutomationBrief(grouped);
    const report = buildProjectReportDraftLayer(grouped);
    const control = buildProjectControlReadinessLayer(grouped);

    expect(automation.readyDomainCount).toBe(5);
    expect(automation.metrics).toContainEqual({ key: 'coverage', label: 'Automation coverage', value: 5 });
    expect(automation.domains.find((domain) => domain.key === 'data')).toMatchObject({
      count: 3,
      citationCount: 3,
      primaryTitle: '결제 실패 사유 데이터 요건',
    });
    expect(report.readyDraftCount).toBe(2);
    expect(report.statusUpdate).toBe('상태 자동 업데이트: PG timeout risk 검토 필요');
    expect(report.riskAction).toBe('다음 액션: PG timeout risk 확인');
    expect(report.metrics).toContainEqual({ key: 'status', label: 'Status update ready', value: 1 });
    expect(control.readyItemCount).toBe(5);
    expect(control.reviewerAction).toBe('검토자 액션: 누락 근거 없음, 인수 검토 가능');
    expect(control.metrics).toContainEqual({ key: 'acceptanceAction', label: 'Acceptance-to-action coverage', value: 1 });
    expect(control.metrics).toContainEqual({ key: 'scopeRisk', label: 'Scope-risk balance', value: 1 });
  });

  it('returns actionable fallback copy when evidence is missing or has no citations', () => {
    const emptyGroup = groupProjectTraceObjects([]);
    const sparseGroup = groupProjectTraceObjects([
      traceObject('milestone', '  ', 0),
      traceObject('requirement', 'Scope requirement', 0),
    ]);

    const emptyAutomation = buildAutomationBrief(emptyGroup);
    const emptyReport = buildProjectReportDraftLayer(emptyGroup);
    const emptyControl = buildProjectControlReadinessLayer(emptyGroup);
    const sparseReport = buildProjectReportDraftLayer(sparseGroup);
    const sparseControl = buildProjectControlReadinessLayer(sparseGroup);

    expect(emptyAutomation.readyDomainCount).toBe(0);
    expect(emptyAutomation.domains[0].primaryTitle).toBe('근거 객체 대기');
    expect(emptyReport.readyDraftCount).toBe(0);
    expect(emptyReport.drafts[0]).toMatchObject({
      summary: '주간 보고에 반영할 변화와 리스크 근거가 아직 없습니다.',
      sourceTitle: '근거 객체 대기',
      citationCount: 0,
    });
    expect(emptyReport.statusUpdate).toBe('상태 자동 업데이트: 보고 근거 기준 진행 중');
    expect(emptyReport.riskAction).toBe('다음 액션: 리스크 근거 대기');
    expect(emptyReport.metrics).toContainEqual({ key: 'risk', label: 'Risk action coverage', value: 0 });
    expect(emptyReport.metrics).toContainEqual({ key: 'status', label: 'Status update ready', value: 0 });
    expect(emptyControl.readyItemCount).toBe(0);
    expect(emptyControl.missingEvidenceCount).toBe(5);
    expect(emptyControl.reviewerAction).toBe('검토자 액션: 5개 컨트롤 근거 보강');
    expect(emptyControl.metrics).toContainEqual({ key: 'score', label: 'Control readiness score', value: 0 });
    expect(emptyControl.metrics).toContainEqual({ key: 'acceptanceAction', label: 'Acceptance-to-action coverage', value: 0 });
    expect(emptyControl.metrics).toContainEqual({ key: 'scopeRisk', label: 'Scope-risk balance', value: 0 });
    expect(sparseReport.statusUpdate).toBe('상태 자동 업데이트: 보고 근거 기준 진행 중');
    expect(sparseReport.metrics).toContainEqual({ key: 'status', label: 'Status update ready', value: 1 });
    expect(sparseControl.readyItemCount).toBe(0);
    expect(sparseControl.items.find((item) => item.key === 'schedule')).toMatchObject({
      count: 1,
      citationCount: 0,
      primaryTitle: '근거 객체 대기',
    });
  });
});
