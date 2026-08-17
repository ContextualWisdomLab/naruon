# Contributing

## Setup

1. Copy `.env.example` to `.env`.
2. Prefer `docker compose up -d --build` for full-stack local work.
3. For manual backend work, run commands from `backend/`.
4. For frontend work, run `npm install` before lint/build/test.

Agent writer-boundary, PR-stacking, and Phase 10 rules live in
[`docs/development/agent-operating-rules.md`](docs/development/agent-operating-rules.md).
Merge-gate and current-head robot-review evidence live in
[`docs/development/merge-gate-policy.md`](docs/development/merge-gate-policy.md).

## Verification before opening a PR

```bash
./scripts/verify_threading.sh
```

For backend-only changes, run `cd backend && python3 -m pytest -q`. For frontend changes, run `cd frontend && npm test && npm run lint && npm run build`.

## Threading changes

- Add or update tests before production code changes.
- Keep `backend/services/threading_service.py` as the only canonical thread assignment owner.
- Keep fixtures in `backend/tests/fixtures` small and synthetic; do not commit real email data.
- Preserve honest send semantics: simulated local send is not delivery proof.
- Do not claim production multi-user email isolation until historical
  `emails.user_id` values are audited/backfilled against verified mailbox
  owners and the scoped query tests are kept green.

## Secrets and data

Never commit `.env`, real mailbox exports, SMTP credentials, OAuth secrets, OpenAI keys, or user email content. Use synthetic `.eml` fixtures only.

## Communication Guidelines

To keep our project organized and easy to navigate for everyone, please adhere to the following communication guidelines:

* **Issues:** Use the provided Issue Templates (`Bug Report` or `Feature Request`). Search existing issues before creating a new one to prevent duplicates.
* **Pull Requests:** Ensure your PR title is descriptive (e.g., `fix: correct email parsing bug`). Fill out the PR template entirely. Keep PRs focused on a single logical change.
* **Review Process:**
    * Ensure all CI checks pass (linting, tests, etc.) before requesting a review.
    * Respond to reviewer comments promptly.
    * Be respectful and constructive in your code reviews.
