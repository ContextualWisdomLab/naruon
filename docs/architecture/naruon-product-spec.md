# Naruon North Star Product Specification

## 1. Product Vision & Architecture
Naruon is not an email hosting server (SMTP/IMAP storage), but a **Web Client and AI Workspace** that acts as a Relay Proxy to customer-owned data sources.
- **Self-Hosted Runner**: For enterprises using private networks (on-premise Exchange, internal postfix/dovecot), Naruon uses a Self-Hosted Runner. This runner sits within the customer's VPC, establishes an outbound-only connection to `naruon.net`, and securely proxies IMAP/SMTP/CalDAV traffic.
- **Data Sovereignty**: Naruon stores only metadata, AI extracted intent, and task state. CalDAV/WebDAV read/writebacks prioritize the customer's own servers.

## 2. Universal Access Control (RBAC/ABAC)
The platform supports a Universal structure:
- **Platform Admin (SaaS Provider)**: Global system management.
- **Enterprise (B2B2C)**: Corporate groups, organizational units, and independent departments.
- **Security & IT Admins**: Role delegation.
- **SOHO / B2C**: Individual users.
- **Authentication**: Keycloak is the primary Enterprise OIDC target, with Casdoor as a lightweight alternative. Traefik is used for edge routing and gateway policies.

## 3. Core Features & AI Agent Ontology
- **Thread Consolidation**: Emails imported via ZIP or forwarded across accounts are normalized into unified threads based on unique constraints and fingerprints.
- **DAG Sender Ontology**: Naruon can display owner-scoped, source-backed sender relationship records and their provenance. Automatic relationship type, confidence, and next-action judgments must come from a separately validated semantic/model authority; repository-authored keyword, sender-domain, local-part, or phrase rules are not relationship evidence. Until that authority is configured, automatic source capture fails closed and persists no guessed relationship.
- **Self-Sent Knowledge Indexing**: Emails sent to oneself are automatically parsed and structured into a connected WebDAV or Notes system.
- **Ticket-based Tasks**: To-Do items are treated as trackable Tickets with statuses, priorities, and 2-way links to the original email threads and calendar events.
- **Reply Tracking**: The system tracks unanswered sent emails and queues them in the Dashboard.
- **CalDAV/WebDAV Integration**: Naruon merges events from N accounts. AI-organized events and attachments are written back (writeback) to the most appropriate source account based on context.

## 4. Branding & User Experience (UX)
- **Selectable Startup View**: Users can select whether the Dashboard, Email, or Calendar appears first upon login.
- **10 Core GNB Menus**: Home, Mail, Calendar, Tasks, Projects, Context Search, Data, AI Hub, Security, Settings.
- **Responsive Design**: Full cross-resolution testing via Playwright (Mobile, Tablet, Desktop) ensures hamburger menu integrity and no horizontal scroll clipping.
- **No Dead Space**: Marketing placeholders are replaced with functional metrics, execution queues, and actionable insights.

## 5. Observability & Governance
- **Open Source APM**: Application Performance Monitoring is implemented using OpenTelemetry, Prometheus, Loki, Tempo, and Grafana.
- **CI/CD Automation**: GitHub Actions and CodeRabbitAI are used for autonomous reviews. A missing AI review is a wait-state, not a blocker.
- **Error Handling**: `Timeout`, `Fatal`, `Warn`, and `Denied` outputs in tests or execution are treated as hard failures.
- **Database Standards**: All database tables and columns must use two-word `snake_case` (e.g., `task_title`, `status_code`).
- **Anti-Regression**: All identified bug patterns and public/private identifier leaks are documented in `AGENTS.md` to prevent recurrence.