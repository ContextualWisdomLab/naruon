# NewsDOM runtime selection

Naruon's default `newsdom` compose profile builds the supplier's API-only
Dockerfile. Its `/health` response proves liveness, not PDF recognition.
Compose uses `/ready`, which requires both parser authentication and an available
MinerU runtime. The supplier at `072ea5dbfa616eb4113843a64abee71982b9aaa9`
provides `Dockerfile.nvidia` with MinerU 3.4.4.

On a Linux amd64 host with an NVIDIA GPU and NVIDIA Container Toolkit, select
the existing runtime image:

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

The selected immutable supplier commit is the dependency-only artifact from
canonical security PR newsdom-api #822, before later mixed changes. Its parser,
authentication, Dockerfiles and test workflow are byte-identical to supplier
`develop@539528f9667524f6b65de0ee7b8b21fbdd97c380`; only its dependency repair
and associated tests/documentation are adopted. Supplier develop's runtime
lock still reports five known AnyIO/pypdf vulnerabilities and is not the
selected build source. PR #822 remains draft and has not received protected
merge acceptance. This pin is a review candidate, not deployment authorization
or inherited current-head approval. Validate the selected lock and API boundary
separately before deployment; the GPU build and actual OCR remain unverified.

Validation receipts for this candidate: the selected API runtime lock reports
zero known vulnerabilities (the supplier main lock reports five); consumer
Compose/hygiene tests pass 23/23 and client/PDF-contract tests pass 21/21.
Supplier main's selected auth/readiness tests pass 58/58, but those results do
not transfer to the changed dependency lock. On the selected security artifact,
warnings-as-errors currently stops test collection in four modules: Starlette
1.3.1 references AnyIO 4.15.1's deprecated `anyio.abc.BlockingPortal` alias.
No warning filter was added. Supplier dependency compatibility, GPU image
build/MinerU transitive dependencies, real model execution, and independent
protected acceptance remain unverified.
