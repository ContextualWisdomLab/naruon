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
```

Figma placement result:

```text
QA Notes board created and verified.
Contact-sheet image uploaded with imageHash 9a0afeec7bb84c24f4369154c88d1e9c5a775a1f.
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

1. Desktop route coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce non-empty screenshots.
   - Health: pass for route-level smoke.

2. Mobile route coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce mobile screenshots.
   - Health: pass for route-level smoke.

3. Mobile Settings had a responsive label wrapping defect before correction.
   - Evidence: `mobile-settings.png` initially showed `일정 관리` split awkwardly inside a narrow 3-column card.
   - Fix: `frontend/src/components/SettingsLayout.tsx` now switches the startup view selector from `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`.
   - Health: fixed and re-captured.

4. The smoke gate still verifies route rendering, not full workflow completion.
   - Evidence: the command checks expected route text, console errors, not-found states, and screenshot creation.
   - Remaining gap: critical interactions such as send, writeback confirmation, graph expansion, permission edits, connector rotation, and settings save need workflow-specific assertions before final procurement readiness.

## Accessibility Risks

- Screenshots alone do not prove keyboard order, focus trapping, screen-reader semantics, or color contrast compliance.
- The fixed mobile settings selector reduces visible text wrapping risk, but a full accessibility pass still needs keyboard and accessibility-tree checks.
- Bottom mobile navigation is visually present across routes; target-size and focus-state verification remain unproven from screenshots alone.

## Product Design Assessment

The current branch now has repeatable desktop and mobile visual evidence for the ten buyer-review IA routes. This moves the package from route-existence evidence to responsive route-level evidence, but it does not prove full sale readiness.

The remaining Product Design P0/P1 work is:

1. Add interaction-state coverage for the most important buyer flows:
   - mail selection and reply draft
   - search result detail and source drawer
   - calendar writeback intent
   - task completion
   - project evidence opening
   - data quality action
   - AI Hub run/log detail
   - security permission review
   - settings save and connector rotation
2. Capture keyboard/focus evidence for mobile and desktop.
3. Keep placing final screenshot evidence in Figma `QA Notes` after each accepted run.
4. Avoid claiming public launch or final procurement readiness until live provider, production deployment, rollback, support, security, and measured ROI evidence exist.
