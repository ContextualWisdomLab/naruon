import { toSafeReactText } from '@/lib/safe-text';

export interface ProjectCitation {
  content_segment_uid: string;
  source_kind: string;
  source_record_uid: string;
  heading_path: string | null;
  segment_path: string | null;
  ordinal_index: number;
  safe_text_excerpt: string;
}

export interface ProjectTraceObject {
  object_uid: string;
  object_type: string;
  title: string;
  summary: string;
  status_code: string;
  confidence: number;
  source_segment_uids: string[];
  citation_bundle: ProjectCitation[];
  attributes: Record<string, unknown>;
}

export interface AutomationBriefMetric {
  key: string;
  label: string;
  value: number;
}

export interface AutomationBriefDomain {
  key: string;
  label: string;
  description: string;
  objectTypes: string[];
  count: number;
  citationCount: number;
  primaryTitle: string;
}

export interface AutomationBrief {
  domains: AutomationBriefDomain[];
  metrics: AutomationBriefMetric[];
  readyDomainCount: number;
  totalDomainCount: number;
}

export interface ProjectReportDraft {
  key: string;
  label: string;
  summary: string;
  sourceTitle: string;
  sourceCount: number;
  citationCount: number;
}

export interface ProjectReportDraftLayer {
  drafts: ProjectReportDraft[];
  metrics: AutomationBriefMetric[];
  readyDraftCount: number;
  totalDraftCount: number;
  statusUpdate: string;
  riskAction: string;
  reviewerAction: string;
}

export interface ProjectControlReadinessItem {
  key: string;
  label: string;
  description: string;
  objectTypes: string[];
  count: number;
  citationCount: number;
  primaryTitle: string;
}

export interface ProjectControlReadinessLayer {
  items: ProjectControlReadinessItem[];
  metrics: AutomationBriefMetric[];
  readyItemCount: number;
  totalItemCount: number;
  missingEvidenceCount: number;
  summary: string;
  reviewerAction: string;
}

type ProjectTraceObjectGroups = ReadonlyMap<string, readonly ProjectTraceObject[]>;

function safeText(value: string | null | undefined, fallback = '') {
  return toSafeReactText(value, fallback).trim() || fallback;
}

function matchingObjects(
  groupedObjects: ProjectTraceObjectGroups,
  objectTypes: readonly string[],
) {
  return objectTypes.flatMap((type) => groupedObjects.get(type) ?? []);
}

export function groupProjectTraceObjects(objects: readonly ProjectTraceObject[]) {
  const grouped = new Map<string, ProjectTraceObject[]>();
  for (const projectObject of objects) {
    const currentGroup = grouped.get(projectObject.object_type);
    if (currentGroup) {
      currentGroup.push(projectObject);
    } else {
      grouped.set(projectObject.object_type, [projectObject]);
    }
  }
  return grouped;
}

export function buildAutomationBrief(groupedObjects: ProjectTraceObjectGroups): AutomationBrief {
  const domains = [
    {
      key: 'wbs',
      label: 'WBS / 일정',
      description: 'Waterfall·Agile 실행 단위를 일정과 WBS로 묶습니다.',
      objectTypes: ['wbs_item', 'milestone'],
    },
    {
      key: 'report',
      label: '보고 자동 생성',
      description: '주간·일일 보고 초안에 들어갈 변화와 리스크를 모읍니다.',
      objectTypes: ['report_delta'],
    },
    {
      key: 'wiki',
      label: '프로젝트 위키',
      description: 'LLM Wiki 스타일 프로젝트 지식 페이지 후보를 표시합니다.',
      objectTypes: ['wiki_projection'],
    },
    {
      key: 'data',
      label: '데이터·ERD·인프라',
      description: '데이터 요건, ERD 후보, 인프라 요건을 같은 근거 체인으로 묶습니다.',
      objectTypes: ['data_requirement', 'erd_candidate', 'infra_requirement'],
    },
    {
      key: 'deliverable',
      label: '산출물 준비도',
      description: '요구사항에서 산출물까지 추적 가능한 납품 후보를 계산합니다.',
      objectTypes: ['requirement', 'feature', 'deliverable'],
    },
  ].map((domain) => {
    const objects = matchingObjects(groupedObjects, domain.objectTypes);
    return {
      ...domain,
      count: objects.length,
      citationCount: objects.reduce((total, projectObject) => total + projectObject.citation_bundle.length, 0),
      primaryTitle: safeText(objects[0]?.title, '근거 객체 대기'),
    };
  });
  const readyDomainCount = domains.filter((domain) => domain.count > 0).length;
  const reportReadyCount = domains.find((domain) => domain.key === 'report')!.count;
  const wikiReadyCount = domains.find((domain) => domain.key === 'wiki')!.count;
  return {
    domains,
    readyDomainCount,
    totalDomainCount: domains.length,
    metrics: [
      { key: 'coverage', label: 'Automation coverage', value: readyDomainCount },
      { key: 'report', label: 'Report ready signals', value: reportReadyCount },
      { key: 'wiki', label: 'Wiki ready signals', value: wikiReadyCount },
    ],
  };
}

function buildDraft(
  groupedObjects: ProjectTraceObjectGroups,
  key: string,
  label: string,
  objectTypes: readonly string[],
  fallbackSummary: string,
): ProjectReportDraft {
  const objects = matchingObjects(groupedObjects, objectTypes);
  const primaryObject = objects[0];
  return {
    key,
    label,
    summary: safeText(primaryObject?.summary, fallbackSummary),
    sourceTitle: safeText(primaryObject?.title, '근거 객체 대기'),
    sourceCount: objects.length,
    citationCount: objects.reduce((total, projectObject) => total + projectObject.citation_bundle.length, 0),
  };
}

