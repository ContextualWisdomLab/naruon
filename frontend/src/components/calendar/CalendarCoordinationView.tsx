export function CalendarCoordinationView() {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">회의 조율</h3>
        <p className="text-sm text-muted-foreground mb-4">참석자들의 캘린더(CalDAV)를 종합 분석하여 최적의 시간을 제안합니다.</p>
        <div className="grid gap-3 max-w-lg">
          <button type="button" className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 p-4 hover:bg-primary/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">
            <div className="flex items-center gap-3">
              <span className="grid size-8 place-items-center rounded-lg bg-primary/20 text-primary font-bold">1안</span>
              <div className="text-left">
                <p className="font-bold">5월 23일 (목) 14:00 - 15:00</p>
                <p className="text-xs text-muted-foreground">모든 참석자 참석 가능</p>
              </div>
            </div>
            <span className="text-xs font-bold text-primary">제안하기</span>
          </button>
          <button type="button" className="flex items-center justify-between rounded-xl border border-border bg-card p-4 hover:bg-secondary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40">
            <div className="flex items-center gap-3">
              <span className="grid size-8 place-items-center rounded-lg bg-secondary text-muted-foreground font-bold">2안</span>
              <div className="text-left">
                <p className="font-bold">5월 24일 (금) 10:00 - 11:00</p>
                <p className="text-xs text-muted-foreground">1명(김개발) 불참 예상</p>
              </div>
            </div>
            <span className="text-xs font-bold text-muted-foreground">제안하기</span>
          </button>
        </div>
      </div>
    </div>
  );
}
