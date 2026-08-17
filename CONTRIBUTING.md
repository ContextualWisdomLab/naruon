# Contributing

Thank you for improving Naruon. Keep each change focused, preserve customer-owned source boundaries, and make verification reproducible for the exact code under review.

## Setup

1. Copy `.env.example` to `.env`.
2. Prefer `./scripts/naruon_compose.sh up -d --build` for full-stack local work.
3. Use synthetic fixtures only. Do not commit real email, calendar, contact, file, credential, or customer data.

## Manual development paths

Backend:

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 scripts/migrate_db.py
python3 -m pytest -q
uvicorn main:app --reload
```

Frontend:

```bash
corepack enable pnpm
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm run lint
pnpm run build
pnpm run dev
```

## Verification before opening or updating a PR

Run the checks that cover the changed surface. The repository-wide threading verification remains the default starting point:

```bash
./scripts/verify_threading.sh
```

For focused changes, run each path from the repository root so one directory change cannot affect the next command:

```bash
(cd backend && python3 -m pytest -q)
(cd frontend && pnpm test && pnpm run lint && pnpm run build)
```

UI changes require a real-browser check of the changed user flow. The supported full-product smoke path mirrors [Application CI](.github/workflows/app-ci.yml) and requires Node.js 24, Corepack/pnpm, installed frontend dependencies, and Playwright Chromium:

```bash
corepack enable pnpm
(cd frontend && pnpm install --frozen-lockfile)
(cd frontend && pnpm exec playwright install --with-deps chromium)
(
  cd frontend
  NARUON_FULL_PRODUCT_BASE_URL=http://127.0.0.1:3001 \
  NARUON_FULL_PRODUCT_SCREENSHOT_DIR=/tmp/naruon-full-product-smoke \
  pnpm run full:smoke
)
```

Do not infer browser behavior only from unit tests or source inspection. Add a narrower Playwright target when the changed flow has a focused test, and record the exact command and result in the PR body.

## Pull request scope

- Use a descriptive title such as `fix: preserve thread provenance during import`.
- Keep one logical product or infrastructure change per PR.
- State the customer or operator outcome, changed boundary, exact focused verification commands and results, and known limitations.
- Do not mix unrelated dependency churn, workflow repair, feature work, or sibling-repository implementation in one PR.
- When a sibling integration is needed, change Naruon's adapter or contract here and use a separate PR in the owning sibling repository. Do not copy sibling source into Naruon.

## Threading changes

- Add or update tests before production code changes.
- Keep `backend/services/threading_service.py` as the only canonical thread-assignment owner.
- Keep fixtures in `backend/tests/fixtures` small and synthetic; do not commit real email data.
- Preserve honest send semantics: simulated local send is not delivery proof.
- Do not claim production multi-user email isolation until historical `emails.user_id` and organization ownership have been audited and backfilled against verified mailbox owners.

## Source and writeback boundaries

- Customer mail, calendar, contact, and file systems remain authoritative.
- Browser input must not choose provider credentials, private server URLs, or unscoped database identifiers.
- Provider writes require server-authoritative source lookup, ownership and capability checks, explicit execution intent, and conflict evidence such as ETag/If-Match when supported.
- Pending, simulated, deferred, or locally validated operations must not be described as completed provider writes.

## Secrets and data

Never commit:

- `.env` files or secret-manager exports;
- mailbox archives or real `.eml` content;
- SMTP, IMAP, POP3, CalDAV, CardDAV, or WebDAV credentials;
- OAuth, OIDC, model-provider, or connector tokens;
- session-signing or encryption keys; or
- customer message, attachment, document, calendar, or contact data.

Use synthetic fixtures and opaque identifiers in tests and documentation.

## Automation and concurrent work

Before making changes, read the instructions that govern the repository and the delivery surface:

- [`AGENTS.md`](AGENTS.md)
- [`docs/development/automation-and-collaboration.md`](docs/development/automation-and-collaboration.md)
- [`docs/development/merge-gate-policy.md`](docs/development/merge-gate-policy.md)

For frontend work, also read [`frontend/AGENTS.md`](frontend/AGENTS.md). After installing frontend dependencies, read the relevant version-matched Next.js guide under `frontend/node_modules/next/dist/docs/` before relying on framework APIs or conventions.

These documents are mandatory before changing a PR branch, acting on a dependent PR, interpreting required checks, or modifying frontend behavior.

## Communication guidelines

- Search existing issues before creating a new one.
- Use the issue templates for bugs and feature requests.
- Fill out the PR template completely.
- Respond to review findings with a fix, evidence-backed rebuttal, or explicit supersession.
- Keep review comments respectful, specific, and actionable.
