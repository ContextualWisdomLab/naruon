#!/usr/bin/env python3
"""Correct the bounded PR 1245 transformer after exact CI evidence."""

from pathlib import Path

path = Path(__file__).with_name("repair_pr1245_review.py")
text = path.read_text(encoding="utf-8")


def replace_exact(old: str, new: str, label: str) -> None:
    """Replace one audited transformer fragment or fail closed."""
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    text = text.replace(old, new, 1)


replace_exact(
    '    start = text.index("          {email.schedule_conflict && (")\n',
    '''    start = text.index(
        '          {email.schedule_conflict && (\\n'
        '            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-sm">'
    )
''',
    "main conflict panel",
)

replace_exact(
    '''  it("reports a selected-source conflict and requires confirmation again", async () => {''',
    '''  it("reports a server source mismatch and requires confirmation again", async () => {''',
    "source mismatch test title",
)
replace_exact(
    '''      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ detail: "conflict" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }));
      }
''',
    '''      if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({
          target_source_id: "different_source",
          protocol: "caldav",
          provider_write_executed: false,
          provenance: { source_provider: "Unexpected source" },
        }));
      }
''',
    "source mismatch response",
)

write_anchor = '    TESTS.write_text(text[:start] + replacement + text[end:], encoding="utf-8")\n'
write_replacement = '''    TESTS.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    replace_once(
        TESTS,
        '  it("waits for context synthesis action items before requesting a server-authoritative calendar writeback intent", async () => {',
        '  it("waits for action items and explicit source confirmation before calendar writeback", async () => {',
    )
    replace_once(
        TESTS,
        '''      if (url.endsWith("/api/llm/summarize")) return summaryResponse.promise;
      if (url.endsWith("/api/calendar/writeback-intent")) {
''',
        '''      if (url.endsWith("/api/llm/summarize")) return summaryResponse.promise;
      if (url.endsWith("/api/calendar/writeback-sources")) {
        return Promise.resolve(jsonResponse([{
          source_id: "caldav-primary",
          provider: "Customer CalDAV",
          protocol: "caldav",
          owner_id: "default",
          organization_id: "default",
          capabilities: ["read", "write", "etag"],
          writeback_enabled: true,
          etag: '"v1"',
        }]));
      }
      if (url.endsWith("/api/calendar/writeback-intent")) {
''',
    )
    replace_once(
        TESTS,
        '        expect(JSON.parse(String(init?.body))).toEqual({ action: "create", summary: "출시 회의 일정 잡기" });\n',
        '''        expect(JSON.parse(String(init?.body))).toEqual({
          action: "create",
          summary: "출시 회의 일정 잡기",
          target_source_id: "caldav-primary",
        });
''',
    )
    replace_once(
        TESTS,
        '''    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/sync"))).toHaveLength(0);
    expect(container.textContent).toContain("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.");
    expect(container.textContent).not.toContain("Customer CalDAV");
    expect(container.textContent).not.toContain("caldav-primary");
''',
        '''    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(0);
    const sourceSelect = container.querySelector<HTMLSelectElement>('#email-detail-calendar-source');
    await act(async () => {
      if (sourceSelect) {
        sourceSelect.value = "caldav-primary";
        sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    const syncButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => button.textContent?.trim() === "일정 반영",
    );
    await act(async () => {
      syncButton?.click();
      await flushAsyncWork();
    });

    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/sync"))).toHaveLength(0);
    expect(container.textContent).toContain("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다. (Customer CalDAV)");
    expect(container.textContent).not.toContain("caldav-primary");
''',
    )
'''
replace_exact(write_anchor, write_replacement, "existing command regression update")
path.write_text(text, encoding="utf-8")
