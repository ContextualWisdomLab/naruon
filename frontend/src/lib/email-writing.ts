const MAX_JSON_BYTES = 1_000_000;
const MAX_JSON_DEPTH = 16;
const MAX_JSON_ITEMS = 1_000;
const MAX_DIAGNOSTICS = 64;
const MAX_SAFE_OFFSET = Number.MAX_SAFE_INTEGER;

const DIGEST_PATTERN = /^[0-9a-f]{64}$/u;
const HASH_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const CATEGORY_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;

const REVIEW_STATUSES = new Set([
  'completed',
  'abstained',
  'unavailable',
  'stale',
  'rejected',
  'context_insufficient',
  'judge_disagreement',
]);
const PRIORITIES = new Set(['advisory', 'important', 'critical']);
const ORCHESTRATION_MODES = new Set(['route', 'conduct']);

export class EmailWritingContractError extends Error {
  readonly code: string;

  constructor(code: string) {
    super(code);
    this.name = 'EmailWritingContractError';
    this.code = code;
  }
}

export interface EmailWritingDocumentRevision {
  readonly algorithm: 'SHA-256';
  readonly digest_hex: string;
  readonly strong_entity_tag: string;
}

export interface EmailWritingTextPositionSelector {
  readonly type: 'TextPositionSelector';
  readonly start: number;
  readonly end: number;
}

export interface EmailWritingProvenance {
  readonly workflow_id: string;
  readonly workflow_version: string;
  readonly judge_policy_version: string;
  readonly rubric_version: string;
  readonly model_profile_id: string;
  readonly orchestration_mode: 'route' | 'conduct';
  readonly prompt_hash: string;
}

export interface EmailWritingDiagnostic {
  readonly diagnostic_id: string;
  readonly document_revision: EmailWritingDocumentRevision;
  readonly projection_name: 'inkspan-prosemirror-text';
  readonly projection_version: 1;
  readonly selector: EmailWritingTextPositionSelector;
  readonly category_code: string;
  readonly priority: 'advisory' | 'important' | 'critical';
  readonly title: string;
  readonly explanation: string;
  readonly suggested_replacement?: string;
  readonly confidence: number;
  readonly provenance: EmailWritingProvenance;
}

export interface EmailWritingDocumentGuidance {
  readonly purpose_summary: string;
  readonly reader_interpretation: string;
  readonly missing_requests: readonly string[];
  readonly structure_suggestion: string;
}

export interface EmailWritingReviewResponse {
  readonly review_session_id: string;
  readonly document_revision: EmailWritingDocumentRevision;
  readonly projection_name: 'inkspan-prosemirror-text';
  readonly projection_version: 1;
  readonly review_status:
    | 'completed'
    | 'abstained'
    | 'unavailable'
    | 'stale'
    | 'rejected'
    | 'context_insufficient'
    | 'judge_disagreement';
  readonly diagnostics: readonly EmailWritingDiagnostic[];
  readonly document_guidance: EmailWritingDocumentGuidance;
  readonly context_limitations: readonly string[];
  readonly abstained_claims: readonly string[];
  readonly provenance: EmailWritingProvenance;
}

/** Structurally compatible with Inkspan's released React-free diagnostic contract. */
export interface InkspanWritingDiagnosticTransport {
  readonly diagnosticId: string;
  readonly documentRevision: {
    readonly algorithm: 'SHA-256';
    readonly digestHex: string;
    readonly strongEntityTag: string;
  };
  readonly textProjection: {
    readonly id: 'inkspan-prosemirror-text';
    readonly version: 1;
  };
  readonly selector: EmailWritingTextPositionSelector;
  readonly categoryCode: string;
  readonly priority: 'advisory' | 'important' | 'critical';
  readonly title: string;
  readonly explanation: string;
  readonly suggestedReplacement?: string;
  readonly confidence: number;
  readonly provenance: {
    readonly workflowId: string;
    readonly workflowVersion: string;
    readonly judgePolicyVersion: string;
  };
}

function fail(code: string): never {
  throw new EmailWritingContractError(code);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function record(value: unknown, code = 'object_expected'): Record<string, unknown> {
  if (!isRecord(value)) fail(code);
  return value;
}

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
): void {
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail('unexpected_field');
  }
  for (const key of required) {
    if (!Object.hasOwn(value, key)) fail('missing_field');
  }
}

