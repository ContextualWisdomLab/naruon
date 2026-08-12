import { describe, expect, it } from 'vitest';
import {
  EmailWritingContractError,
  parseEmailWritingReviewResponse,
  parseEmailWritingReviewResponseText,
  toInkspanWritingDiagnostics,
} from './email-writing';

const digestHex = '7c'.repeat(32);

function baseResponse(): Record<string, unknown> {
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
    review_session_id: 'email_review_coverage',
    document_revision: revision,
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    review_status: 'abstained',
    diagnostics: [
      {
        diagnostic_id: 'coverage_diagnostic',
        document_revision: revision,
        projection_name: 'inkspan-prosemirror-text',
        projection_version: 1,
        selector: {
          type: 'TextPositionSelector',
          start: 0,
          end: 1,
        },
        category_code: 'clarity',
        priority: 'advisory',
        title: 'A😀',
        explanation: 'Explain the structural issue.',
        confidence: 0,
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

function mutate(
  callback: (payload: Record<string, unknown>) => void,
): Record<string, unknown> {
  const payload = structuredClone(baseResponse());
  callback(payload);
  return payload;
}

function diagnostic(payload: Record<string, unknown>): Record<string, unknown> {
  return (payload.diagnostics as Record<string, unknown>[])[0]!;
}

function provenance(payload: Record<string, unknown>): Record<string, unknown> {
  return diagnostic(payload).provenance as Record<string, unknown>;
}

function expectContractFailure(value: unknown): void {
  expect(() => parseEmailWritingReviewResponse(value)).toThrow(
    EmailWritingContractError,
  );
}

describe('email writing contract branch coverage', () => {
  it('rejects non-objects plus missing and unexpected response fields', () => {
    for (const value of [null, [], 3, 'response']) expectContractFailure(value);
    expectContractFailure(mutate((payload) => delete payload.review_session_id));
    expectContractFailure(mutate((payload) => {
      payload.unexpected = true;
    }));
  });

  it('exercises revision validation branches', () => {
    expectContractFailure(mutate((payload) => {
      payload.document_revision = [];
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).algorithm = 'SHA-1';
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).digest_hex = 7;
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).digest_hex = '0'.repeat(63);
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).strong_entity_tag = 7;
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).strong_entity_tag =
        `"sha256-${'00'.repeat(32)}"`;
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_revision as Record<string, unknown>).extra = 'secret';
    }));
  });

  it('exercises selector bounds and primitive validation', () => {
    const cases = [
      (selector: Record<string, unknown>) => {
        selector.type = 'TextQuoteSelector';
      },
      (selector: Record<string, unknown>) => {
        selector.start = 0.5;
      },
      (selector: Record<string, unknown>) => {
        selector.end = 0.5;
      },
      (selector: Record<string, unknown>) => {
        selector.start = -1;
      },
      (selector: Record<string, unknown>) => {
        selector.start = 2;
        selector.end = 1;
      },
      (selector: Record<string, unknown>) => {
        selector.end = Number.MAX_SAFE_INTEGER + 1;
      },
      (selector: Record<string, unknown>) => {
        delete selector.end;
      },
      (selector: Record<string, unknown>) => {
        selector.extra = true;
      },
    ];
    for (const change of cases) {
      expectContractFailure(mutate((payload) => {
        const selector = diagnostic(payload).selector as Record<string, unknown>;
        change(selector);
      }));
    }
    expectContractFailure(mutate((payload) => {
      diagnostic(payload).selector = null;
    }));
  });

  it('exercises diagnostic projection, category, priority, confidence and inert text branches', () => {
    const mutators: Array<(item: Record<string, unknown>) => void> = [
      (item) => {
        item.projection_name = 'nearest-text';
      },
      (item) => {
        item.projection_version = 2;
      },
      (item) => {
        item.category_code = 'Bad Category';
      },
      (item) => {
        item.priority = 1;
      },
      (item) => {
        item.priority = 'danger';
      },
      (item) => {
        item.confidence = '1';
      },
      (item) => {
        item.confidence = Number.POSITIVE_INFINITY;
      },
      (item) => {
        item.confidence = -0.1;
      },
      (item) => {
        item.confidence = 1.1;
      },
      (item) => {
        item.title = '';
      },
      (item) => {
        item.title = 'x'.repeat(513);
      },
      (item) => {
        item.title = '\udc00';
      },
      (item) => {
        item.explanation = '';
      },
      (item) => {
        item.explanation = 'x'.repeat(4_001);
      },
      (item) => {
        item.suggested_replacement = 7;
      },
      (item) => {
        item.suggested_replacement = 'x'.repeat(20_001);
      },
      (item) => {
        item.extra = 'not allowed';
      },
    ];
    for (const change of mutators) {
      expectContractFailure(mutate((payload) => change(diagnostic(payload))));
    }

    const withReplacement = parseEmailWritingReviewResponse(
      mutate((payload) => {
        diagnostic(payload).suggested_replacement = 'State the action.';
        diagnostic(payload).confidence = 1;
        diagnostic(payload).priority = 'critical';
      }),
    );
    expect(toInkspanWritingDiagnostics(withReplacement)[0]).toMatchObject({
      suggestedReplacement: 'State the action.',
      confidence: 1,
      priority: 'critical',
    });
  });

  it('exercises provenance and opaque identifier validation', () => {
    const invalidProvenance: Array<(item: Record<string, unknown>) => void> = [
      (item) => {
        item.workflow_id = '';
      },
      (item) => {
        item.workflow_version = ' '.repeat(2);
      },
      (item) => {
        item.judge_policy_version = 'x'.repeat(129);
      },
      (item) => {
        item.rubric_version = 1;
      },
      (item) => {
        item.model_profile_id = 'bad/value';
      },
      (item) => {
        item.orchestration_mode = 1;
      },
      (item) => {
        item.orchestration_mode = 'direct';
      },
      (item) => {
        item.prompt_hash = 'sha256:bad';
      },
      (item) => {
        delete item.prompt_hash;
      },
      (item) => {
        item.unexpected = 'provider';
      },
    ];
    for (const change of invalidProvenance) {
      expectContractFailure(mutate((payload) => change(provenance(payload))));
    }
    expectContractFailure(mutate((payload) => {
      diagnostic(payload).provenance = null;
    }));

    const conduct = parseEmailWritingReviewResponse(
      mutate((payload) => {
        provenance(payload).orchestration_mode = 'conduct';
        (payload.provenance as Record<string, unknown>).orchestration_mode = 'conduct';
      }),
    );
    expect(conduct.diagnostics[0]!.provenance.orchestration_mode).toBe('conduct');
  });

  it('exercises whole-document guidance and bounded string-array validation', () => {
    expectContractFailure(mutate((payload) => {
      payload.document_guidance = [];
    }));
    expectContractFailure(mutate((payload) => {
      delete (payload.document_guidance as Record<string, unknown>).purpose_summary;
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_guidance as Record<string, unknown>).extra = true;
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_guidance as Record<string, unknown>).missing_requests = 'not-array';
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_guidance as Record<string, unknown>).missing_requests =
        Array.from({ length: 33 }, () => 'item');
    }));
    expectContractFailure(mutate((payload) => {
      (payload.document_guidance as Record<string, unknown>).missing_requests = [7];
    }));
    expectContractFailure(mutate((payload) => {
      payload.context_limitations = 'not-array';
    }));
    expectContractFailure(mutate((payload) => {
      payload.abstained_claims = Array.from({ length: 33 }, () => 'item');
    }));
    expectContractFailure(mutate((payload) => {
      payload.context_limitations = [''];
    }));

    const populated = parseEmailWritingReviewResponse(
      mutate((payload) => {
        payload.context_limitations = ['Missing role metadata'];
        payload.abstained_claims = ['Technical claim needs evidence'];
        (payload.document_guidance as Record<string, unknown>).missing_requests = [
          'Reply deadline',
        ];
      }),
    );
    expect(populated.context_limitations).toEqual(['Missing role metadata']);
  });

  it('exercises response-level projection, status and diagnostic collection branches', () => {
    for (const status of [
      'completed',
      'unavailable',
      'stale',
      'rejected',
      'context_insufficient',
      'judge_disagreement',
    ]) {
      const parsed = parseEmailWritingReviewResponse(
        mutate((payload) => {
          payload.review_status = status;
        }),
      );
      expect(parsed.review_status).toBe(status);
    }
    expectContractFailure(mutate((payload) => {
      payload.projection_name = 7;
    }));
    expectContractFailure(mutate((payload) => {
      payload.projection_name = 'other';
    }));
    expectContractFailure(mutate((payload) => {
      payload.projection_version = 2;
    }));
    expectContractFailure(mutate((payload) => {
      payload.review_status = 1;
    }));
    expectContractFailure(mutate((payload) => {
      payload.diagnostics = 'not-array';
    }));
    expectContractFailure(mutate((payload) => {
      payload.diagnostics = Array.from({ length: 65 }, () => diagnostic(baseResponse()));
    }));
    expectContractFailure(mutate((payload) => {
      diagnostic(payload).diagnostic_id = 'bad/id';
    }));
  });

  it('exercises strict JSON scalar, object, array, string, number and delimiter branches', () => {
    const valid = JSON.stringify(baseResponse());
    expect(parseEmailWritingReviewResponseText(`  ${valid}\n`).review_status).toBe(
      'abstained',
    );

    const invalidJson = [
      '',
      'x',
      '-',
      'truX',
      '{} trailing',
      '{unquoted:1}',
      '{"a" 1}',
      '{"a":1 "b":2}',
      '[1 2]',
      '"unterminated',
      '"bad\\x"',
      '"line\nbreak"',
      '1e9999',
    ];
    for (const source of invalidJson) {
      expect(() => parseEmailWritingReviewResponseText(source)).toThrow(
        EmailWritingContractError,
      );
    }

    for (const scalar of ['true', 'false', 'null', '0', '-1', '1.5', '1e2', '"text"', '[]', '{}']) {
      expect(() => parseEmailWritingReviewResponseText(scalar)).toThrow(
        EmailWritingContractError,
      );
    }
    expect(() =>
      parseEmailWritingReviewResponseText('{"a":1,"a":2}'),
    ).toThrow(/duplicate_key/u);
  });

  it('enforces raw JSON depth, object, array and payload bounds', () => {
    let nested: unknown = 'leaf';
    for (let index = 0; index < 18; index += 1) nested = { nested };
    expect(() =>
      parseEmailWritingReviewResponseText(JSON.stringify(nested)),
    ).toThrow(/nesting_limit/u);

    const hugeArray = `[${Array.from({ length: 1_001 }, () => '0').join(',')}]`;
    expect(() => parseEmailWritingReviewResponseText(hugeArray)).toThrow(
      /array_limit/u,
    );
    const hugeObject = `{${Array.from(
      { length: 1_001 },
      (_, index) => `"k${index}":0`,
    ).join(',')}}`;
    expect(() => parseEmailWritingReviewResponseText(hugeObject)).toThrow(
      /object_limit/u,
    );
    expect(() =>
      parseEmailWritingReviewResponseText(`"${'x'.repeat(1_000_001)}"`),
    ).toThrow(/payload_limit/u);
  });
});
