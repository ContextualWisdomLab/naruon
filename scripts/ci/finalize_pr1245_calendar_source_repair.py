"""Finalize the reviewed PR 1245 repair helper before executing it.

This one-shot bridge corrects exact, previously reviewed source anchors in the
branch-local repair module, runs that module, applies durable interaction and
source-lifecycle contracts, and is removed before the verified product commit is
published.
"""

from __future__ import annotations

import runpy
from pathlib import Path
from textwrap import dedent


REPAIR_SCRIPT = Path("scripts/ci/apply_pr1245_calendar_source_repair.py")
EMAIL_DETAIL = Path("frontend/src/components/EmailDetail.tsx")
EMAIL_DETAIL_TEST = Path("frontend/src/components/EmailDetail.test.tsx")


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    """Replace one exact source fragment or fail closed on branch drift."""
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label} fragment, observed {count}")
    return source.replace(old, new, 1)


def _repair_source_registry_lifecycle() -> None:
    """Key source state to the active email without synchronous effect resets."""
    source = EMAIL_DETAIL.read_text(encoding="utf-8")
    old_state = dedent(
        '''
          const [writebackSources, setWritebackSources] = useState<CalendarWritebackSource[]>([]);
          const [selectedWritebackSourceId, setSelectedWritebackSourceId] = useState('');
          const [sourceLoadStatus, setSourceLoadStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
        '''
    )
    new_state = dedent(
        '''
          type CalendarSourceLoadStatus = 'idle' | 'loading' | 'ready' | 'error';
          type CalendarSourceState = {
            contextKey: string;
            sources: CalendarWritebackSource[];
            selectedSourceId: string;
            status: CalendarSourceLoadStatus;
          };
          const actionItemCount = llmData?.action_items.length ?? 0;
          const sourceContextIsActionable = email?.id === emailId && actionItemCount > 0;
          const sourceContextKey = `${emailId ?? 'none'}:${email?.id ?? 'none'}:${sourceContextIsActionable ? 'actionable' : 'idle'}`;
          const [loadedCalendarSourceState, setLoadedCalendarSourceState] = useState<CalendarSourceState>(() => ({
            contextKey: sourceContextKey,
            sources: [],
            selectedSourceId: '',
            status: sourceContextIsActionable ? 'loading' : 'idle',
          }));
          const calendarSourceState: CalendarSourceState = loadedCalendarSourceState.contextKey === sourceContextKey
            ? loadedCalendarSourceState
            : {
                contextKey: sourceContextKey,
                sources: [],
                selectedSourceId: '',
                status: sourceContextIsActionable ? 'loading' : 'idle',
              };
          const writebackSources = calendarSourceState.sources;
          const selectedWritebackSourceId = calendarSourceState.selectedSourceId;
          const sourceLoadStatus = calendarSourceState.status;
          const setSelectedWritebackSourceId = useCallback((selectedSourceId: string) => {
            setLoadedCalendarSourceState((current) => {
              const activeState = current.contextKey === sourceContextKey
                ? current
                : {
                    contextKey: sourceContextKey,
                    sources: [],
                    selectedSourceId: '',
                    status: sourceContextIsActionable ? 'loading' as const : 'idle' as const,
                  };
              return { ...activeState, selectedSourceId };
            });
          }, [sourceContextIsActionable, sourceContextKey]);
        '''
    )
    source = _replace_once(
        source,
        old_state,
        new_state,
        label="calendar source keyed state",
    )

    old_effect = dedent(
        '''
          useEffect(() => {
            let isMounted = true;
            const actionItemCount = llmData?.action_items.length ?? 0;
            setWritebackSources([]);
            setSelectedWritebackSourceId('');

            if (emailId === null || actionItemCount === 0) {
              setSourceLoadStatus('idle');
              return () => {
                isMounted = false;
              };
            }

            setSourceLoadStatus('loading');
            void apiClient.get<CalendarWritebackSource[]>('/api/calendar/writeback-sources')
              .then((sources) => {
                if (!isMounted) return;
                if (!Array.isArray(sources)) {
                  throw new Error('Invalid calendar source registry response');
                }
                setWritebackSources(sources.filter(isCustomerOwnedWritableSource));
                setSelectedWritebackSourceId('');
                setSourceLoadStatus('ready');
              })
              .catch(() => {
                if (!isMounted) return;
                setWritebackSources([]);
                setSelectedWritebackSourceId('');
                setSourceLoadStatus('error');
              });

            return () => {
              isMounted = false;
            };
          }, [emailId, llmData]);
        '''
    )
    new_effect = dedent(
        '''
          useEffect(() => {
            if (!sourceContextIsActionable) return;

            let isMounted = true;
            const requestedContextKey = sourceContextKey;
            void apiClient.get<CalendarWritebackSource[]>('/api/calendar/writeback-sources')
              .then((sources) => {
                if (!isMounted) return;
                if (!Array.isArray(sources)) {
                  throw new Error('Invalid calendar source registry response');
                }
                setLoadedCalendarSourceState({
                  contextKey: requestedContextKey,
                  sources: sources.filter(isCustomerOwnedWritableSource),
                  selectedSourceId: '',
                  status: 'ready',
                });
              })
              .catch(() => {
                if (!isMounted) return;
                setLoadedCalendarSourceState({
                  contextKey: requestedContextKey,
                  sources: [],
                  selectedSourceId: '',
                  status: 'error',
                });
              });

            return () => {
              isMounted = false;
            };
          }, [sourceContextIsActionable, sourceContextKey]);
        '''
    )
    source = _replace_once(
        source,
        old_effect,
        new_effect,
        label="calendar source asynchronous effect",
    )

    old_reset = dedent(
        '''
              setIsSyncing(false);
              setIsCreatingTask(false);
              setSyncStatus(null);
              setWritebackSources([]);
              setSelectedWritebackSourceId('');
              setSourceLoadStatus('idle');
              setTaskStatus(null);
        '''
    )
    new_reset = dedent(
        '''
              setIsSyncing(false);
              setIsCreatingTask(false);
              setSyncStatus(null);
              setLoadedCalendarSourceState({
                contextKey: '',
                sources: [],
                selectedSourceId: '',
                status: 'idle',
              });
              setTaskStatus(null);
        '''
    )
    source = _replace_once(
        source,
        old_reset,
        new_reset,
        label="calendar source fetch reset",
    )
    EMAIL_DETAIL.write_text(source, encoding="utf-8")


