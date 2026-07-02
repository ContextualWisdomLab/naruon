# Naruon 20B Full Product Commercial Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Naruon from a controlled frontend pilot slice into a buyer-reviewable full product package for a 2,000,000,000 KRW enterprise sale review.

**Architecture:** Keep the current monorepo as the source of truth. Extend existing frontend, backend, connector, Figma, and docs boundaries before introducing any new package. Separate proof artifacts from product code: implementation changes live in existing source modules, while sales-readiness evidence lives under `docs/superpowers/`.

**Tech Stack:** Next 16, React 19, TypeScript 6, Vitest, Playwright, FastAPI, Python 3.14 CI target, PostgreSQL, Docker Compose, Figma MCP (`get_metadata`, `search_design_system`, `use_figma`, `get_screenshot` with Code Connect excluded), GitHub app/CLI evidence, Product Design screenshot audit, Data Analytics KPI framework.

## Global Constraints

- Do not use Figma Code Connect.
- Do not add a git submodule in the first pass.
- Do not split a separately versioned library until at least three independent consumers or independent release ownership exists.
- Do not add a new frontend dependency for work already covered by React, Next, CSS, existing UI components, Vitest, or Playwright.
- Do not claim public launch readiness from PR #893.
- Do not claim live KPI values without a live analytics source.
- Do not send raw email body, raw draft body, raw search query, credentials, provider usernames, or raw mailbox paths to analytics.
- Preserve existing user changes in `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat review-process delay as non-blocking; treat actual failing checks or reproducible product defects as blocking.

---

## File Structure

- Create: `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md`
  - Owns the 20B KRW full-product completion standard.
- Create: `docs/superpowers/plans/2026-07-02-naruon-20b-full-product-commercial-readiness.md`
  - Owns this implementation plan.
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`
  - Captures current evidence, gaps, and non-blockers.
- Modify later: `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`
  - Add new events only after the corresponding UI actions exist.
- Modify later: `frontend/src/components/*`
  - Extend UI surfaces area by area.
- Modify later: `backend/api/*`, `backend/services/*`, `backend/tests/*`
  - Add production-path evidence for provider integration, authorization, audit, and data quality.
- Modify later: Figma file `68b5XB58w8nwT2LYOOnikK`
  - Repair or recreate required pages without Code Connect.

## Task 1: Lock Current Evidence

**Files:**
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`

**Interfaces:**
- Consumes: GitHub PR #893, issue #634, Figma metadata, Product Design context preflight, repo tree, existing superpowers docs.
- Produces: A stable baseline used by every later task.

- [x] **Step 1: Record branch and dirty state**

Run:

```bash
git -C naruon status --short --branch
git -C naruon log --oneline -5
```

Expected:

```text
## sellable-pilot-hardening-2026-07-02
 M .Jules/palette.md
 M .Jules/sentinel.md
```

- [x] **Step 2: Record PR #893 status**

Run:

```bash
gh -R ContextualWisdomLab/naruon pr view 893 --json number,title,url,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
```

Expected evidence:

- head SHA is `a970b78c5eb6664e844b48ce15689feb0c27bda2`.
- `opencode-review` may be `IN_PROGRESS`.
- Passing app/security/image checks are product evidence.
- `CHANGES_REQUESTED` and review delay are tracked separately from actual product blockers.

- [x] **Step 3: Record Figma file reality**

Use Figma tools:

```text
get_metadata(fileKey="68b5XB58w8nwT2LYOOnikK")
search_design_system(fileKey="68b5XB58w8nwT2LYOOnikK", query="naruon dashboard mail search calendar security settings evidence drawer", disableCodeConnect=true)
```

Expected evidence:

- Current metadata exposes top-level page `Source Map`.
- Design-system search returns no components, variables, or styles.
- Required follow-up is Figma file structure repair or verified replacement.

- [x] **Step 4: Record GitHub issue #634**

Use GitHub app:

```text
fetch_issue(repository_full_name="ContextualWisdomLab/naruon", issue_number=634)
```

Expected evidence:

- Issue is open.
- The issue tracks a post-merge security gate governance gap, not a current PR #893 code failure.

## Task 2: Define Full-Product Commercial Standard

**Files:**
- Create: `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md`

**Interfaces:**
- Consumes: `docs/ui-ux/naruon-ui-ux-mapping.md`, existing commercial pilot spec, current PR evidence.
- Produces: Product, design, analytics, security, ops, and commercial gates.

- [x] **Step 1: Separate pilot slice from full sale readiness**

Write this rule into the spec:

```text
PR #893 proves a controlled frontend pilot slice. It does not prove final enterprise procurement or public launch readiness.
```

- [x] **Step 2: Define ten-area product coverage**

Use these areas exactly:

```text
Home, Mail, Calendar, Tasks, Projects, Context Search, Data, AI Hub, Security, Settings
```

Each area must have buyer-visible UI coverage, runnable test coverage, and either live integration evidence or explicit caveat language.

- [x] **Step 3: Define non-negotiable gates**

Include gates for:

```text
buyer-visible product coverage
real integration boundaries
security and compliance
production operations
Figma and Product Design evidence
Data Analytics and ROI
commercial handoff
```

## Task 3: Decide Library/Submodule Boundary

**Files:**
- Create: `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md`
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`

