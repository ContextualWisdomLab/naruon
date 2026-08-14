import { describe, expect, it } from "vitest";

import { calendarCoordinationProposals, calendarDisplayMonth } from "./constants";
import { formatCalendarDisplayMonth, formatCoordinationProposalLabel } from "./helpers";

describe("formatCoordinationProposalLabel", () => {
  it("derives weekday from the Seoul ISO instant, not a hardcoded 목/금 pair", () => {
    expect(
      formatCoordinationProposalLabel(
        "2026-05-23T14:00:00+09:00",
        "2026-05-23T15:00:00+09:00",
      ),
    ).toBe("5월 23일 (토) 14:00 - 15:00");
    expect(
      formatCoordinationProposalLabel(
        "2026-05-21T14:00:00+09:00",
        "2026-05-21T15:00:00+09:00",
      ),
    ).toBe("5월 21일 (목) 14:00 - 15:00");
  });

  it("keeps 회의 조율 proposals inside the calendar chrome month", () => {
    expect(formatCalendarDisplayMonth(calendarDisplayMonth)).toBe("2026년 5월");
    for (const proposal of calendarCoordinationProposals) {
      expect(proposal.startsAt.startsWith(`${calendarDisplayMonth}-`)).toBe(true);
      const label = formatCoordinationProposalLabel(proposal.startsAt, proposal.endsAt);
      expect(label).toMatch(/5월 \d+일 \([월화수목금토일]\) \d{2}:\d{2} - \d{2}:\d{2}/);
    }
    expect(
      formatCoordinationProposalLabel(
        calendarCoordinationProposals[0].startsAt,
        calendarCoordinationProposals[0].endsAt,
      ),
    ).toBe("5월 21일 (목) 14:00 - 15:00");
  });
});