def _repair_action_command_test() -> None:
    """Require an explicit source selection after a calendar shell command."""
    source = EMAIL_DETAIL_TEST.read_text(encoding="utf-8")
    start_marker = (
        '  it("waits for context synthesis action items before requesting a '
        'server-authoritative calendar writeback intent", async () => {\n'
    )
    end_marker = '  it("ignores a late draft response after the selected email changes", async () => {\n'
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise RuntimeError("action-command test region drifted")
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    replacement = dedent(
        '''
          it("waits for context synthesis and explicit source confirmation before requesting a server-authoritative calendar writeback intent", async () => {
            const email: TestEmail = {
              id: 9,
              message_id: "<calendar-command@example.com>",
              thread_id: null,
              sender: "calendar@example.com",
              recipients: "user@example.com",
              subject: "Calendar command",
              date: "2026-05-17T10:00:00Z",
              body: "Please sync the launch meeting.",
            };
            const summaryResponse = deferred<ReturnType<typeof jsonResponse>>();

            const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
              const url = String(input);
              if (url.endsWith("/api/emails/9")) return Promise.resolve(jsonResponse(email));
              if (url.endsWith("/api/llm/summarize")) return summaryResponse.promise;
              if (url.endsWith("/api/calendar/writeback-sources")) {
                return Promise.resolve(jsonResponse([{
                  source_id: "caldav_source_primary",
                  provider: "Fastmail",
                  protocol: "caldav",
                  owner_id: "owner_primary",
                  organization_id: null,
                  capabilities: ["read", "write", "etag"],
                  writeback_enabled: true,
                  etag: "etag-primary",
                }]));
              }
              if (url.endsWith("/api/calendar/writeback-intent")) {
                expect(init?.method).toBe("POST");
                expect(JSON.parse(String(init?.body))).toEqual({
                  action: "create",
                  summary: "출시 회의 일정 잡기",
                  target_source_id: "caldav_source_primary",
                });
                return Promise.resolve(jsonResponse({
                  workspace_id: "default",
                  target_source_id: "caldav_source_primary",
                  protocol: "caldav",
                  writeback_mode: "customer_owned",
                  requires_if_match: true,
                  if_match: "etag-primary",
                  provenance: {
                    created_by: "default",
                    source_provider: "Fastmail",
                    source_protocol: "caldav",
                  },
                  audit_event: "calendar.writeback_intent.created",
                  provider_write_executed: false,
                }));
              }
              throw new Error(`Unexpected fetch: ${url}`);
            });
            vi.stubGlobal("fetch", fetchMock);

            container = document.createElement("div");
            document.body.appendChild(container);
            root = createRoot(container);

            await act(async () => {
              root?.render(<EmailDetail emailId={9} actionCommand={{ id: 2, action: "calendar-sync" }} />);
            });
            await flushAsyncWork();

            expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(0);
            expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/sync"))).toHaveLength(0);

            await act(async () => {
              summaryResponse.resolve(jsonResponse({ summary: "회의 일정", action_items: ["출시 회의 일정 잡기"] }));
              await summaryResponse.promise;
            });
            await waitForCondition(() =>
              container?.querySelector('select[aria-label="일정 원본 선택"]') !== null,
            );

            expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(0);
            const sourceSelect = container.querySelector<HTMLSelectElement>(
              'select[aria-label="일정 원본 선택"]',
            );
            expect(sourceSelect).not.toBeNull();
            act(() => {
              if (!sourceSelect) return;
              sourceSelect.value = "caldav_source_primary";
              sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
            });

            const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
              (button) => button.textContent?.includes("일정 반영"),
            );
            expect(scheduleButton?.disabled).toBe(false);
            act(() => scheduleButton?.click());
            await flushAsyncWork();

            expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/writeback-intent"))).toHaveLength(1);
            expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/calendar/sync"))).toHaveLength(0);
            expect(container.textContent).toContain("1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.");
            expect(container.textContent).not.toContain("caldav_source_primary");
            expect(container.textContent).not.toContain("calendar.writeback_intent.created");
            expect(getRecordedProductEvents().some((event) =>
              event.name === "calendar_reflected" &&
              event.payload.calendar_candidate_id === "mail-calendar:9" &&
              event.payload.calendar_event_id === null &&
              event.payload.provider_write_executed === false,
            )).toBe(true);
          });

        '''
    )
    EMAIL_DETAIL_TEST.write_text(source[:start] + replacement + source[end:], encoding="utf-8")


