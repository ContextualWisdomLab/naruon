# E1 Story 1.3 attachment acceptance audit

Status: partial implementation, protected merge not authorized.

Contract: [platform plan, Story 1.3](../planning/naruon-platform-plan.md).
Evidence tree: `b14ff3d7e2700a3833c60fd7c5ab8a26912e3cd1`.

| Requirement | Implementation and evidence | Remaining proof |
| --- | --- | --- |
| Attachments become nodes and segments linked to their message | `backend/services/content_graph/parser.py`; import wiring in `backend/services/email_import_service.py`; deferred PDF recognition in `backend/services/newsdom_worker.py` | An actual NewsDOM/MinerU service run with representative nonconfidential PDF inputs; parser unit tests alone do not prove remote recognition |
| Facts become KG nodes with exact segment citations | `extract_attachment_facts` in `backend/services/project_graph/extractors.py`; import and recognition workers persist the projection; fact API checks source UID and text hash | Current extractor promotes literal labelled facts only. General prose interpretation remains unproven; do not call Story 1.3 complete on the strength of this slice |
| Attachments appear beside their message | `backend/api/emails.py` returns metadata in the owned thread and bounded source pages; `frontend/src/components/EmailDetail.tsx` loads on open and follows exact source UIDs | Broader accessibility, locale, performance acceptance and hosted current-head checks/review |
| Parse failures retain filenames and are searchable by metadata | Thread response/UI keep filename and parse status. Filename search implementation is separately proposed in #1792 | Revalidate the union after #1792 and #1795 merge into develop; this branch's UI evidence does not establish filename search adoption |

## Verification recorded in this audit

On the evidence tree, the project environment ran:

```sh
cd backend
/Users/seonghobae/naruon/backend/.venv/bin/python -m pytest \
  tests/test_attachment_parser.py tests/test_content_graph_parser.py \
  tests/test_project_graph_extractors.py tests/test_project_graph_projection.py -q
```

Result: 48 passed. These cover parser classification, graph decomposition,
literal fact extraction, and PostgreSQL persistence/owner isolation. They do
not prove production model inference, remote PDF service availability, or
protected merge eligibility.

The preceding browser evidence at `af7bb6db` passed desktop, tablet, and mobile
attachment opening, first-page failure/retry, exact citation focus, pagination,
and horizontal overflow checks. The subsequent source-lookup recovery change
at the evidence tree passed 26 component tests, TypeScript and ESLint; browser
coverage of that subsequent change has not been claimed.

## Dependency and next-action order

1. Obtain current-head hosted checks/reviews for #1794 (baseline PostgreSQL
   smoke repair), #1792 (filename fallback), #1795 (literal cited facts), and
   #1793 (thread source UI). Merge only after each protected gate is satisfied.
2. Bring the dependent UI branch forward by an ordinary merge of develop after
   the fact parent lands, inspect its remaining three-dot diff, and rerun the
   relevant suite against the resulting head.
3. Verify a PDF recognition service run and the resulting message/attachment
   source identity, persisted facts, and UI citation from the same source.
4. Resolve broader fact inference and frontend locale/performance acceptance
   against the platform contract before marking Story 1.3 complete.

Actions queue cause is still unproven. REST job evidence was unavailable because
its response reported core quota remaining zero; GraphQL PR state remained
readable. Quota exhaustion explains the observation failure, not queued jobs.
Do not cancel/restart model runs or reduce inference time budgets based on this
missing evidence.
