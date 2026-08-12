import { describe, expect, it } from 'vitest';
import {
  EmailWritingContractError,
  parseEmailWritingReviewResponseText,
} from './email-writing';

describe('email writing strict JSON parser terminal branches', () => {
  it('rejects a JSON string token whose escape sequence fails native JSON parsing', () => {
    expect(() =>
      parseEmailWritingReviewResponseText('{"value":"\\uZZZZ"}'),
    ).toThrow(EmailWritingContractError);
  });

  it('rejects a truncated JSON literal from the literal parser', () => {
    expect(() => parseEmailWritingReviewResponseText('tru')).toThrow(
      EmailWritingContractError,
    );
  });

  it('rejects a non-string source at the runtime boundary despite static typing', () => {
    const runtimeParser = parseEmailWritingReviewResponseText as unknown as (
      source: unknown,
    ) => unknown;
    expect(() => runtimeParser(null)).toThrow(/source_type/u);
  });
});
