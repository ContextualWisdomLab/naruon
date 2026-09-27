# NewsDOM runtime selection

Naruon's default `newsdom` compose profile builds the supplier's API-only
Dockerfile. Its `/health` response proves liveness, not PDF recognition.
Compose uses `/ready`, which requires both parser authentication and an available
MinerU runtime. The supplier at `65696f393224a1e08ab42fff5151cbf3639a8a4e`
provides `Dockerfile.nvidia` with MinerU 3.4.4.

The existing MinerU 3.4.4 runtime fails the combined GPU dependency audit.
See [the audit and migration requirement](newsdom-gpu-dependency-audit-20260928.md).
The following reproduces its Linux NVIDIA configuration; deployment acceptance
requires the migrated, audited runtime and real OCR verification:

```sh
docker compose -f docker-compose.yml -f docker-compose.newsdom-nvidia.yml \
  --profile newsdom up --build newsdom
```

Configure the organization's NewsDOM provider through Naruon's existing
provider registry. Set `NEWSDOM_API_TOKEN` in the deployment environment and
store the same bearer token in that registry. Authentication remains required
in the production profile; a missing token leaves the service unready. Starting
the service alone does not configure a provider.
The override inherits the full supplier commit pin and internal network;
it adds no host port mapping. Keep the authenticated parser private.
Both selections use a read-only root filesystem and no-new-privileges.
Temporary request/output files use `/tmp` tmpfs; the named `newsdom-model-cache`
volume preserves the nonroot home, including model caches and generated
`mineru.json`. External configuration mounts must remain read-only.
The volume uses the supplier image's existing home-directory ownership.
The override's healthcheck requires the MinerU executable as well as API
liveness. This checks installation, not model availability or inference.

This configuration requires NVIDIA hardware; it is not a Mac or CPU runtime.
Models may need download/cache provisioning. Validate recognition using a
nonconfidential PDF, then verify the resulting source segments and citations
before accepting the deployment. Compose validation does not prove model
availability, OCR quality, or successful inference. A CPU deployment still
needs a reviewed MinerU runtime supplied to the API image.

## Attachment inference configuration

After deploying the attachment-inference worker, configure the existing
organization-scoped LLM provider and select extraction through the backend's
Compose environment. The default remains disabled with the keyword selector.
For orchestrator routing, set these existing variables in the deployment `.env`:

```dotenv
PROJECT_GRAPH_EXTRACTION_ENABLED=true
PROJECT_GRAPH_EXTRACTOR=orchestrator
PROJECT_GRAPH_ORCHESTRATOR_BASE_URL=http://orchestrator:8000/v1
```

Use the actual deployed, trusted endpoint. The base Compose configuration permits
only the local Ollama provider host; a different provider requires a reviewed
deployment override that explicitly allowlists its hostname. The example does
not deploy an orchestrator service or grant network access. Provider
credentials remain in the scoped registry. Compose previously omitted these
variables, so host `.env` settings never reached the backend. Recreate the backend
through the normal deployment procedure after changing its environment. Validate
recognized segments and inferred candidates with exact source citations; enabling
the flags alone is not inference acceptance.

## Supplier security prerequisite

The selected immutable supplier commit is blank-page successor PR newsdom-api
#958's head `65696f393224a1e08ab42fff5151cbf3639a8a4e`, based on canonical security PR #822's
head `927ff2dec160a00ed11ec045727a422ff7ba4cbd`. The successor changes only DOM
page preservation and its regression test; its lock and Dockerfiles are unchanged. Its lock retains
security-fixed AnyIO 4.14.2 and pypdf 6.18.0. The supplier owner branch remains
unchanged. Its additional form-field bounds are preserved; qualifying review
and protected supplier acceptance remain pending.

Validation on this exact supplier source and lock: 487 tests pass with warnings
as errors and 100% production branch coverage; exported API runtime requirements
report zero known vulnerabilities. The strict test command applies no warning
suppression, independently from the supplier workflow's existing filter.

Historical evidence is narrower: supplier develop's runtime lock reports five
known AnyIO/pypdf vulnerabilities. The previously selected `072ea5db` artifact
used AnyIO 4.15.1 and failed strict collection in four modules because Starlette
1.3.1 referenced its deprecated BlockingPortal alias. The current owner already
repaired that compatibility; its PR body still describes the previous lock and
must not override the actual current files. A separate Starlette 1.7.0 experiment
passed 485 tests but is not adopted, because the owner's existing fix suffices.

This pin remains a review candidate. The GPU image build, MinerU transitive
packages/model execution, real OCR, and independent protected acceptance are
unverified. Dependency/API tests do not establish those outcomes.

The successor preserves a model-declared blank page between content pages; page numbers and dimensions remain present even when no article is emitted. This closes the supplier-to-runtime pin gap without claiming a MinerU 4 adapter or a deployed OCR result.
