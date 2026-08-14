import { calendarCoordinationProposals } from "./constants";
import { formatCoordinationProposalLabel } from "./helpers";

export function CalendarCoordinationView() {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">회의 조율</h3>
        <p className="text-sm text-muted-foreground mb-4">참석자들의 캘린더(CalDAV)를 종합 분석하여 최적의 시간을 제안합니다.</p>
        <div className="grid gap-3 max-w-lg">
          {calendarCoordinationProposals.map((proposal) => {
            const slotLabel = formatCoordinationProposalLabel(proposal.startsAt, proposal.endsAt);
            return (
              <button
                key={proposal.id}
                type="button"
                aria-label={`${proposal.rankLabel} 제안하기: ${slotLabel}, ${proposal.availability}`}
                className={`flex items-center justify-between rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                  proposal.emphasized
                    ? "border-primary/20 bg-primary/5 hover:bg-primary/10"
                    : "border-border bg-card hover:bg-secondary"
                }`}
              >
                <div className="flex items-center gap-3" aria-hidden="true">
                  <span className={`grid size-8 place-items-center rounded-lg font-bold ${
                    proposal.emphasized
                      ? "bg-primary/20 text-primary"
                      : "bg-secondary text-muted-foreground"
                  }`}
                  >
                    {proposal.rankLabel}
                  </span>
                  <div className="text-left">
                    <p className="font-bold">{slotLabel}</p>
                    <p className="text-xs text-muted-foreground">{proposal.availability}</p>
                  </div>
                </div>
                <span className={`text-xs font-bold ${
                  proposal.emphasized ? "text-primary" : "text-muted-foreground"
                }`}
                aria-hidden="true"
                >
                  제안하기
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