export function buildProjectReportDraftLayer(groupedObjects: ProjectTraceObjectGroups): ProjectReportDraftLayer {
  const issueObject = groupedObjects.get('issue')?.[0];
  const milestoneObject = groupedObjects.get('milestone')?.[0];
  const weeklyDraft = buildDraft(
    groupedObjects,
    'weekly',
    '주간 보고 초안',
    ['report_delta', 'milestone', 'deliverable', 'issue'],
    '주간 보고에 반영할 변화와 리스크 근거가 아직 없습니다.',
  );
  const dailyDraft = buildDraft(
    groupedObjects,
    'daily',
    '일일 보고 초안',
    ['issue', 'requirement', 'wbs_item'],
    '일일 보고에 반영할 실행 항목 근거가 아직 없습니다.',
  );
  const readyDraftCount = [weeklyDraft, dailyDraft].filter((draft) => draft.sourceCount > 0).length;
  const riskAction = issueObject
    ? `다음 액션: ${safeText(issueObject.title, '이슈 근거')} 확인`
    : '다음 액션: 리스크 근거 대기';
  const statusUpdate = issueObject
    ? `상태 자동 업데이트: ${safeText(issueObject.title, '이슈')} 검토 필요`
    : `상태 자동 업데이트: ${safeText(milestoneObject?.title, '보고 근거')} 기준 진행 중`;
  return {
    drafts: [weeklyDraft, dailyDraft],
    readyDraftCount,
    totalDraftCount: 2,
    statusUpdate,
    riskAction,
    reviewerAction: `검토자 액션: ${readyDraftCount}개 보고 초안 근거 확인`,
    metrics: [
      { key: 'report', label: 'Report readiness', value: readyDraftCount },
      { key: 'risk', label: 'Risk action coverage', value: issueObject ? 1 : 0 },
      { key: 'status', label: 'Status update ready', value: groupedObjects.size > 0 ? 1 : 0 },
    ],
  };
}

export function buildProjectControlReadinessLayer(groupedObjects: ProjectTraceObjectGroups): ProjectControlReadinessLayer {
  const items = [
    {
      key: 'acceptance',
      label: 'Acceptance coverage',
      description: '요구사항, 기능, 산출물이 인수 기준으로 이어지는지 확인합니다.',
      objectTypes: ['requirement', 'feature', 'deliverable'],
    },
    {
      key: 'schedule',
      label: 'Schedule confidence',
      description: '마일스톤과 WBS 근거가 일정 추적에 충분한지 확인합니다.',
      objectTypes: ['milestone', 'wbs_item'],
    },
    {
      key: 'scope',
      label: 'Scope clarity',
      description: '요구사항과 위키 후보가 프로젝트 범위를 설명하는지 확인합니다.',
      objectTypes: ['requirement', 'feature', 'wiki_projection'],
    },
    {
      key: 'dataInfra',
      label: 'Data/infra readiness',
      description: '데이터 요건, ERD 후보, 인프라 요건이 함께 잡혔는지 확인합니다.',
      objectTypes: ['data_requirement', 'erd_candidate', 'infra_requirement'],
    },
    {
      key: 'ownerAction',
      label: 'Owner/action readiness',
      description: '담당자, 이슈, WBS 근거가 다음 액션으로 이어지는지 확인합니다.',
      objectTypes: ['participant', 'issue', 'wbs_item'],
    },
  ].map((item) => {
    const objects = matchingObjects(groupedObjects, item.objectTypes);
    return {
      ...item,
      count: objects.length,
      citationCount: objects.reduce((total, projectObject) => total + projectObject.citation_bundle.length, 0),
      primaryTitle: safeText(objects[0]?.title, '근거 객체 대기'),
    };
  });
  const readyItemCount = items.filter((item) => item.count > 0 && item.citationCount > 0).length;
  const missingEvidenceCount = items.length - readyItemCount;
  const acceptanceReady = items.find((item) => item.key === 'acceptance')?.count ? 1 : 0;
  const actionReady = items.find((item) => item.key === 'ownerAction')?.count ? 1 : 0;
  const scopeReady = items.find((item) => item.key === 'scope')?.count ? 1 : 0;
  const riskReady = groupedObjects.has('issue') ? 1 : 0;
  return {
    items,
    readyItemCount,
    totalItemCount: items.length,
    missingEvidenceCount,
    summary: `실행 준비 종합: ${readyItemCount}개 컨트롤이 문단 근거로 준비됨`,
    reviewerAction: missingEvidenceCount > 0
      ? `검토자 액션: ${missingEvidenceCount}개 컨트롤 근거 보강`
      : '검토자 액션: 누락 근거 없음, 인수 검토 가능',
    metrics: [
      { key: 'score', label: 'Control readiness score', value: Math.round((readyItemCount / items.length) * 100) },
      { key: 'missing', label: 'Missing evidence count', value: missingEvidenceCount },
      { key: 'acceptanceAction', label: 'Acceptance-to-action coverage', value: acceptanceReady && actionReady ? 1 : 0 },
      { key: 'scopeRisk', label: 'Scope-risk balance', value: scopeReady && riskReady ? 1 : 0 },
    ],
  };
}
