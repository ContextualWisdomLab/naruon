# Naruon 20B Buyer Demo Script

Date: 2026-07-02 KST

## Purpose

This script supports a controlled enterprise buyer technical review. It avoids claiming public-launch readiness, live ROI, or final procurement completion.

## Pre-demo Checks

Run before a buyer session:

```bash
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend full:smoke
```

Optional pilot-depth checks:

```bash
pnpm --dir frontend test scripts/pilot-ui-smoke.test.mjs
pnpm --dir frontend pilot:smoke
```

Required evidence to have open:

- PR #893: `https://github.com/ContextualWisdomLab/naruon/pull/893`
- Figma file `68b5XB58w8nwT2LYOOnikK`, frame `Sales Demo / 20B Enterprise Review Flow`
- Current audit: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`
- Buyer package: `docs/superpowers/reports/2026-07-02-naruon-20b-buyer-package.md`

## Opening Talk Track

```text
Naruon is being shown as a controlled enterprise technical-review package. The demo proves buyer-visible workflows, privacy-safe local measurement for pilot flows, and governance evidence. It does not claim public SaaS launch readiness or final procurement completion.
```

## Flow 1: Home Context

Route: `/`

Show:

- Navigation across mail, calendar, tasks, projects, search, data, AI Hub, security, and settings.
- Context synthesis as the first working surface.
- The distinction between buyer-review surfaces and production-live evidence still needed.

Evidence:

- `frontend/scripts/full-product-ui-smoke.mjs`
- Screenshot path produced by smoke: `/tmp/naruon-full-product-smoke/home.png`

## Flow 2: Mail Evidence And Source Review

Route: `/mail`

Show:

- Mail list item.
- Context synthesis in the mail detail surface.
- Source evidence drawer.
- Focus trap, Escape close, and source-grounded review.

Talk track:

```text
The core value is not generic summarization. The buyer can inspect source evidence before acting.
```

Evidence:

- `frontend/src/components/EmailDetail.tsx`
- `frontend/src/components/SourceDrawer.tsx`
- `frontend/scripts/pilot-ui-smoke.mjs`

## Flow 3: Privacy-safe Draft And Action Creation

Route: `/mail`

Show:

- Draft generation.
- Development-mode send simulation.
- Action item creation.
- Calendar reflection intent.

Required caveat:

```text
Provider-send and provider-write evidence is not final procurement evidence yet. The current package proves intent handling and UI flow; live provider execution must be proven in a buyer-approved environment.
```

Evidence:

- `frontend/src/lib/product-events.ts`
- `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`
- `docs/superpowers/reports/2026-07-02-naruon-kpi-validation.md`

## Flow 4: Search And Relationship Capture

Route: `/search`

Show:

- Context search.
- Result detail.
- Sender relationship capture.
- Action reason displayed from source context.

Evidence:

- `frontend/src/components/SearchLayout.tsx`
- `frontend/scripts/pilot-ui-smoke.mjs`

## Flow 5: Tasks

Route: `/tasks`

Show:

- Ticket counts.
- Kanban columns.
- Source-linked action item.
- Priority and status changes.

Evidence:

- `frontend/src/components/TasksLayout.tsx`
- `frontend/scripts/full-product-ui-smoke.mjs`
- Screenshot path: `/tmp/naruon-full-product-smoke/tasks.png`

## Flow 6: Data And Files

Route: `/data`

Show:

- Data repository surface.
- File/document evidence state.
- Pipeline and quality checks.
- Explicit provider-write boundary language.

Evidence:

- `frontend/src/components/DataLayout.tsx`
- `backend/api/data.py`
- Screenshot path: `/tmp/naruon-full-product-smoke/data.png`

## Flow 7: AI Hub

Route: `/ai-hub`

Show:

- Prompt/workflow/agent surfaces.
- Provider readiness cards.
- Evaluation metric placeholders.

Required caveat:

```text
The framework is ready for evaluation reporting, but live evaluation scores and ROI claims require measured pilot data.
```

Evidence:

- `frontend/src/components/AIHubLayout.tsx`
- `backend/api/ai_hub.py`

## Flow 8: Security And Settings

Routes: `/security`, `/settings`

Show:

- RBAC/ABAC security governance surface.
- Audit and policy tabs.
- Workspace settings.
- AI model and connector configuration boundaries.

Evidence:

- `frontend/src/components/SecurityLayout.tsx`
- `frontend/src/components/SettingsLayout.tsx`
- `backend/api/security.py`
- `docs/superpowers/reports/2026-07-02-naruon-security-governance-followup.md`

## Closing Talk Track

```text
This package is ready for a controlled technical review and pilot acceptance discussion after CI gates pass. Final procurement requires production deployment proof, live provider evidence, security/legal approval, support/SLA agreement, and measured ROI.
```

## Do Not Say

- "Naruon is public-launch ready."
- "The 20B KRW sale is guaranteed."
- "Live ROI has been proven."
- "All provider writes are production-proven."
- "Issue #634 is closed."
