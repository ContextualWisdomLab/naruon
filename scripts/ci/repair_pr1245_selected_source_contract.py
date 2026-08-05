#!/usr/bin/env python3
"""Apply the bounded, test-first repair for Naruon PR 1245.

The helper has two explicit phases. ``--tests`` installs the permanent
regression and doctoring changes before production code is modified, allowing
the workflow to prove a meaningful red state. ``--production`` then applies the
minimal product changes required by that regression. Every transformation is
anchored and fails closed on missing or repeated source text.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend/src/components/EmailDetail.tsx"
TESTS = ROOT / "frontend/src/components/EmailDetail.test.tsx"
DOCTORING = ROOT / "docs/doctoring/email-detail-responsive-action-surface.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    """Replace one reviewed source fragment or verify the desired state."""
    text = path.read_text(encoding="utf-8")
    old_count = text.count(old)
    new_count = text.count(new)
    if old_count == 1 and new_count == 0:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    if old_count == 0 and new_count == 1:
        return
    raise SystemExit(
        f"{label}: invalid source state old={old_count} new={new_count} path={path}"
    )


def apply_tests() -> None:
    """Install permanent regression tests and update evidence documentation."""
    old_test = r'''  it("renders responsive participant and attachment evidence and executes the meeting action", async () => {
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
    await act(async () => { await flushAsyncWork(); });

    expect(container.textContent).toContain("sender@example.com, user@example.com");
    expect(container.textContent).toContain("참여자");
    expect(container.textContent).toContain("proposal.pdf");
    expect(container.textContent).toContain("회의 제안 확인");

    const attachmentRail = container.querySelector<HTMLElement>('[aria-label="첨부파일"]');
    expect(attachmentRail).not.toBeNull();
    expect(attachmentRail?.classList.contains("hidden")).toBe(false);
    expect(attachmentRail?.classList.contains("overflow-x-auto")).toBe(true);

    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    expect(scheduleButton?.disabled).toBe(false);
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/calendar/writeback-intent",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "create", summary: actionItem }),
      }),
    );
    expect(container.textContent).toContain("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.");
  });'''
    new_test = r'''  it("requires an explicit server-authorized calendar source and executes the selected source", async () => {
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
    const sources = [
      {
        source_id: "caldav_source_primary",
        provider: "Fastmail",
        protocol: "caldav",
        owner_id: "owner-1",
        organization_id: "org-1",
        capabilities: ["read", "write", "etag"],
        writeback_enabled: true,
        etag: "etag-primary",
      },
      {
        source_id: "caldav_source_secondary",
        provider: "Nextcloud",
        protocol: "caldav",
        owner_id: "owner-1",
        organization_id: "org-1",
        capabilities: ["read", "write"],
        writeback_enabled: true,
        etag: null,
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/30")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [actionItem] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse(sources));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({
          workspace_id: "workspace-1",
          target_source_id: "caldav_source_primary",
          protocol: "caldav",
          writeback_mode: "customer_owned",
          requires_if_match: false,
          if_match: null,
          provider_write_executed: false,
          status: "intent_recorded",
          runner_request_id: null,
          provider_status: null,
          error_code: null,
          audit_event: "calendar_writeback_intent_created",
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
    await act(async () => { await flushAsyncWork(); });

    expect(container.textContent).toContain("sender@example.com, user@example.com");
    expect(container.textContent).toContain("참여자");
    expect(container.textContent).toContain("proposal.pdf");
    expect(container.textContent).toContain("회의 제안 확인");

    const attachmentRail = container.querySelector<HTMLElement>(
      '[role="region"][aria-label="첨부파일"]',
    );
    expect(attachmentRail).not.toBeNull();
    expect(attachmentRail?.classList.contains("hidden")).toBe(false);
    expect(attachmentRail?.classList.contains("overflow-x-auto")).toBe(true);

    const sourceSelect = container.querySelector<HTMLSelectElement>("#email-calendar-source");
    expect(sourceSelect).not.toBeNull();
    expect(sourceSelect?.value).toBe("");

    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    expect(scheduleButton?.disabled).toBe(true);

    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      await flushAsyncWork();
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
    expect(container.textContent).toContain(
      "1개 일정 반영 의도를 Fastmail 원본 계정에 요청했습니다.",
    );
    expect(getRecordedProductEvents().some((event) =>
      event.name === "calendar_reflected"
      && event.payload.calendar_event_id === null
      && event.payload.conflict_state === "none",
    )).toBe(true);
  });

  it("keeps calendar coordination disabled when no extracted action item exists", async () => {
    const email = {
      id: 31,
      message_id: "<no-action@example.com>",
      thread_id: null,
      sender: "sender@example.com",
      recipients: "user@example.com",
      subject: "No action",
      date: "2026-05-18T10:00:00Z",
      body: "No schedule candidate",
      schedule_conflict: true,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/emails/31")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "owner-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: null,
        }]));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={31} />); });
    await act(async () => { await flushAsyncWork(); });

    const sourceSelect = container.querySelector<HTMLSelectElement>("#email-calendar-source");
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      await flushAsyncWork();
    });
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    expect(scheduleButton?.disabled).toBe(true);
  });

  it("disables calendar coordination and exposes progress while the intent is pending", async () => {
    const pendingIntent = deferred<Response>();
    const email = {
      id: 32,
      message_id: "<pending-calendar@example.com>",
      thread_id: null,
      sender: "sender@example.com",
      recipients: "user@example.com",
      subject: "Pending schedule",
      date: "2026-05-18T10:00:00Z",
      body: "Schedule this",
      schedule_conflict: true,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/32")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: ["Schedule this"] }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "owner-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: null,
        }]));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return pendingIntent.promise;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root?.render(<EmailDetail emailId={32} />); });
    await act(async () => { await flushAsyncWork(); });

    const sourceSelect = container.querySelector<HTMLSelectElement>("#email-calendar-source");
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      await flushAsyncWork();
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
      pendingIntent.resolve(jsonResponse({
        workspace_id: "workspace-1",
        target_source_id: "caldav_source_primary",
        protocol: "caldav",
        writeback_mode: "customer_owned",
        requires_if_match: false,
        if_match: null,
        provider_write_executed: false,
        status: "intent_recorded",
        runner_request_id: null,
        provider_status: null,
        error_code: null,
        audit_event: "calendar_writeback_intent_created",
        provenance: { source_provider: "Fastmail" },
      }));
      await pendingIntent.promise;
      await flushAsyncWork();
    });
    expect(scheduleButton?.disabled).toBe(false);
  });

  it("reports partial calendar intent failures and requires source reconfirmation", async () => {
    const email = {
      id: 33,
      message_id: "<partial-calendar@example.com>",
      thread_id: null,
      sender: "sender@example.com",
      recipients: "user@example.com",
      subject: "Partial schedule",
      date: "2026-05-18T10:00:00Z",
      body: "Two schedule candidates",
      schedule_conflict: true,
    };
    let intentCall = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/emails/33")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({
          summary: "Summary",
          action_items: ["First schedule", "Second schedule"],
        }));
      }
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav_source_primary",
          provider: "Fastmail",
          protocol: "caldav",
          owner_id: "owner-1",
          organization_id: "org-1",
          capabilities: ["write"],
          writeback_enabled: true,
          etag: null,
        }]));
      }
      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        intentCall += 1;
        if (intentCall === 1) {
          return Promise.resolve(jsonResponse({
            workspace_id: "workspace-1",
            target_source_id: "caldav_source_primary",
            protocol: "caldav",
            writeback_mode: "customer_owned",
            requires_if_match: false,
            if_match: null,
            provider_write_executed: false,
            status: "intent_recorded",
            runner_request_id: null,
            provider_status: null,
            error_code: null,
            audit_event: "calendar_writeback_intent_created",
            provenance: { source_provider: "Fastmail" },
          }));
        }
        return Promise.resolve(new Response(JSON.stringify({ detail: "source conflict" }), {
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
    await act(async () => { await flushAsyncWork(); });

    const sourceSelect = container.querySelector<HTMLSelectElement>("#email-calendar-source");
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav_source_primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      await flushAsyncWork();
    });
    const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.includes("일정 조율"),
    );
    await act(async () => {
      scheduleButton?.click();
      await flushAsyncWork();
    });

    expect(container.textContent).toContain("1개 성공, 1개 실패");
    expect(container.textContent).toContain("원본을 다시 선택");
    expect(sourceSelect?.value).toBe("");
    expect(scheduleButton?.disabled).toBe(true);
  });'''
    replace_once(TESTS, old_test, new_test, "EmailDetail scheduling regression")

    if not DOCTORING.is_file():
        raise SystemExit(f"{DOCTORING}: reviewed doctoring file not found")
    doctoring = DOCTORING.read_text(encoding="utf-8")
    doctoring = doctoring.replace(
        "gives the attachment evidence region an\naccessible name, and exposes asynchronous status through `role=status` and\n`aria-live=polite`.",
        "exposes the attachment evidence as a named `region` landmark, and exposes\nasynchronous status through `role=status` and `aria-live=polite`.",
    )
    doctoring = doctoring.replace(
        "- The meeting action is disabled when no extracted action item exists.\n"
        "- Activating the meeting action sends the exact writeback-intent request.\n"
        "- Successful writeback intent produces a polite live status.",
        "- The meeting action is disabled without an extracted action item, while\n"
        "  the source registry loads, without an explicit source choice, and while a\n"
        "  request is pending.\n"
        "- Activating the meeting action sends the exact opaque source identifier\n"
        "  selected from the server-authorized registry.\n"
        "- Source conflicts require explicit reconfirmation; partial success and\n"
        "  failure counts remain visible through a polite live status.",
    )
    DOCTORING.write_text(doctoring, encoding="utf-8")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    changelog = changelog.replace(
        "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 연결하고 loading·disabled·live-status 상태를 검증합니다.",
        "- 일정 충돌 패널의 `일정 조율` 버튼을 서버가 승인한 불투명 원본 ID의 명시적 선택과 calendar writeback intent에 연결하고, loading·disabled·부분 실패·충돌 재확인·live-status 상태를 검증합니다.",
    )
    CHANGELOG.write_text(changelog, encoding="utf-8")


def apply_production() -> None:
    """Apply the minimal product implementation required by the red tests."""
    replace_once(
        COMPONENT,
        '''import {
  bucketTextLength,
  createProductEventId,
  recordProductEvent,
} from "@/lib/product-events";
''',
        '''import {
  bucketTextLength,
  createProductEventId,
  recordProductEvent,
} from "@/lib/product-events";
import {
  getApiErrorStatus,
  getCalendarSourceLabel,
  getProtocolLabel,
  isCustomerOwnedWritableSource,
} from "@/components/calendar/helpers";
import type {
  CalendarWritebackIntentResponse,
  CalendarWritebackSource,
} from "@/components/calendar/types";
''',
        "calendar writeback imports",
    )
    replace_once(
        COMPONENT,
        '''interface CalendarWritebackIntentResponse {
  target_source_id: string;
  protocol: string;
  provider_write_executed?: boolean;
  status?: string;
  runner_request_id?: string | null;
  provider_status?: number | null;
  error_code?: string | null;
  provenance: {
    source_provider?: string;
  };
}

''',
        "",
        "duplicate calendar response interface",
    )
    replace_once(
        COMPONENT,
        '''  const [isSyncing, setIsSyncing] = useState(false);
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [syncStatus, setSyncStatus] = useState<{type: 'success' | 'error', message: string} | null>(null);
''',
        '''  const [isSyncing, setIsSyncing] = useState(false);
  const [calendarSources, setCalendarSources] = useState<CalendarWritebackSource[]>([]);
  const [calendarSourceLoadStatus, setCalendarSourceLoadStatus] = useState<
    'idle' | 'loading' | 'ready' | 'error'
  >('idle');
  const [selectedCalendarSourceId, setSelectedCalendarSourceId] = useState('');
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [syncStatus, setSyncStatus] = useState<{type: 'success' | 'error', message: string} | null>(null);
''',
        "calendar source state",
    )
    replace_once(
        COMPONENT,
        '''  useEffect(() => {
    handledActionCommandIdRef.current = null;
  }, [emailId]);

  const fetchThread = useCallback(async (currentEmail: EmailData) => {
''',
        '''  useEffect(() => {
    handledActionCommandIdRef.current = null;
  }, [emailId]);

  useEffect(() => {
    if (!email?.schedule_conflict) {
      setCalendarSources([]);
      setCalendarSourceLoadStatus('idle');
      setSelectedCalendarSourceId('');
      return;
    }

    let isActive = true;
    setCalendarSources([]);
    setCalendarSourceLoadStatus('loading');
    setSelectedCalendarSourceId('');
    setSyncStatus(null);

    void apiClient.get<CalendarWritebackSource[]>('/api/calendar/writeback-sources')
      .then((sources) => {
        if (!isActive) return;
        setCalendarSources(sources.filter(isCustomerOwnedWritableSource));
        setCalendarSourceLoadStatus('ready');
      })
      .catch(() => {
        if (!isActive) return;
        setCalendarSources([]);
        setCalendarSourceLoadStatus('error');
      });

    return () => {
      isActive = false;
    };
  }, [email?.id, email?.schedule_conflict]);

  const fetchThread = useCallback(async (currentEmail: EmailData) => {
''',
        "calendar source registry effect",
    )

    old_handler = r'''  const handleSyncCalendar = useCallback(async () => {
    const actionEmailId = emailId;
    const isCurrentEmail = () => currentEmailIdRef.current === actionEmailId;
    const actionItems = llmData?.action_items ?? [];
    if (!actionItems.length) {
      setSyncStatus({ type: 'error', message: '캘린더에 반영할 실행 항목이 없습니다.' });
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
          }),
        ),
      );
      if (!isCurrentEmail()) return;
      setSyncStatus({ type: 'success', message: `${intents.length}개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.` });
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
    } catch {
      if (!isCurrentEmail()) return;
      setSyncStatus({ type: 'error', message: '일정 반영 의도 요청에 실패했습니다.' });
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
  }, [email, emailId, llmData]);
'''
    new_handler = r'''  const handleSyncCalendar = useCallback(async () => {
    const actionEmailId = emailId;
    const isCurrentEmail = () => currentEmailIdRef.current === actionEmailId;
    const actionItems = llmData?.action_items ?? [];
    if (!actionItems.length) {
      setSyncStatus({ type: 'error', message: '캘린더에 반영할 실행 항목이 없습니다.' });
      return;
    }
    if (calendarSourceLoadStatus !== 'ready') {
      setSyncStatus({
        type: 'error',
        message: calendarSourceLoadStatus === 'error'
          ? '일정 원본을 불러오지 못했습니다.'
          : '일정 원본을 불러오는 중입니다.',
      });
      return;
    }

    const selectedSource = calendarSources.find(
      (source) => source.source_id === selectedCalendarSourceId,
    );
    if (!selectedSource || !isCustomerOwnedWritableSource(selectedSource)) {
      setSyncStatus({ type: 'error', message: '일정을 반영할 원본 계정을 먼저 선택하세요.' });
      return;
    }

    setIsSyncing(true);
    setSyncStatus(null);
    const startedAt = nowMs();
    try {
      const settledIntents = await Promise.allSettled(
        actionItems.map((summary) =>
          apiClient.post<CalendarWritebackIntentResponse>('/api/calendar/writeback-intent', {
            action: 'create',
            summary,
            target_source_id: selectedSource.source_id,
          }),
        ),
      );
      if (!isCurrentEmail()) return;

      const successfulIntents: CalendarWritebackIntentResponse[] = [];
      let rejectedCount = 0;
      let conflictCount = 0;
      settledIntents.forEach((result) => {
        if (result.status === 'rejected') {
          rejectedCount += 1;
          if (getApiErrorStatus(result.reason) === 409) conflictCount += 1;
          return;
        }
        if (result.value.target_source_id !== selectedSource.source_id) {
          conflictCount += 1;
          return;
        }
        successfulIntents.push(result.value);
      });

      const failedCount = rejectedCount + conflictCount;
      if (conflictCount > 0) setSelectedCalendarSourceId('');
      const sourceProvider = toMailDisplayText(
        successfulIntents[0]?.provenance?.source_provider || selectedSource.provider,
        '선택한 원본',
      );

      if (successfulIntents.length === 0) {
        setSyncStatus({
          type: 'error',
          message: conflictCount > 0
            ? '선택한 일정 원본이 변경되었습니다. 원본을 다시 선택하세요.'
            : '일정 반영 의도 요청에 실패했습니다.',
        });
        recordProductEvent("latency_guardrail_recorded", {
          surface: "mail_detail",
          request_trace_id: createProductEventId("calendar_trace"),
          operation: "calendar_reflection",
          duration_ms: Math.round(nowMs() - startedAt),
          status: "error",
        });
        return;
      }

      setSyncStatus({
        type: failedCount > 0 ? 'error' : 'success',
        message: failedCount > 0
          ? `${successfulIntents.length}개 성공, ${failedCount}개 실패했습니다. 원본을 다시 선택해 실패 항목을 재시도하세요.`
          : `${successfulIntents.length}개 일정 반영 의도를 ${sourceProvider} 원본 계정에 요청했습니다.`,
      });
      recordProductEvent("calendar_reflected", {
        surface: "mail_detail",
        calendar_candidate_id: `mail-calendar:${actionEmailId ?? "unknown"}`,
        calendar_event_id: null,
        thread_id: email ? getThreadEventId(email) : null,
        conflict_state: conflictCount > 0 ? "conflict" : failedCount > 0 ? "warning" : "none",
        provider_write_executed: successfulIntents.some(
          (intent) => Boolean(intent.provider_write_executed),
        ),
      });
      recordProductEvent("latency_guardrail_recorded", {
        surface: "mail_detail",
        request_trace_id: createProductEventId("calendar_trace"),
        operation: "calendar_reflection",
        duration_ms: Math.round(nowMs() - startedAt),
        status: failedCount > 0 ? "error" : "success",
      });
    } catch {
      if (!isCurrentEmail()) return;
      setSyncStatus({ type: 'error', message: '일정 반영 의도 요청에 실패했습니다.' });
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
  }, [
    calendarSourceLoadStatus,
    calendarSources,
    email,
    emailId,
    llmData,
    selectedCalendarSourceId,
  ]);
'''
    replace_once(COMPONENT, old_handler, new_handler, "calendar writeback handler")

    replace_once(
        COMPONENT,
        '''              <div
                aria-label="첨부파일"
                className="mt-2 flex min-w-0 items-center gap-2 overflow-x-auto pb-1"
              >''',
        '''              <div
                role="region"
                aria-label="첨부파일"
                className="mt-2 flex min-w-0 items-center gap-2 overflow-x-auto pb-1"
              >''',
        "attachment region landmark",
    )

    old_panel = r'''          {email.schedule_conflict && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-sm font-bold text-emerald-800 dark:text-emerald-200">회의 제안 확인</h3>
                  <p className="mt-1 text-xs text-emerald-700/80 dark:text-emerald-300/80">이메일에 포함된 회의 일정을 캘린더와 조율합니다.</p>
                </div>
                <Button
                  size="sm"
                  onClick={handleSyncCalendar}
                  disabled={isSyncing || actionItems.length === 0}
                  aria-busy={isSyncing}
                  className="h-8 rounded-xl bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700"
                >
                  {isSyncing && <Loader2 className="mr-2 h-3 w-3 animate-spin" aria-hidden="true" />}
                  {isSyncing ? "조율 중" : "일정 조율"}
                </Button>
              </div>
            </div>
          )}'''
    new_panel = r'''          {email.schedule_conflict && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-sm">
              <div className="flex flex-col gap-3">
                <div>
                  <h3 className="text-sm font-bold text-emerald-800 dark:text-emerald-200">회의 제안 확인</h3>
                  <p className="mt-1 text-xs text-emerald-700/80 dark:text-emerald-300/80">
                    서버가 승인한 원본 계정을 직접 선택한 뒤 일정 반영 의도를 요청합니다.
                  </p>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <label className="grid min-w-0 flex-1 gap-1 text-xs font-semibold text-emerald-900 dark:text-emerald-100" htmlFor="email-calendar-source">
                    일정 원본 계정
                    <select
                      id="email-calendar-source"
                      value={selectedCalendarSourceId}
                      onChange={(event) => {
                        setSelectedCalendarSourceId(event.target.value);
                        setSyncStatus(null);
                      }}
                      disabled={calendarSourceLoadStatus !== 'ready' || isSyncing}
                      className="h-9 min-w-0 rounded-lg border border-emerald-500/30 bg-background px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                    >
                      <option value="">원본 계정 선택</option>
                      {calendarSources.map((source, index) => (
                        <option key={source.source_id} value={source.source_id}>
                          {getCalendarSourceLabel(index)} · {getProtocolLabel(source.protocol)} · {source.provider}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    size="sm"
                    onClick={handleSyncCalendar}
                    disabled={
                      isSyncing
                      || actionItems.length === 0
                      || calendarSourceLoadStatus !== 'ready'
                      || !selectedCalendarSourceId
                    }
                    aria-busy={isSyncing}
                    className="h-9 rounded-xl bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700"
                  >
                    {isSyncing && <Loader2 className="mr-2 h-3 w-3 animate-spin" aria-hidden="true" />}
                    {isSyncing ? "조율 중" : "일정 조율"}
                  </Button>
                </div>
                {calendarSourceLoadStatus === 'loading' && (
                  <p role="status" aria-live="polite" className="text-xs text-emerald-700 dark:text-emerald-300">
                    일정 원본을 불러오는 중입니다.
                  </p>
                )}
                {calendarSourceLoadStatus === 'error' && (
                  <p role="alert" className="text-xs text-red-600 dark:text-red-400">
                    일정 원본을 불러오지 못했습니다.
                  </p>
                )}
                {calendarSourceLoadStatus === 'ready' && calendarSources.length === 0 && (
                  <p role="status" aria-live="polite" className="text-xs text-emerald-700 dark:text-emerald-300">
                    쓰기 권한이 있는 원본 계정이 없습니다.
                  </p>
                )}
              </div>
            </div>
          )}'''
    replace_once(COMPONENT, old_panel, new_panel, "calendar coordination panel")


def main() -> None:
    """Run the requested deterministic repair phase."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", action="store_true")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    if args.tests == args.production:
        raise SystemExit("choose exactly one of --tests or --production")
    if args.tests:
        apply_tests()
    else:
        apply_production()


if __name__ == "__main__":
    main()
