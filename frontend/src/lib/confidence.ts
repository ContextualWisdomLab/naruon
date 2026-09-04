export function toConfidencePercent(confidence: number | undefined): number | undefined {
  if (typeof confidence !== "number" || !Number.isFinite(confidence)) {
    return undefined;
  }

  return Math.round(Math.min(100, Math.max(0, confidence)));
}
