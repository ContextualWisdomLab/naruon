# NewsDOM runtime selection

Naruon's default `newsdom` compose profile builds the supplier's API-only
Dockerfile. Its `/health` response proves liveness, not PDF recognition:
without an external MinerU executable, `/parse` returns 503. The supplier
already provides `Dockerfile.nvidia` at the pinned revision, with MinerU 3.0.9.

On a Linux amd64 host with an NVIDIA GPU and NVIDIA Container Toolkit, select
the existing runtime image:

```sh
docker compose -f docker-compose.yml -f docker-compose.newsdom-nvidia.yml \
  --profile newsdom up --build newsdom
```

Configure the organization's NewsDOM provider through Naruon's existing
provider registry. Starting the service alone does not configure a provider.
The override inherits the full supplier commit pin and internal network;
it adds no host port mapping. Keep the unauthenticated parser private.
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