function unicodeString(
  value: unknown,
  maximum: number,
  code = 'string_invalid',
  allowEmpty = true,
): string {
  if (typeof value !== 'string') fail(code);
  if (!allowEmpty && value.length === 0) fail(code);
  if (value.length > maximum) fail('string_limit');
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail('invalid_unicode');
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      fail('invalid_unicode');
    }
  }
  return value;
}

function identifier(value: unknown): string {
  const parsed = unicodeString(value, 128, 'identifier_invalid', false);
  if (!IDENTIFIER_PATTERN.test(parsed)) fail('identifier_invalid');
  return parsed;
}

function parseRevision(value: unknown): EmailWritingDocumentRevision {
  const input = record(value, 'revision_invalid');
  exactKeys(input, ['algorithm', 'digest_hex', 'strong_entity_tag']);
  if (input.algorithm !== 'SHA-256') fail('revision_invalid');
  const digestHex = unicodeString(input.digest_hex, 64, 'revision_invalid', false);
  if (!DIGEST_PATTERN.test(digestHex)) fail('revision_invalid');
  const strongEntityTag = unicodeString(
    input.strong_entity_tag,
    80,
    'revision_invalid',
    false,
  );
  if (strongEntityTag !== `"sha256-${digestHex}"`) fail('revision_invalid');
  return Object.freeze({
    algorithm: 'SHA-256',
    digest_hex: digestHex,
    strong_entity_tag: strongEntityTag,
  });
}

function parseSelector(value: unknown): EmailWritingTextPositionSelector {
  const input = record(value, 'selector_invalid');
  exactKeys(input, ['type', 'start', 'end']);
  if (input.type !== 'TextPositionSelector') fail('selector_invalid');
  if (!Number.isSafeInteger(input.start) || !Number.isSafeInteger(input.end)) {
    fail('selector_invalid');
  }
  const start = input.start as number;
  const end = input.end as number;
  if (start < 0 || end < start || end > MAX_SAFE_OFFSET) fail('selector_invalid');
  return Object.freeze({ type: 'TextPositionSelector', start, end });
}

function parseProvenance(value: unknown): EmailWritingProvenance {
  const input = record(value, 'provenance_invalid');
  exactKeys(input, [
    'workflow_id',
    'workflow_version',
    'judge_policy_version',
    'rubric_version',
    'model_profile_id',
    'orchestration_mode',
    'prompt_hash',
  ]);
  const workflowId = identifier(input.workflow_id);
  const workflowVersion = identifier(input.workflow_version);
  const judgePolicyVersion = identifier(input.judge_policy_version);
  const rubricVersion = identifier(input.rubric_version);
  const modelProfileId = identifier(input.model_profile_id);
  if (
    typeof input.orchestration_mode !== 'string' ||
    !ORCHESTRATION_MODES.has(input.orchestration_mode)
  ) {
    fail('orchestration_mode_invalid');
  }
  const promptHash = unicodeString(input.prompt_hash, 71, 'prompt_hash_invalid');
  if (!HASH_PATTERN.test(promptHash)) fail('prompt_hash_invalid');
  return Object.freeze({
    workflow_id: workflowId,
    workflow_version: workflowVersion,
    judge_policy_version: judgePolicyVersion,
    rubric_version: rubricVersion,
    model_profile_id: modelProfileId,
    orchestration_mode: input.orchestration_mode as 'route' | 'conduct',
    prompt_hash: promptHash,
  });
}

function parseDiagnostic(value: unknown): EmailWritingDiagnostic {
  const input = record(value, 'diagnostic_invalid');
  exactKeys(
    input,
    [
      'diagnostic_id',
      'document_revision',
      'projection_name',
      'projection_version',
      'selector',
      'category_code',
      'priority',
      'title',
      'explanation',
      'confidence',
      'provenance',
    ],
    ['suggested_replacement'],
  );
  if (input.projection_name !== 'inkspan-prosemirror-text') {
    fail('projection_invalid');
  }
  if (input.projection_version !== 1) fail('projection_invalid');
  const categoryCode = unicodeString(input.category_code, 64, 'category_invalid', false);
  if (!CATEGORY_PATTERN.test(categoryCode)) fail('category_invalid');
  if (typeof input.priority !== 'string' || !PRIORITIES.has(input.priority)) {
    fail('priority_invalid');
  }
  if (
    typeof input.confidence !== 'number' ||
    !Number.isFinite(input.confidence) ||
    input.confidence < 0 ||
    input.confidence > 1
  ) {
    fail('confidence_invalid');
  }
  const replacement = Object.hasOwn(input, 'suggested_replacement')
    ? unicodeString(input.suggested_replacement, 20_000, 'replacement_invalid')
    : undefined;
  return Object.freeze({
    diagnostic_id: identifier(input.diagnostic_id),
    document_revision: parseRevision(input.document_revision),
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    selector: parseSelector(input.selector),
    category_code: categoryCode,
    priority: input.priority as 'advisory' | 'important' | 'critical',
    title: unicodeString(input.title, 512, 'title_invalid', false),
    explanation: unicodeString(
      input.explanation,
      4_000,
      'explanation_invalid',
      false,
    ),
    ...(replacement === undefined ? {} : { suggested_replacement: replacement }),
    confidence: input.confidence,
    provenance: parseProvenance(input.provenance),
  });
}