**Interfaces:**
- Consumes: current repo layout, `frontend/package.json`, `backend/`, `connector/`.
- Produces: A boundary decision for future implementation.

- [x] **Step 1: Reject submodule for the first pass**

Decision:

```text
No git submodule now. The work has one product repo, one active frontend package, one backend, one connector, and no independent external consumer that justifies submodule overhead.
```

- [x] **Step 2: Reject separate published library for the first pass**

Decision:

```text
No separately versioned library now. Keep shared code under existing frontend/backend boundaries until there are at least three consumers, independent release ownership, or a public API contract.
```

- [x] **Step 3: Allow a future internal workspace package only with evidence**

Allowed future condition:

```text
Create an internal workspace package only if product events, design tokens, or shared UI primitives are reused by frontend, a separate admin console, and buyer demo tooling.
```

## Task 4: Repair Or Replace Figma Structure

**Files:**
- Figma file: `68b5XB58w8nwT2LYOOnikK`
- Update after work: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`

**Interfaces:**
- Consumes: Figma `Source Map`, canonical mockups under `docs/ui-ux/mockups/`.
- Produces: Required Figma pages and page metadata evidence.

- [x] **Step 1: Create missing pages without Code Connect**

Use `use_figma` with `skillNames="figma-use"` and this JavaScript:

```js
const requiredPages = [
  "Source Map",
  "Foundations",
  "Components",
  "Desktop Screens",
  "Mobile Screens",
  "Interaction States",
  "Sales Demo",
  "QA Notes",
];

const existing = new Set(figma.root.children.map((page) => page.name));
const createdNodeIds = [];

for (const name of requiredPages) {
  if (!existing.has(name)) {
    const page = figma.createPage();
    page.name = name;
    createdNodeIds.push(page.id);
  }
}

