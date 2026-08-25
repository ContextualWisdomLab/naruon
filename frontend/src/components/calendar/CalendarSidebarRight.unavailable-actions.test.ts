import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const sidebarSource = readFileSync(
  new URL("./CalendarSidebarRight.tsx", import.meta.url),
  "utf8",
);

describe("CalendarSidebarRight unavailable-action contract", () => {
  it("keeps the unavailable location action itself discoverable", () => {
    expect(sidebarSource).toContain('aria-disabled={ !selectedDetailEvent?.location }');
    expect(sidebarSource).toContain(
      'aria-describedby={!selectedDetailEvent?.location ? "calendar-location-unavailable" : undefined}',
    );
    expect(sidebarSource).toContain(
      'id="calendar-location-unavailable" className="text-right text-xs leading-4 text-muted-foreground"',
    );
    expect(sidebarSource).toContain(
      "일정에 위치를 추가하면 위치를 열 수 있습니다.",
    );
    expect(sidebarSource).not.toContain("disabled={!selectedDetailEvent?.location}");
    expect(sidebarSource).not.toContain(
      "tabIndex={!selectedDetailEvent?.location ? 0 : -1}",
    );
    expect(sidebarSource).not.toContain(
      "tabIndex={locationUnavailable ? 0 : -1}",
    );
    expect(sidebarSource).not.toContain(
      'id="calendar-location-unavailable" className="text-right text-xs leading-4 text-muted-foreground sr-only"',
    );
  });

  it("describes selection-dependent actions with one visible next action", () => {
    expect(sidebarSource).toContain(
      'id="calendar-selection-required" className="mb-2 text-xs leading-4 text-muted-foreground"',
    );
    expect(sidebarSource).toContain(
      "왼쪽 캘린더에서 일정을 선택하면 삭제·복사·수정할 수 있습니다.",
    );
    expect(
      sidebarSource.match(/aria-disabled=\{ !selectedDetailEvent \}/g) ?? [],
    ).toHaveLength(3);
    expect(
      sidebarSource.match(
        /aria-describedby=\{!selectedDetailEvent \? "calendar-selection-required" : undefined\}/g,
      ) ?? [],
    ).toHaveLength(3);
    expect(sidebarSource).not.toContain("disabled={!selectedDetailEvent}");
    expect(sidebarSource).not.toContain(
      "tabIndex={!selectedDetailEvent ? 0 : -1}",
    );
    expect(sidebarSource).not.toContain(
      "tabIndex={selectionRequired ? 0 : -1}",
    );
    expect(sidebarSource).not.toContain(
      'id="calendar-selection-required" className="mb-2 text-xs leading-4 text-muted-foreground sr-only"',
    );
  });
});