function parseStringArray(
  value: unknown,
  maximumItems: number,
  maximumLength: number,
): readonly string[] {
  if (!Array.isArray(value) || value.length > maximumItems) fail('array_limit');
  return Object.freeze(
    value.map((item) => unicodeString(item, maximumLength, 'string_invalid', false)),
  );
}

function parseGuidance(value: unknown): EmailWritingDocumentGuidance {
  const input = record(value, 'guidance_invalid');
  exactKeys(input, [
    'purpose_summary',
    'reader_interpretation',
    'missing_requests',
    'structure_suggestion',
  ]);
  return Object.freeze({
    purpose_summary: unicodeString(input.purpose_summary, 4_000),
    reader_interpretation: unicodeString(input.reader_interpretation, 4_000),
    missing_requests: parseStringArray(input.missing_requests, 32, 1_024),
    structure_suggestion: unicodeString(input.structure_suggestion, 4_000),
  });
}

export function parseEmailWritingReviewResponse(
  value: unknown,
): EmailWritingReviewResponse {
  const input = record(value, 'review_response_invalid');
  exactKeys(input, [
    'review_session_id',
    'document_revision',
    'projection_name',
    'projection_version',
    'review_status',
    'diagnostics',
    'document_guidance',
    'context_limitations',
    'abstained_claims',
    'provenance',
  ]);
  if (input.projection_name !== 'inkspan-prosemirror-text') {
    fail('projection_invalid');
  }
  if (input.projection_version !== 1) fail('projection_invalid');
  if (typeof input.review_status !== 'string' || !REVIEW_STATUSES.has(input.review_status)) {
    fail('review_status_invalid');
  }
  if (!Array.isArray(input.diagnostics) || input.diagnostics.length > MAX_DIAGNOSTICS) {
    fail('diagnostics_limit');
  }
  const diagnostics = Object.freeze(input.diagnostics.map(parseDiagnostic));
  const ids = new Set<string>();
  for (const diagnostic of diagnostics) {
    if (ids.has(diagnostic.diagnostic_id)) fail('diagnostic_id_duplicate');
    ids.add(diagnostic.diagnostic_id);
  }
  return Object.freeze({
    review_session_id: identifier(input.review_session_id),
    document_revision: parseRevision(input.document_revision),
    projection_name: 'inkspan-prosemirror-text',
    projection_version: 1,
    review_status: input.review_status as EmailWritingReviewResponse['review_status'],
    diagnostics,
    document_guidance: parseGuidance(input.document_guidance),
    context_limitations: parseStringArray(input.context_limitations, 32, 4_000),
    abstained_claims: parseStringArray(input.abstained_claims, 32, 4_000),
    provenance: parseProvenance(input.provenance),
  });
}

class StrictJsonParser {
  private index = 0;

  constructor(private readonly source: string) {}

  parse(): unknown {
    this.skipWhitespace();
    const value = this.parseValue(0);
    this.skipWhitespace();
    if (this.index !== this.source.length) fail('invalid_json');
    return value;
  }

  private parseValue(depth: number): unknown {
    if (depth > MAX_JSON_DEPTH) fail('nesting_limit');
    this.skipWhitespace();
    const character = this.source[this.index];
    if (character === '{') return this.parseObject(depth);
    if (character === '[') return this.parseArray(depth);
    if (character === '"') return this.parseString();
    if (character === 't') return this.parseLiteral('true', true);
    if (character === 'f') return this.parseLiteral('false', false);
    if (character === 'n') return this.parseLiteral('null', null);
    if (character === '-' || (character !== undefined && /[0-9]/u.test(character))) {
      return this.parseNumber();
    }
    fail('invalid_json');
  }