return {
  existingPages: Array.from(existing),
  requiredPages,
  createdNodeIds,
  allPages: figma.root.children.map((page) => ({ id: page.id, name: page.name })),
};
```

Expected:

```text
Figma returns createdNodeIds for missing pages and allPages includes all eight required pages.
```

- [x] **Step 2: Verify page metadata**

Use:

```text
get_metadata(fileKey="68b5XB58w8nwT2LYOOnikK")
```

Expected:

```text
Top-level pages include Source Map, Foundations, Components, Desktop Screens, Mobile Screens, Interaction States, Sales Demo, QA Notes.
```

Actual 2026-07-02 KST evidence:

```text
use_figma returned allPages with all eight required pages.
get_metadata without nodeId still listed only Source Map, so direct page metadata was also checked.
get_metadata(nodeId="15:3") confirmed the Sales Demo page.
```

- [x] **Step 3: Add a Sales Demo frame**

Create a `Sales Demo / 20B Enterprise Review Flow` frame on the `Sales Demo` page. It must list:

```text
1. Home decision dashboard
2. Mail evidence-to-action
3. Context search to relation capture
4. Calendar/task provider intent
5. Data quality and document materialization
6. AI Hub workflow run evidence
7. Security access/audit proof
8. Settings members/accounts/billing/developer package
```

Expected:

```text
The frame is visible in Figma and has no placeholder shimmer left enabled.
```

Actual 2026-07-02 KST evidence:

```text
Sales Demo page id: 15:3
Sales Demo frame id: 16:2
Frame name: Sales Demo / 20B Enterprise Review Flow
Final screenshot downloaded to /tmp/naruon-20b-sales-demo-final.png
PNG size: 1080 x 608
Visual inspection: no text overlap, no clipped bottom copy, no placeholder shimmer.
```

## Task 5: Build Product Design Audit Package

**Files:**
- Create later: `docs/superpowers/reports/2026-07-02-naruon-20b-product-design-audit.md`
- Create later: `docs/superpowers/artifacts/naruon-20b-product-design-audit/`

**Interfaces:**
- Consumes: local running app, Figma, existing mockups.
- Produces: screenshot-backed UX and accessibility findings.

- [ ] **Step 1: Capture buyer flows**

Capture these routes at desktop 1440 x 1024 and mobile 390 x 844:

```text
/
/mail
/search
/calendar
/tasks
/projects
/data
/ai-hub
/security
/settings
```

Expected:

```text
Every screenshot is saved locally and inspected before being accepted.
```

- [ ] **Step 2: Write audit findings**

Each finding must include:

```text
severity
flow step
screenshot path
what failed or passed
user impact
concrete fix
```

Expected:

```text
No finding relies on memory or uninspected screenshots.
```

## Task 6: Expand Data Analytics Readiness

**Files:**
- Modify: `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`
- Create later: `docs/superpowers/reports/2026-07-02-naruon-20b-kpi-roi-model.md`

**Interfaces:**
- Consumes: existing event dictionary, product-event implementation, buyer sale target.
- Produces: KPI/ROI model with measurement caveats.

- [ ] **Step 1: Add full-product event candidates only after UI actions exist**

Candidate events:

```text
home_decision_opened
calendar_candidate_confirmed
task_status_changed
project_decision_logged
data_quality_check_requested
ai_workflow_run_started
security_permission_changed
settings_member_invited
provider_write_intent_created
provider_write_executed
```

Expected:

```text
No event is marked implemented unless code emits it and tests cover privacy-safe payloads.
```

- [ ] **Step 2: Define ROI model**

Minimum model:

```text
time_saved_per_user_per_week_hours
fully_loaded_hourly_cost_krw
weekly_active_users
evidence_open_rate
decision_to_action_conversion_rate
pilot_period_weeks
risk_reduction_adjustment
```

Formula:

```text
estimated_period_value_krw =
  time_saved_per_user_per_week_hours
  * fully_loaded_hourly_cost_krw
  * weekly_active_users
  * pilot_period_weeks
  * risk_reduction_adjustment
```

Expected:

```text
The report labels all unmeasured values as assumptions and does not claim live performance.
```

## Task 7: Extend Full Product Smoke Gates

**Files:**
- Modify later: `frontend/scripts/pilot-ui-smoke.mjs`
- Create: `frontend/scripts/full-product-ui-smoke.mjs`
- Create: `frontend/scripts/full-product-ui-smoke.test.mjs`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: existing localhost-only pilot smoke.
- Produces: full-product browser smoke that stays localhost-only.

- [x] **Step 1: Add localhost-only resolver test**

Use the existing `resolvePilotBaseUrl()` pattern. The full-product smoke must reject:

```text
https://staging.example.com
https://naruon.example.com
http://192.168.0.10:3000
```

Expected:

```text
The smoke script can only target localhost, 127.0.0.1, ::1, or [::1].
```

- [x] **Step 2: Exercise all ten routes**

The script must visit:

```text
/
/mail
/search
/calendar
/tasks
/projects
/data
/ai-hub
/security
/settings
```

Expected:

```text
Every route renders without console errors and saves a screenshot.
```

Actual implementation:

```text
Added frontend/scripts/full-product-ui-smoke.mjs.
Added frontend/scripts/full-product-ui-smoke.test.mjs.
Added pnpm --dir frontend full:smoke.
The route smoke covers /, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings.
```

Validation evidence captured on 2026-07-02 KST:

```text
pnpm --dir frontend test scripts/full-product-ui-smoke.test.mjs
Test Files  1 passed (1)
Tests       3 passed (3)

