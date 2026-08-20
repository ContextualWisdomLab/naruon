# Image-Content Detection Flow

This document outlines the architecture and flow for processing and detecting image contents within the Naruon workspace.

## Flow Diagram

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend API
    participant Image Processing Module
    participant Content Detection Model

    User->>Frontend: Upload Image / Provide URL
    Frontend->>Backend API: POST /api/images (Payload: image data)
    Backend API->>Image Processing Module: Send for processing
    Image Processing Module->>Image Processing Module: Resize/Normalize/Sanitize
    Image Processing Module->>Content Detection Model: Request Content Analysis
    Content Detection Model-->>Image Processing Module: Return Labels, Confidence Scores, Safety Checks
    Image Processing Module-->>Backend API: Return detection results
    Backend API-->>Frontend: Return annotated image / status
    Frontend-->>User: Display results

    Frontend-->>Backend API: Invalid image, unsupported URL, or oversize payload
    Backend API-->>Frontend: 400 validation error
    Image Processing Module-->>Backend API: Sanitization or resize failure
    Backend API-->>Frontend: 422 image processing failed
    Content Detection Model-->>Image Processing Module: Timeout or model error
    Backend API-->>Frontend: 503 detection temporarily unavailable
```

## Processing Steps

1. **Ingestion:** Images are uploaded via the frontend or fetched through URLs (e.g., email attachments).
2. **Sanitization:** The image is stripped of EXIF data and malicious payloads to prevent security risks.
3. **Normalization:** The image is resized and converted to a standard format (e.g., JPEG or WebP) to ensure consistent model input.
4. **Detection:** The image is sent to an open-source detection model.
5. **Classification:** The model returns labels (e.g., categories, text OCR) and safety scores.
6. **Action:** Based on the results, the content is either indexed for search, flagged for review, or rejected.

## Current Naruon implementation boundary

Email ingestion now runs the bounded `image_metadata` parser for PNG, JPEG,
GIF, and BMP attachments. It reads only format headers and adds the detected
format, dimensions, and animation flag to the existing attachment content
graph and embedding path. It does not decode pixels or send image bytes to a
hosted model. OCR, captioning, and object detection remain deferred until a
configured local vision sidecar can provide source-backed results.

The decision and failure states are fixed in [ADR-0009](../adr/0009-image-attachment-metadata-parser.md).

## Current structured attachment boundary

Email ingestion also runs the bounded `office_text` and `archive_manifest`
parsers for DOCX, XLSX, PPTX, HWPX, and ZIP attachments. Office parsing reads
selected XML members for searchable text; ZIP parsing reads member names and
declared sizes without extraction. Both paths use payload/member limits and
fail closed on malformed input. Macros, external relationships, formula
evaluation, rendering, OCR, and archive execution remain out of scope under
[ADR-0010](../adr/0010-bounded-office-archive-text-parsing.md).

Nested `.eml`/`message/rfc822`, MP3, and legacy `.doc` attachments have a
separate bounded metadata boundary under
[ADR-0011](../adr/0011-safe-nested-media-legacy-metadata.md): one-level email
headers, MP3 signature metadata, and OLE container metadata only. Generic MIME
binary attachments use the safe `binary_metadata` parser under
[ADR-0012](../adr/0012-generic-binary-metadata.md), which records only the
declared media type and exact byte count, including payloads larger than 20 MiB.
The 1 MiB image prefix is an animation-marker scan window, not an attachment
size limit.

## Failure Modes and Recovery

* **POST /api/images validation:** Reject unsupported MIME types, unsafe URLs, and oversized payloads before storage or model work, then return a deterministic 400 response.
* **Image Processing Module:** Treat sanitization, decoding, and resize failures as non-retryable user-input errors. Log the failure with request provenance, but do not persist unsafe transformed images.
* **Content Detection Model:** Apply bounded retries for transient model timeouts and return a 503 response when the detector is unavailable. Keep the original source item queued for later analysis instead of claiming a completed detection result.
* **Monitoring:** Emit structured processing, retry, and failure counters so operators can distinguish invalid input from detector capacity or model health issues.

## Open-Source Image Detection Model Choices & Limitations

Currently, Naruon leverages open-source vision models to ensure privacy and control.

*   **Models:** We utilize models like LLaVA or similar open-weights vision-language models depending on the environment context (hosted via Ollama when applicable).
*   **Why Open Source:**
    *   Data Privacy: User email attachments and images never leave the controlled network environment unless explicitly permitted.
    *   Customization: We can fine-tune or swap models based on specific detection needs (e.g., document OCR vs. general object detection).
*   **Limitations:**
    *   **Resource Intensive:** Running large vision models requires significant GPU/CPU resources, which might limit throughput on smaller deployments.
    *   **Hallucination/Accuracy:** While powerful, open-source models may sometimes hallucinate details or struggle with highly complex visual scenes or tiny text compared to massive proprietary APIs.
    *   **Latency:** Processing time might be longer than managed cloud APIs.

## Verification and Testing

Our CI pipeline includes testing for the image processing flow, using synthetic test images to verify the sanitization, scaling, and classification logic. Model regressions are caught using static assertion checks against known image sets.
