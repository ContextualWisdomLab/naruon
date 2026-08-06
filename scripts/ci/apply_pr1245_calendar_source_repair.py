"""Apply the reviewed EmailDetail calendar-source repair and self-remove.

The branch-only helper transforms the exact RED product contract into the
smallest durable frontend change. It fails closed when any source marker drifts,
updates authoritative evidence, removes every temporary repair artifact, and
leaves publication to the exact-head workflow only after the complete frontend
quality gate succeeds.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent, indent


EMAIL_DETAIL_PATH = Path("frontend/src/components/EmailDetail.tsx")
EMAIL_DETAIL_TEST_PATH = Path("frontend/src/components/EmailDetail.test.tsx")
DOCTORING_PATH = Path("docs/doctoring/email-detail-responsive-action-surface.md")
CHANGELOG_PATH = Path("CHANGELOG.md")
TEMPORARY_PATHS = (
    Path(".github/workflows/repair-pr1245-calendar-source.yml"),
    Path(".github/workflows/reopen-pr1245-calendar-source.yml"),
    Path("scripts/ci/apply_pr1245_calendar_source_repair.py"),
)


def _block(value: str, spaces: int = 0) -> str:
    """Return one normalized multiline source block with fixed indentation."""
    normalized = dedent(value).strip("\n") + "\n"
    return indent(normalized, " " * spaces)


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    """Replace one exact fragment or fail closed on branch-source drift."""
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label} fragment, observed {count}")
    return source.replace(old, new, 1)


def _replace_region(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    *,
    label: str,
) -> str:
    """Replace one bounded source region while retaining its end marker."""
    start_count = source.count(start_marker)
    if start_count != 1:
        raise RuntimeError(
            f"expected exactly one {label} start marker, observed {start_count}"
        )
    start_index = source.index(start_marker)
    end_index = source.find(end_marker, start_index + len(start_marker))
    if end_index < 0:
        raise RuntimeError(f"missing {label} end marker")
    if source.find(end_marker, end_index + len(end_marker)) >= 0:
        # The end marker may legitimately occur elsewhere before the selected region,
        # but a second occurrence after this start would make the transform ambiguous.
        raise RuntimeError(f"expected one {label} end marker after the start")
    return source[:start_index] + replacement + source[end_index:]


def _repair_email_detail() -> None:
    """Require one confirmed server-authorized source before calendar writeback."""
    source = EMAIL_DETAIL_PATH.read_text(encoding="utf-8")

    product_event_import = _block(
        '''
        import {
          bucketTextLength,
          createProductEventId,
          recordProductEvent,
        } from "@/lib/product-events";
        '''
    )
    calendar_imports = _block(
        '''
        import type {
          CalendarWritebackIntentResponse,
          CalendarWritebackSource,
        } from "@/components/calendar/types";
        import {
          getApiErrorStatus,
          isCustomerOwnedWritableSource,
        } from "@/components/calendar/helpers";
        '''
    )
    source = _replace_once(
        source,
        product_event_import,
        product_event_import + calendar_imports,
        label="calendar contract imports",
    )

    source = _replace_region(
        source,
        "interface CalendarWritebackIntentResponse {\n",
        "type EmailDetailActionCommand = {\n",
        "",
        label="duplicate calendar response type",
    )

    source = _replace_once(
        source,
        "function normalizeLlmData(payload: unknown): LlmData {\n",
        _block(
            '''
            function getCalendarWritebackSourceLabel(source: CalendarWritebackSource): string {
              const provider = source.provider.trim();
              return `${provider || source.protocol.toUpperCase()} 원본`;
            }

            function normalizeLlmData(payload: unknown): LlmData {
            '''
        ),
        label="calendar source label helper",
    )

    sync_state = (
        "  const [syncStatus, setSyncStatus] = useState<"
        "{type: 'success' | 'error', message: string} | null>(null);\n"
    )
    source = _replace_once(
        source,
        sync_state,
        sync_state
        + "  const [writebackSources, setWritebackSources] = "
        "useState<CalendarWritebackSource[]>([]);\n"
        + "  const [selectedWritebackSourceId, setSelectedWritebackSourceId] = "
        "useState('');\n"
        + "  const [sourceLoadStatus, setSourceLoadStatus] = "
        "useState<'idle' | 'loading' | 'ready' | 'error'>('idle');\n",
        label="calendar source state",
    )

    action_reset_effect = _block(
        '''
        useEffect(() => {
          handledActionCommandIdRef.current = null;
        }, [emailId]);
        ''',
        spaces=2,
    )
    source_registry_effect = _block(
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
        ''',
        spaces=2,
    )
    source = _replace_once(
        source,
        action_reset_effect,
        action_reset_effect + "\n" + source_registry_effect,
        label="calendar source registry effect",
    )

    reset_state = _block(
        '''
        setIsSyncing(false);
        setIsCreatingTask(false);
        setSyncStatus(null);
        setTaskStatus(null);
        ''',
        spaces=6,
    )
    source = _replace_once(
        source,
        reset_state,
        _block(
            '''
            setIsSyncing(false);
            setIsCreatingTask(false);
            setSyncStatus(null);
            setWritebackSources([]);
            setSelectedWritebackSourceId('');
            setSourceLoadStatus('idle');
            setTaskStatus(null);
            ''',
            spaces=6,
        ),
        label="calendar source reset",
    )

    new_sync_handler = _block(
        '''
        const handleSyncCalendar = useCallback(async () => {
          const actionEmailId = emailId;
          const isCurrentEmail = () => currentEmailIdRef.current === actionEmailId;
          const actionItems = llmData?.action_items ?? [];
          const selectedSource = writebackSources.find(
            (candidate) => candidate.source_id === selectedWritebackSourceId
              && isCustomerOwnedWritableSource(candidate),
          ) ?? null;

          if (!actionItems.length) {
            setSyncStatus({ type: 'error', message: '캘린더에 반영할 실행 항목이 없습니다.' });
            return;
          }
          if (sourceLoadStatus !== 'ready' || selectedSource === null) {
            setSyncStatus({ type: 'error', message: '일정 원본을 먼저 선택해 주세요.' });
            return;
          }

          setIsSyncing(true);
          setSyncStatus(null);
          const startedAt = nowMs();
          const settledIntents = await Promise.allSettled(
            actionItems.map((summary) =>
              apiClient.post<CalendarWritebackIntentResponse>('/api/calendar/writeback-intent', {
                action: 'create',
                summary,
                target_source_id: selectedSource.source_id,
              }),
            ),
          );

          try {
            if (!isCurrentEmail()) return;
            const successfulIntents = settledIntents.flatMap((result) => {
              if (result.status !== 'fulfilled') return [];
              return result.value.target_source_id === selectedSource.source_id
                ? [result.value]
                : [];
            });
            const failedCount = settledIntents.length - successfulIntents.length;
            const conflictDetected = settledIntents.some(
              (result) => result.status === 'rejected' && getApiErrorStatus(result.reason) === 409,
            );

            if (conflictDetected) {
              setSelectedWritebackSourceId('');
              setSyncStatus({
                type: 'error',
                message: '원본 일정이 변경되었습니다. 일정 원본을 다시 선택해 주세요.',
              });
            } else if (failedCount === 0) {
              setSyncStatus({
                type: 'success',
                message: `${successfulIntents.length}개 일정 반영 의도를 ${getCalendarWritebackSourceLabel(selectedSource)}에 요청했습니다.`,
              });
            } else if (successfulIntents.length > 0) {
              setSyncStatus({
                type: 'error',
                message: `${successfulIntents.length}개 성공, ${failedCount}개 실패했습니다. 선택한 원본에는 성공한 의도만 기록했습니다.`,
              });
            } else {
              setSyncStatus({ type: 'error', message: '일정 반영 의도 요청에 실패했습니다.' });
            }

            recordProductEvent("calendar_reflected", {
              surface: "mail_detail",
              calendar_candidate_id: `mail-calendar:${actionEmailId ?? "unknown"}`,
              calendar_event_id: null,
              thread_id: email ? getThreadEventId(email) : null,
              conflict_state: conflictDetected ? "conflict" : failedCount > 0 ? "warning" : "none",
              provider_write_executed: successfulIntents.some(
                (intent) => Boolean(intent.provider_write_executed),
              ),
            });
            recordProductEvent("latency_guardrail_recorded", {
              surface: "mail_detail",
              request_trace_id: createProductEventId("calendar_trace"),
              operation: "calendar_reflection",
              duration_ms: Math.round(nowMs() - startedAt),
              status: failedCount === 0 ? "success" : "error",
            });
          } finally {
            if (isCurrentEmail()) setIsSyncing(false);
          }
        }, [
          email,
          emailId,
          llmData,
          selectedWritebackSourceId,
          sourceLoadStatus,
          writebackSources,
        ]);
        ''',
        spaces=2,
    )
    source = _replace_region(
        source,
        "  const handleSyncCalendar = useCallback(async () => {\n",
        "  const handleCreateTask = useCallback(async () => {\n",
        new_sync_handler + "\n",
        label="calendar writeback handler",
    )

    render_action_items = "  const actionItems = llmData?.action_items ?? [];\n"
    render_source_contract = _block(
        '''
        const selectedWritebackSource = writebackSources.find(
          (candidate) => candidate.source_id === selectedWritebackSourceId
            && isCustomerOwnedWritableSource(candidate),
        ) ?? null;
        const isCalendarWritebackDisabled = isSyncing
          || actionItems.length === 0
          || sourceLoadStatus !== 'ready'
          || selectedWritebackSource === null;
        const calendarSourceSelectId = `email-calendar-source-${email.id}`;
        const calendarSourceSelector = (
          <div className="min-w-0 rounded-xl border border-emerald-500/20 bg-background/80 p-3">
            <label
              htmlFor={calendarSourceSelectId}
              className="text-xs font-bold text-emerald-800 dark:text-emerald-200"
            >
              일정 원본
            </label>
            <select
              id={calendarSourceSelectId}
              aria-label="일정 원본 선택"
              value={selectedWritebackSourceId}
              onChange={(event) => {
                setSelectedWritebackSourceId(event.target.value);
                setSyncStatus(null);
              }}
              disabled={isSyncing || sourceLoadStatus !== 'ready' || writebackSources.length === 0}
              className="mt-2 h-9 w-full rounded-lg border border-emerald-500/30 bg-card px-3 text-xs font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="">일정 원본을 선택하세요</option>
              {writebackSources.map((sourceOption) => (
                <option key={sourceOption.source_id} value={sourceOption.source_id}>
                  {getCalendarWritebackSourceLabel(sourceOption)} · {sourceOption.protocol.toUpperCase()}
                </option>
              ))}
            </select>
            <p
              role={sourceLoadStatus === 'error' ? 'alert' : 'status'}
              aria-live="polite"
              className="mt-2 text-[11px] text-muted-foreground"
            >
              {sourceLoadStatus === 'loading'
                ? '서명 세션으로 일정 원본을 확인하는 중입니다.'
                : sourceLoadStatus === 'error'
                  ? '일정 원본을 확인할 수 없어 외부 반영을 차단했습니다.'
                  : writebackSources.length === 0
                    ? '반영 가능한 고객 원본 일정이 없습니다.'
                    : selectedWritebackSource
                      ? `${getCalendarWritebackSourceLabel(selectedWritebackSource)}을(를) 명시적으로 선택했습니다.`
                      : '반영 전에 고객 원본 일정을 명시적으로 선택해야 합니다.'}
            </p>
          </div>
        );
        ''',
        spaces=2,
    )
    source = _replace_once(
        source,
        render_action_items,
        render_action_items + render_source_contract,
        label="calendar source selector",
    )

    source = _replace_once(
        source,
        "              <div\n                aria-label=\"첨부파일\"\n",
        "              <div\n                role=\"region\"\n                aria-label=\"첨부파일\"\n",
        label="attachment named region",
    )
    source = _replace_once(
        source,
        "                  disabled={isSyncing || actionItems.length === 0}\n",
        "                  disabled={isCalendarWritebackDisabled}\n",
        label="meeting-action disabled boundary",
    )
    conflict_action_end = _block(
        '''
        {isSyncing ? "조율 중" : "일정 조율"}
        </Button>
        </div>
        </div>
        )}
        ''',
        spaces=18,
    )
    source = _replace_once(
        source,
        conflict_action_end,
        _block(
            '''
            {isSyncing ? "조율 중" : "일정 조율"}
            </Button>
            </div>
            <div className="mt-3">{calendarSourceSelector}</div>
            </div>
            )}
            ''',
            spaces=18,
        ),
        label="meeting source confirmation panel",
    )

    footer_button = _block(
        '''
        <Button
          size="sm"
          onClick={handleSyncCalendar}
          disabled={isSyncing}
          aria-busy={isSyncing}
          className="h-9 rounded-xl bg-emerald-600 px-4 text-white hover:bg-emerald-700"
        >
        ''',
        spaces=18,
    )
    source = _replace_once(
        source,
        footer_button,
        _block(
            '''
            <Button
              size="sm"
              onClick={handleSyncCalendar}
              disabled={isCalendarWritebackDisabled}
              aria-busy={isSyncing}
              className="h-9 rounded-xl bg-emerald-600 px-4 text-white hover:bg-emerald-700"
            >
            ''',
            spaces=18,
        ),
        label="action-card calendar button",
    )

    action_card_body = _block(
        '''
        >
          {llmData ? (
            actionItems.length > 0 ? (
        ''',
        spaces=10,
    )
    source = _replace_once(
        source,
        action_card_body,
        _block(
            '''
            >
              {!email.schedule_conflict && actionItems.length > 0 ? (
                <div className="mb-3">{calendarSourceSelector}</div>
              ) : null}
              {llmData ? (
                actionItems.length > 0 ? (
            ''',
            spaces=10,
        ),
        label="non-conflict source confirmation panel",
    )

    EMAIL_DETAIL_PATH.write_text(source, encoding="utf-8")


def _repair_existing_test() -> None:
    """Align the existing responsive test with explicit source confirmation."""
    source = EMAIL_DETAIL_TEST_PATH.read_text(encoding="utf-8")
    summary_response = _block(
        '''
        if (url.endsWith("/api/llm/summarize")) {
          return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [actionItem] }));
        }
        ''',
        spaces=6,
    )
    registry_response = _block(
        '''
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
        ''',
        spaces=6,
    )
    source = _replace_once(
        source,
        summary_response,
        summary_response + registry_response,
        label="responsive-test source registry",
    )
    source = _replace_once(
        source,
        "    const attachmentRail = container.querySelector<HTMLElement>("
        "'[aria-label=\"첨부파일\"]');\n",
        "    const attachmentRail = container.querySelector<HTMLElement>("
        "'[role=\"region\"][aria-label=\"첨부파일\"]');\n",
        label="responsive-test attachment region",
    )
    schedule_button = _block(
        '''
        const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
          (button) => button.textContent?.includes("일정 조율"),
        );
        expect(scheduleButton?.disabled).toBe(false);
        ''',
        spaces=4,
    )
    source = _replace_once(
        source,
        schedule_button,
        _block(
            '''
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
              (button) => button.textContent?.includes("일정 조율"),
            );
            expect(scheduleButton?.disabled).toBe(false);
            ''',
            spaces=4,
        ),
        label="responsive-test source selection",
    )
    source = _replace_once(
        source,
        "        body: JSON.stringify({ action: \"create\", summary: actionItem }),\n",
        _block(
            '''
            body: JSON.stringify({
              action: "create",
              summary: actionItem,
              target_source_id: "caldav_source_primary",
            }),
            ''',
            spaces=8,
        ),
        label="responsive-test opaque source body",
    )
    source = _replace_once(
        source,
        "    expect(container.textContent).toContain("
        "\"1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.\");\n",
        "    expect(container.textContent).toContain("
        "\"1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.\");\n",
        label="responsive-test source confirmation status",
    )
    EMAIL_DETAIL_TEST_PATH.write_text(source, encoding="utf-8")


def _update_durable_evidence() -> None:
    """Record source confirmation, conflict, and partial-failure semantics."""
    doctoring = DOCTORING_PATH.read_text(encoding="utf-8")
    doctoring = _replace_once(
        doctoring,
        _block(
            '''
            panel reuses the existing calendar writeback-intent handler rather than rendering
            an inert call-to-action. Loading, disabled, and polite live-status states remain
            in the same product surface.
            '''
        ),
        _block(
            '''
            panel reuses the existing calendar writeback-intent handler rather than rendering
            an inert call-to-action. The user must select an opaque source returned by the
            signed server registry before the action is enabled; every intent carries that
            exact `target_source_id`, and a source conflict clears the selection so the user
            must confirm the current source again. Mixed batch outcomes preserve successful
            intents, report the failed count, and never relabel a source identifier as a
            provider calendar-event identifier. Loading, disabled, and polite live-status
            states remain in the same product surface.
            '''
        ),
        label="doctoring source-confirmation decision",
    )
    doctoring = _replace_once(
        doctoring,
        _block(
            '''
            - The meeting action is disabled when no extracted action item exists.
            - Activating the meeting action sends the exact writeback-intent request.
            - Successful writeback intent produces a polite live status.
            '''
        ),
        _block(
            '''
            - The meeting action is disabled when no extracted action item exists, while the
              request is pending, or until one current server-authorized source is confirmed.
            - Activating the meeting action sends the exact opaque `target_source_id` with
              every writeback-intent request.
            - A `409` source conflict clears confirmation and requires explicit reselection.
            - Complete and partial batches produce distinct polite status evidence, and
              analytics never treat `target_source_id` as a provider event identifier.
            '''
        ),
        label="doctoring verification contract",
    )
    DOCTORING_PATH.write_text(doctoring, encoding="utf-8")

    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    changelog = _replace_once(
        changelog,
        "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 "
        "연결하고 loading·disabled·live-status 상태를 검증합니다.\n",
        "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 "
        "연결하고, 서명된 서버 목록에서 사용자가 명시적으로 선택한 opaque "
        "`target_source_id`만 전송하며, source conflict 재확인·부분 실패·loading·"
        "disabled·live-status 상태를 검증합니다.\n",
        label="changelog calendar source boundary",
    )
    CHANGELOG_PATH.write_text(changelog, encoding="utf-8")


def _remove_temporary_artifacts() -> None:
    """Remove every branch-only repair file before publication."""
    for path in TEMPORARY_PATHS:
        if path.exists():
            path.unlink()


def main() -> None:
    """Apply durable changes and remove all temporary repair machinery."""
    _repair_email_detail()
    _repair_existing_test()
    _update_durable_evidence()
    _remove_temporary_artifacts()


if __name__ == "__main__":
    main()
