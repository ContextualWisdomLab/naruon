# Button Action Contract

Naruon screens must not contain decorative buttons. Every button, tab, menu item, hot spot, and empty-state call-to-action must map to a route, service action, or modal/drawer state that helps the customer take the next step.

## Universal action contract

Every interactive control must define:

| Field | Requirement |
| --- | --- |
| `action_name` | Stable product action name. |
| `action_type` | `navigate`, `open_modal`, `open_drawer`, `query`, `create`, `update`, `delete`, `provider_write`, `ai_run`, `job_run`. |
| `permission_scope` | Workspace, project, mail, document, security, admin, or developer scope. |
| `input_context` | Source objects needed by the action. |
| `side_effect` | None, local DB change, provider writeback, external sharing, destructive change. |
| `confirmation` | Whether the user must confirm. |
| `loading_state` | Visible progress copy. |
| `success_state` | Next-action success copy. |
| `error_state` | Recoverable user action. |
| `audit_event` | Required for side-effecting actions. |

## Top-level navigation

| Button | Action |
| --- | --- |
| Home | Navigate to today's judgment/action overview. |
| Mail | Navigate to inbox with last-used filters. |
| Calendar | Navigate to calendar with current period. |
| Tasks | Navigate to task board/list. |
| Projects | Navigate to project list. |
| Context Search | Open unified search. |
| Data | Navigate to document and pipeline control plane. |
| AI Hub | Navigate to prompt, workflow, agent, evaluation, and run controls. |
| Security | Navigate to security dashboard. |
| Settings | Navigate to workspace settings. |

## Home actions

| Control | Type | Action |
| --- | --- | --- |
| Open judgment point | navigate | Open source mail/thread/task/calendar context. |
| Defer judgment point | update | Mark point as deferred with a review time. |
| Create action item | create | Create task candidate from selected judgment point. |
| Resolve schedule conflict | open_drawer | Open conflict resolution drawer. |
| Open recent mail | navigate | Open mail detail. |
| New mail | navigate | Open compose. |
| Add event | open_modal | Open calendar event modal. |
| New project | open_modal | Open project creation modal. |

## Mail actions

| Control | Type | Action |
| --- | --- | --- |
| Compose | navigate | Open compose page. |
| Send | provider_write | Validate recipients, attachments, policy, then send. |
| Save draft | create/update | Store draft revision. |
| AI draft reply | ai_run | Generate evidence-bound draft from thread and artifacts. |
| Regenerate draft | ai_run | Re-run draft with selected tone and context. |
| Insert draft | update | Insert generated text into composer. |
| Context synthesis | ai_run | Build thread/document context synthesis. |
| Judgment points | ai_run | Extract decision points with citations. |
| Create task | create | Convert selected action item candidate to task. |
| Reflect to calendar | provider_write | Create/update event after conflict and If-Match checks. |
| Merge thread | update | Add manual thread override edge. |
| Split thread | update | Create new canonical thread from selected message. |
| Analyze attachment | job_run | Queue parser/OCR/vision job. |
| Download attachment | provider_write/read | Download if policy allows. |
| Move to folder | provider_write | Apply folder/label state. |
| Archive/delete | provider_write | Confirm destructive or visibility-changing provider action. |

## Calendar actions

| Control | Type | Action |
| --- | --- | --- |
| New event | open_modal | Open event form. |
| Save event | provider_write | Write to connected calendar. |
| Find meeting time | query | Compute available slots from attendees/calendars. |
| Propose time | provider_write | Send/update meeting proposal. |
| Accept candidate | provider_write | Promote AI calendar candidate to event. |
| Reject candidate | update | Store rejection feedback. |
| Open related mail | navigate | Open source thread. |
| Resolve conflict | open_drawer | Open side-by-side conflict view. |

## Task actions

| Control | Type | Action |
| --- | --- | --- |
| New task | open_modal/create | Create task. |
| Change assignee | update | Update assignee and audit. |
| Change status | update | Move task state. |
| Drag card | update | Persist status/order move. |
| Change due date | update | Open date picker and persist date. |
| Link mail | open_modal/update | Add task-mail edge. |
| Add checklist item | update | Append checklist row. |
| Comment | create | Add activity log entry. |
| Complete task | update | Mark done and ask whether related judgment point is resolved. |

## Project actions

| Control | Type | Action |
| --- | --- | --- |
| New project | open_modal/create | Create project record. |
| Open project | navigate | Open detail page. |
| Add milestone | create | Create milestone. |
| Add decision | create | Create decision log entry. |
| Link document | update | Add context graph edge. |
| Link mail | update | Add project-mail edge. |
| Open dashboard | navigate | Open project-specific dashboard. |
| Export report | job_run | Generate project report artifact. |

## Context search actions

| Control | Type | Action |
| --- | --- | --- |
| Search | query | Run hybrid text/vector/graph search. |
| Filter | query | Re-run search with filter constraints. |
| Open result | navigate | Open result detail. |
| Synthesize result | ai_run | Create evidence-bound synthesis for selected cluster. |
| Expand graph | query | Increase graph depth for selected node. |
| Open timeline item | navigate | Open source event/mail/document. |
| Save search | create | Save query and filter state. |

## Data actions

| Control | Type | Action |
| --- | --- | --- |
| Upload | create/job_run | Register document and start parser job. |
| Re-parse | job_run | Re-run parser for selected document. |
| Re-embed | job_run | Rebuild embeddings. |
| Quality check | job_run | Run quality rule suite. |
| Quarantine | update | Mark file as quarantined and revoke ordinary search visibility. |
| HWP convert | job_run | Run sandbox HWP conversion worker. |
| View provenance | navigate/open_drawer | Show source section/page/image evidence. |

## AI Hub actions

| Control | Type | Action |
| --- | --- | --- |
| Test prompt | ai_run | Run prompt on a controlled sample. |
| Publish prompt | update | Publish prompt version. |
| Run workflow | job_run/ai_run | Execute workflow graph. |
| Add node | update | Insert workflow node. |
| Run agent | ai_run | Execute selected agent with tool and data policy. |
| Start evaluation | job_run | Run evaluation set. |
| View run log | navigate/open_drawer | Show execution log, artifacts, tokens, latency, model version. |

## Security actions

| Control | Type | Action |
| --- | --- | --- |
| Change permission | update | Update RBAC/ABAC policy. |
| Approve share | update/provider_write | Approve external share with expiry and audit. |
| Reject share | update | Deny share request. |
| Revoke share | update/provider_write | Disable active external access. |
| Open audit event | navigate/open_drawer | Show event details and source object. |
| Publish policy | update | Publish policy version. |
| Export report | job_run | Generate compliance/security report. |

## Settings actions

| Control | Type | Action |
| --- | --- | --- |
| Save workspace | update | Persist workspace metadata. |
| Invite member | create/provider_write | Send invite. |
| Connect account | provider_write | Start OAuth flow. |
| Disconnect account | update/provider_write | Revoke integration. |
| Add automation rule | create | Create rule with trigger and action. |
| Create API key | create | Generate secret and display once. |
| Add webhook | create | Validate endpoint then save. |
| Change plan | provider_write/update | Start billing plan change flow. |

## Empty/loading/error copies

Every state must include a next action.

| State | Copy rule |
| --- | --- |
| Empty | Explain what is missing and provide one CTA. |
| Loading | Explain what is being fetched or generated. |
| Partial | Show what succeeded and what can be retried. |
| Error | Provide a retry, settings, or support action. |
| Permission denied | Explain who can grant access. |
| Quarantined | Explain why access is limited and how to request review. |
