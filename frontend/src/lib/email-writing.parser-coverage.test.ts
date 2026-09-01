import { describe, expect, it } from 'vitest';
import {
  EmailWritingContractError,
  parseEmailWritingReviewResponse,
  parseEmailWritingReviewResponseText,
  toInkspanWritingDiagnostics,
} from './email-writing';

const digestHex = '7c'.repeat(32);

function responseWithoutReplacement(): Record<string, unknown> {
  const revision = {
    algorithm: 'SHA-256',
    digest_hex: digestHex,
    strong_entity_tag: `"sha256-${digestHex}"`,
  };
  const provenance = {
    workflow_id: 'email_writing_review',
    workflow_version: '1',
    judge_policy_version: 'evaluation_only_v1',
    rubric_version: 'email_writing_rubric_v1',
    model_profile_id: 'review_profile_v1',
    orchestration_mode: 'route',
    prompt_hash: `sha256:${'ab'.repeat(32)}`,
  };
  return {
    review_session_id: 'email_review_terminal_coverage',
    document_revision: revision,
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    review_status: 'abstained',
    diagnostics: [
      {
        diagnostic_id: 'terminal_coverage_diagnostic',
        document_revision: revision,
        projection_name: 'inkspan-prosemirror-text',
        projection_version: 1,
        selector: {
          type: 'TextPositionSelector',
          start: 0,
          end: 5,
        },
        category_code: 'clarity',
        priority: 'advisory',
        title: 'Clarify the action',
        explanation: 'State the requested action explicitly.',
        confidence: 0.5,
        provenance,
      },
    ],
    document_guidance: {
      purpose_summary: '',
      reader_interpretation: '',
      missing_requests: [],
      structure_suggestion: '',
    },
    context_limitations: [],
    abstained_claims: [],
    provenance,
  };
}

describe('email writing strict JSON parser terminal branches', () => {
  it('rejects a JSON string token whose escape sequence fails native JSON parsing', () => {
    expect(() =>
      parseEmailWritingReviewResponseText('{"value":"\\uZZZZ"}'),
    ).toThrow(EmailWritingContractError);
  });

  it('propagates hostile Unicode detected after native JSON parsing', () => {
    expect(() =>
      parseEmailWritingReviewResponseText('{"value":"\\ud800"}'),
    ).toThrow(/invalid_unicode/u);
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

  it('omits an Inkspan replacement field when the reviewed diagnostic has none', () => {
    const response = parseEmailWritingReviewResponse(
      responseWithoutReplacement(),
    );
    const [diagnostic] = toInkspanWritingDiagnostics(response);

    expect(diagnostic).not.toHaveProperty('suggestedReplacement');
  });
});
