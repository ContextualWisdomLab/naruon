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

This configuration requires NVIDIA hardware; it is not a Mac or CPU runtime.
Models may need download/cache provisioning. Validate recognition using a
nonconfidential PDF, then verify the resulting source segments and citations
before accepting the deployment. Compose validation does not prove model
availability, OCR quality, or successful inference. A CPU deployment still
needs a reviewed MinerU runtime supplied to the API image.
