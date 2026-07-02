# Naruon 20B Responsive Product Design QA

Audit date: 2026-07-02 KST

## Scope

Surface audited: Naruon full-product buyer-review IA.

Routes:

```text
/, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings
```

Viewports:

```text
desktop: 1440 x 1024
mobile: 390 x 844
```

Destination:

- Local screenshot evidence: `/tmp/naruon-full-product-responsive-qa/`
- Durable contact sheet: `docs/superpowers/reports/assets/2026-07-02-naruon-responsive-qa-contact-sheet.png`
- Figma destination: `68b5XB58w8nwT2LYOOnikK / QA Notes / Naruon 20B Responsive QA Evidence`
- Figma board node: `18:3`
- Figma contact-sheet image target node: `18:7`

## Command

```bash
NARUON_FULL_PRODUCT_SCREENSHOT_DIR=/tmp/naruon-full-product-responsive-qa \
NARUON_FULL_PRODUCT_VIEWPORTS=desktop,mobile \
pnpm --dir frontend run full:smoke
```

Result:

```text
Naruon full-product route smoke passed.
Routes: /, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings
Viewports: desktop(1440x1024), mobile(390x844)
Critical interactions: desktop:mail:select-message, desktop:mail:open-source-drawer, desktop:mail:generate-reply-draft, desktop:mail:send-simulated-reply, desktop:mail:send-provider-reply, desktop:mail:create-source-linked-task, desktop:search:select-result, desktop:search:open-source-evidence-tab, desktop:search:open-decision-assist-tab, desktop:search:capture-sender-relationship, desktop:search:verify-captured-relationship-state, desktop:search:open-network-graph, desktop:search:verify-network-graph-summary, desktop:search:verify-network-graph-canvas-label, desktop:calendar:create-writeback-intent, desktop:calendar:verify-etag-update-intent, desktop:calendar:request-provider-write, desktop:calendar:verify-provider-completion-state, desktop:calendar:verify-provider-no-retry-state, desktop:tasks:create-reply-sla-followup, desktop:tasks:complete-source-linked-task, desktop:tasks:create-knowledge-webdav-intent, desktop:tasks:request-knowledge-provider-write, desktop:tasks:verify-knowledge-provider-completion-state, desktop:tasks:verify-knowledge-provider-no-retry-state, desktop:projects:open-decision-log, desktop:projects:reopen-project-detail, desktop:projects:verify-source-boundary, desktop:data:create-embedding-regeneration-intent, desktop:data:create-hwp-conversion-intent, desktop:data:execute-webdav-materialization, desktop:data:verify-webdav-materialization-completion-state, desktop:data:create-webdav-writeback-intent, desktop:data:create-unique-thread-intent, desktop:data:open-quality-checks, desktop:ai-hub:open-workflow-tab, desktop:ai-hub:open-evaluation-tab, desktop:ai-hub:open-run-history-from-evidence, desktop:ai-hub:open-run-history, desktop:security:open-sharing-review, desktop:security:verify-external-write-block, desktop:security:open-policy-order, desktop:security:verify-deny-sample, desktop:settings:switch-ai-model-tab, desktop:settings:save-embedding-model, desktop:settings:save-account-config, desktop:settings:select-calendar-startup-view, desktop:settings:verify-startup-view-persistence, desktop:settings:rotate-connector-token, mobile:mail:select-message, mobile:mail:open-source-drawer, mobile:mail:generate-reply-draft, mobile:mail:send-simulated-reply, mobile:mail:send-provider-reply, mobile:mail:create-source-linked-task, mobile:search:select-result, mobile:search:open-source-evidence-tab, mobile:search:open-decision-assist-tab, mobile:search:capture-sender-relationship, mobile:search:verify-captured-relationship-state, mobile:search:open-network-graph, mobile:search:verify-network-graph-summary, mobile:search:verify-network-graph-canvas-label, mobile:calendar:create-writeback-intent, mobile:calendar:verify-etag-update-intent, mobile:calendar:request-provider-write, mobile:calendar:verify-provider-completion-state, mobile:calendar:verify-provider-no-retry-state, mobile:tasks:create-reply-sla-followup, mobile:tasks:complete-source-linked-task, mobile:tasks:create-knowledge-webdav-intent, mobile:tasks:request-knowledge-provider-write, mobile:tasks:verify-knowledge-provider-completion-state, mobile:tasks:verify-knowledge-provider-no-retry-state, mobile:projects:open-decision-log, mobile:projects:reopen-project-detail, mobile:projects:verify-source-boundary, mobile:data:create-embedding-regeneration-intent, mobile:data:create-hwp-conversion-intent, mobile:data:execute-webdav-materialization, mobile:data:verify-webdav-materialization-completion-state, mobile:data:create-webdav-writeback-intent, mobile:data:create-unique-thread-intent, mobile:data:open-quality-checks, mobile:ai-hub:open-workflow-tab, mobile:ai-hub:open-evaluation-tab, mobile:ai-hub:open-run-history-from-evidence, mobile:ai-hub:open-run-history, mobile:security:open-sharing-review, mobile:security:verify-external-write-block, mobile:security:open-policy-order, mobile:security:verify-deny-sample, mobile:settings:switch-ai-model-tab, mobile:settings:save-embedding-model, mobile:settings:save-account-config, mobile:settings:select-calendar-startup-view, mobile:settings:verify-startup-view-persistence, mobile:settings:rotate-connector-token
Accessibility checks: home:a11y-basics, mail:a11y-basics, search:a11y-basics, calendar:a11y-basics, tasks:a11y-basics, projects:a11y-basics, data:a11y-basics, ai-hub:a11y-basics, security:a11y-basics, settings:a11y-basics, home:a11y-basics, mail:a11y-basics, search:a11y-basics, calendar:a11y-basics, tasks:a11y-basics, projects:a11y-basics, data:a11y-basics, ai-hub:a11y-basics, security:a11y-basics, settings:a11y-basics
```

