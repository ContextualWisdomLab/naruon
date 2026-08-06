"""Apply the reviewed EmailDetail calendar-source repair and self-remove.

This branch-only helper converts the exact RED contract into the smallest
product change, updates durable evidence, removes its temporary workflow and
itself, and leaves publication to the exact-head GitHub Actions caller after
focused and complete frontend verification succeeds.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


EMAIL_DETAIL_PATH = Path("frontend/src/components/EmailDetail.tsx")
EMAIL_DETAIL_TEST_PATH = Path("frontend/src/components/EmailDetail.test.tsx")
DOCTORING_PATH = Path("docs/doctoring/email-detail-responsive-action-surface.md")
CHANGELOG_PATH = Path("CHANGELOG.md")
TEMPORARY_PATHS = (
    Path(".github/workflows/repair-pr1245-calendar-source.yml"),
    Path("scripts/ci/apply_pr1245_calendar_source_repair.py"),
)


def _replace_exact(source: str, old: str, new: str, *, label: str) -> str:
    """Replace one exact source fragment or fail closed on branch drift."""
    if source.count(old) != 1:
        raise RuntimeError(f"expected exactly one {label} fragment")
    return source.replace(old, new, 1)


def _repair_email_detail() -> None:
    """Require a confirmed server-authorized calendar source before writeback."""
    source = EMAIL_DETAIL_PATH.read_text(encoding="utf-8")

    import_anchor = dedent(
        '''
        import {
          bucketTextLength,
          createProductEventId,
          recordProductEvent,
        } from "@/lib/product-events";
        '''
    )
    import_replacement = import_anchor + dedent(
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
    source = _replace_exact(
        source,
        import_anchor,
        import_replacement,
        label="calendar contract imports",
    )

    local_response_type = dedent(
        '''
        interface CalendarWritebackIntentResponse {
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

        '''
    )
    source = _replace_exact(
        source,
        local_response_type,
        "",
        label="duplicate calendar response type",
    )

    normalization_anchor = dedent(
        '''
        function normalizeLlmData(payload: unknown): LlmData {
        '''
    )
    source_label_helper = dedent(
        '''
        function getCalendarWritebackSourceLabel(source: CalendarWritebackSource): string {
          const provider = source.provider.trim();
          return `${provider || source.protocol.toUpperCase()} 원본`;
        }

        function normalizeLlmData(payload: unknown): LlmData {
        '''
    )
    source = _replace_exact(
        source,
        normalization_anchor,
        source_label_helper,
        label="calendar source label helper",
    )

    state_anchor = dedent(
        '''
          const [isSyncing, setIsSyncing] = useState(false);
          const [isCreatingTask, setIsCreatingTask] = useState(false);
          const [syncStatus, setSyncStatus] = useState<{type: 'success' | 'error', message: string} | null>(null);
        '''
    )
    state_replacement = dedent(
        '''
          const [isSyncing, setIsSyncing] = useState(false);
          const [isCreatingTask, setIsCreatingTask] = useState(false);
          const [syncStatus, setSyncStatus] = useState<{type: 'success' | 'error', message: string} | null>(null);
          const [writebackSources, setWritebackSources] = useState<CalendarWritebackSource[]>([]);
          const [selectedWritebackSourceId, setSelectedWritebackSourceId] = useState('');
          const [sourceLoadStatus, setSourceLoadStatus] = useState<'loading' | 'ready' | 'error'>('loading');
        '''
    )
    source = _replace_exact(
        source,
        state_anchor,
        state_replacement,
        label="calendar source state",
    )

    action_reset_effect = dedent(
        '''
          useEffect(() => {
            handledActionCommandIdRef.current = null;
          }, [emailId]);

        '''
    )
    source_registry_effect = action_reset_effect + dedent(
        '''
          useEffect(() => {
            let isMounted = true;
            setWritebackSources([]);
            setSelectedWritebackSourceId('');
            setSourceLoadStatus(emailId === null ? 'ready' : 'loading');
            if (emailId === null) {
              return () => {
                isMounted = false;
              };
            }

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
          }, [emailId]);

        '''
    )
    source = _replace_exact(
        source,
        action_reset_effect,
        source_registry_effect,
        label="calendar source registry effect",
    )

    reset_anchor = dedent(
        '''
              setIsSyncing(false);
              setIsCreatingTask(false);
              setSyncStatus(null);
              setTaskStatus(null);
        '''
    )
    reset_replacement = dedent(
        '''
              setIsSyncing(false);
              setIsCreatingTask(false);
              setSyncStatus(null);
              setWritebackSources([]);
              setSelectedWritebackSourceId('');
              setSourceLoadStatus('loading');
              setTaskStatus(null);
        '''
    )
    source = _replace_exact(
        source,
        reset_anchor,
        reset_replacement,
        label="calendar source reset",
    )

    old_sync_handler = dedent(
        '''
          const handleSyncCalendar = useCallback(async () => {
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
    )
    new_sync_handler = dedent(
        '''
          const handleSyncCalendar = useCallback(async () => {
            const actionEmailId = emailId;
            const isCurrentEmail = () => currentEmailIdRef.current === actionEmailId;
            const actionItems = llmData?.action_items ?? [];
            const selectedSource = writebackSources.find(
              (source) => source.source_id === selectedWritebackSourceId
                && isCustomerOwnedWritableSource(source),
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
              } else if (successfulIntents.length === settledIntents.length) {
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
        '''
    )
    source = _replace_exact(
        source,
        old_sync_handler,
        new_sync_handler,
        label="calendar writeback handler",
    )

    action_items_anchor = dedent(
        '''
          const confidencePercent = toConfidencePercent(llmData?.confidence);
          const actionItems = llmData?.action_items ?? [];

          const handleOpenSourceDrawer = () => {
        '''
    )
    action_items_replacement = dedent(
        '''
          const confidencePercent = toConfidencePercent(llmData?.confidence);
          const actionItems = llmData?.action_items ?? [];
          const selectedWritebackSource = writebackSources.find(
            (source) => source.source_id === selectedWritebackSourceId
              && isCustomerOwnedWritableSource(source),
          ) ?? null;
          const isCalendarWritebackDisabled = isSyncing
            || actionItems.length === 0
            || sourceLoadStatus !== 'ready'
            || selectedWritebackSource === null;
          const calendarSourceSelectId = `email-calendar-source-${email.id}`;
          const calendarSourceSelector = (
            <div className="min-w-0 rounded-xl border border-emerald-500/20 bg-background/80 p-3">
              <label htmlFor={calendarSourceSelectId} className="text-xs font-bold text-emerald-800 dark:text-emerald-200">
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
                {writebackSources.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {getCalendarWritebackSourceLabel(source)} · {source.protocol.toUpperCase()}
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

          const handleOpenSourceDrawer = () => {
        '''
    )
    source = _replace_exact(
        source,
        action_items_anchor,
        action_items_replacement,
        label="calendar source selector",
    )

    source = _replace_exact(
        source,
        '              <div\n                aria-label="첨부파일"\n',
        '              <div\n                role="region"\n                aria-label="첨부파일"\n',
        label="attachment named region",
    )

    conflict_panel = dedent(
        '''
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
        '''
    )
    conflict_panel_replacement = dedent(
        '''
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-emerald-800 dark:text-emerald-200">회의 제안 확인</h3>
                      <p className="mt-1 text-xs text-emerald-700/80 dark:text-emerald-300/80">이메일에 포함된 회의 일정을 캘린더와 조율합니다.</p>
                    </div>
                    <Button
                      size="sm"
                      onClick={handleSyncCalendar}
                      disabled={isCalendarWritebackDisabled}
                      aria-busy={isSyncing}
                      className="h-8 rounded-xl bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700"
                    >
                      {isSyncing && <Loader2 className="mr-2 h-3 w-3 animate-spin" aria-hidden="true" />}
                      {isSyncing ? "조율 중" : "일정 조율"}
                    </Button>
                  </div>
                  <div className="mt-3">{calendarSourceSelector}</div>
        '''
    )
    source = _replace_exact(
        source,
        conflict_panel,
        conflict_panel_replacement,
        label="meeting source confirmation panel",
    )

    footer_button_anchor = dedent(
        '''
                        <Button
                          size="sm"
                          onClick={handleSyncCalendar}
                          disabled={isSyncing}
                          aria-busy={isSyncing}
                          className="h-9 rounded-xl bg-emerald-600 px-4 text-white hover:bg-emerald-700"
        '''
    )
    footer_button_replacement = dedent(
        '''
                        <Button
                          size="sm"
                          onClick={handleSyncCalendar}
                          disabled={isCalendarWritebackDisabled}
                          aria-busy={isSyncing}
                          className="h-9 rounded-xl bg-emerald-600 px-4 text-white hover:bg-emerald-700"
        '''
    )
    source = _replace_exact(
        source,
        footer_button_anchor,
        footer_button_replacement,
        label="action-card calendar button",
    )

    action_list_end = dedent(
        '''
                    ) : null
                  ) : null}
                </DecisionPointCard>
        '''
    )
    action_list_end_replacement = dedent(
        '''
                    ) : null
                  ) : null}
                  {!email.schedule_conflict && actionItems.length > 0 ? calendarSourceSelector : null}
                </DecisionPointCard>
        '''
    )
    source = _replace_exact(
        source,
        action_list_end,
        action_list_end_replacement,
        label="non-conflict calendar source selector",
    )

    EMAIL_DETAIL_PATH.write_text(source, encoding="utf-8")


def _repair_existing_test() -> None:
    """Align the original responsive regression with explicit source selection."""
    source = EMAIL_DETAIL_TEST_PATH.read_text(encoding="utf-8")
    fetch_anchor = dedent(
        '''
              if (url.endsWith("/api/llm/summarize")) {
                return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [actionItem] }));
              }
              if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        '''
    )
    fetch_replacement = dedent(
        '''
              if (url.endsWith("/api/llm/summarize")) {
                return Promise.resolve(jsonResponse({ summary: "Summary", action_items: [actionItem] }));
              }
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
              if (url.endsWith("/api/calendar/writeback-intent") && init?.method === "POST") {
        '''
    )
    source = _replace_exact(
        source,
        fetch_anchor,
        fetch_replacement,
        label="responsive-test source registry",
    )
    source = _replace_exact(
        source,
        '    const attachmentRail = container.querySelector<HTMLElement>(\'[aria-label="첨부파일"]\');\n',
        '    const attachmentRail = container.querySelector<HTMLElement>(\'[role="region"][aria-label="첨부파일"]\');\n',
        label="responsive-test attachment region",
    )
    schedule_anchor = dedent(
        '''
            const scheduleButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
              (button) => button.textContent?.includes("일정 조율"),
            );
            expect(scheduleButton?.disabled).toBe(false);
        '''
    )
    schedule_replacement = dedent(
        '''
            const sourceSelect = container.querySelector<HTMLSelectElement>('select[aria-label="일정 원본 선택"]');
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
        '''
    )
    source = _replace_exact(
        source,
        schedule_anchor,
        schedule_replacement,
        label="responsive-test source selection",
    )
    source = _replace_exact(
        source,
        '        body: JSON.stringify({ action: "create", summary: actionItem }),\n',
        '        body: JSON.stringify({\n          action: "create",\n          summary: actionItem,\n          target_source_id: "caldav_source_primary",\n        }),\n',
        label="responsive-test opaque source body",
    )
    source = _replace_exact(
        source,
        '    expect(container.textContent).toContain("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.");\n',
        '    expect(container.textContent).toContain("1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.");\n',
        label="responsive-test source confirmation status",
    )
    EMAIL_DETAIL_TEST_PATH.write_text(source, encoding="utf-8")


def _update_durable_evidence() -> None:
    """Record the source-confirmation, conflict, and partial-failure boundary."""
    doctoring = DOCTORING_PATH.read_text(encoding="utf-8")
    old_decision = dedent(
        '''
        panel reuses the existing calendar writeback-intent handler rather than rendering
        an inert call-to-action. Loading, disabled, and polite live-status states remain
        in the same product surface.
        '''
    )
    new_decision = dedent(
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
    )
    doctoring = _replace_exact(
        doctoring,
        old_decision,
        new_decision,
        label="doctoring source-confirmation decision",
    )
    old_verification = dedent(
        '''
        - The meeting action is disabled when no extracted action item exists.
        - Activating the meeting action sends the exact writeback-intent request.
        - Successful writeback intent produces a polite live status.
        '''
    )
    new_verification = dedent(
        '''
        - The meeting action is disabled when no extracted action item exists, while the
          request is pending, or until one current server-authorized source is confirmed.
        - Activating the meeting action sends the exact opaque `target_source_id` with
          every writeback-intent request.
        - A `409` source conflict clears confirmation and requires explicit reselection.
        - Complete and partial batches produce distinct polite status evidence, and
          analytics never treat `target_source_id` as a provider event identifier.
        '''
    )
    doctoring = _replace_exact(
        doctoring,
        old_verification,
        new_verification,
        label="doctoring verification contract",
    )
    DOCTORING_PATH.write_text(doctoring, encoding="utf-8")

    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    old_bullet = (
        "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 "
        "연결하고 loading·disabled·live-status 상태를 검증합니다.\n"
    )
    new_bullet = (
        "- 일정 충돌 패널의 `일정 조율` 버튼을 기존 calendar writeback intent에 "
        "연결하고, 서명된 서버 목록에서 사용자가 명시적으로 선택한 opaque "
        "`target_source_id`만 전송하며, source conflict 재확인·부분 실패·loading·"
        "disabled·live-status 상태를 검증합니다.\n"
    )
    changelog = _replace_exact(
        changelog,
        old_bullet,
        new_bullet,
        label="changelog calendar source boundary",
    )
    CHANGELOG_PATH.write_text(changelog, encoding="utf-8")


def _remove_temporary_artifacts() -> None:
    """Remove this helper and its exact-head workflow before publication."""
    for path in TEMPORARY_PATHS:
        if path.exists():
            path.unlink()


def main() -> None:
    """Apply product, test, and durable evidence changes, then self-remove."""
    _repair_email_detail()
    _repair_existing_test()
    _update_durable_evidence()
    _remove_temporary_artifacts()


if __name__ == "__main__":
    main()
