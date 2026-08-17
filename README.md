# Naruon AI Email Workspace

[![Application CI](https://github.com/ContextualWisdomLab/naruon/actions/workflows/app-ci.yml/badge.svg)](https://github.com/ContextualWisdomLab/naruon/actions/workflows/app-ci.yml)
[![Bandit Security Scan](https://github.com/ContextualWisdomLab/naruon/actions/workflows/bandit.yml/badge.svg)](https://github.com/ContextualWisdomLab/naruon/actions/workflows/bandit.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ContextualWisdomLab/naruon)

Naruon is an AI email and workspace **control plane**: a FastAPI backend and
Next.js client that indexes member-configured mail, calendar, and file systems,
threads conversations, and exposes signed search and task APIs.

It is **not an SMTP server, IMAP host, MX, or mailbox**. Customer mail,
CalDAV/CardDAV, and WebDAV accounts stay the source of truth. Naruon stores
bounded metadata, indexes, preferences, and auditable writeback intent.

## Run it alone

Independent boot needs only this repository and its Compose stack (Postgres +
the in-repo Ollama service). Sibling products are optional. Default
`docker compose up` does not need a `../pg-llm-batch` checkout, a git submodule,
or any other sibling working tree.

Required runtime secrets have no code defaults. Copy the example env file and
generate them locally:

```bash
cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import base64
import secrets

env_path = Path(".env")
env_values = {}
for line in env_path.read_text().splitlines():
    if "=" not in line or line.lstrip().startswith("#"):
        continue
    key, value = line.split("=", 1)
    env_values[key] = value

db_password = secrets.token_urlsafe(32)
env_values.update(
    {
        "POSTGRES_DB": "ai_email",
        "POSTGRES_USER": "naruon_local",
        "POSTGRES_PASSWORD": db_password,
        "DATABASE_URL": (
            "postgresql+asyncpg://naruon_local:"
            f"{db_password}@localhost:5432/ai_email"
        ),
        "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
        "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    }
)

existing_lines = env_path.read_text().splitlines()
existing_keys = {
    line.split("=", 1)[0]
    for line in existing_lines
    if "=" in line and not line.lstrip().startswith("#")
}
required_lines = [f"{key}={value}" for key, value in env_values.items() if key not in existing_keys]
env_path.write_text("\n".join(existing_lines + required_lines) + "\n")
PY
./scripts/naruon_compose.sh up -d --build
./scripts/naruon_compose.sh exec backend python import_fixtures.py
curl -s http://localhost:8000/
python3 -m webbrowser http://localhost:3000
```

`./scripts/naruon_compose.sh` reads `${NARUON_ENV_FILE}`, otherwise `~/.env` if
present, otherwise the project `.env`. It passes that file to Compose only as
an interpolation source. The backend container still requires
`POSTGRES_PASSWORD`, `AUTH_SESSION_HMAC_SECRET`, and `ENCRYPTION_KEY`.

What you should see:

- `GET /` returns `{"status":"ok","message":"AI Email Client API"}`.
- Fixture import loads a three-message `Quarterly plan` conversation.
- The frontend at `http://localhost:3000` opens the Today dashboard, with Mail
  and Calendar as explicit workspace entries.
- Inbox threading shows one conversation with `reply_count` greater than 1
  once you call the signed email API (see below).

Compose injects `DATABASE_URL` for the backend service. A host-side
`DATABASE_URL` is only needed if you run the API outside Compose. Image builds
can parse without local secrets; `docker compose up` still fails closed when
the required secrets are missing.

## How a sibling calls Naruon

Naruon is the intended ContextualWisdomLab composition hub. A sibling calls the
published HTTP contract with a signed `Authorization: Bearer` session. It does
not vendor this repo as a path dependency, and this repo does not require the
sibling checkout.

Live OpenAPI (when the API is running):

- `http://localhost:8000/openapi.json`
- `http://localhost:8000/docs`

Stable routes from this repository (do not invent others from README):

| Surface | Auth | Purpose |
|---|---|---|
| `GET /` | public | Process liveness |
| `GET /api/emails` | signed bearer | Threaded inbox |
| `POST /api/search` | signed bearer | Hybrid context search |
| `GET /api/tasks` | signed bearer | Source-linked ticket tasks |

Mint a short-lived local HMAC session against the same
`AUTH_SESSION_HMAC_SECRET` the API process loaded. Examples:
[`docs/development/local-api-smoke.md`](docs/development/local-api-smoke.md).
Browser clients use the HttpOnly `naruon_session` cookie through the
same-origin Next.js `/api/*` proxy instead of storing a bearer token.

Siblings such as TEPP, contextual-orchestrator, pg-llm-batch, RankWeave,
ThreadWeave, Keyverse, Inkspan, and BandScope are **optional**. Naruon boots
without them. Composition is through published contracts (OpenAPI, a library
API such as the pinned `rankweave` PyPI package, or an optional HTTP client)
and degrades when unconfigured — never sibling checkouts. Topic intelligence
stays fail-closed until a versioned fitted TEPP artifact exists; see
[`docs/topic-intelligence/`](docs/topic-intelligence/README.md).

The optional [`docker-compose.pg-llm-batch.yml`](docker-compose.pg-llm-batch.yml)
overlay documents a local `git clone ../pg-llm-batch` only for offline batch
Postgres. Default `docker compose up` does not need that checkout.

## Manual development path

Backend:

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 scripts/migrate_db.py
python3 -m pytest -q
uvicorn main:app --reload
```

Frontend (pnpm is the repo package manager):

```bash
cd frontend
corepack pnpm@11.5.3 install --frozen-lockfile
corepack pnpm@11.5.3 test
corepack pnpm@11.5.3 run lint
corepack pnpm@11.5.3 run build
corepack pnpm@11.5.3 run dev
```

## Docs

- [Architecture](ARCHITECTURE.md) and [architecture notes](docs/architecture/)
- [Email relay / proxy boundary](docs/operations/email-relay-proxy-boundary.md)
- [Auth and key management](docs/operations/auth-key-management.md)
- [Local API smoke](docs/development/local-api-smoke.md)
- [Apple Silicon / MLX override](docs/development/local-mlx-apple-silicon.md)
- [Topic-intelligence documentation set](docs/topic-intelligence/README.md)
- [Architecture decisions](docs/adr/README.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- Agent / robot-review rules:
  [`docs/development/agent-operating-rules.md`](docs/development/agent-operating-rules.md)
  and [`docs/development/merge-gate-policy.md`](docs/development/merge-gate-policy.md)
