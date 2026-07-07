# Project Semantic Knowledge Graph 제품화 실행 계획

작성일: 2026-07-02
기준: PR #895가 develop에 병합된 이후의 다음 실행 단계
Goal: 20억 원 판매 가능 제품 기준으로 이메일/첨부 DOM·문단 지식그래프를 프로젝트 관리 자동화 그래프로 확장한다.
Figma 산출물: [Naruon Project Semantic KG FigJam](https://www.figma.com/board/ayoR2im9q2xNCxR4hNK2nN)
Figma Code Connect: 제외

## 완료 기준

다음 조건이 충족되면 이 단계는 판매 가능한 제품화 계획으로 닫을 수 있다.

- `docs/superpowers/specs/2026-07-02-project-semantic-knowledge-graph-productization.md`가 제품 정의, 아키텍처, KPI, 라이브러리 분리 판단을 담는다.
- 새 구현 PR들은 이 문서의 phase 순서와 verification gate를 따른다.
- 모든 phase는 source segment citation, confidence/correction, workspace isolation, private runner 원칙을 유지한다.
- Review process와 queued GitHub checks는 blocker가 아니며, 실패 로그가 있는 current-head check만 수정 대상으로 본다.

## Phase 1: Project Graph 내부 모델과 golden corpus

목표: project semantic layer를 DB 변경 없이 read-only extractor로 먼저 세운다.

파일:

- `backend/services/project_graph/__init__.py`
- `backend/services/project_graph/models.py`
- `backend/services/project_graph/extractors.py`
- `backend/tests/test_project_graph_extractors.py`
- `backend/tests/fixtures/project_graph/*.json`

구현:

- `ProjectObjectType` enum을 추가한다.
  - `project_candidate`
  - `requirement`
  - `feature`
  - `issue`
  - `milestone`
  - `wbs_item`
  - `deliverable`
  - `participant`
  - `data_requirement`
  - `erd_candidate`
  - `infra_requirement`
  - `report_delta`
  - `wiki_projection`
- `ProjectSemanticObject` dataclass를 추가한다.
  - `uid`, `object_type`, `title`, `summary`, `source_segment_uids`, `confidence`, `extractor_name`, `extractor_version`, `attributes`.
- `ProjectSemanticEdge` dataclass를 추가한다.
  - `source_uid`, `target_uid`, `edge_type`, `confidence`, `source_segment_uids`.
- deterministic extractor부터 구현한다.
  - Korean/English requirement keyword.
  - date/milestone phrase.
  - blocker/risk/question/approval phrase.
  - data/entity/field/privacy phrase.
  - infra/environment/network/runner/secret/SLO phrase.
- golden fixture는 실제 메일이 아니라 합성 segment로 만든다.

검증:

- `cd backend && python3 -m pytest -q tests/test_project_graph_extractors.py`
- `ruff check backend/services/project_graph backend/tests/test_project_graph_extractors.py`
- extractor 결과는 source segment UID 없는 객체를 생성하면 실패한다.

## Phase 2: Projection persistence와 correction trail

목표: read-only extractor 결과를 저장하고 사람이 고칠 수 있는 audit surface를 만든다.

파일:

- `backend/db/models.py`
- `backend/db/migrations/versions/*_add_project_graph_projection.py`
- `backend/services/project_graph/repository.py`
- `backend/services/project_graph/projection.py`
- `backend/tests/test_project_graph_projection.py`

구현:

- `ProjectGraphObjectRecord` 모델을 추가한다.
  - workspace scope, object type, title, summary, status, confidence, extractor audit, source segment citations.
- `ProjectGraphEdgeRecord` 모델을 추가한다.
  - object-to-object traceability edge와 source segment citations.
- `ProjectGraphCorrectionRecord` 모델을 추가한다.
  - human action, before/after, rationale, actor, timestamp.
- import 직후 자동 저장은 아직 켜지 않는다. batch command 또는 service call로 projection을 생성한다.

검증:

- migration upgrade/downgrade smoke.
- `cd backend && python3 -m pytest -q tests/test_project_graph_projection.py tests/test_data_api.py`
- workspace가 다른 source segment를 edge에 섞으면 실패한다.

## Phase 3: Project auto registration과 traceability API

목표: 고객이 import 후 프로젝트 후보와 traceability path를 API로 조회할 수 있게 한다.

파일:

- `backend/api/projects.py` 또는 기존 router의 project section.
- `backend/services/project_graph/project_registration.py`
- `backend/services/project_graph/traceability.py`
- `backend/tests/test_project_graph_api.py`
- `frontend/src/components/data-layout/types.ts`

API:

- `GET /api/projects/candidates`
- `POST /api/projects/candidates/{candidate_uid}/confirm`
- `GET /api/projects/{project_uid}/traceability`
- `GET /api/projects/{project_uid}/evidence/{object_uid}`
- `POST /api/projects/{project_uid}/corrections`

구현:

- 프로젝트 후보는 thread cluster, participant density, requirement/deliverable/date signal로 점수화한다.
- traceability API는 requirement -> feature -> WBS -> issue -> deliverable -> report/wiki path를 반환한다.
- 모든 response item은 citation bundle을 포함한다.

검증:

- source segment가 삭제되거나 workspace scope가 맞지 않으면 API는 404/403을 반환한다.
- `cd backend && python3 -m pytest -q tests/test_project_graph_api.py`

## Phase 4: Project Command Center UX

목표: "자동 생성된 프로젝트 관리 지식그래프"를 사용자가 검토하고 수정할 수 있는 첫 화면을 만든다.

파일:

- `frontend/src/app/projects/page.tsx`
- `frontend/src/components/projects/ProjectCommandCenter.tsx`
- `frontend/src/components/projects/TraceabilityMap.tsx`
- `frontend/src/components/projects/EvidenceInspector.tsx`
- `frontend/src/components/projects/WbsProjectionTabs.tsx`
- `frontend/src/components/projects/ReportWikiPanel.tsx`
- `frontend/src/components/projects/__tests__/*.test.tsx`

UX:

- 첫 화면은 project list, graph health, traceability map, WBS/issue/milestone tabs, Evidence Inspector로 구성한다.
- 카드 중첩 없이 밀도 높은 업무 화면으로 만든다.
- AI 요약 텍스트 옆에는 항상 citation count와 source open action이 있어야 한다.
- Waterfall/Agile WBS는 같은 source object를 다른 projection으로 보여준다.
- report/wiki panel은 "generate draft"와 "regenerate from graph"를 구분한다.

검증:

- `cd frontend && corepack pnpm test --run src/components/projects`
- Playwright 또는 기존 frontend smoke가 있으면 project route를 열어 citation click을 검증한다.
- Product Design audit 기준으로 text overflow, broken spacing, card nesting, uncited AI text를 확인한다.

## Phase 5: Reports, wiki, data/ERD/infra automation

목표: 프로젝트 관리자가 바로 살 수 있는 업무 산출물을 만든다.

파일:

- `backend/services/project_graph/reporting.py`
- `backend/services/project_graph/wiki.py`
- `backend/services/project_graph/data_requirements.py`
- `backend/services/project_graph/erd.py`
- `backend/services/project_graph/infra_requirements.py`
- `backend/tests/test_project_graph_reporting.py`
- `backend/tests/test_project_graph_data_infra.py`

구현:

- daily report는 지난 24시간 graph delta로 생성한다.
- weekly report는 requirement, issue, milestone, deliverable, participant, risk movement를 묶는다.
- wiki page는 graph projection view이며 별도 truth source가 아니다.
- data requirement는 entity, attribute, source, retention, privacy, quality rule로 나눈다.
- ERD는 candidate와 approved를 분리한다.
- infra requirement는 environment, network, host, runner, storage, backup, SLO, deployment, compliance control을 추출한다.

검증:

- uncited generated paragraph가 있으면 실패한다.
- stale source segment를 가진 wiki/report snapshot은 freshness warning을 표시한다.

## Phase 6: Buyer diligence evidence package

목표: 20억 원 판매 협상에서 기술 실사자가 확인할 수 있는 증거 묶음을 만든다.

파일:

- `docs/superpowers/plans/2026-07-02-project-kg-buyer-evidence-checklist.md`
- `backend/scripts/project_graph_benchmark.py`
- `backend/scripts/private_project_graph_smoke.py`
- `frontend/src/app/data/page.tsx` evidence summary 확장.

증거:

- private corpus import timing.
- parser success, paragraph coverage, semantic extraction precision sample.
- source-backed decision rate.
- citation click success.
- correction trail sample.
- cross-workspace isolation sample.
- local/private runner proof.
- Figma/FigJam architecture and workflow diagram.

검증:

- `python3 backend/scripts/project_graph_benchmark.py --fixture backend/tests/fixtures/project_graph`
- private real mail은 local/private runner에서만 실행한다.
- public CI에는 합성 fixture만 사용한다.

## KPI Gate

MVP gate:

- `source_backed_project_decision_rate >= 0.95`
- `citation_click_success_rate >= 0.99`
- `unsupported_parser_false_success_count = 0`
- `cross_workspace_leak_count = 0`
- `uncited_generated_report_paragraph_count = 0`

Pilot gate:

- 1,000-message private corpus에서 project candidate, requirement, WBS, issue, deliverable, data requirement, infra requirement, daily/weekly report draft가 생성된다.
- p95 import-to-project-ready time은 120초 이내다.
- semantic extractor precision sample은 0.85 이상이다.
- human correction이 projection과 report/wiki에 반영된다.

Sale gate:

- 고객 실사자가 10개 샘플 요구사항을 선택했을 때 10개 모두 source segment, related WBS, issue/deliverable, report/wiki paragraph까지 추적된다.
- buyer evidence package가 architecture, security, KPI, private runner, correction trail, UI screenshot을 포함한다.
- 라이브러리 분리 필요성이 pilot에서 입증되기 전까지 submodule/package split은 보류한다.

## PR 순서

1. `feat: add project graph extractor foundation`
2. `feat: persist project graph projections`
3. `feat: expose project traceability api`
4. `feat: add project command center`
5. `feat: generate cited project reports and wiki`
6. `docs: add project kg buyer evidence package`

각 PR은 작게 유지한다. Review process와 queued checks는 blocker가 아니며, 실패 로그가 있는 current-head check만 수정한다.
