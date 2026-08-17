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
cd frontend
npm install
npm test
npm run lint
npm run build
npm run dev
```

## Verification before opening or updating a PR

Run the checks that cover the changed surface. The repository-wide threading verification remains the default starting point:

```bash
./scripts/verify_threading.sh
```

For focused changes, also run the relevant paths:

```bash
cd backend && python3 -m pytest -q
cd frontend && npm test && npm run lint && npm run build
```

UI changes require a real-browser check of the changed user flow. Do not infer browser behavior only from unit tests or source inspection.

## Pull request scope

- Use a descriptive title such as `fix: preserve thread provenance during import`.
- Keep one logical product or infrastructure change per PR.
- State the customer or operator outcome, changed boundary, validation, and known limitations.
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

The normative procedures for Phase 10 delivery, exact-head CI evidence, stacked PRs, workflow operation, and repository writer ownership are in:

- [`docs/development/automation-and-collaboration.md`](docs/development/automation-and-collaboration.md)
- [`docs/development/merge-gate-policy.md`](docs/development/merge-gate-policy.md)

Read both before changing a PR branch, acting on a dependent PR, or interpreting required checks.

## Communication guidelines

- Search existing issues before creating a new one.
- Use the issue templates for bugs and feature requests.
- Fill out the PR template completely.
- Respond to review findings with a fix, evidence-backed rebuttal, or explicit supersession.
- Keep review comments respectful, specific, and actionable.
