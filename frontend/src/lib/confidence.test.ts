import { describe, it, expect } from 'vitest';
import { toConfidencePercent } from './confidence';

describe('toConfidencePercent', () => {
  it('returns undefined for non-number inputs', () => {
    expect(toConfidencePercent(undefined)).toBeUndefined();
    expect(toConfidencePercent(null as unknown as number)).toBeUndefined();
    expect(toConfidencePercent('80' as unknown as number)).toBeUndefined();
    expect(toConfidencePercent(NaN)).toBeUndefined();
    expect(toConfidencePercent(Infinity)).toBeUndefined();
    expect(toConfidencePercent(-Infinity)).toBeUndefined();
  });

  it('handles percentage values correctly (0 to 100)', () => {
    expect(toConfidencePercent(0)).toBe(0);
    expect(toConfidencePercent(50)).toBe(50);
    expect(toConfidencePercent(100)).toBe(100);
  });

  it('rejects values outside the backend 0-100 contract', () => {
    expect(toConfidencePercent(-10)).toBeUndefined();
    expect(toConfidencePercent(150)).toBeUndefined();
    expect(toConfidencePercent(-0.1)).toBeUndefined();
  });

  it('rejects non-integer values outside the backend integer contract', () => {
    expect(toConfidencePercent(0.5)).toBeUndefined();
    expect(toConfidencePercent(0.856)).toBeUndefined();
    expect(toConfidencePercent(1)).toBe(1);
    expect(toConfidencePercent(1.01)).toBeUndefined();
    expect(toConfidencePercent(85.5)).toBeUndefined();
    expect(toConfidencePercent(99.5)).toBeUndefined();
  });

  it('normalizes negative zero to positive zero', () => {
    const percent = toConfidencePercent(-0);

    expect(Object.is(percent, 0)).toBe(true);
    expect(Object.is(percent, -0)).toBe(false);
  });
});
