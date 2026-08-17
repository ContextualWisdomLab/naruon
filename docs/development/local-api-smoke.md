# Local API smoke

Signed-session smoke against a running Naruon backend. The live contract is
FastAPI OpenAPI at `http://localhost:8000/openapi.json` and
`http://localhost:8000/docs`. Do not invent endpoints from this page.

Private `/api/*` routes accept only a signed bearer session. Public identity
headers such as `X-User-Id` are rejected. Generate a local-only
`AUTH_SESSION_HMAC_SECRET`, start the API with that exact value, and mint a
short-lived fixture token from the same shell. Do not copy a static secret from
docs or tests; known public fixtures are denied at startup.

```bash
export AUTH_SESSION_HMAC_SECRET="$(python3 - <<'PY'
import secrets

print(secrets.token_urlsafe(48))
PY
)"
export NARUON_DEV_BEARER="$(python3 - <<'PY'
import base64, hashlib, hmac, json, os, time

secret = os.environ["AUTH_SESSION_HMAC_SECRET"].encode()
payload = {
    "ver": 1,
    "iss": "naruon-control-plane",
    "aud": "naruon-api",
    "sub": "default",
    "role": "organization_admin",
    "org": "default",
    "groups": [],
    "workspace": "default",
    "exp": int(time.time()) + 300,
}
enc = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
header = enc(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
body = enc(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
sig = enc(hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest())
print(f"{header}.{body}.{sig}")
PY
)"
```

```bash
curl -s http://localhost:8000/ \
  | jq .
curl -s http://localhost:8000/api/emails \
  -H "Authorization: Bearer $NARUON_DEV_BEARER" \
  | jq '.emails[] | {subject, thread_id, reply_count}'
curl -s http://localhost:8000/api/emails/thread/thread-root@example.com \
  -H "Authorization: Bearer $NARUON_DEV_BEARER" \
  | jq '.thread[] | {message_id, in_reply_to, references}'

# Search degrades to lexical-only when no embedding provider is configured.
curl -s -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $NARUON_DEV_BEARER" \
  -H 'content-type: application/json' \
  -d '{"query":"Quarterly plan"}'

# Send remains honest in local/dev mode: missing SMTP config returns 400.
curl -s -X POST http://localhost:8000/api/emails/send \
  -H "Authorization: Bearer $NARUON_DEV_BEARER" \
  -H 'content-type: application/json' \
  -d '{"to":"alice@example.com","subject":"Re: Quarterly plan","body":"Thanks"}'

TASK_BODY="$(cat <<'JSON'
{
  "source_email_id": "<root@example.com>",
  "thread_id": "thread-root@example.com",
  "items": ["담당자 확인"]
}
JSON
)"
curl -s -X POST http://localhost:8000/api/tasks/from-email \
  -H "Authorization: Bearer $NARUON_DEV_BEARER" \
  -H 'content-type: application/json' \
  -d "$TASK_BODY"

curl -s http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $NARUON_DEV_BEARER"
```

HMAC fixture tokens are local/control-plane compatibility credentials. They
must not be treated as authoritative workspace-membership evidence for
admin-gated surfaces such as `/api/security/access-surface`.

## Error-message contract

Errors should tell a contributor what failed and avoid leaking internals:

- SMTP not configured: `400 {"detail":"SMTP is not configured"}`.
- Local simulated send: `{"status":"simulated","simulated":true}`. Treat as
  payload/header verification only, not delivery proof.
- Search backend failure: `500 {"detail":"Search failed"}`. Raw exceptions are
  not returned to clients.
- Missing thread: `404 {"detail":"Thread not found"}`.
- Task creation from a missing or unauthorized source email:
  `404 {"detail":"Source email not found"}`.
- Task creation without usable execution items:
  `422 {"detail":"At least one execution item is required"}`.
- Calendar writeback with no trusted customer-owned source:
  `422 {"detail":"No customer-owned writeback source is available"}`.
