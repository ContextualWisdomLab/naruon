# 이메일 콘텐츠 그래프 Phase 1 실행 계획

작성일: 2026-07-02
대상 PR: #895
범위: 이메일 본문과 텍스트 계열 첨부를 DOM 유사 노드와 문단 세그먼트로 분해하는 내부 순수 파서 기반을 추가한다.

## 목표

Phase 1의 완료 기준은 기존 `email_parser`와 `email_import_service`의 동작을 변경하지 않으면서, 이후 DB 저장과 지식 그래프 엣지 생성을 붙일 수 있는 안정적인 중간 표현을 제공하는 것이다.

구현 산출물은 `backend/services/content_graph/` 내부 패키지로 둔다. 아직 별도 라이브러리, submodule, 외부 패키지 분리는 하지 않는다. 첫 소비자는 Naruon 백엔드 하나이고, 데이터 모델과 UX 계약이 아직 검증 중이므로 내부 모듈이 변경 비용이 가장 낮다. 두 번째 소비자나 고객 SDK가 생기는 시점에 패키지 분리 여부를 다시 결정한다.

## 구현 단계

1. `backend/tests/test_content_graph_parser.py`를 먼저 추가한다.
   - plain text 본문을 빈 줄 기준 문단 세그먼트로 나누는지 검증한다.
   - HTML 본문에서 block DOM 경로, heading 경로, 안전 텍스트가 생성되는지 검증한다.
   - Markdown heading 문맥이 문단 세그먼트에 붙는지 검증한다.
   - script/style/template 내용과 활성 HTML이 결과 텍스트에 남지 않는지 검증한다.

2. 실패하는 테스트를 확인한다.
   - 명령: `cd backend && python3 -m pytest -q tests/test_content_graph_parser.py`
   - 예상 실패: `services.content_graph` 모듈이 아직 존재하지 않는다.

3. `backend/services/content_graph/models.py`를 추가한다.
   - `ContentNode`: 원본 내부의 DOM 유사 구조 단위.
   - `ContentSegment`: 검색, 임베딩, 그래프 엣지 생성의 최소 문단 단위.
   - `ParseResult`: 파싱 결과와 원본 콘텐츠 해시.
   - UID와 해시는 deterministic SHA-256 기반으로 만든다.

4. `backend/services/content_graph/parser.py`를 추가한다.
   - `parse_content(source_kind, source_record_uid, content, content_type, display_name)` public API를 제공한다.
   - `text/plain`은 빈 줄 기준 문단으로 나눈다.
   - `text/markdown`은 heading stack을 유지하면서 heading/paragraph 세그먼트를 만든다.
   - `text/html`은 stdlib `html.parser.HTMLParser`로 block-level 노드를 만들고 기존 `strip_html_markup` 안전 텍스트 계약을 재사용한다.
   - 지원하지 않는 MIME 타입은 안전 텍스트 fallback으로 단일 문단 세그먼트를 만든다.

5. `backend/services/content_graph/__init__.py`에서 public API를 노출한다.

6. 테스트를 통과시킨다.
   - `cd backend && python3 -m pytest -q tests/test_content_graph_parser.py`
   - 회귀 확인: `cd backend && python3 -m pytest -q tests/test_email_parser.py tests/test_email_import_service.py tests/test_text_safety.py`

7. CodeGraph와 git 상태를 확인한다.
   - `codegraph sync`
   - `codegraph status`
   - `.Jules/*` 대소문자 충돌 변경은 건드리지 않는다.

8. 커밋과 PR 갱신을 한다.
   - 커밋 메시지: `feat: add content graph parser foundation`
   - 브랜치: `plan/email-dom-paragraph-kg-2026-07-02`
   - PR #895에 Phase 1 구현이 포함되었음을 푸시한다.

## Phase 1 비범위

- DB 마이그레이션과 `content_nodes`, `content_segments`, `knowledge_graph_edges` 테이블 추가.
- import pipeline에서 실제 저장 또는 임베딩 job fan-out 연결.
- PDF, DOCX, XLSX, HWP 등 바이너리 첨부의 deep parser.
- Figma Code Connect.
- 고객 데이터나 실제 이메일을 외부 CI/공개 runner로 업로드하는 테스트.

## 다음 Phase 진입 조건

- `parse_content`가 본문/첨부 텍스트에 대해 deterministic UID와 안전 텍스트를 생성한다.
- 기존 이메일 import, text safety 테스트가 깨지지 않는다.
- 문단 단위 저장 스키마와 검색 UX가 PR 설명과 설계 문서에서 같은 용어로 연결된다.