  private parseObject(depth: number): Record<string, unknown> {
    this.index += 1;
    const output: Record<string, unknown> = {};
    const keys = new Set<string>();
    let count = 0;
    this.skipWhitespace();
    if (this.source[this.index] === '}') {
      this.index += 1;
      return output;
    }
    while (true) {
      this.skipWhitespace();
      if (this.source[this.index] !== '"') fail('invalid_json');
      const key = this.parseString();
      if (keys.has(key)) fail('duplicate_key');
      keys.add(key);
      this.skipWhitespace();
      if (this.source[this.index] !== ':') fail('invalid_json');
      this.index += 1;
      output[key] = this.parseValue(depth + 1);
      count += 1;
      if (count > MAX_JSON_ITEMS) fail('object_limit');
      this.skipWhitespace();
      const delimiter = this.source[this.index];
      if (delimiter === '}') {
        this.index += 1;
        return output;
      }
      if (delimiter !== ',') fail('invalid_json');
      this.index += 1;
    }
  }

  private parseArray(depth: number): unknown[] {
    this.index += 1;
    const output: unknown[] = [];
    this.skipWhitespace();
    if (this.source[this.index] === ']') {
      this.index += 1;
      return output;
    }
    while (true) {
      output.push(this.parseValue(depth + 1));
      if (output.length > MAX_JSON_ITEMS) fail('array_limit');
      this.skipWhitespace();
      const delimiter = this.source[this.index];
      if (delimiter === ']') {
        this.index += 1;
        return output;
      }
      if (delimiter !== ',') fail('invalid_json');
      this.index += 1;
    }
  }

  private parseString(): string {
    const start = this.index;
    this.index += 1;
    let escaped = false;
    while (this.index < this.source.length) {
      const character = this.source[this.index]!;
      if (escaped) {
        escaped = false;
        this.index += 1;
        continue;
      }
      if (character === '\\') {
        escaped = true;
        this.index += 1;
        continue;
      }
      if (character === '"') {
        this.index += 1;
        const token = this.source.slice(start, this.index);
        try {
          return unicodeString(JSON.parse(token), 200_000, 'invalid_unicode');
        } catch (error) {
          if (error instanceof EmailWritingContractError) throw error;
          fail('invalid_json');
        }
      }
      if (character.charCodeAt(0) < 0x20) fail('invalid_json');
      this.index += 1;
    }
    fail('invalid_json');
  }

  private parseNumber(): number {
    const rest = this.source.slice(this.index);
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/u.exec(rest);
    if (match === null) fail('invalid_json');
    this.index += match[0].length;
    const value = Number(match[0]);
    if (!Number.isFinite(value)) fail('non_finite_number');
    return value;
  }

  private parseLiteral<T>(literal: string, value: T): T {
    if (!this.source.startsWith(literal, this.index)) fail('invalid_json');
    this.index += literal.length;
    return value;
  }

  private skipWhitespace(): void {
    while (/\s/u.test(this.source[this.index] ?? '')) this.index += 1;
  }
}

export function parseEmailWritingReviewResponseText(
  source: string,
): EmailWritingReviewResponse {
  if (typeof source !== 'string') fail('source_type');
  if (new TextEncoder().encode(source).byteLength > MAX_JSON_BYTES) {
    fail('payload_limit');
  }
  return parseEmailWritingReviewResponse(new StrictJsonParser(source).parse());
}

export function toInkspanWritingDiagnostics(
  response: EmailWritingReviewResponse,
): readonly InkspanWritingDiagnosticTransport[] {
  return Object.freeze(
    response.diagnostics.map((diagnostic) =>
      Object.freeze({
        diagnosticId: diagnostic.diagnostic_id,
        documentRevision: Object.freeze({
          algorithm: diagnostic.document_revision.algorithm,
          digestHex: diagnostic.document_revision.digest_hex,
          strongEntityTag: diagnostic.document_revision.strong_entity_tag,
        }),
        textProjection: Object.freeze({
          id: diagnostic.projection_name,
          version: diagnostic.projection_version,
        }),
        selector: diagnostic.selector,
        categoryCode: diagnostic.category_code,
        priority: diagnostic.priority,
        title: diagnostic.title,
        explanation: diagnostic.explanation,
        ...(diagnostic.suggested_replacement === undefined
          ? {}
          : { suggestedReplacement: diagnostic.suggested_replacement }),
        confidence: diagnostic.confidence,
        provenance: Object.freeze({
          workflowId: diagnostic.provenance.workflow_id,
          workflowVersion: diagnostic.provenance.workflow_version,
          judgePolicyVersion: diagnostic.provenance.judge_policy_version,
        }),
      }),
    ),
  );
}
