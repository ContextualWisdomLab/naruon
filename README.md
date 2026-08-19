# Naruon

[![Application CI](https://github.com/ContextualWisdomLab/naruon/actions/workflows/app-ci.yml/badge.svg)](https://github.com/ContextualWisdomLab/naruon/actions/workflows/app-ci.yml)
[![Bandit Security Scan](https://github.com/ContextualWisdomLab/naruon/actions/workflows/bandit.yml/badge.svg)](https://github.com/ContextualWisdomLab/naruon/actions/workflows/bandit.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ContextualWisdomLab/naruon)

**Naruon is a self-hostable work hub for customer-owned email, calendar, files, tasks, projects, search, and AI-assisted workflows.**

It connects to systems an organization already controls, keeps bounded workspace metadata and provenance in PostgreSQL, and gives users one place to review work, find context, create follow-up actions, and operate integrations without turning Naruon into the authoritative mailbox, calendar, or file server.

## What Naruon provides

| Workspace | Customer outcome |
| --- | --- |
| Today | See pending replies, judgment points, and the next work that needs attention. |
| Mail | Import and thread messages, inspect conversation history, summarize context, and prepare replies. |
| Calendar | Review calendar evidence, detect conflicts, and create explicit writeback intents. |
| Tasks and Projects | Turn source-linked email or document evidence into trackable work without losing provenance. |
| Context Search | Search indexed messages, attachments, documents, and relationship context. |
| AI Hub | Configure approved model providers and use AI-backed flows when an operator enables them. |
| Data | Review document ingestion, parsing, embeddings, and data-quality state. |
| Security | Inspect source-backed access, policy, connector, and audit evidence. |
| Settings | Manage connected accounts, provider configuration, and self-hosted connector registration. |

Naruon labels simulated, deferred, pending, and completed actions differently. A generated intent or local payload check is not presented as proof that a customer-owned provider accepted a write.

Review and merge automation is supplied by the ContextualWisdomLab central required workflows. This repository does not carry repo-local OpenCode, Strix, or merge-scheduler workflow copies; branch updates, auto-merge, and mechanical merge actions run through the central workflow as the target repository's `github-actions[bot]`.

## Product boundary

### Naruon owns

- the web workspace and API control plane;
- authentication and authorization enforcement;
- bounded metadata, indexes, preferences, task records, and audit evidence;
- canonical email threading and source-linked work provenance;
- server-authoritative action intent and connector dispatch policy; and
- explicit failure, conflict, and abstention states.

### Customer systems remain authoritative

- IMAP, POP3, SMTP, and hosted mailbox data;
- CalDAV and CardDAV calendars and contacts;
- WebDAV files and provider revisions;
- enterprise identity and account lifecycle; and
- credentials and provider-side delivery or write status.

Naruon is **not** an SMTP or IMAP server, an MX host, a mailbox-capacity provider, or a general-purpose credential relay. Private-network integrations belong behind the outbound-only self-hosted connector boundary.

## Hub architecture and optional contracts

Naruon is the CWL ecosystem hub, but it is not a source-code aggregator or a mandatory bundle of sibling products.

The core application runs from this repository with:

- a Next.js frontend;
- a FastAPI backend;
- PostgreSQL with pgvector; and
- an operator-selected OpenAI-compatible model path when AI features are enabled.

Sibling repositories connect only through **optional, versioned contracts**. A sibling integration must use a released package, API, event schema, or OCI artifact pinned by version or digest. It must not become an undeclared startup dependency, mutable branch dependency, copied code fork, or direct database dependency.

| Optional contract | Role | Default behavior when absent |
| --- | --- | --- |
| `newsdom-api` | PDF-to-DOM recognition sidecar, enabled with the `newsdom` Compose profile | PDFs remain pending or use other configured paths; the core stack still starts. |
| Enterprise OIDC/JWKS provider | Production identity and membership authority | Local HMAC sessions remain a compatibility path, not production membership proof. |
| OpenAI-compatible provider | Summaries, drafting, embeddings, and model-backed workflows | AI-dependent actions are unavailable or fail explicitly; non-AI workspace functions remain usable. |
| Other CWL siblings | Specialized identity, orchestration, document, catalog, or analysis capabilities | Disabled until an operator accepts and configures the published contract. |

See [Architecture](ARCHITECTURE.md) for the detailed system and trust boundaries.

## Five-minute local deployment

### Prerequisites

- Docker Engine or a compatible Compose runtime;
- Python 3 for local secret generation; and
- enough disk space for PostgreSQL, images, and the local model runtime.

### 1. Create local configuration

```bash
cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import base64
import re
import secrets

path = Path(".env")
text = path.read_text()
password = secrets.token_urlsafe(32)
values = {
    "POSTGRES_DB": "ai_email",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": password,
    "DATABASE_URL": (
        "postgresql+asyncpg://postgres:"
        f"{password}@127.0.0.1:15432/ai_email"
    ),
    "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
    "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
}

for key, value in values.items():
    pattern = rf"(?m)^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, text):
        text = re.sub(pattern, replacement, text)
    else:
        text += f"\n{replacement}"

path.write_text(text.rstrip() + "\n")
PY
```

Keep `.env` local. Never commit mailbox exports, provider credentials, session secrets, encryption keys, or customer content.

### 2. Start the core stack

```bash
./scripts/naruon_compose.sh up -d --build
./scripts/naruon_compose.sh exec backend python import_fixtures.py
```

The default Compose profile starts PostgreSQL, Ollama, the backend, and the frontend.

### 3. Verify the deployment

```bash
./scripts/naruon_compose.sh ps
curl -fsS http://127.0.0.1:8000/
python3 -m webbrowser http://localhost:3000
```

The API root should return an `ok` status. The fixture import creates a small synthetic conversation so the Mail and threading path can be checked without real customer data.

### Optional PDF recognition

```bash
COMPOSE_PROFILES=newsdom ./scripts/naruon_compose.sh up -d --build
```

The `newsdom` service stays on the internal Compose network and is not published to the host. Enable it deliberately and review the pinned sidecar revision before production use.

## Required operator configuration

| Setting | Purpose |
| --- | --- |
| `POSTGRES_PASSWORD` | PostgreSQL runtime password. |
| `AUTH_SESSION_HMAC_SECRET` | Local/control-plane session signing bootstrap secret. |
| `ENCRYPTION_KEY` | Root key used to protect encrypted credential records. |
| `DATABASE_URL` | Required for manual backend execution outside the Compose network. |

Production deployments should inject bootstrap secrets from an approved secret manager rather than a shared environment file. Tenant provider and account credentials belong in the encrypted server-side registry and must not be exposed to the browser or copied into documentation.

## Identity and tenant safety

- Browser traffic uses same-origin `/api/*`; the Next.js server-side proxy converts the HttpOnly session cookie into the backend bearer session.
- Public identity headers such as `X-User-Id` and `X-Organization-Id` are not trusted as authentication.
- Local HMAC sessions are suitable for local and compatibility testing. Production workspace membership should use verified OIDC/JWKS or another explicit server-side membership authority. [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0-18.html#IDTokenValidation) requires clients to validate token issuer, audience, signature, and expiry rather than trusting unverified claims.
- Before mixing real multi-user data in one database, operators must complete and audit mailbox-owner and organization backfills for historical rows. This product-specific migration requirement is defined in the [data and tenancy architecture](ARCHITECTURE.md#data-and-tenancy-boundary) and the [authentication and key-management runbook](docs/operations/auth-key-management.md).
- Authorization is deny-first RBAC plus ABAC. [NIST SP 800-162](https://csrc.nist.gov/pubs/sp/800/162/upd2/final) defines ABAC decisions over subject, object, operation, and environment attributes; the [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) recommends deny-by-default behavior and permission validation on every request. Naruon's data-region, consent, workspace, group, source-capability, and customer-policy denies therefore take precedence over broad role grants.

See [Authentication and key management](docs/operations/auth-key-management.md) and the [Security policy](SECURITY.md).

## Connector and writeback operations

For customer-owned mail, calendar, contact, and file systems:

1. register the source and its capabilities server-side;
2. scope the source to the authenticated organization and workspace;
3. verify the current provider revision, such as ETag/If-Match where applicable;
4. create an explicit action intent;
5. set provider execution explicitly when the workflow is ready; and
6. confirm the resulting connector and provider evidence before reporting completion.

A conflict, missing capability, absent runner, stale ETag, unapproved destination, or unavailable credential fails closed. Naruon does not silently overwrite customer-owned state.

Read:

- [Email relay and proxy boundary](docs/operations/email-relay-proxy-boundary.md)
- [Source-of-truth and writeback sovereignty](docs/operations/source-of-truth-and-writeback-sovereignty.md)

## Routine operator checks

```bash
./scripts/naruon_compose.sh ps
./scripts/naruon_compose.sh logs --tail=200 db backend frontend
curl -fsS http://127.0.0.1:8000/
```

Also verify in the application:

- connected-account readiness in Settings;
- active self-hosted connector and recent heartbeat evidence;
- pending or conflicted writeback intents;
- failed ingestion or embedding jobs;
- security-policy denials and recent audit events; and
- storage growth, database backup status, and restore readiness.

Prometheus metrics are opt-in through `ENABLE_PROMETHEUS_METRICS`; do not expose operational telemetry publicly without an authenticated observability boundary.

## Backup, upgrade, and recovery

Before an upgrade:

1. review the target release notes and image provenance;
2. take and verify a PostgreSQL backup;
3. confirm object or file artifacts are covered by the deployment backup plan;
4. apply database migrations through the supported startup or migration path;
5. verify the API root, signed-session access, Mail, Search, and configured connectors; and
6. retain a rollback point until the new deployment has passed operator smoke checks.

Operational references:

- [Release and deployment architecture](docs/operations/release-deployment-architecture.md)
- [Container provenance contract](docs/operations/container-provenance-contract.md)
- [PostgreSQL replication and recovery](docs/operations/postgresql-physical-replication.md)
- [Open-source observability](docs/operations/open-source-apm.md)
- [Latest release](https://github.com/ContextualWisdomLab/naruon/releases/latest)

## Current limitations

- Naruon does not host customer mailboxes or provide inbound MX service.
- Production multi-user operation requires verified identity plus an audited historical ownership migration.
- Provider write intent is not delivery proof; some workflows require an active self-hosted connector and source revision evidence.
- Topic-intelligence documentation is a design and governance record, not a live Structural Topic Modeling feature. Naruon fails closed when an accepted fitted-model authority is unavailable.
- Optional sibling services are not enabled merely because their repositories exist. Operators must select, pin, configure, and validate each contract.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Architecture detail](docs/architecture/)
- [Architecture decisions](docs/adr/README.md)
- [Threading contract](docs/threading-contract.md)
- [Topic-intelligence boundary](docs/topic-intelligence/README.md)
- [Operations](docs/operations/)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)

## License

See [LICENSE](LICENSE).
