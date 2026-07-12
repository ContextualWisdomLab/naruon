# Clearfolio document-viewer integration (naruon)

**Goal:** use Clearfolio (`ContextualWisdomLab/clearfolio` — Java/Spring doc→PDF
viewer platform) as naruon's in-app document viewer for the Data → 문서 저장소
and email-attachment surfaces.

## Clearfolio contract (from its README)

- `POST /api/v1/convert/jobs` — upload a document → `{jobId, status, statusUrl}` (async).
- `GET /api/v1/convert/jobs/{jobId}` — poll conversion status/lifecycle.
- `GET /api/v1/viewer/{docId}` (and `/api/v1/convert/viewer/{docId}`) — viewer
  bootstrap JSON with a **short-lived signed artifact URL**.
- `GET /viewer/{docId}` — canonical HTML viewer UI (mobile-safe loading/failed/ready).
- `POST /api/v1/viewer/{docId}/artifact-links` — mint a tenant-bound signed artifact URL for succeeded jobs.
- `GET /artifacts/{docId}.pdf` — PDF bytes (SUCCEEDED only), single-range supported, artifact-token gated.
- **Tenant headers (required on protected JSON APIs):** `X-Clearfolio-Tenant-Id`,
  `X-Clearfolio-Subject-Id`, `X-Clearfolio-Permissions`. (Runtime scaffold, not OIDC/JWT.)
- HWP/HWPX are blocked by clearfolio config.

## Architecture (naruon side)

```
DocumentRepositoryTab (row → "미리보기")
  → naruon FE DocumentViewer component
    → naruon BE  POST /api/data/documents/{asset_key}/viewer
         (owner-scoped; loads the stored attachment/document bytes)
      → Clearfolio client  POST /api/v1/convert/jobs  (+ tenant headers)
        → poll job → GET /api/v1/viewer/{docId}  → { viewerUrl, signedArtifactUrl, status }
    ← naruon returns { status, viewerUrl | artifactUrl }
  → FE embeds Clearfolio `/viewer/{docId}` in a sandboxed <iframe>  (recommended)
     OR renders the signed `artifactUrl` PDF via the browser's native PDF view.
```

### Tenant/identity mapping (naruon → clearfolio headers)
- `X-Clearfolio-Tenant-Id`  ← naruon `organization_id`
- `X-Clearfolio-Subject-Id` ← naruon `user_id`
- `X-Clearfolio-Permissions`← derived from naruon RBAC (e.g. `viewer:read`)
- naruon stays the trust boundary: the FE never calls clearfolio directly; the
  naruon BE proxies with owner-scoped auth so a signed artifact URL is only
  minted for documents the caller owns.

### Config (the one deployment decision needed)
- `CLEARFOLIO_BASE_URL` (e.g. `http://clearfolio.internal:8080`) — where naruon's
  BE reaches clearfolio. Add to `ALLOWED_*`-style egress allowlist. Integration
  is **disabled when unset** (feature-flag): the 미리보기 button stays hidden.
- Deployment: clearfolio as a sibling k8s Service in the same namespace, reached
  over the cluster network (not public). Artifact URLs are short-lived + signed.

## Slices (PR sequence)
1. **BE client + config** — `services/clearfolio_client.py` (submit/poll/bootstrap
   with tenant headers + timeouts/retry) behind `CLEARFOLIO_BASE_URL`; unit-tested
   with a mocked transport. No endpoint yet.
2. **BE endpoint** — `POST /api/data/documents/{asset_key}/viewer` owner-scoped;
   maps naruon doc → clearfolio job → returns `{status, viewerUrl|artifactUrl}`.
3. **FE viewer** — `DocumentViewer.tsx` (sandboxed iframe + loading/failed/ready),
   wired into `DocumentRepositoryTab` behind the feature flag.
4. **Hardening** — HWP pre-check (clearfolio blocks HWP/HWPX → surface naruon's
   own HWP-convert path first), size/type guardrails, artifact-URL TTL handling.

## Open decision for the user
- **Deployment + auth model:** (a) confirm clearfolio's base URL / that it runs as
  an in-cluster Service, and (b) confirm the tenant-header mapping above is the
  intended trust model (naruon BE proxies; FE never talks to clearfolio directly).
  Everything else can proceed against a configurable `CLEARFOLIO_BASE_URL`.
