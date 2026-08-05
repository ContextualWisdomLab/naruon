#!/usr/bin/env python3
"""Apply the bounded PR 1243 responsive EmailDetail repair.

The temporary script edits only reviewed frontend, test, changelog, and doctoring
paths. The one-shot workflow restores unrelated backend files from the exact PR
base, verifies the product behavior, and removes this script before publishing
the final product commit.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    """Replace exactly one reviewed fragment or terminate without partial trust."""
    target = REPO_ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one reviewed fragment, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def repair_component() -> None:
    """Make the proposed responsive surface functional and source typed."""
    path = "frontend/src/components/EmailDetail.tsx"
    replace_once(
        path,
        '''type EmailData = ThreadEmailData & {
  requires_reply?: boolean;
  schedule_conflict?: boolean;
  attachments?: string[];
};
''',
        '''type EmailData = ThreadEmailData & {
  requires_reply?: boolean;
  schedule_conflict?: boolean;
  recipients?: string;
  attachments?: string[];
};
''',
    )
    replace_once(
        path,
        '''  const safeReplyTo = toMailDisplayText(email.reply_to || email.sender, '답장 주소 없음');
  const safeRecipients = toMailDisplayText((email as ThreadEmailData & { recipients?: string }).recipients || email.sender, '참여자 없음');
  const confidencePercent = toConfidencePercent(llmData?.confidence);
''',
        '''  const safeReplyTo = toMailDisplayText(email.reply_to || email.sender, '답장 주소 없음');
  const safeRecipients = toMailDisplayText(email.recipients || email.sender, '참여자 없음');
  const safeParticipants = Array.from(new Set([safeEmailSender, safeRecipients])).join(', ');
  const confidencePercent = toConfidencePercent(llmData?.confidence);
''',
    )
    replace_once(
        path,
        '''            <div className="hidden sm:block text-xs text-muted-foreground">
              <span className="font-semibold mr-1">참여자:</span>
              <span className="break-all">{safeEmailSender}, {safeRecipients}</span>
            </div>
            {email.attachments && email.attachments.length > 0 && (
              <div className="hidden md:flex items-center gap-2 mt-2">
                <span className="text-xs font-semibold text-muted-foreground">첨부파일:</span>
                {email.attachments.map((file, idx) => (
                  <Badge key={idx} variant="secondary" className="text-[10px] py-0 px-2 h-5">{file}</Badge>
                ))}
              </div>
            )}
''',
        '''            <div className="text-xs text-muted-foreground">
              <span className="mr-1 font-semibold">참여자:</span>
              <span className="break-all">{safeParticipants}</span>
            </div>
            {email.attachments && email.attachments.length > 0 && (
              <div
                aria-label="첨부파일"
                className="mt-2 flex min-w-0 items-center gap-2 overflow-x-auto pb-1"
              >
                <span className="shrink-0 text-xs font-semibold text-muted-foreground">첨부파일:</span>
                {email.attachments.map((file, idx) => (
                  <Badge
                    key={`${file}-${idx}`}
                    variant="secondary"
                    className="h-5 shrink-0 px-2 py-0 text-[10px]"
                  >
                    {toMailDisplayText(file, '첨부파일')}
                  </Badge>
                ))}
              </div>
            )}
''',
    )
    replace_once(
        path,
        '''          {email.schedule_conflict && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-50 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-emerald-800">회의 제안 확인</h3>
                  <p className="text-xs text-emerald-600/80 mt-1">이메일에 포함된 회의 일정을 캘린더와 조율합니다.</p>
                </div>
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl h-8 px-3 text-xs">일정 조율</Button>
              </div>
            </div>
          )}
''',
        '''          {email.schedule_conflict && (
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
          )}
''',
    )
    replace_once(
        path,
        '''                {syncStatus && (
                  <span className={`self-center text-xs ${syncStatus.type === 'success' ? 'text-green-600' : 'text-red-500'}`}>
                    {syncStatus.message}
                  </span>
                )}
''',
        '''                {syncStatus && (
                  <span
                    role="status"
                    aria-live="polite"
                    className={`self-center text-xs ${syncStatus.type === 'success' ? 'text-green-600' : 'text-red-500'}`}
                  >
                    {syncStatus.message}
                  </span>
                )}
''',
    )


def repair_test() -> None:
    """Replace the presentation-only test with a real responsive action flow."""
    replace_once(
        "frontend/src/components/EmailDetail.test.tsx",
        '''  it("renders desktop high-density variants (participant list, attachment rail) and meeting proposal panel", async () => {
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
    const fetchMock = vi.fn((input) => {
      const url = String(input);
      if (url.endsWith("/api/emails/30")) return Promise.resolve(jsonResponse(email));
      if (url.endsWith("/api/llm/summarize")) {
        return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [] }));
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
    expect(container.textContent).toContain("참여자");
    expect(container.textContent).toContain("첨부파일");
    expect(container.textContent).toContain("proposal.pdf");
    expect(container.textContent).toContain("회의 제안 확인");
    expect(container.querySelector(".hidden.md\\\\:flex")).not.toBeNull();
  });
''',
        '''  it("renders responsive participant and attachment evidence and executes the meeting action", async () => {
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
  });
''',
    )


def update_changelog() -> None:
    """Record the buyer-visible interaction and scope cleanup."""
    target = REPO_ROOT / "CHANGELOG.md"
    text = target.read_text(encoding="utf-8")
    section = '''### EmailDetail 반응형 실행 표면

- 참여자와 첨부파일 증거를 모바일·데스크톱에서 동일하게 확인할 수 있도록 반응형 스크롤 레일과 명시적 접근성 이름을 추가했습니다.
- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 연결하고 loading·disabled·live-status 상태를 검증합니다.
- UI PR에 섞인 thread ID, SMTP allowlist, `.msg` import, tenant scope backend 변경은 정확한 `develop` 기준으로 제거했습니다.

'''
    if section in text:
        return
    marker = "## [Unreleased]"
    marker_index = text.find(marker)
    if marker_index < 0 or text[:marker_index].strip("\ufeff\r\n \t"):
        raise SystemExit("CHANGELOG.md: Unreleased must be the first heading")
    heading_end = text.find("\n", marker_index)
    if heading_end < 0:
        raise SystemExit("CHANGELOG.md: Unreleased heading has no line terminator")
    target.write_text(
        text[: heading_end + 1] + section + text[heading_end + 1 :],
        encoding="utf-8",
    )


def write_doctoring() -> None:
    """Document the accessibility and functional-action boundary in APA 7th form."""
    target = REPO_ROOT / "docs/doctoring/email-detail-responsive-action-surface.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '''# EmailDetail responsive action surface doctoring

## Decision

The email detail view exposes participants and attachment names at every viewport
size. Attachments use a horizontally scrollable, explicitly named region so a
small viewport does not silently remove source evidence. The meeting-conflict
panel reuses the existing calendar writeback-intent handler rather than rendering
an inert call-to-action. Loading, disabled, and polite live-status states remain
in the same product surface.

Unrelated backend changes are excluded from this UI slice. Thread identifier,
SMTP destination, import-format, and tenant-scope policy changes require their
own security rationale and regression contracts rather than hitchhiking on a
presentation PR.

## Accessibility boundary

The implementation preserves native button semantics and the repository's
keyboard-visible focus system, gives the attachment evidence region an
accessible name, and exposes asynchronous status through `role=status` and
`aria-live=polite`. WCAG 2.2 is used as the current normative target. The focused
regression proves discoverability and activation in the DOM, but this record does
not claim full WCAG conformance without contrast, zoom, assistive-technology, and
manual usability evidence.

## Verification contract

- The participant list renders without an unsafe type assertion.
- The attachment rail is present and not hidden on small viewports.
- The meeting action is disabled when no extracted action item exists.
- Activating the meeting action sends the exact writeback-intent request.
- Successful writeback intent produces a polite live status.
- The three unrelated backend files are byte-identical to the exact PR base.
- Frontend focused tests, full tests, lint, type checking, coverage collection,
  and production build run before the verified commit is published.

## References

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (n.d.). *Understanding success criterion 2.4.7:
Focus visible*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

World Wide Web Consortium. (n.d.). *Understanding success criterion 4.1.3:
Status messages*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
''',
        encoding="utf-8",
    )


def main() -> None:
    """Apply all bounded frontend, test, changelog, and doctoring repairs."""
    repair_component()
    repair_test()
    update_changelog()
    write_doctoring()


if __name__ == "__main__":
    main()
