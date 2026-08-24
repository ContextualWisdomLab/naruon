import { describe, expect, it } from "vitest";
import {
  calendarWritebackBlockedSummaries,
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

  it("classifies the real runner conflict shape (provider_conflict / status conflict)", () => {
    // backend/runner/local_dav_adapters.py returns exactly this shape for
    // provider 409/412 responses; keep coverage on the production contract,
    // not only on forward-compatible placeholder codes.
    expect(
      calendarWritebackConflictState([
        {
          requires_if_match: true,
          if_match: "etag-friday-1500-standup",
          provider_status: 412,
          error_code: "provider_conflict",
          status: "conflict",
        },
        {
          requires_if_match: false,
          if_match: null,
          provider_status: 409,
          error_code: "provider_conflict",
          status: "conflict",
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

  it("does not treat a non-conflict status substring as a hard conflict", () => {
    expect(
      calendarWritebackConflictState([
        {
          requires_if_match: true,
          if_match: "etag-room-a-1500",
          status: "no_conflict",
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

describe("calendarWritebackBlockedSummaries", () => {
  it("keeps only action items whose paired intent is a hard conflict", () => {
    expect(
      calendarWritebackBlockedSummaries(
        [
          { status: "intent_ready" },
          {
            provider_status: 412,
            error_code: "etag_conflict",
            status: "if_match_conflict",
          },
        ],
        ["새 일정 만들기", "금요일 15:00 스탠드업 반영"],
      ),
    ).toEqual(["금요일 15:00 스탠드업 반영"]);
  });
});

describe("calendarWritebackConflictMessage", () => {
  it("tells the user a confirmed commitment was preserved", () => {
    expect(calendarWritebackConflictMessage("conflict", 2)).toContain("덮어쓰지");
  });

  it("names the blocked Friday 15:00 intent without inventing a clock time", () => {
    expect(
      calendarWritebackConflictMessage("conflict", 1, ["금요일 15:00 스탠드업 반영"]),
    ).toBe("기존 확정 일정과 충돌이 있어 ‘금요일 15:00 스탠드업 반영’을 덮어쓰지 않았습니다.");
  });

  it("keeps the no-conflict copy used by mail-detail calendar sync", () => {
    expect(calendarWritebackConflictMessage("none", 1)).toBe(
      "1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.",
    );
  });
});