def main() -> None:
    """Correct reviewed anchors and execute the self-removing repair module."""
    source = REPAIR_SCRIPT.read_text(encoding="utf-8")
    source = _replace_once(
        source,
        '    render_action_items = "  const actionItems = llmData?.action_items ?? [];\\n"\n',
        (
            '    render_action_items = (\n'
            '        "  const confidencePercent = toConfidencePercent(llmData?.confidence);\\n"\n'
            '        "  const actionItems = llmData?.action_items ?? [];\\n"\n'
            '    )\n'
        ),
        label="unique render source contract",
    )

    start_marker = "    conflict_action_end = _block(\n"
    end_marker = '        label="meeting source confirmation panel",\n    )\n'
    start_count = source.count(start_marker)
    end_count = source.count(end_marker)
    if start_count != 1 or end_count != 1:
        raise RuntimeError(
            "expected one meeting source panel repair region, "
            f"observed start={start_count}, end={end_count}"
        )
    start = source.index(start_marker)
    end = source.index(end_marker, start) + len(end_marker)
    replacement = (
        "    conflict_action_end = (\n"
        "        '                  {isSyncing ? \"조율 중\" : \"일정 조율\"}\\n'\n"
        "        '                </Button>\\n'\n"
        "        '              </div>\\n'\n"
        "        '            </div>\\n'\n"
        "        '          )}\\n'\n"
        "    )\n"
        "    source = _replace_once(\n"
        "        source,\n"
        "        conflict_action_end,\n"
        "        (\n"
        "            '                  {isSyncing ? \"조율 중\" : \"일정 조율\"}\\n'\n"
        "            '                </Button>\\n'\n"
        "            '              </div>\\n'\n"
        "            '              <div className=\"mt-3\">{calendarSourceSelector}</div>\\n'\n"
        "            '            </div>\\n'\n"
        "            '          )}\\n'\n"
        "        ),\n"
        "        label=\"meeting source confirmation panel\",\n"
        "    )\n"
    )
    source = source[:start] + replacement + source[end:]

    ambiguous_confirmation = (
        "    source = _replace_once(\n"
        "        source,\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.\\\");\\n\",\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.\\\");\\n\",\n"
        "        label=\"responsive-test source confirmation status\",\n"
        "    )\n"
    )
    deterministic_confirmation = (
        "    confirmation_before = (\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.\\\");\\n\"\n"
        "    )\n"
        "    confirmation_after = (\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.\\\");\\n\"\n"
        "    )\n"
        "    confirmation_count = source.count(confirmation_before)\n"
        "    if confirmation_count != 2:\n"
        "        raise RuntimeError(\n"
        "            \"expected exactly two responsive-test source confirmation \"\n"
        "            f\"status fragments, observed {confirmation_count}\"\n"
        "        )\n"
        "    source = source.replace(confirmation_before, confirmation_after)\n"
    )
    source = _replace_once(
        source,
        ambiguous_confirmation,
        deterministic_confirmation,
        label="responsive confirmation multiplicity repair",
    )

    REPAIR_SCRIPT.write_text(source, encoding="utf-8")
    runpy.run_path(str(REPAIR_SCRIPT), run_name="__main__")
    _repair_source_registry_lifecycle()
    _repair_action_command_test()


if __name__ == "__main__":
    main()