Figma placement result:

```text
QA Notes board created and verified.
Contact-sheet upload accepted with response imageHash e4162ee8c49646e320d48fff2eaf3b948006b0fa.
Figma node 18:7 verified with image fill hash e4162ee8c49646e320d48fff2eaf3b948006b0fa and FIT scale mode.
Verification screenshot confirmed the contact sheet and notes are visible inside board node 18:3.
```

## Evidence Files

Captured screenshot files:

```text
desktop-ai-hub.png
desktop-calendar.png
desktop-data.png
desktop-home.png
desktop-mail.png
desktop-projects.png
desktop-search.png
desktop-security.png
desktop-settings.png
desktop-tasks.png
mobile-ai-hub.png
mobile-calendar.png
mobile-data.png
mobile-home.png
mobile-mail.png
mobile-projects.png
mobile-search.png
mobile-security.png
mobile-settings.png
mobile-tasks.png
```

All desktop screenshots were verified at `1440 x 1024`. All mobile screenshots were verified at `390 x 844`.

## Findings

1. Desktop route and expanded selected workflow-state coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce non-empty screenshots.
   - Interaction evidence: mail source drawer, reply draft, simulated send, mocked provider-send completion, and source task creation; search evidence/assist tabs, captured relationship state, graph summary, and graph canvas label; calendar create/update/provider-write completion/no-retry state; task completion plus knowledge WebDAV intent and provider-write completion/no-retry state; project decision/detail/source boundary; data embedding, HWP, mocked WebDAV materialization completion, writeback, unique-thread, and quality checks; AI Hub workflow/evaluation/run history; security external-write block and deny sample; settings embedding save, account save, startup selection reload persistence, and connector token rotation all passed.
   - Health: pass for route-level and selected interaction smoke.

2. Mobile route and expanded selected workflow-state coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce mobile screenshots.
   - Interaction evidence: the same selected buyer-critical flows passed on the mobile viewport.
   - Health: pass for route-level and selected interaction smoke.

3. Desktop and mobile accessibility basics now have repeatable smoke evidence.
   - Evidence: all ten IA routes passed visible duplicate-ID, visible interactive accessible-name, and keyboard Tab focus-entry checks on desktop and mobile.
   - Health: pass for basic automated accessibility smoke.

4. Mobile Settings had a responsive label wrapping defect before correction.
   - Evidence: `mobile-settings.png` initially showed `일정 관리` split awkwardly inside a narrow 3-column card.
   - Fix: `frontend/src/components/SettingsLayout.tsx` now switches the startup view selector from `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`.
   - Health: fixed and re-captured.

5. The smoke gate still does not prove full workflow completion.
   - Evidence: the command now checks expected route text, console errors, not-found states, screenshot creation, broad selected desktop/mobile interactions across nine IA routes, and basic automated accessibility checks.
   - Remaining gap: live provider send/write execution against real connectors, production delivery confirmation, interactive graph selection/zoom/edge detail, permission edit/save flows, broader reload-backed settings persistence, and remaining route-specific drawer/modal variants need workflow-specific assertions before final procurement readiness.

## Accessibility Risks

- The current automated gate proves only three basic checks: no visible duplicate IDs, no visible interactive controls without accessible names, and keyboard Tab entry reaches a focusable element.
- It does not prove full keyboard order, focus trapping, screen-reader semantics, color contrast, zoom reflow, target size, or assistive-technology robustness.
- Bottom mobile navigation is visually present across routes; target-size and full focus-order verification remain unproven from screenshots and the basic gate alone.

## Product Design Assessment

The current branch now has repeatable desktop and mobile visual evidence for the ten buyer-review IA routes, expanded selected desktop/mobile workflow-state smoke evidence across nine IA routes, mocked provider completion result-state evidence, search graph summary/canvas-label evidence, startup-view reload persistence evidence, and basic automated accessibility evidence across desktop and mobile. This moves the package from route-existence evidence to responsive route-level evidence with materially broader workflow and accessibility proof, but it does not prove full sale readiness.

The remaining Product Design P0/P1 work is:

1. Expand interaction-state coverage from selected actions to complete workflow completion paths:
   - mail live provider send and delivery-state persistence
   - search interactive graph selection, zoom, and edge-detail variants beyond summary/canvas-label proof
   - calendar live provider write completion and conflict/result variants
   - task assignment, delegation, and live provider-backed completion variants
   - project evidence opening and source attachment variants
   - data live provider-executed WebDAV materialization and document action failure variants
   - AI Hub run/log detail beyond workflow, evaluation, and run-history navigation
   - security permission review
   - settings save persistence beyond startup-view reload and connector rotation
2. Expand accessibility evidence beyond the basic gate:
   - deterministic focus order for primary workflows
   - modal/drawer focus trapping
   - contrast sampling
   - screen-reader semantics for evidence drawers and workflow panels
3. Keep placing final screenshot evidence in Figma `QA Notes` after each accepted run.
4. Avoid claiming public launch or final procurement readiness until live provider, production deployment, rollback, support, security, and measured ROI evidence exist.
