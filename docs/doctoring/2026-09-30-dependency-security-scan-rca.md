# Dependency Security Scan owner repair

## Status and scope

Status: Proposed until the dedicated owner PR's exact-current-head required
Checks are terminal successful. Protected-branch authority remains
`develop@042b0c70531b229af3acbd0421a2f23098d848b3`.

This RCA covers the repo-wide dependency findings inherited by Draft PRs
#1824, #1825, and #1827. It does not claim that any consumer PR is merge-ready.

## Exact evidence

| PR head | Security Scan run / job | Findings |
| --- | --- | --- |
| #1824 `23a4a883…` | `36559236390` / `109375871091` | AnyIO CVE-2026-63374, CVE-2026-63349, CVE-2026-64847; Next.js CVE-2026-75604 and GHSA-2xp9-vwfh-vxw4; Sharp GHSA-rgj7-g3m4-5g8c |
| #1825 `c2206af6…` | `36662347179` / `109719692285` | Next.js CVE-2026-75604 and GHSA-2xp9-vwfh-vxw4; Sharp GHSA-rgj7-g3m4-5g8c |
| #1827 `fc52acb0…` | `36658025933` / `109706499334` | the #1824 set plus PyJWT CVE-2026-101917 and CVE-2026-102265–102274, and oauthlib CVE-2026-49264/CVE-2026-49265 |

The different finding sets are caused by partial dependency edits on stale PR
heads, not three independent product defects. All three branches share the same
protected base and the scanner explicitly directs remediation to the shared
base branch.

## Root cause

Protected `develop` still resolves PyJWT 2.13.0, AnyIO 4.14.1, oauthlib 3.3.1,
Next.js 16.2.12, and Sharp 0.35.0. A previous database PR carried a partial
dependency repair, while #1825 later mixed another partial repair into unrelated
UI work and added a dummy backend comment to trigger Strix. Neither open branch
is production authority, and neither provides a focused owner boundary.

## Repair

The dedicated owner change exact-pins PyJWT 2.14.0, AnyIO 4.15.1, oauthlib
4.0.0, Next.js and `eslint-config-next` 16.3.6, and Sharp 0.35.4. It regenerates
the uv lock, Python hash lock, and pnpm lock from those manifests. The existing
container dependency contract now verifies every source pin and resolved lock,
so a future partial update fails before the hosted scanner.

The first full warning-fatal backend run exposed a second-order compatibility
failure: Starlette 1.3.1 evaluates the `anyio.abc.BlockingPortal` alias at
TestClient import time, while AnyIO 4.15.1 deprecates that alias. Downgrading
the patched AnyIO dependency or suppressing the warning would leave the causal
owner unresolved. The repair therefore upgrades Starlette to 1.7.0, where the
alias is removed, and installs its official HTTPX2 2.13.1 TestClient backend as
a development dependency. A direct `PYTHONWARNINGS=error` import now succeeds.

The first hosted Application CI run on owner PR #1828 then exposed a separate
lock-ownership defect. Exact-head run `36668747540`, backend job
`109738989019`, installed the required core and optional Noema hash locks in
one resolver invocation and failed because `requirements-agent.txt` still
redeclared HTTPX2 and HTTPCore2 at 2.5.0 while the core lock required 2.13.1.
The optional lock now contains only optional-package pins; every shared package
is supplied by the core lock. This makes one file authoritative for each pin
instead of merely aligning duplicate values that could drift again.

No advisory is ignored, no scanner threshold is weakened, and no elapsed-time
or queued state is treated as success. Consumer PRs must integrate the verified
owner commit through ordinary non-force history and receive fresh exact-head
Checks.

## Verification contract

The first TDD RED run failed on PyJWT 2.13.0. The compatibility RED run then
failed on Starlette 1.3.1 and the missing HTTPX2 backend. After lock
regeneration, the focused contract passes with:

`cd backend && uv run --frozen pytest tests/test_container_dependency_pin_contract.py -q`

For the hosted resolver regression, the new
`test_optional_agent_lock_does_not_redeclare_core_packages` contract first
failed with the duplicated `httpx2==2.5.0` and `httpcore2==2.5.0` pins. After
removing shared packages from the optional lock, a fresh Python 3.14 virtual
environment completed the same hash-enforced combined install used by CI:

`python -m pip install --disable-pip-version-check --require-hashes -r backend/requirements-hashes.txt -r backend/requirements-agent.txt`

Local verification records 1,808 backend tests passed with 32 explicitly
skipped under fatal warnings, 437 frontend tests passed, Python and pnpm
production audits reported no known vulnerabilities, and the frontend lint,
typecheck, and production build passed. The runner injects a SOCKS proxy that
is irrelevant to the hermetic DAV client-construction unit test, so the full
backend run explicitly removes only proxy environment variables; the initial
run's single `socksio` import failure and this environment boundary are retained
as evidence rather than hidden. Hosted exact-head evidence must still be
terminal successful before promotion from Proposed.

## References

- Agronholm, A. (2026, July 7). *AnyIO process-pool workers can block indefinitely on undrained stderr*. GitHub Security Advisory. https://github.com/agronholm/anyio/security/advisories/GHSA-5p39-cfhj-2xmp
- Fuller, L. (2026, August 27). *Vulnerabilities in libheif: CVE-2026-84383 and GHSA-2jg2-4ch7-h545*. GitHub Security Advisory. https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c
- PyJWT maintainers. (2026, September 11). *PyJWKClient follows redirects when fetching JWKS*. GitHub Security Advisory. https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9v7f-9g4p-ffgj
- Starlette maintainers. (2026, September 23). *Release 1.7.0*. PyPI. https://pypi.org/project/starlette/1.7.0/
- Vercel. (2026, September 22). *Next.js security update for a critical upstream issue*. https://nextjs.org/blog/nextjs-security-update-september-22-2026
