export function toConfidencePercent(confidence: number | undefined): number | undefined {
  if (
    typeof confidence !== "number" ||
    !Number.isFinite(confidence) ||
    confidence < 0 ||
    confidence > 100
  ) {
    return undefined;
  }

  return confidence === 0 ? 0 : Math.round(confidence);
}
