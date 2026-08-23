import { describe, it, expect } from "vitest";
import {
  toConfidencePercent,
  confidenceLabel,
  isLowConfidence,
  LOW_CONFIDENCE_PERCENT,
  MISSING_CONFIDENCE_LABEL,
  LOW_CONFIDENCE_LABEL,
} from "./confidence";

describe("toConfidencePercent", () => {
  it("returns undefined for non-number inputs", () => {
    expect(toConfidencePercent(undefined)).toBeUndefined();
    expect(toConfidencePercent(null as unknown as number)).toBeUndefined();
    expect(toConfidencePercent("80" as unknown as number)).toBeUndefined();
    expect(toConfidencePercent(NaN)).toBeUndefined();
    expect(toConfidencePercent(Infinity)).toBeUndefined();
    expect(toConfidencePercent(-Infinity)).toBeUndefined();
  });

  it("uses one scale for 0, 1, 0.5, 50, and 1.01", () => {
    expect(toConfidencePercent(0)).toBe(0);
    expect(toConfidencePercent(0.5)).toBe(50);
    expect(toConfidencePercent(1)).toBe(100);
    expect(toConfidencePercent(1.01)).toBe(100);
    expect(toConfidencePercent(50)).toBe(50);
  });

  it("does not treat 1 as 100% and 1.01 as about 1%", () => {
    const one = toConfidencePercent(1);
    const overflow = toConfidencePercent(1.01);
    expect(one).toBe(100);
    expect(overflow).toBe(100);
    expect(Math.abs((one ?? 0) - (overflow ?? 0))).toBeLessThan(2);
  });

  it("treats values in [0, 2) as unit-interval and values >= 2 as already percent", () => {
    expect(toConfidencePercent(0.856)).toBe(86);
    expect(toConfidencePercent(1.5)).toBe(100);
    expect(toConfidencePercent(85.6)).toBe(86);
    expect(toConfidencePercent(100)).toBe(100);
    expect(toConfidencePercent(99.5)).toBe(100);
  });

  it("clamps values to the 0-100 range", () => {
    expect(toConfidencePercent(-10)).toBe(0);
    expect(toConfidencePercent(150)).toBe(100);
    expect(toConfidencePercent(-0.1)).toBe(0);
  });

  it("handles floating point precision gracefully", () => {
    expect(toConfidencePercent(0.1 + 0.2)).toBe(30);
    expect(toConfidencePercent(0.14)).toBe(14);
  });

  it("handles exact rounding thresholds correctly", () => {
    expect(toConfidencePercent(0.854)).toBe(85);
    expect(toConfidencePercent(0.855)).toBe(86);
    expect(toConfidencePercent(85.4)).toBe(85);
    expect(toConfidencePercent(85.5)).toBe(86);
  });

  it("normalizes negative zero to positive zero", () => {
    const percent = toConfidencePercent(-0);

    expect(Object.is(percent, 0)).toBe(true);
    expect(Object.is(percent, -0)).toBe(false);
  });
});

describe("confidence display contract", () => {
  it("labels missing confidence distinctly from a numeric score", () => {
    expect(confidenceLabel(undefined)).toBe(MISSING_CONFIDENCE_LABEL);
    expect(confidenceLabel(0)).toBe("신뢰도 0%");
    expect(confidenceLabel(100)).toBe("신뢰도 100%");
  });

  it("treats scores below 50 as low confidence", () => {
    expect(LOW_CONFIDENCE_PERCENT).toBe(50);
    expect(isLowConfidence(undefined)).toBe(false);
    expect(isLowConfidence(0)).toBe(true);
    expect(isLowConfidence(49)).toBe(true);
    expect(isLowConfidence(50)).toBe(false);
    expect(LOW_CONFIDENCE_LABEL).toBe("낮은 신뢰도");
  });
});
