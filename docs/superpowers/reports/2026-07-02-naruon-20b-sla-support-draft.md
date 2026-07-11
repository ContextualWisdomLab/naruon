# Naruon 20B SLA And Support Draft

Date: 2026-07-02 KST

## Status

Draft for commercial negotiation. This is not a signed SLA.

## Service Scope

Covered in a controlled pilot:

- Naruon frontend workspace.
- Backend API for configured tenant environment.
- Customer-owned connectors that are explicitly enabled for the pilot.
- Source-grounded mail, search, task, data, AI Hub, security, and settings workflows.

Excluded unless separately contracted:

- Public SaaS multi-tenant launch.
- Buyer production cutover.
- Live provider writes outside an approved pilot environment.
- Custom SSO, DPA, and incident terms that are not yet approved.

## Draft Support Tiers

| Tier | Target response | Scope |
| --- | --- | --- |
| P0 critical outage | 1 business hour | Service unavailable, security incident, data exposure suspicion |
| P1 major degradation | 4 business hours | Core workflow unusable for pilot users |
| P2 functional defect | 1 business day | Important feature degraded with workaround |
| P3 question or enhancement | 3 business days | Usage questions, reporting requests, backlog items |

Final response targets must be buyer-approved and tied to staffed support hours.

## Draft Availability Language

For a controlled pilot:

```text
Availability is measured only for the contracted pilot environment and excludes planned maintenance, buyer-owned source-system outage, identity provider outage, and unsupported provider/network changes.
```

Do not claim a production uptime target until:

- Production environment exists.
- Monitoring and alerting are active.
- On-call owner is assigned.
- Backup and rollback procedures are tested.
- Buyer maintenance windows are agreed.

## Draft Incident Process

1. Detect incident through monitoring, user report, or CI/security alert.
2. Classify P0/P1/P2/P3.
3. Open an incident record with time, impact, affected tenant, and suspected source.
4. Assign owner and communication channel.
5. Mitigate or roll back.
6. Preserve evidence for security and audit review.
7. Publish RCA for P0/P1 incidents.

Required production evidence before final procurement:

- Monitoring dashboard.
- Alert routing.
- Rollback runbook.
- Backup/restore proof.
- Security incident escalation contact.
- Data exposure notification workflow.

## Draft Acceptance Gates

A buyer pilot should not start until:

- Current PR head has passing required CI.
- `pnpm --dir frontend full:smoke` passes.
- Security caveats are disclosed.
- Live provider-write scope is either disabled, simulated, or explicitly approved.
- Support owner and escalation channel are named.

Final procurement should not proceed until:

- Production deployment and rollback proof are attached.
- Security questionnaire is approved.
- DPA and retention terms are approved.
- SLA response/availability targets are signed.
- Measured pilot KPI report is available.

## Evidence Links

- Commercial readiness spec: `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md`
- Current audit: `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md`
- Security questionnaire draft: `docs/superpowers/reports/2026-07-02-naruon-20b-security-questionnaire.md`
- Buyer package index: `docs/superpowers/reports/2026-07-02-naruon-20b-buyer-package.md`
