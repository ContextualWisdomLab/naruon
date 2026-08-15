# Naruon Evidence-based AI Email Workspace Task Definition

## Purpose

Naruon is not an email summarizer. It is an evidence-based AI workspace that turns email, attachments, images, calendars, people, and project context into better judgment and executable next actions.

The product promise is:

> Cross the flow of scattered mail into clearer judgment and action.

This task definition fixes the implementation boundary that every menu, button, parser, resolver, and AI workflow must follow.

## Product language

| Avoid | Use in Naruon |
| --- | --- |
| AI Summary | Context synthesis / 맥락 종합 |
| Summary | Synthesis / 종합 |
| Insight | Judgment point / 판단 포인트 |
| Todo | Action item / 실행 항목 |
| Smart Reply | Draft reply / 답장 초안 |
| Search | Context search / 맥락 검색 |
| Network Graph | Relationship context / 관계 맥락 |
| Calendar Sync | Reflect to calendar / 일정 반영 |

All customer-facing help text must tell the user what next action they can take.

## Architectural stance

Naruon must be a hybrid evidence system, not a rule-only or AI-only system.

```text
Raw evidence
  -> deterministic parsing
  -> feature extraction
  -> probabilistic resolution
  -> evidence-bound AI synthesis
  -> human correction feedback
```

Deterministic logic is used only where the input has a standard structure or security boundary. Probabilistic and model-based logic owns ambiguous identity, thread, document, image, and relationship decisions.

## Core work packages

### 1. Email identity resolution

Build canonical email identity as an entity-resolution problem.

Required objects:

- `email_raw`: raw provider/mailbox capture, provider id, raw RFC822 hash, fetched time.
- `email_message`: canonical message object, normalized identifiers, body fingerprints, attachment manifest hash, identity confidence.
- `email_instance`: account/folder/label state for a canonical message.
- `email_duplicate_candidate`: review queue for ambiguous duplicate candidates.

Required features:

- normalized `message_id` from RFC headers;
- canonicalized raw MIME SHA-256;
- normalized body hash and simhash;
- body embedding similarity;
- attachment manifest similarity;
- sender, recipient overlap, subject similarity, and sent-time delta;
- forward/quote evidence.

Resolution outcomes:

| Outcome | Contract |
| --- | --- |
| `same_message` | Merge automatically only at high calibrated confidence. |
| `review_required` | Show a human review queue. |
| `related_message` | Connect in context graph but do not deduplicate. |
| `distinct_message` | Preserve as separate canonical message. |

### 2. Email thread resolution

Threading is a message graph problem.

Required edges:

- `rfc_reply_edge` from `In-Reply-To` and `References`;
- `provider_thread_edge` from Gmail/Outlook/IMAP provider hints;
- `quote_overlap_edge` from quoted body detection;
- `participant_overlap_edge` from people overlap;
- `semantic_context_edge` from embedding/context similarity;
- `manual_override_edge` from user merge/split feedback.

The thread resolver must return:

- `thread_id`;
- confidence;
- evidence list;
- whether a human review is required.

### 3. Email images and media

Images must never be sent to a model directly from raw email. Every media item passes through a normalization and classification pipeline first.

Supported image origins:

- inline `cid:` image;
- ordinary attachment image;
- remote image URL;
- base64 data URL;
- extracted document page image.

Required classifications:

- tracking pixel;
- repeated logo/signature;
- screenshot;
- chart/graph;
- document scan;
- table image;
- ordinary photo;
- unsupported or quarantined media.

Only semantically relevant, supported, normalized artifacts may enter OCR or vision/LLM analysis.

### 4. HWP and HWPX documents

HWPX is a first-class structured document target. Parse the XML package before falling back to PDF rendering.

HWP processing is conversion-first and sandboxed:

1. HWP -> HWPX conversion when available;
2. HWP -> PDF/page-image conversion;
3. native text parser fallback;
4. quarantine plus user-visible remediation when conversion fails.

The parser must report separate confidence values for text extraction, table extraction, image extraction, layout preservation, and provenance binding.

### 5. AI synthesis

AI output must always be bound to source artifacts.

Required outputs:

- context synthesis;
- judgment points;
- action items;
- calendar candidates;
- risks;
- related people;
- related documents;
- confidence;
- source citations.

AI must not create external side effects without explicit user approval. Sending mail, reflecting calendar events, external sharing, policy changes, and destructive actions all require confirmation.

## GNB scope

| GNB | Delivery contract |
| --- | --- |
| Home | Judgment points, pending tasks, schedule conflicts, and recent mail. |
| Mail | Inbox, detail, compose, draft reply, and full thread. |
| Calendar | Month/week calendar, detail, coordination, and candidates. |
| Tasks | My tasks, delegated tasks, kanban, and task detail. |
| Projects | List, detail, milestones, and decision log. |
| Context Search | Unified search, result detail, relationship graph, and timeline. |
| Data | Document store, ingestion pipeline, embedding, and quality checks. |
| AI Hub | Prompt studio, workflow builder, agents, evaluation, and execution history. |
| Security | Dashboard, access, audit log, external sharing, and policies. |
| Settings | Workspace, members, connections, notifications, automation, billing, developer. |

## Button/action contract

Every visible button must have:

1. a route or service action;
2. permission boundary;
3. loading state;
4. success state;
5. error state;
6. audit event when it changes data;
7. user-facing next-action copy.

For example, `AI 답장 초안` calls evidence-bound draft generation; `일정 반영` writes a calendar event only after conflict checks and user confirmation; `스레드 병합` creates a manual override edge.

## Required evidence and citations

- RFC 5322 is authoritative for `Message-ID`, `In-Reply-To`, and `References` fields.
- RFC 2387 is authoritative for `multipart/related` inline media handling.
- RFC 2392 is authoritative for `cid:` and `mid:` URL references.
- Fellegi-Sunter record linkage is the baseline model family for probabilistic identity resolution.
- HWPX/OWPML must be treated as an XML-based open document package, not merely as PDF fallback.

## Acceptance criteria

- Duplicate email resolution distinguishes `same_message`, `related_message`, and `distinct_message`.
- Thread resolution stores graph edges and confidence, not only a provider thread id.
- Inline images are resolved through MIME/CID mapping before OCR or vision.
- HWPX documents produce paragraph/table/image artifacts with source provenance.
- HWP failures are explicit `partial`, `failed`, or `quarantined` states.
- Every AI-generated judgment point has source evidence and confidence.
- Every side-effecting UI action has confirmation, audit logging, and rollback guidance.

## References

Ather, H. (2026). LLM-assisted record linkage: A framework for official statistics. *Statistical Journal of the IAOS*. https://doi.org/10.1177/18747655261422068

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *Journal of the American Statistical Association, 64*(328), 1183-1210. https://doi.org/10.1080/01621459.1969.10501049

Hancom. (n.d.). *HWP/OWPML format*. https://online.hancom.co.kr/support/downloadCenter/hwpOwpml

Hancom Tech. (2024). *HWPX format structure*. https://tech.hancom.com/hwpxformat/

Levinson, E. (1998). *The Content-ID and Message-ID Uniform Resource Locators* (RFC 2392). RFC Editor. https://www.rfc-editor.org/rfc/rfc2392

Levinson, E. (1998). *The MIME Multipart/Related Content-type* (RFC 2387). RFC Editor. https://www.rfc-editor.org/rfc/rfc2387

Resnick, P. (2008). *Internet Message Format* (RFC 5322). RFC Editor. https://www.rfc-editor.org/rfc/rfc5322
