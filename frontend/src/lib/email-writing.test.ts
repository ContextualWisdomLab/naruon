import { describe, expect, it } from 'vitest';
import {
  EmailWritingContractError,
  parseEmailWritingReviewResponse,
  parseEmailWritingReviewResponseText,
  toInkspanWritingDiagnostics,
  type EmailWritingReviewResponse,
} from './email-writing';

const digestHex = '4a'.repeat(32);
const revision = {
  algorithm: 'SHA-256',
  digest_hex: digestHex,
  strong_entity_tag: `"sha256-${digestHex}"`,
} as const;

function validDiagnostic(diagnosticId = 'writing_diagnostic_01') {
  return {
    diagnostic_id: diagnosticId,
    document_revision: revision,
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    selector: {
      type: 'TextPositionSelector',
      start: 7,
      end: 12,
    },
    category_code: 'audience_pragmatics',
    priority: 'important',
    title: '질문의 목적을 먼저 제시하세요',
    explanation:
      '현재 문장은 확인 요청보다 답변을 평가하는 반문으로 읽힐 수 있습니다.',
    suggested_replacement:
      '말씀하신 작업의 수행 주체와 범위를 확인 부탁드립니다.',
    confidence: 0.86,
    provenance: {
      workflow_id: 'email_writing_review',
      workflow_version: '1',
      judge_policy_version: 'evaluation_only_v1',
      rubric_version: 'email_writing_rubric_v1',
      model_profile_id: 'review_profile_v1',
      orchestration_mode: 'conduct',
      prompt_hash: `sha256:${'ab'.repeat(32)}`,
    },
  } as const;
}

function validResponse(): unknown {
  return {
    review_session_id: 'email_review_01JTEST',
    document_revision: revision,
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    review_status: 'completed',
    diagnostics: [validDiagnostic()],
    document_guidance: {
      purpose_summary: '수행 범위와 일정 확인',
      reader_interpretation: '핵심 요청과 전문성 방어가 섞일 수 있음',
      missing_requests: ['수행 주체', '회신 가능 예정일'],
      structure_suggestion: '목적, 확인 항목, 일정 순으로 정리',
    },
    context_limitations: [],
    abstained_claims: [],
    provenance: validDiagnostic().provenance,
  };
}

describe('email writing transport parser', () => {
  it('validates an exact response and adapts snake_case transport into Inkspan camelCase data', () => {
    const response = parseEmailWritingReviewResponse(validResponse());
    expect(response.review_status).toBe('completed');
    expect(response.diagnostics).toHaveLength(1);

    const diagnostics = toInkspanWritingDiagnostics(response);
    expect(diagnostics).toEqual([
      {
        diagnosticId: 'writing_diagnostic_01',
        documentRevision: {
          algorithm: 'SHA-256',
          digestHex,
          strongEntityTag: `"sha256-${digestHex}"`,
        },
        textProjection: {
          id: 'inkspan-prosemirror-text',
          version: 1,
        },
        selector: {
          type: 'TextPositionSelector',
          start: 7,
          end: 12,
        },
        categoryCode: 'audience_pragmatics',
        priority: 'important',
        title: '질문의 목적을 먼저 제시하세요',
        explanation:
          '현재 문장은 확인 요청보다 답변을 평가하는 반문으로 읽힐 수 있습니다.',
        suggestedReplacement:
          '말씀하신 작업의 수행 주체와 범위를 확인 부탁드립니다.',
        confidence: 0.86,
        provenance: {
          workflowId: 'email_writing_review',
          workflowVersion: '1',
          judgePolicyVersion: 'evaluation_only_v1',
        },
      },
    ]);
  });

  it('rejects extra fields, unsafe enum values, bad revisions and duplicate diagnostic IDs', () => {
    const extra = validResponse() as Record<string, unknown>;
    extra.safe_to_send = true;
    expect(() => parseEmailWritingReviewResponse(extra)).toThrow(
      EmailWritingContractError,
    );

    const invalidStatus = validResponse() as {
      review_status: string;
    };
    invalidStatus.review_status = 'safe_to_send';
    expect(() => parseEmailWritingReviewResponse(invalidStatus)).toThrow(
      EmailWritingContractError,
    );

    const badRevision = validResponse() as {
      document_revision: { digest_hex: string };
    };
    badRevision.document_revision = {
      ...badRevision.document_revision,
      digest_hex: 'AB'.repeat(32),
    };
    expect(() => parseEmailWritingReviewResponse(badRevision)).toThrow(
      EmailWritingContractError,
    );

    const duplicates = validResponse() as {
      diagnostics: unknown[];
    };
    duplicates.diagnostics = [validDiagnostic('same'), validDiagnostic('same')];
    expect(() => parseEmailWritingReviewResponse(duplicates)).toThrow(
      EmailWritingContractError,
    );
  });

  it('rejects non-finite confidence, invalid selectors, oversized arrays and hostile Unicode', () => {
    const nan = validResponse() as {
      diagnostics: Array<Record<string, unknown>>;
    };
    nan.diagnostics[0]!.confidence = Number.NaN;
    expect(() => parseEmailWritingReviewResponse(nan)).toThrow(
      EmailWritingContractError,
    );

    const selector = validResponse() as {
      diagnostics: Array<{ selector: { start: number; end: number } }>;
    };
    selector.diagnostics[0]!.selector.start = 13;
    selector.diagnostics[0]!.selector.end = 12;
    expect(() => parseEmailWritingReviewResponse(selector)).toThrow(
      EmailWritingContractError,
    );

    const excessive = validResponse() as { diagnostics: unknown[] };
    excessive.diagnostics = Array.from({ length: 65 }, (_, index) =>
      validDiagnostic(`diag_${index}`),
    );
    expect(() => parseEmailWritingReviewResponse(excessive)).toThrow(
      EmailWritingContractError,
    );

    const surrogate = validResponse() as {
      diagnostics: Array<Record<string, unknown>>;
    };
    surrogate.diagnostics[0]!.title = 'unsafe\ud800title';
    expect(() => parseEmailWritingReviewResponse(surrogate)).toThrow(
      EmailWritingContractError,
    );
  });

  it('parses raw JSON with duplicate-key, depth, array and non-finite protection before object validation', () => {
    const parsed = parseEmailWritingReviewResponseText(
      JSON.stringify(validResponse()),
    );
    expect(parsed.review_session_id).toBe('email_review_01JTEST');

    expect(() =>
      parseEmailWritingReviewResponseText(
        '{"review_session_id":"one","review_session_id":"two"}',
      ),
    ).toThrow(/duplicate_key/);

    let nested: unknown = 'leaf';
    for (let index = 0; index < 20; index += 1) {
      nested = { nested };
    }
    expect(() =>
      parseEmailWritingReviewResponseText(JSON.stringify(nested)),
    ).toThrow(/nesting_limit/);

    expect(() =>
      parseEmailWritingReviewResponseText('{"confidence":NaN}'),
    ).toThrow(/invalid_json|non_finite_number/);
  });

  it('does not expose provider URLs, credentials, raw prompts, raw outputs, send decisions or semantic fallbacks in the public contract', () => {
    const response: EmailWritingReviewResponse =
      parseEmailWritingReviewResponse(validResponse());
    const serialized = JSON.stringify(response);
    for (const forbidden of [
      'provider_url',
      'api_key',
      'bearer_token',
      'raw_prompt',
      'raw_output',
      'safe_to_send',
      'keyword_match',
      'nearest_text',
    ]) {
      expect(serialized).not.toContain(forbidden);
    }
  });
});
