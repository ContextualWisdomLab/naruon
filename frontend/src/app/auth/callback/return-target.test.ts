import { expect, test, describe } from 'vitest';
import { toSafeReturnTo } from './return-target';

describe('toSafeReturnTo', () => {
  test('allows valid local paths', () => {
    expect(toSafeReturnTo('/mail')).toBe('/mail');
    expect(toSafeReturnTo('/settings?tab=profile')).toBe('/settings?tab=profile');
    expect(toSafeReturnTo('/projects#some-hash')).toBe('/projects#some-hash');
  });

  test('rejects external URLs', () => {
    expect(toSafeReturnTo('https://example.com')).toBe('/');
    expect(toSafeReturnTo('http://example.com/login')).toBe('/');
  });

  test('rejects protocol-relative URLs', () => {
    expect(toSafeReturnTo('//example.com')).toBe('/');
    expect(toSafeReturnTo('////example.com')).toBe('/');
  });

  test('rejects URL-encoded bypass attempts', () => {
    expect(toSafeReturnTo('/%5C%5Cexample.com')).toBe('/');
    expect(toSafeReturnTo('/%2F%2Fexample.com')).toBe('/');
    expect(toSafeReturnTo('/%00/example.com')).toBe('/');
  });

  test('rejects un-normalized paths', () => {
    expect(toSafeReturnTo('/\\example.com')).toBe('/');
    expect(toSafeReturnTo('/\\/example.com')).toBe('/');
  });
});
