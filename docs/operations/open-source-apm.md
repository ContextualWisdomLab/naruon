# Open Source APM and Observability

## 확인된 사실 / Confirmed

- `backend/main.py` leaves shared telemetry disabled until explicit SDK
  configuration and exposes Prometheus `/metrics` only when
  `ENABLE_PROMETHEUS_METRICS=true`.
- `backend/api/observability.py` exposes signed-session
  `/api/observability/operational-signals` for organization admins. It reports
  Prometheus/active shared runtime state, self-hosted connector registration, active
  outbound runner connection state, recent durable `connector_signal_events`,
  and the remaining instrumentation gaps without executing provider writes.
- `backend/api/runner_ws.py` records self-hosted connector connect, heartbeat,
  and disconnect events as control-plane APM evidence. These events do not turn
  Naruon into an SMTP/IMAP mailbox server and do not execute provider writes.
- The draft backend `telemetry` extra pins a reviewed shared SDK commit. The
  Docker image still uses its hashed dependency set and cannot enable the SDK
  until a released wheel is pinned there.
- `docker-compose.observability.yml`, `docker-compose.apm.yml`, and
  `docker-compose.infra.yml` document local Prometheus/APM stack entry points.
- `docker-compose.live-e2e.yml` proves the image-based smoke path before any APM
  stack is claimed as production-ready.

## 가설 / Hypothesis

- The default open-source APM stack should be OpenTelemetry SDK + Collector,
  Prometheus for metrics, Grafana for dashboards, Loki for logs, and Tempo or
  Jaeger for traces.
- Runtime instrumentation should start with request latency, status code,
  dependency calls, and worker-loop spans, while redacting email body and secret
  values.

## North-star telemetry targets

- Connector heartbeat, version, queue depth, and outbound control-channel health.
- Sync lag per mailbox/calendar/file source, provider throttling, retry budgets,
  and conflict rates.
- Writeback intent lifecycle: selected source, ETag/If-Match requirement,
  provider response class, conflict outcome, and audit event id.
- Tenant/workspace latency, error budget, AI action audit events, and prompt/model
  usage without logging email bodies, secrets, DSNs, or raw provider tokens.

## 도입 기준

- Require a validated SDK config with exact source revision, HTTPS Collector,
  and scoped token before telemetry export. `/metrics` must stay
  disabled by default and enabled only behind a trusted scrape path or reverse
  proxy access policy.
- Keep `/healthz`, `/readyz`, and `/metrics` semantics separate as the stack
  matures.
- Do not claim APM production readiness until a live stack shows trace, metric,
  and log evidence without leaking user email content.

## Remaining gaps

- Add queue depth beyond the in-process runner WebSocket manager.
- Wire the reviewed SDK release to the hashed Docker dependency set and an
  operator credential registry; validate deployed Collector delivery before
  calling trace export active.
- Add sync lag, writeback conflict, and AI action audit dashboards fed by
  source-backed connector/provider events.
- Add log and trace redaction tests for email bodies, provider tokens, DSNs, and
  calendar/file descriptions.
