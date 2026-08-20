# Evidence Workspace Technical Sources

This doctoring note records standards and research sources for the Naruon evidence-based AI email workspace task definition.

## Why this exists

Naruon must not regress into a rule-only email client or a black-box AI summarizer. The technical contract separates:

- deterministic parsing for standard structures and security boundaries;
- feature extraction for identity, media, document, and graph signals;
- probabilistic resolution for duplicate, thread, and relationship ambiguity;
- evidence-bound AI synthesis for judgment and action;
- human correction feedback for governance and quality.

## Email identity and threading

RFC 5322 defines `Message-ID`, `In-Reply-To`, and `References`. These fields are structural evidence for message identity and reply chains, but Naruon still treats real-world deduplication and threading as probabilistic because provider data, forwarded messages, missing headers, and imported mailbox history can be incomplete or inconsistent.

Naruon therefore uses RFC headers as high-value features, not as the only source of truth.

## Inline images and MIME packages

RFC 2387 defines `multipart/related` as a package for body parts that should be processed as one aggregate object. RFC 2392 defines `cid:` and `mid:` URL references. Naruon uses these standards to connect HTML body references to MIME body parts before any OCR, computer vision, or LLM step.

This prevents inline charts, screenshots, signatures, and tracking pixels from being treated as unrelated ordinary attachments.

## Entity resolution

The Fellegi-Sunter framework remains the classic probabilistic record linkage baseline. Current LLM-assisted record linkage literature frames LLMs as a way to assist candidate comparison and difficult free-text linkage, not as a replacement for structured evidence, calibrated scoring, and clerical review queues.

Naruon applies this distinction by using structured features and calibrated confidence for canonical email and thread resolution, then using AI for evidence-bound synthesis.

## HWP and HWPX

HWPX/OWPML is an XML-based open document format. The shipped Naruon import
boundary recognizes and bounds the package, then records a deferred status and
retains the validated source bytes; it does not yet claim section, paragraph,
table, or image extraction. A later worker may produce those artifacts before a
PDF fallback, subject to separate sandbox and provenance evidence. HWP remains
conversion-first and sandboxed because it is a binary format with higher parsing
risk.

## Media and multimodal AI boundary

Vision-capable model inputs have supported media types and payload limits. Naruon must normalize images into LLM-safe artifacts before any model call. Remote images, unknown binaries, macro-bearing files, OLE payloads, archive bombs, and unsupported media stay outside the model boundary unless a safe conversion worker produces a supported artifact.

## APA 7 references

Ather, H. (2026). LLM-assisted record linkage: A framework for official statistics. *Statistical Journal of the IAOS*. https://doi.org/10.1177/18747655261422068

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *Journal of the American Statistical Association, 64*(328), 1183-1210. https://doi.org/10.1080/01621459.1969.10501049

Hancom. (n.d.). *HWP/OWPML format*. https://online.hancom.co.kr/support/downloadCenter/hwpOwpml

Hancom Developer. (n.d.). *Open*. https://developer.hancom.com/en-us/webhwp/devguide/hwpctrl/methods/open

Hancom Tech. (2024). *HWPX format structure*. https://tech.hancom.com/hwpxformat/

Levinson, E. (1998a). *The MIME Multipart/Related Content-type* (RFC 2387). RFC Editor. https://www.rfc-editor.org/rfc/rfc2387

Levinson, E. (1998b). *The Content-ID and Message-ID Uniform Resource Locators* (RFC 2392). RFC Editor. https://www.rfc-editor.org/rfc/rfc2392

OpenAI. (n.d.). *Images and vision*. https://platform.openai.com/docs/guides/images-vision

Resnick, P. (2008). *Internet Message Format* (RFC 5322). RFC Editor. https://www.rfc-editor.org/rfc/rfc5322
