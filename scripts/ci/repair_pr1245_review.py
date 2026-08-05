#!/usr/bin/env python3
"""Apply the bounded PR 1245 review repair in test-first stages."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend/src/components/EmailDetail.tsx"
TESTS = ROOT / "frontend/src/components/EmailDetail.test.tsx"
DOCTORING = ROOT / "docs/doctoring/email-detail-responsive-action-surface.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def replace_once(path: Path, old: str, new: str) -> None:
    """Replace exactly one reviewed anchor or fail closed."""
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_tests() -> None:
    """Replace the original shallow regression with selected-source contracts."""
    text = TESTS.read_text(encoding="utf-8")
    marker = '  it("renders responsive participant and attachment evidence and executes the meeting action", async () => {'
    start = text.index(marker)
    end_marker = "\n  });\n});"
    end = text.index(end_marker, start) + len("\n  });")
    replacement = r'''  it("renders responsive evidence and executes the selected-source meeting action", async () => {
    const email = {
      id: 30,
      message_id: "<ui-density@example.com>",
      thread_id: null,
      sender: "sender@example.com",
      recipients: "user@example.com",
      subject: "UI Density",
      date: "2026-05-18T10:00:00Z",
      body: "High density UI",
      schedule_conflict: true,
      requires_reply: true,
      attachments: ["proposal.pdf", "schedule.xlsx"],
    };
    const actionItem = "Review project meeting on 2026-05-19";
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/30")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [actionItem] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([
          {
            source_id: "caldav_source_primary",
            provider: "Fastmail",
            protocol: "caldav",
            owner_id: "user-1",
            organization_id: "org-1",
            capabilities: ["read", "write", "etag"],
            writeback_enabled: true,
            etag: '"v1"',
          },
          {
            source_id: "local_source_ignored",
            provider: "Local",
            protocol: "local",
            owner_id: "user-1",
            organization_id: "org-1",
            capabilities: ["read", "write"],
            writeback_enabled: true,
            etag: null,
          },
        ]));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({
          target_source_id: "caldav_source_primary",
          protocol: "caldav",
          provider_write_executed: false,
          provenance: { source_provider: "Fastmail" },
        }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={30} />); });
    await flushAsyncWork();

    expect(container.textContent).toContain("sender@example.com, user@example.com");
    expect(container.textContent).toContain("proposal.pdf");
    const attachmentRail = container.querySelector<HTMLElement>('[role="region"][aria-label="첨부파일"]');
    expect(attachmentRail).not.toBeNull();
    expect(attachmentRail?.classList.contains("hidden")).toBe(false);

    const sourceSelect = container.querySelector<HTMLSelectElement>('#email-detail-calendar-source');
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    expect(sourceSelect).not.toBeNull();
    expect(scheduleButton?.disabled).toBe(true);
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    expect(scheduleButton?.disabled).toBe(false);
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/calendar/writeback-intent",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          action: "create",
          summary: actionItem,
          target_source_id: "caldav_source_primary",
        }),
      }),
    );
    expect(container.textContent).toContain("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다. (Fastmail)");
  });

  it("keeps the meeting action disabled without extracted action items", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/31")) {
        return Promise.resolve(jsonResponse({
          id: 31,
          message_id: "<no-actions@example.com>",
          thread_id: null,
          sender: "sender@example.com",
          recipients: "user@example.com",
          subject: "No actions",
          date: "2026-05-18T10:00:00Z",
          body: "No calendar action",
          schedule_conflict: true,
        }));
      }
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "user-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: '"v1"',
        }]));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={31} />); });
    await flushAsyncWork();

    const sourceSelect = container.querySelector<HTMLSelectElement>('#email-detail-calendar-source');
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    expect(scheduleButton?.disabled).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toBe(false);
  });

  it("disables and relabels the meeting action while writeback is pending", async () => {
    const writebackRequest = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/32")) {
        return Promise.resolve(jsonResponse({
          id: 32,
          message_id: "<pending@example.com>",
          thread_id: null,
          sender: "sender@example.com",
          recipients: "user@example.com",
          subject: "Pending",
          date: "2026-05-18T10:00:00Z",
          body: "Pending calendar action",
          schedule_conflict: true,
        }));
      }
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: ["Schedule review"] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "user-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: '"v1"',
        }]));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return writebackRequest.promise;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={32} />); });
    await flushAsyncWork();

    const sourceSelect = container.querySelector<HTMLSelectElement>('#email-detail-calendar-source');
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    await act(async () => {
      scheduleButton?.click();
      await Promise.resolve();
    });
    expect(scheduleButton?.disabled).toBe(true);
    expect(scheduleButton?.textContent).toContain("조율 중");

    await act(async () => {
      writebackRequest.resolve(jsonResponse({
        target_source_id: "caldav_source_primary",
        protocol: "caldav",
        provider_write_executed: false,
        provenance: { source_provider: "Fastmail" },
      }));
      await writebackRequest.promise;
      await flushAsyncWork();
    });
    expect(scheduleButton?.disabled).toBe(false);
  });

  it("reports a selected-source conflict and requires confirmation again", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/33")) {
        return Promise.resolve(jsonResponse({
          id: 33,
          message_id: "<conflict@example.com>",
          thread_id: null,
          sender: "sender@example.com",
          recipients: "user@example.com",
          subject: "Conflict",
          date: "2026-05-18T10:00:00Z",
          body: "Conflict calendar action",
          schedule_conflict: true,
        }));
      }
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: ["Schedule review"] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "user-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: '"v1"',
        }]));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ detail: "conflict" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={33} />); });
    await flushAsyncWork();

    const sourceSelect = container.querySelector<HTMLSelectElement>('#email-detail-calendar-source');
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(container.textContent).toContain("선택한 일정 원본이 변경되어 충돌했습니다. 원본을 다시 선택하세요.");
    expect(sourceSelect?.value).toBe("");
    expect(scheduleButton?.disabled).toBe(true);
  });'''
    TESTS.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def apply_production() -> None:
    """Apply the source-selection, conflict, landmark, and documentation repair."""
    replace_once(
        COMPONENT,
        '} from "@/lib/product-events";\n\n',
        '} from "@/lib/product-events";\nimport type { CalendarWritebackSource } from "@/components/calendar/types";\nimport { getApiErrorStatus, isCustomerOwnedWritableSource } from "@/components/calendar/helpers";\n\n',
    )
    replace_once(
        COMPONENT,
        "  const [taskStatus, setTaskStatus] = useState<string | null>(null);\n  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);\n",
        "  const [taskStatus, setTaskStatus] = useState<string | null>(null);\n  const [calendarSources, setCalendarSources] = useState<CalendarWritebackSource[]>([]);\n  const [calendarSourceStatus, setCalendarSourceStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');\n  const [selectedCalendarSourceId, setSelectedCalendarSourceId] = useState('');\n  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);\n",
    )
    replace_once(
        COMPONENT,
        "  const activeDraftReplyIdRef = useRef<string | null>(null);\n\n  useEffect(() => {\n",
        "  const activeDraftReplyIdRef = useRef<string | null>(null);\n  const selectedCalendarSource = calendarSources.find(\n    (source) => source.source_id === selectedCalendarSourceId,\n  ) ?? null;\n  const shouldLoadCalendarSources = Boolean(\n    email && (email.schedule_conflict || (llmData?.action_items.length ?? 0) > 0),\n  );\n\n  useEffect(() => {\n",
    )
    replace_once(
        COMPONENT,
        "  useEffect(() => {\n    handledActionCommandIdRef.current = null;\n  }, [emailId]);\n\n  const fetchThread = useCallback(async (currentEmail: EmailData) => {\n",
        "  useEffect(() => {\n    handledActionCommandIdRef.current = null;\n  }, [emailId]);\n\n  useEffect(() => {\n    if (!shouldLoadCalendarSources) {\n      setCalendarSources([]);\n      setCalendarSourceStatus('idle');\n      setSelectedCalendarSourceId('');\n      return;\n    }\n\n    let isMounted = true;\n    setCalendarSourceStatus('loading');\n    setCalendarSources([]);\n    setSelectedCalendarSourceId('');\n    void apiClient.get<CalendarWritebackSource[]>('/api/calendar/writeback-sources')\n      .then((sources) => {\n        if (!isMounted) return;\n        setCalendarSources(sources.filter(isCustomerOwnedWritableSource));\n        setCalendarSourceStatus('ready');\n      })\n      .catch(() => {\n        if (!isMounted) return;\n        setCalendarSources([]);\n        setSelectedCalendarSourceId('');\n        setCalendarSourceStatus('error');\n      });\n\n    return () => {\n      isMounted = false;\n    };\n  }, [email?.id, shouldLoadCalendarSources]);\n\n  const fetchThread = useCallback(async (currentEmail: EmailData) => {\n",
    )
    replace_once(
        COMPONENT,
        "      setSyncStatus(null);\n      setTaskStatus(null);\n      setSourceDrawerOpen(false);\n",
        "      setSyncStatus(null);\n      setTaskStatus(null);\n      setCalendarSources([]);\n      setCalendarSourceStatus('idle');\n      setSelectedCalendarSourceId('');\n      setSourceDrawerOpen(false);\n",
    )

    text = COMPONENT.read_text(encoding="utf-8")
    start = text.index("  const handleSyncCalendar = useCallback(async () => {")
    end = text.index("\n\n  const handleCreateTask = useCallback", start)
    handler = '''  const handleSyncCalendar = useCallback(async () => {
    const actionEmailId = emailId;
    const isCurrentEmail = () => currentEmailIdRef.current === actionEmailId;
    const actionItems = llmData?.action_items ?? [];
    if (!actionItems.length) {
      setSyncStatus({ type: 'error', message: '캘린더에 반영할 실행 항목이 없습니다.' });
      return;
    }
    if (calendarSourceStatus !== 'ready' || selectedCalendarSource === null) {
      setSyncStatus({ type: 'error', message: '일정을 반영할 원본 계정을 먼저 선택하세요.' });
      return;
    }
    setIsSyncing(true);
    setSyncStatus(null);
    const startedAt = nowMs();
    try {
      const intents = await Promise.all(
        actionItems.map((summary) =>
          apiClient.post<CalendarWritebackIntentResponse>('/api/calendar/writeback-intent', {
            action: 'create',
            summary,
            target_source_id: selectedCalendarSource.source_id,
          }),
        ),
      );
      if (!isCurrentEmail()) return;
      if (intents.some((intent) => intent.target_source_id !== selectedCalendarSource.source_id)) {
        const conflict = new Error('Calendar source mismatch') as Error & { status: number };
        conflict.status = 409;
        throw conflict;
      }
      const sourceProvider = intents[0]?.provenance?.source_provider || selectedCalendarSource.provider;
      setSyncStatus({
        type: 'success',
        message: `${intents.length}개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.${sourceProvider ? ` (${sourceProvider})` : ''}`,
      });
      recordProductEvent("calendar_reflected", {
        surface: "mail_detail",
        calendar_candidate_id: `mail-calendar:${actionEmailId ?? "unknown"}`,
        calendar_event_id: intents[0]?.target_source_id ?? null,
        thread_id: email ? getThreadEventId(email) : null,
        conflict_state: "none",
        provider_write_executed: intents.some((intent) => Boolean(intent.provider_write_executed)),
      });
      recordProductEvent("latency_guardrail_recorded", {
        surface: "mail_detail",
        request_trace_id: createProductEventId("calendar_trace"),
        operation: "calendar_reflection",
        duration_ms: Math.round(nowMs() - startedAt),
        status: "success",
      });
    } catch (error: unknown) {
      if (!isCurrentEmail()) return;
      const status = getApiErrorStatus(error);
      if (status === 409) {
        setSelectedCalendarSourceId('');
        setSyncStatus({ type: 'error', message: '선택한 일정 원본이 변경되어 충돌했습니다. 원본을 다시 선택하세요.' });
      } else if (status === 422) {
        setSelectedCalendarSourceId('');
        setSyncStatus({ type: 'error', message: '선택한 일정 원본을 사용할 수 없습니다. 원본을 다시 선택하세요.' });
      } else if (status === 401 || status === 403) {
        setSyncStatus({ type: 'error', message: '선택한 일정 원본을 사용할 권한이 없습니다.' });
      } else {
        setSyncStatus({ type: 'error', message: '일정 반영 의도 요청에 실패했습니다.' });
      }
      recordProductEvent("latency_guardrail_recorded", {
        surface: "mail_detail",
        request_trace_id: createProductEventId("calendar_trace"),
        operation: "calendar_reflection",
        duration_ms: Math.round(nowMs() - startedAt),
        status: "error",
      });
    } finally {
      if (isCurrentEmail()) setIsSyncing(false);
    }
  }, [calendarSourceStatus, email, emailId, llmData, selectedCalendarSource]);'''
    COMPONENT.write_text(text[:start] + handler + text[end:], encoding="utf-8")

    replace_once(
        COMPONENT,
        "  const confidencePercent = toConfidencePercent(llmData?.confidence);\n  const actionItems = llmData?.action_items ?? [];\n\n  const handleOpenSourceDrawer = () => {\n",
        '''  const confidencePercent = toConfidencePercent(llmData?.confidence);
  const actionItems = llmData?.action_items ?? [];
  const isCalendarSyncDisabled = isSyncing
    || actionItems.length === 0
    || calendarSourceStatus !== 'ready'
    || selectedCalendarSource === null;
  const calendarSourceControl = (
    <div className="min-w-[13rem]">
      <label htmlFor="email-detail-calendar-source" className="mb-1 block text-xs font-semibold text-emerald-800 dark:text-emerald-200">
        일정 원본
      </label>
      <select
        id="email-detail-calendar-source"
        aria-label="일정 원본"
        value={selectedCalendarSourceId}
        onChange={(event) => {
          setSelectedCalendarSourceId(event.currentTarget.value);
          setSyncStatus(null);
        }}
        disabled={isSyncing || calendarSourceStatus !== 'ready' || calendarSources.length === 0}
        className="h-9 w-full rounded-lg border border-emerald-500/30 bg-card px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">
          {calendarSourceStatus === 'loading'
            ? '일정 원본 불러오는 중'
            : calendarSourceStatus === 'error'
              ? '일정 원본을 불러오지 못했습니다'
              : calendarSources.length === 0
                ? '사용 가능한 일정 원본 없음'
                : '일정 원본 선택'}
        </option>
        {calendarSources.map((source) => (
          <option key={source.source_id} value={source.source_id}>
            {source.provider || '원본 계정'} · {source.protocol.toUpperCase()}
          </option>
        ))}
      </select>
    </div>
  );

  const handleOpenSourceDrawer = () => {
''',
    )
    replace_once(
        COMPONENT,
        '              <div\n                aria-label="첨부파일"\n                className="mt-2 flex min-w-0 items-center gap-2 overflow-x-auto pb-1"\n',
        '              <div\n                role="region"\n                aria-label="첨부파일"\n                className="mt-2 flex min-w-0 items-center gap-2 overflow-x-auto pb-1"\n',
    )

    text = COMPONENT.read_text(encoding="utf-8")
    start = text.index("          {email.schedule_conflict && (")
    end = text.index("\n          )}\n          <DecisionPointCard", start) + len("\n          )}")
    conflict_block = '''          {email.schedule_conflict && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-sm">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-bold text-emerald-800 dark:text-emerald-200">회의 제안 확인</h3>
                  <p className="mt-1 text-xs text-emerald-700/80 dark:text-emerald-300/80">이메일에 포함된 회의 일정을 캘린더와 조율합니다.</p>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                  {calendarSourceControl}
                  <Button
                    size="sm"
                    onClick={handleSyncCalendar}
                    disabled={isCalendarSyncDisabled}
                    aria-busy={isSyncing}
                    className="h-9 rounded-xl bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700 disabled:hover:bg-emerald-600"
                  >
                    {isSyncing && <Loader2 className="mr-2 h-3 w-3 animate-spin" aria-hidden="true" />}
                    {isSyncing ? "조율 중" : "일정 조율"}
                  </Button>
                </div>
              </div>
            </div>
          )}'''
    COMPONENT.write_text(text[:start] + conflict_block + text[end:], encoding="utf-8")

    replace_once(
        COMPONENT,
        '''                {actionItems.length > 0 && (
                  <Button
                    size="sm"
                    onClick={handleSyncCalendar}
                    disabled={isSyncing}
''',
        '''                {actionItems.length > 0 && !email.schedule_conflict && calendarSourceControl}
                {actionItems.length > 0 && (
                  <Button
                    size="sm"
                    onClick={handleSyncCalendar}
                    disabled={isCalendarSyncDisabled}
''',
    )

    DOCTORING.write_text('''# EmailDetail responsive action surface doctoring

## Decision

EmailDetail preserves participant and attachment evidence at every viewport and
exposes attachments as a named `region` landmark. Calendar writeback is never
automatically routed: the user must confirm a server-authorized, customer-owned,
writable opaque `target_source_id`. The identifier is sent unchanged to the
existing writeback-intent boundary, and server provenance remains authoritative.

## Failure and concurrency boundary

The action remains disabled until action items and a confirmed source exist, and
while a request is pending. HTTP 409 and 422 clear the selection and require new
confirmation; authorization errors do not silently choose another account.
Asynchronous status is announced through `role=status` and `aria-live=polite`.

## Verification contract

- attachment evidence is a named region and remains visible on small viewports;
- local or non-writable source records are excluded;
- no-action and pending-request states disable the action;
- the exact selected source is present in every writeback request;
- source mismatch and HTTP 409/422 require renewed confirmation;
- focused and full frontend tests, type checking, lint, coverage collection, and
  production build pass before publication.

## References

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (n.d.). *WAI-ARIA 1.2: Region role*. Retrieved August
5, 2026, from https://www.w3.org/TR/wai-aria-1.2/#region

World Wide Web Consortium. (n.d.). *Understanding success criterion 4.1.3:
Status messages*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
''', encoding="utf-8")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    old = "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 연결하고 loading·disabled·live-status 상태를 검증합니다."
    new = "- 일정 충돌 패널의 `일정 조율` 버튼을 서버가 허용한 고객 소유 원본의 명시적 선택과 연결하고, exact `target_source_id`, 충돌 재확인, loading·disabled·live-status 상태를 검증합니다."
    if old not in changelog:
        raise SystemExit("CHANGELOG.md: reviewed EmailDetail bullet not found")
    CHANGELOG.write_text(changelog.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    """Apply one requested stage."""
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("tests", "production"))
    args = parser.parse_args()
    if args.stage == "tests":
        apply_tests()
    else:
        apply_production()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