pnpm --dir frontend full:smoke
Naruon full-product route smoke passed.
Routes: /, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings
Screenshots: /tmp/naruon-full-product-smoke/home.png, /tmp/naruon-full-product-smoke/mail.png, /tmp/naruon-full-product-smoke/search.png, /tmp/naruon-full-product-smoke/calendar.png, /tmp/naruon-full-product-smoke/tasks.png, /tmp/naruon-full-product-smoke/projects.png, /tmp/naruon-full-product-smoke/data.png, /tmp/naruon-full-product-smoke/ai-hub.png, /tmp/naruon-full-product-smoke/security.png, /tmp/naruon-full-product-smoke/settings.png
```

## Task 8: Close Security Governance Gaps

**Files:**
- Modify: `scripts/ci/pr_governance_gate.sh`
- Modify: `scripts/ci/test_pr_governance_gate.sh`
- Create: `docs/superpowers/reports/2026-07-02-naruon-security-governance-followup.md`

**Interfaces:**
- Consumes: issue #634.
- Produces: proof that future request-changes or missing required-check metadata cannot pass as green governance.

- [x] **Step 1: Reproduce issue #634 condition**

Read issue #634 and inspect current governance script behavior.

Expected:

```text
The report identifies whether the green governance check can still occur when blocker metadata is unreadable.
```

- [x] **Step 2: Patch the smallest policy path**

Ponytail rule:

```text
Patch one central gate, not every PR workflow.
```

Expected:

```text
The gate exits non-zero when it emits a blocker comment about unreadable required-check metadata.
```

Actual implementation:

```text
scripts/ci/pr_governance_gate.sh exits 1 after posting/updating a blocker comment.
scripts/ci/test_pr_governance_gate.sh now records and asserts blocker, wait-state, and pass exit codes.
No `.github` workflow change was required because the trusted workflow already runs the central script.
```

Validation evidence captured on 2026-07-02 KST:

```text
bash scripts/ci/test_pr_governance_gate.sh
test_pr_governance_gate: PASS

cd backend && python3 -m pytest tests/test_release_governance.py -q
29 passed in 0.21s
```

## Task 9: Build Commercial Handoff Package

**Files:**
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-buyer-package.md`
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-demo-script.md`
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-security-questionnaire.md`
- Create: `docs/superpowers/reports/2026-07-02-naruon-20b-sla-support-draft.md`

**Interfaces:**
- Consumes: verified product flows, security reports, analytics model, Figma screenshots.
- Produces: buyer-facing artifacts.

- [x] **Step 1: Write buyer package index**

Sections:

```text
product overview
demo script
architecture
deployment
security
privacy
analytics
SLA/support
pilot acceptance
known caveats
evidence links
```

Expected:

```text
Every claim links to a repo file, PR, test, screenshot, Figma node, or report.
```

Actual implementation:

```text
Created buyer package index, buyer demo script, security questionnaire draft, and SLA/support draft.
The documents explicitly reject public-launch, guaranteed 20B ROI, complete provider-write proof, and issue #634 closure claims.
```

## Task 10: Final Verification And Completion Decision

**Files:**
- Update: all reports above.

**Interfaces:**
- Consumes: all implementation and evidence artifacts.
- Produces: final completion or explicit not-complete decision.

- [ ] **Step 1: Run local gates**

Run:

```bash
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend pilot:smoke
git diff --check
```

Expected:

```text
Every command exits 0 before claiming local frontend readiness.
```

- [ ] **Step 2: Run backend gates**

Run:

```bash
cd naruon/backend
pytest
```

Expected:

```text
Backend tests pass before claiming production-path readiness.
```

- [ ] **Step 3: Run evidence scans**

Run:

```bash
rg -n "Figma Code Connect|Code Connect" docs/superpowers frontend/src backend | cat
rg -n "public launch ready|live KPI|20B complete|20억 완성" docs/superpowers frontend/src backend | cat
```

Expected:

```text
Matches are either explicit exclusions or guarded caveats, not unsupported success claims.
```

- [ ] **Step 4: Decide completion**

Completion is allowed only when:

```text
all ten IA surfaces have buyer-visible UI proof
Figma required pages and screenshots exist
Product Design audit has no P0/P1/P2 blockers
analytics/ROI reports separate assumptions from measurements
production/security/ops/commercial reports exist
local and remote gates pass
open governance risks are either closed or buyer-facing caveats
```

Expected:

```text
If any item is missing, keep the Goal active and continue work.
```
