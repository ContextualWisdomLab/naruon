import { describe, expect, it } from "vitest";
import {
  calendarWritebackConflictMessage,
  calendarWritebackConflictState,
} from "./calendar-writeback-conflict";

describe("calendarWritebackConflictState", () => {
  it("keeps a Friday 15:00 confirmed booking when a later intent reports 412", () => {
    expect(
      calendarWritebackConflictState([
        { requires_if_match: false, if_match: null, status: "intent_ready" },
        {
          requires_if_match: true,
          if_match: "etag-friday-1500-standup",
          provider_status: 412,
          error_code: "etag_conflict",
          status: "if_match_conflict",
        },
      ]),
    ).toBe("conflict");
  });

  it("warns when an existing event needs If-Match but has not failed yet", () => {
    expect(
      calendarWritebackConflictState([
        {
          requires_if_match: true,
          if_match: "etag-room-a-1500",
          status: "intent_ready",
        },
      ]),
    ).toBe("warning");
  });

  it("returns none when every intent is a new slot with no precondition", () => {
    expect(
      calendarWritebackConflictState([
        { requires_if_match: false, if_match: null, status: "intent_ready" },
      ]),
    ).toBe("none");
  });
});

describe("calendarWritebackConflictMessage", () => {
  it("tells the user a confirmed commitment was preserved", () => {
    expect(calendarWritebackConflictMessage("conflict", 2)).toContain("덮어쓰지");
  });

  it("keeps the no-conflict copy used by mail-detail calendar sync", () => {
    expect(calendarWritebackConflictMessage("none", 1)).toBe(
      "1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.",
    );
  });
});
