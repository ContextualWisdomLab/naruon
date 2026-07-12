#!/usr/bin/env python3
"""Local-only Naruon mail smoke test without printing private mail content."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import mailbox
import mimetypes
import os
import sys
import time
from collections import Counter
from email import message_from_bytes, policy
from email.parser import BytesHeaderParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

SESSION_COOKIE_NAME = "naruon_session"
SUPPORTED_SUFFIXES = {".eml", ".emlx", ".mbox", ".zip"}
MATCH_SEPARATORS = str.maketrans("", "", " \t\r\n-_./\\()[]{}:;·ㆍ")
SEARCH_RETRY_DEFAULT_ATTEMPTS = 3
SEARCH_RETRY_DEFAULT_DELAY_SECONDS = 0.75
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def _b64_json(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _signed_token(secret: str) -> str:
    header = _b64_json({"alg": "HS256", "typ": "JWT"})
    payload = _b64_json(
        {
            "ver": 1,
            "iss": "naruon-control-plane",
            "aud": "naruon-api",
            "sub": "testuser",
            "role": "member",
            "org": "org-acme",
            "groups": ["group-1", "group-2"],
            "workspace": "workspace-org-acme",
            "exp": int(time.time()) + 1800,
        }
    )
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def _private_files(mail_dir: Path, limit: int) -> list[Path]:
    if not mail_dir.is_dir():
        raise SystemExit("mail_dir_missing")
    try:
        next(mail_dir.iterdir(), None)
    except PermissionError as exc:
        raise SystemExit(
            "mail_dir_unreadable: confirm macOS file permission or copy mails to a local folder"
        ) from exc

    picked: list[Path] = []
    for root, dirs, files in os.walk(mail_dir, followlinks=False):
        dirs[:] = [item for item in dirs if not item.startswith(".")]
        for name in sorted(files):
            path = Path(root, name)
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            if not path.is_file() or path.is_symlink():
                continue
            picked.append(path)
            if len(picked) >= limit:
                return picked
    return picked


def _decoded_probe(raw: bytes, max_body_bytes: int) -> str:
    header, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        header, _, body = raw.partition(b"\n\n")
    chunks = [header[:65536], body[:max_body_bytes]]
    decoded: list[str] = []
    for encoding in ("utf-8", "cp949", "euc-kr", "latin1"):
        for chunk in chunks:
            decoded.append(chunk.decode(encoding, errors="ignore"))
    return "\n".join(decoded)


def _header_text(raw: bytes) -> str:
    try:
        msg = BytesHeaderParser(policy=policy.default).parsebytes(raw)
    except Exception:
        return ""
    return "\n".join(
        str(msg.get(name, ""))
        for name in ("Subject", "From", "To", "Cc", "Date")
    )


def _message_text(raw: bytes, max_parse_bytes: int) -> str:
    parts = [_header_text(raw), _decoded_probe(raw, max_parse_bytes)]
    if len(raw) > max_parse_bytes:
        return "\n".join(parts)

    try:
        msg = message_from_bytes(raw, policy=policy.default)
    except Exception:
        return "\n".join(parts)

    parts.extend([
        str(msg.get("Subject", "")),
        str(msg.get("From", "")),
        str(msg.get("To", "")),
        str(msg.get("Cc", "")),
        str(msg.get("Date", "")),
    ])
    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                parts.append(filename)
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            try:
                content = part.get_content()
            except (LookupError, ValueError, UnicodeError):
                continue
            if isinstance(content, str):
                parts.append(content)
    else:
        try:
            content = msg.get_content()
        except Exception:
            content = raw.decode("utf-8", errors="ignore")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def _read_eml_like_bytes(path: Path) -> bytes | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    return _strip_emlx_prefix(raw) if path.suffix.lower() == ".emlx" else raw


def _strip_emlx_prefix(raw: bytes) -> bytes:
    first_line, separator, rest = raw.partition(b"\n")
    if not separator or not first_line.strip().isdigit():
        return raw
    message_length = int(first_line.strip())
    if message_length <= 0:
        return rest
    return rest[:message_length]


def _normalize_for_match(value: str) -> str:
    return value.casefold().translate(MATCH_SEPARATORS)


def _matches_queries(
    raw: bytes,
    queries: list[str],
    max_parse_bytes: int,
    match_mode: str,
) -> bool:
    if not queries:
        return True
    haystack = _message_text(raw, max_parse_bytes).casefold()
    normalized_haystack = _normalize_for_match(haystack)
    for query in queries:
        normalized_query = _normalize_for_match(query)
        if match_mode == "all-terms":
            terms = [
                _normalize_for_match(term)
                for term in query.split()
                if _normalize_for_match(term)
            ]
            if terms and all(term in normalized_haystack for term in terms):
                return True
            continue
        if query.casefold() in haystack or normalized_query in normalized_haystack:
            return True
    return False


def _selected_upload_files(
    mail_dir: Path,
    queries: list[str],
    limit: int,
    *,
    max_parse_bytes: int,
    match_mode: str,
    progress_every: int,
) -> list[Path]:
    with TemporaryDirectory(prefix="naruon-private-mail-hits-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        selected: list[Path] = []

        scanned = 0

        def report_progress() -> None:
            if progress_every > 0 and scanned % progress_every == 0:
                print(
                    f"scan_progress scanned={scanned} selected={len(selected)}",
                    file=sys.stderr,
                    flush=True,
                )

        def add_raw(raw: bytes) -> None:
            if len(selected) >= limit:
                return
            path = temp_dir / f"hit_{len(selected) + 1:03d}.eml"
            path.write_bytes(raw)
            selected.append(path)

        for path in _private_files(mail_dir, limit=1000000):
            if len(selected) >= limit:
                break
            suffix = path.suffix.lower()
            if suffix in {".eml", ".emlx"}:
                raw = _read_eml_like_bytes(path)
                if raw is None:
                    continue
                scanned += 1
                report_progress()
                if _matches_queries(raw, queries, max_parse_bytes, match_mode):
                    add_raw(raw)
                continue
            if suffix == ".mbox":
                try:
                    box = mailbox.mbox(path, create=False)
                except (OSError, mailbox.Error):
                    continue
                try:
                    for msg in box:
                        if len(selected) >= limit:
                            break
                        raw = msg.as_bytes(policy=policy.default)
                        scanned += 1
                        report_progress()
                        if _matches_queries(raw, queries, max_parse_bytes, match_mode):
                            add_raw(raw)
                finally:
                    box.close()
                continue
            if suffix == ".zip":
                try:
                    archive = ZipFile(path)
                except (OSError, BadZipFile):
                    continue
                with archive:
                    for info in archive.infolist():
                        if len(selected) >= limit:
                            break
                        entry_suffix = Path(info.filename).suffix.lower()
                        if info.is_dir() or entry_suffix not in {".eml", ".emlx"}:
                            continue
                        try:
                            raw = archive.read(info)
                        except (OSError, BadZipFile):
                            continue
                        if entry_suffix == ".emlx":
                            raw = _strip_emlx_prefix(raw)
                        scanned += 1
                        report_progress()
                        if _matches_queries(raw, queries, max_parse_bytes, match_mode):
                            add_raw(raw)

        persistent: list[Path] = []
        final_dir = Path(
            os.environ.get(
                "NARUON_PRIVATE_MAIL_CACHE",
                str(Path.home() / ".cache" / "naruon" / "private-mail-upload-cache"),
            )
        )
        final_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        for old_hit in final_dir.glob("hit_*.eml"):
            old_hit.unlink()
        for index, path in enumerate(selected, start=1):
            final_path = final_dir / f"hit_{index:03d}.eml"
            final_path.write_bytes(path.read_bytes())
            final_path.chmod(0o600)
            persistent.append(final_path)
        return persistent


def _request(
    base_url: str,
    token: str,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 120.0,
    use_cookie_only: bool = False,
) -> tuple[int, bytes]:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("base-url must be http(s)")
    cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = cls(parsed.hostname, parsed.port, timeout=timeout)
    headers = {
        "Cookie": f"{SESSION_COOKIE_NAME}={token}",
        "Origin": base_url,
        "Referer": f"{base_url}/",
    }
    if not use_cookie_only:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    except OSError as exc:
        raise _RequestNetworkError(f"request transport error to {base_url}: {exc}") from exc
    finally:
        conn.close()


def _multipart(files: list[Path]) -> tuple[bytes, str]:
    boundary = f"naruon-{hashlib.sha256(os.urandom(16)).hexdigest()}"
    chunks: list[bytes] = []
    for index, path in enumerate(files, start=1):
        upload_name = f"hit_{index:03d}{path.suffix.lower() or '.eml'}"
        media_type = mimetypes.guess_type(upload_name)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                'Content-Disposition: form-data; name="files"; '
                f'filename="{upload_name}"\r\n'
                f"Content-Type: {media_type}\r\n\r\n"
            ).encode()
        )
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _json_or_empty(status: int, body: bytes) -> dict[str, object]:
    if status != 200:
        raise _RequestFailed(status, body)
    try:
        return json.loads(body.decode(errors="replace") or "{}")
    except json.JSONDecodeError as exc:
        raise _BadResponse(status, body) from exc


class _RequestFailed(SystemExit):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        super().__init__(f"request failed status={status}")


class _BadResponse(SystemExit):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        super().__init__(f"unexpected non-json response status={status}")


class _RequestNetworkError(SystemExit):
    pass


def _ensure_positive_retry_budget(value: int, option_name: str) -> None:
    if value < 1:
        raise SystemExit(f"{option_name} must be at least 1")


def _request_json_with_retry(
    base_url: str,
    token: str,
    method: str,
    path: str,
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float = 120.0,
    body: bytes | None = None,
    content_type: str | None = None,
    use_cookie_only: bool = False,
) -> dict[str, object]:
    _ensure_positive_retry_budget(attempts, "retry-attempts")
    for attempt in range(attempts):
        try:
            status, raw = _request(
                base_url,
                token,
                method,
                path,
                body=body,
                content_type=content_type,
                use_cookie_only=use_cookie_only,
                timeout=timeout,
            )
            return _json_or_empty(status, raw)
        except _RequestFailed as exc:
            if exc.status in RETRY_STATUS_CODES and attempt != attempts - 1:
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue
            raise
        except _BadResponse:
            raise
        except _RequestNetworkError:
            if attempt != attempts - 1:
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue
            raise
    raise RuntimeError("request retry loop completed without a terminal response")


def _post_json_with_retry(
    base_url: str,
    token: str,
    path: str,
    payload: dict[str, object],
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float = 120.0,
) -> dict[str, object]:
    return _request_json_with_retry(
        base_url,
        token,
        "POST",
        path,
        body=json.dumps(payload).encode(),
        content_type="application/json",
        attempts=attempts,
        delay_seconds=delay_seconds,
        timeout=timeout,
    )


def _post_multipart_with_retry(
    base_url: str,
    token: str,
    path: str,
    body: bytes,
    content_type: str,
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float = 120.0,
) -> dict[str, object]:
    return _request_json_with_retry(
        base_url,
        token,
        "POST",
        path,
        body=body,
        content_type=content_type,
        attempts=attempts,
        delay_seconds=delay_seconds,
        timeout=timeout,
    )


def _get_json_with_retry(
    base_url: str,
    token: str,
    path: str,
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float = 120.0,
    use_cookie_only: bool = False,
) -> dict[str, object]:
    return _request_json_with_retry(
        base_url,
        token,
        "GET",
        path,
        attempts=attempts,
        delay_seconds=delay_seconds,
        timeout=timeout,
        use_cookie_only=use_cookie_only,
    )


def _fetch_inbox_snapshot(
    base_url: str,
    token: str,
    *,
    limit: int,
    min_count: int,
    attempts: int,
    use_cookie_only: bool = False,
    delay_seconds: float,
    timeout: float = 120.0,
) -> tuple[dict[str, object], int]:
    """Fetch /api/emails repeatedly until the minimum expected count is observed."""
    last_data: dict[str, object] = {}
    min_count = max(0, min_count)
    _ensure_positive_retry_budget(attempts, "inbox-retry-attempts")
    for attempt in range(attempts):
        data = _get_json_with_retry(
            base_url,
            token,
            f"/api/emails?limit={limit}",
            attempts=1,
            delay_seconds=0.0,
            timeout=timeout,
            use_cookie_only=use_cookie_only,
        )
        emails = data.get("emails")
        count = len(emails) if isinstance(emails, list) else 0
        last_data = data
        if count >= min_count or attempt == attempts - 1:
            return data, count
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return last_data, 0


def _fetch_search_snapshot(
    base_url: str,
    token: str,
    query: str,
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float = 120.0,
    use_cookie_only: bool = False,
    limit: int = 3,
) -> tuple[dict[str, object], int]:
    """Fetch /api/search repeatedly until query results are available."""
    last_data: dict[str, object] = {}
    _ensure_positive_retry_budget(attempts, "search-retry-attempts")
    for attempt in range(attempts):
        data = _request_json_with_retry(
            base_url,
            token,
            "POST",
            "/api/search",
            body=json.dumps({"query": query, "limit": limit}).encode(),
            content_type="application/json",
            attempts=1,
            delay_seconds=0.0,
            timeout=timeout,
            use_cookie_only=use_cookie_only,
        )
        results = data.get("results")
        count = len(results) if isinstance(results, list) else 0
        last_data = data
        if count > 0 or attempt == attempts - 1:
            return data, count
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return last_data, 0


def _check_frontend_session(base_url: str, token: str) -> dict[str, object] | None:
    try:
        data = _post_json_with_retry(
            base_url,
            token,
            "/auth/session",
            {"access_token": token},
            attempts=SEARCH_RETRY_DEFAULT_ATTEMPTS,
            delay_seconds=SEARCH_RETRY_DEFAULT_DELAY_SECONDS,
            timeout=30.0,
        )
    except _RequestFailed as exc:
        if exc.status == 404:
            return None
        raise

    if not isinstance(data, dict) or data.get("authenticated") is not True:
        raise SystemExit("frontend session sync check failed")
    return data


def _post_json(
    base_url: str,
    token: str,
    path: str,
    payload: dict[str, object],
    *,
    timeout: float = 120.0,
) -> dict[str, object]:
    return _request_json_with_retry(
        base_url,
        token,
        "POST",
        path,
        body=json.dumps(payload).encode(),
        content_type="application/json",
        attempts=1,
        delay_seconds=0.0,
        timeout=timeout,
    )


def _cleanup_private_cache(files: list[Path]) -> None:
    for path in files:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            print(
                f"warning: failed to remove private cache file: {path}",
                file=sys.stderr,
            )


def _print_session_sync_hints(base_url: str, token: str, *, enabled: bool) -> None:
    if not enabled:
        return

    print(
        "session_token="
        + token,
    )
    print("브라우저 동일 세션 동기화 방법:")
    print(
        "  1) 브라우저에서 NARUON 앱(origin)으로 접속한 뒤, 개발자 콘솔에서 아래 한 줄 실행:",
    )
    print(
        "     await fetch('/auth/session', {method:'POST', credentials:'same-origin', "
        "headers:{'content-type':'application/json'}, body: JSON.stringify({access_token: '"
        + token
        + "'})});",
    )
    safe_origin = base_url.rstrip("/")
    print(f"     (요청 대상: {safe_origin}/auth/session)")
    print("  2) 새로고침 후 /mail 또는 /api/emails로 임포트 반영 및 표시 여부 확인")


def _print_session_check_summary(claims: dict[str, object] | None) -> None:
    if claims is None:
        print("session_check=skipped(endpoint_not_frontend)")
        return
    claims_dict = claims.get("claims")
    if not isinstance(claims_dict, dict):
        print("session_check=failed(unexpected_payload)")
        return
    user = claims_dict.get("userId")
    organization = claims_dict.get("organizationId")
    workspace = claims_dict.get("workspaceId")
    if (
        user is None
        or organization is None
        or workspace is None
        or not isinstance(user, str)
        or not isinstance(organization, str)
        or not isinstance(workspace, str)
    ):
        print("session_check=failed(claim_parse_error)")
        return
    print(f"session_check=ok user={user} org={organization} workspace={workspace}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mail-dir", required=True, type=Path)
    parser.add_argument("--base-url", default=os.environ.get("LIVE_BASE_URL", "http://127.0.0.1:18080"))
    parser.add_argument(
        "--api-base-url",
        help="Optional override when frontend and backend ports differ",
    )
    parser.add_argument(
        "--frontend-base-url",
        help="Optional override when frontend and backend ports differ",
    )
    parser.add_argument("--session-secret", default=os.environ.get("LIVE_E2E_SESSION_SECRET", ""))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--match-mode", choices=["exact", "all-terms"], default="exact")
    parser.add_argument("--llm-smoke", action="store_true")
    parser.add_argument("--print-session-token", action="store_true")
    parser.add_argument("--search-retry-attempts", type=int, default=SEARCH_RETRY_DEFAULT_ATTEMPTS)
    parser.add_argument(
        "--search-retry-delay-seconds",
        type=float,
        default=SEARCH_RETRY_DEFAULT_DELAY_SECONDS,
    )
    parser.add_argument("--inbox-retry-attempts", type=int, default=SEARCH_RETRY_DEFAULT_ATTEMPTS)
    parser.add_argument(
        "--inbox-retry-delay-seconds",
        type=float,
        default=SEARCH_RETRY_DEFAULT_DELAY_SECONDS,
    )
    parser.add_argument(
        "--require-browser-visible",
        action="store_true",
        help="Require browser-proxied inbox visibility check after import",
    )
    parser.add_argument("--max-parse-bytes", type=int, default=2_000_000)
    parser.add_argument("--progress-every", type=int, default=0)
    args = parser.parse_args()

    if not args.session_secret:
        raise SystemExit("LIVE_E2E_SESSION_SECRET or --session-secret is required")
    if args.limit <= 0 or args.batch_size <= 0 or args.batch_size > 10:
        raise SystemExit("--limit must be positive and --batch-size must be 1..10")
    if args.search_retry_attempts < 1 or args.inbox_retry_attempts < 1:
        raise SystemExit("retry-attempts must be at least 1")
    if args.search_retry_delay_seconds < 0 or args.inbox_retry_delay_seconds < 0:
        raise SystemExit("retry-delay-seconds must be non-negative")

    api_base_url = (args.api_base_url or args.base_url).rstrip("/")
    frontend_base_url = (args.frontend_base_url or args.base_url).rstrip("/")

    files = _selected_upload_files(
        args.mail_dir,
        args.query,
        args.limit,
        max_parse_bytes=max(0, args.max_parse_bytes),
        match_mode=args.match_mode,
        progress_every=max(0, args.progress_every),
    )
    if not files:
        raise SystemExit("no matching supported .eml/.mbox/.zip messages found or directory is not readable")

    try:
        token = _signed_token(args.session_secret)
        session_claims = _check_frontend_session(frontend_base_url, token)
        _print_session_check_summary(session_claims)
        totals = Counter()
        reasons = Counter()
        for offset in range(0, len(files), args.batch_size):
            body, content_type = _multipart(files[offset : offset + args.batch_size])
            data = _post_multipart_with_retry(
                api_base_url,
                token,
                "/api/emails/import-files",
                body=body,
                content_type=content_type,
                attempts=args.inbox_retry_attempts,
                delay_seconds=args.inbox_retry_delay_seconds,
                timeout=120.0,
            )
            totals["imported"] += int(data.get("imported_count", 0))
            totals["skipped"] += int(data.get("skipped_count", 0))
            totals["failed"] += int(data.get("failed_count", 0))
            totals["attachments"] += int(data.get("attachment_count", 0))
            for item in data.get("items", []):
                if isinstance(item, dict) and item.get("reason_code"):
                    reasons[str(item["reason_code"])] += 1

        expected_min_count = totals["imported"]
        api_limit = max(1, min(200, expected_min_count if expected_min_count else 1))
        visible_min_count = min(expected_min_count, api_limit)

        api_inbox, email_count = _fetch_inbox_snapshot(
            api_base_url,
            token,
            limit=api_limit,
            min_count=visible_min_count,
            attempts=args.inbox_retry_attempts if expected_min_count > 0 else 1,
            delay_seconds=args.inbox_retry_delay_seconds if expected_min_count > 0 else 0.0,
            timeout=120.0,
        )
        frontend_inbox_count = 0
        if args.require_browser_visible:
            _, frontend_inbox_count = _fetch_inbox_snapshot(
                frontend_base_url,
                token,
                limit=api_limit,
                min_count=visible_min_count,
                use_cookie_only=True,
                attempts=args.inbox_retry_attempts,
                delay_seconds=args.inbox_retry_delay_seconds,
                timeout=120.0,
            )
        elif frontend_base_url.rstrip("/") != api_base_url.rstrip("/"):
            _, frontend_inbox_count = _fetch_inbox_snapshot(
                frontend_base_url,
                token,
                limit=api_limit,
                min_count=0,
                attempts=args.inbox_retry_attempts,
                delay_seconds=args.inbox_retry_delay_seconds,
                timeout=120.0,
            )

        if (
            args.require_browser_visible
            and expected_min_count > 0
            and frontend_inbox_count < visible_min_count
        ):
            raise SystemExit(
                f"browser inbox not reflecting import yet: imported={totals['imported']} visible_min_count={visible_min_count} frontend_inbox_count={frontend_inbox_count}"
            )

        search_counts: dict[str, int] = {}
        frontend_search_counts: dict[str, int] = {}
        first_result_id = None
        for index, query in enumerate(args.query, start=1):
            api_search, api_results_count = _fetch_search_snapshot(
                api_base_url,
                token,
                query,
                attempts=args.search_retry_attempts,
                delay_seconds=args.search_retry_delay_seconds,
                timeout=300.0,
            )
            search_counts[f"query_{index}"] = api_results_count
            if args.require_browser_visible:
                frontend_search, frontend_results_count = _fetch_search_snapshot(
                    frontend_base_url,
                    token,
                    query,
                    attempts=args.search_retry_attempts,
                    delay_seconds=args.search_retry_delay_seconds,
                    timeout=300.0,
                    use_cookie_only=True,
                )
                frontend_search_counts[f"query_{index}"] = frontend_results_count
                if api_results_count > 0 and frontend_results_count == 0:
                    raise SystemExit(
                        f"browser search mismatch: query={query!r} api_results={api_results_count} "
                        f"frontend_results={frontend_results_count}"
                    )

            results = api_search.get("results", [])
            if first_result_id is None and isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    first_result_id = first.get("id")

        llm_status = "skipped"
        draft_status = "skipped"
        target_id = first_result_id
        if target_id is None and email_count:
            first = api_inbox.get("emails", [])
            if isinstance(first, list) and first:
                candidate = first[0]
                if isinstance(candidate, dict):
                    target_id = candidate.get("id")
        if args.llm_smoke and target_id is not None:
            status, raw = _request(api_base_url, token, "GET", f"/api/emails/{target_id}")
            detail = _json_or_empty(status, raw)
            body_text = str(detail.get("body", ""))
            summary = _post_json(
                api_base_url,
                token,
                "/api/llm/summarize",
                {"email_body": body_text},
                timeout=600.0,
            )
            llm_status = (
                f"ok summary_chars={len(str(summary.get('summary', '')))} "
                f"todos={len(summary.get('todos', []))}"
            )
            draft = _post_json(
                api_base_url,
                token,
                "/api/llm/draft",
                {
                    "email_body": body_text,
                    "instruction": "업무 메일 답장 초안을 공손하고 간결하게 작성",
                },
                timeout=600.0,
            )
            draft_status = f"ok draft_chars={len(str(draft.get('draft', '')))}"

        print(
            "private_mail_smoke "
            f"selected={len(files)} imported={totals['imported']} "
            f"skipped={totals['skipped']} failed={totals['failed']} "
            f"attachments={totals['attachments']} inbox_visible={email_count} "
            f"frontend_inbox_visible={frontend_inbox_count} "
            f"search_counts={search_counts} frontend_search_counts={frontend_search_counts} "
            f"reason_counts={dict(reasons)} "
            f"llm={llm_status} draft={draft_status}"
        )
        _print_session_sync_hints(
            frontend_base_url,
            token,
            enabled=args.print_session_token,
        )
    finally:
        _cleanup_private_cache(files)


if __name__ == "__main__":
    main()
