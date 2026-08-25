export const LOW_CONFIDENCE_PERCENT = 50;
export const MISSING_CONFIDENCE_LABEL = "신뢰도 미제공";
export const LOW_CONFIDENCE_LABEL = "낮은 신뢰도";
export const EVIDENCE_MISSING_LABEL = "근거 없음";
export const EXECUTION_BLOCKED_LABEL = "실행 차단됨";
export const EXECUTION_INTENT_ONLY_LABEL = "의도만 기록";

const UNIT_INTERVAL_EXCLUSIVE_MAX = 2;

export function toConfidencePercent(confidence: number | undefined): number | undefined {
  if (typeof confidence !== "number" || !Number.isFinite(confidence)) {
    return undefined;
  }

  const magnitude = Math.abs(confidence);
  const percent = magnitude < UNIT_INTERVAL_EXCLUSIVE_MAX ? confidence * 100 : confidence;
  const clamped = Math.round(Math.min(100, Math.max(0, percent)));
  return Object.is(clamped, -0) ? 0 : clamped;
}

export function isLowConfidence(percent: number | undefined): boolean {
  return typeof percent === "number" && percent < LOW_CONFIDENCE_PERCENT;
}

export function confidenceLabel(percent: number | undefined): string {
  return percent === undefined ? MISSING_CONFIDENCE_LABEL : `신뢰도 ${percent}%`;
}

export function confidenceToneClass(percent: number | undefined): string {
  if (percent === undefined) {
    return "border-border bg-muted text-muted-foreground";
  }
  if (isLowConfidence(percent)) {
    return "border-destructive/30 bg-destructive/10 text-destructive";
  }
  if (percent < 75) {
    return "border-accent bg-accent text-accent-foreground";
  }
  return "border-primary/30 bg-primary/10 text-primary";
}

export function confidenceState(percent: number | undefined): "missing" | "low" | "ok" {
  if (percent === undefined) return "missing";
  return isLowConfidence(percent) ? "low" : "ok";
}
