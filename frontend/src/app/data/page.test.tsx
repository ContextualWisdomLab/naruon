/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <a href={href} {...props}>{children}</a>,
}));

vi.mock("lucide-react", () => ({
  Database: () => <svg aria-hidden="true" />,
  FileArchive: () => <svg aria-hidden="true" />,
  FolderTree: () => <svg aria-hidden="true" />,
  ShieldCheck: () => <svg aria-hidden="true" />,
  HardDrive: () => <svg aria-hidden="true" />,
  FolderOpen: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Server: () => <svg aria-hidden="true" />,
  Upload: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
}));

import DataPage from "./page";

const dataQualitySurface = {
  workspace_id: "workspace-org-acme",
  organization_id: "org-acme",
  audit_event: "data.quality_surface.viewed",
  provider_write_executed: false,
  repositories: [
    {
      source_id: "email_repository",
      repository_type: "email_repository",
      display_name: "Scoped email archive",
      object_count: 4,
      writeback_enabled: null,
      evidence_source: "emails",
      provider_write_executed: false,
    },
    {
      source_id: "attachment_repository",
      repository_type: "attachment_repository",
      display_name: "Scoped attachment archive",
      object_count: 3,
      writeback_enabled: null,
      evidence_source: "attachments",
      provider_write_executed: false,
    },
    {
      source_id: "document_repository",
      repository_type: "document_repository",
      display_name: "Scoped document repository",
      object_count: 1,
      writeback_enabled: null,
      evidence_source: "documents",
      provider_write_executed: false,
    },
    {
      source_id: "webdav_src_primary",
      repository_type: "webdav_account",
      display_name: "Customer WebDAV account",
      object_count: 0,
      writeback_enabled: true,
      evidence_source: "webdav_accounts",
      provider_write_executed: false,
    },
  ],
  repository_assets: [
    {
      asset_key: "doc_repository_ready",
      asset_type: "workspace_document",
      display_name: "roadmap.md",
      source_label: "Workspace document",
      state_code: "ready",
      detail_text: "document status: uploaded",
      content_chars: 128,
      captured_at: "2026-05-28T05:46:00Z",
      evidence_source: "documents.document_status",
      thread_key: "workspace_document",
      provider_write_executed: false,
    },
    {
      asset_key: "asset_repository_ready",
      asset_type: "email_attachment",
      display_name: "roadmap.pdf",
      source_label: "Q2 roadmap source email",
      state_code: "ready",
      detail_text: "content and thread evidence ready",
      content_chars: 4096,
      captured_at: "2026-05-28T05:45:00Z",
      evidence_source: "attachments.content, emails.thread_id",
      thread_key: "thread_repository_ready",
      provider_write_executed: false,
    },
    {
      asset_key: "asset_repository_pending",
      asset_type: "email_attachment",
      display_name: "blank-notes.md",
      source_label: "Forwarded duplicate source email",
      state_code: "needs_attention",
      detail_text: "content extraction pending, canonical thread pending",
      content_chars: 0,
      captured_at: "2026-05-28T05:43:00Z",
      evidence_source: "attachments.content, emails.thread_id",
      thread_key: "thread_missing",
      provider_write_executed: false,
    },
  ],
  pipeline_stages: [
    {
      stage_key: "source_registry",
      display_name: "Source registry",
      status_code: "ready",
      progress_percent: 100,
      evidence_source: "webdav_accounts, project_folders",
      detail_text: "2 customer-owned sources are in scope.",
      provider_write_executed: false,
    },
    {
      stage_key: "ingestion_inventory",
      display_name: "Ingestion inventory",
      status_code: "ready",
      progress_percent: 100,
      evidence_source: "emails, attachments",
      detail_text: "4 emails and 3 attachments are visible in the signed workspace scope.",
      provider_write_executed: false,
    },
    {
      stage_key: "embedding_inventory",
      display_name: "Embedding inventory",
      status_code: "running",
      progress_percent: 57,
      evidence_source: "emails.embedding, attachments.embedding",
      detail_text: "4 of 7 objects have vectors.",
      provider_write_executed: false,
    },
  ],
  embedding_collections: [
    {
      collection_key: "emails_embedding",
      display_name: "Email vectors",
      object_count: 4,
      embedded_count: 3,
      embedding_model: "text-embedding-3-small",
      vector_dimensions: 1536,
      status_code: "running",
      evidence_source: "emails.embedding",
      provider_write_executed: false,
    },
    {
      collection_key: "attachments_embedding",
      display_name: "Attachment vectors",
      object_count: 3,
      embedded_count: 1,
      embedding_model: "text-embedding-3-small",
      vector_dimensions: 1536,
      status_code: "running",
      evidence_source: "attachments.embedding",
      provider_write_executed: false,
    },
  ],
  quality_checks: [
    {
      check_key: "thread_id_integrity",
      display_name: "Thread id integrity",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 4,
      evidence_source: "emails.thread_id",
      detail_text: "Some scoped emails need canonical thread ids.",
      provider_write_executed: false,
    },
    {
      check_key: "dedupe_fingerprint",
      display_name: "Dedupe fingerprint",
      status_code: "needs_attention",
      issue_count: 2,
      total_count: 4,
      evidence_source: "emails.fingerprint",
      detail_text: "Some scoped emails need duplicate-detection fingerprints.",
      provider_write_executed: false,
    },
    {
      check_key: "attachment_content",
      display_name: "Attachment content",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 3,
      evidence_source: "attachments.content",
      detail_text: "Some scoped attachments need extracted content.",
      provider_write_executed: false,
    },
  ],
  attachment_parse_breakdown: [
    {
      content_type: "application/octet-stream",
      parse_content_type: "text/markdown",
      parse_status: "parsed",
      parser_key: "markdown",
      display_name: "Markdown attachments",
      object_count: 2,
      evidence_source: "email_attachments.content_type, email_attachments.parse_content_type, email_attachments.parse_status, email_attachments.parser_key",
      provider_write_executed: false,
    },
    {
      content_type: "application/pdf",
      parse_content_type: "application/pdf",
      parse_status: "unsupported_content_type",
      parser_key: "unsupported_binary",
      display_name: "Unsupported binary attachments",
      object_count: 1,
      evidence_source: "email_attachments.content_type, email_attachments.parse_content_type, email_attachments.parse_status, email_attachments.parser_key",
      provider_write_executed: false,
    },
  ],
  connector_events: [
    {
      event_uid: "connector_evt_data_quality",
      signal_key: "connector_heartbeat",
      state_code: "heartbeat",
      detail_text: "outbound connector heartbeat received",
      observed_at: "2026-05-28T05:45:00Z",
    },
  ],
};

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  };
}

function mockWebdavFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === "/api/data/quality-surface") {
      void init;
      return jsonResponse(dataQualitySurface);
    }
    if (path === "/api/webdav/accounts") {
      return jsonResponse([
        {
          source_id: "webdav_src_primary",
          display_label: "운영 문서 원본",
          writeback_enabled: true,
          etag: "etag-webdav-primary",
        },
        {
          source_id: "webdav_src_team",
          display_label: "팀 공유 원본",
          writeback_enabled: true,
          etag: "etag-webdav-team",
        },
      ]);
    }
    if (path === "/api/webdav/folders") {
      return jsonResponse([
        {
          folder_uid: "webdav_folder_roadmap",
          project_name: "Naruon Roadmap 2026",
          webdav_path: "/Projects/Naruon_Roadmap_2026",
        },
      ]);
    }
    if (path === "/api/webdav/writeback-intent") {
      void init;
      return jsonResponse({
        intent: "writeback",
        source_id: "webdav_src_primary",
        target_label: "운영 문서 원본",
        requires_if_match: true,
        if_match: "etag-webdav-primary",
        provenance: "server-authoritative",
      });
    }
    if (path === "/api/emails/unique-thread-intent") {
      void init;
      return jsonResponse({
        status: "intent_ready",
        candidates_checked: 2,
        duplicates_found: 2,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "email.unique_thread_intent.created",
        thread_updates: [
          {
            candidate_key: "zip-q2-root",
            canonical_thread_id: "thread-q2-root",
            dedupe_key: "q2-root@example.com",
            match_reason: "message_id",
            existing_message_id: "q2-root@example.com",
          },
          {
            candidate_key: "forwarded-copy",
            canonical_thread_id: "thread-q2-root",
            dedupe_key: "sha256:duplicate",
            match_reason: "fingerprint",
            existing_message_id: "q2-root@example.com",
          },
        ],
      });
    }
    if (path === "/api/emails/import-files") {
      void init;
      return jsonResponse({
        status: "completed",
        imported_count: 1,
        skipped_count: 0,
        failed_count: 0,
        attachment_count: 1,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "email.file_import.completed",
        items: [
          {
            filename: "customer-source.eml",
            status: "imported",
            reason_code: null,
            attachment_count: 1,
          },
        ],
      });
    }
    if (path === "/api/data/documents") {
      void init;
      return jsonResponse({
        document_id: "doc_uploaded",
        workspace_id: "workspace-org-acme",
        document_name: "decision-note.md",
        document_type: "text/markdown",
        document_status: "uploaded",
        content_chars: 15,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.uploaded",
        message: "Document stored in the signed workspace scope.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/reparse") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "parsed",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.reparsed",
        message: "Document parse metadata refreshed in the signed workspace scope.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/embedding-regeneration-intent") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "embedding_pending",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.embedding_regeneration_intent",
        message: "Embedding regeneration intent recorded; no provider write executed.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/hwp-conversion-intent") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "hwp_conversion_pending",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.hwp_conversion_intent",
        message: "HWP conversion intent recorded; no provider write executed.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/webdav-materialization-intent") {
      void init;
      return jsonResponse({
        intent: "document_webdav_materialization",
        status: "completed",
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        source_id: "webdav_src_primary",
        target_label: "운영 문서 원본",
        target_path: "/Naruon/Data/roadmap.md-opaque.md",
        requires_if_match: true,
        if_match: "etag-webdav-primary",
        provenance: "server-authoritative",
        provider_write_executed: true,
        audit_event: "data.document.webdav_materialization.executed",
        runner_request_id: "runner_req_data_doc_1",
        provider_status: 201,
        error_code: null,
        retry_item_uid: null,
        message: "Workspace document WebDAV materialization executed by the connector.",
      });
    }
    throw new Error(`Unhandled fetch: ${path}`);
  });
}

describe("DataPage", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders document repository ingestion embeddings quality and WebDAV writeback details", async () => {
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    expect(container.querySelector("h1")?.textContent).toContain("데이터와 파일");
    expect(container.textContent).toContain("저장소");
    expect(container.textContent).toContain("데이터와 파일");
    expect(container.textContent).toContain("WebDAV 원본");
    expect(container.textContent).toContain("메일/첨부 저장소");
    expect(container.textContent).toContain("감사 근거 기록됨");
    expect(container.textContent).toContain("connector_heartbeat");
    expect(container.textContent).toContain("최근 파일/첨부 자산");
    expect(container.textContent).toContain("roadmap.md");
    expect(container.textContent).toContain("워크스페이스 문서 근거");
    expect(container.textContent).toContain("roadmap.pdf");
    expect(container.textContent).toContain("원본 메일/스레드 근거 연결");
    expect(container.textContent).toContain("blank-notes.md");
    expect(container.textContent).toContain("WebDAV 반영 의도 승인");
    expect(container.textContent).toContain("쓰기 가능 · 충돌 검사용 ETag 준비");
    expect(container.textContent).toContain("원본 폴더 연결됨");
    expect(container.textContent).not.toContain("asset_repository_ready");
    expect(container.textContent).not.toContain("thread_repository_ready");
    expect(container.textContent).not.toContain("doc_repository_ready");
    expect(container.textContent).not.toContain("webdav_folder_roadmap");
    expect(container.textContent).not.toContain("etag=etag-webdav-primary");
    expect(container.textContent).not.toContain("data.quality_surface.viewed");
    expect(container.textContent).not.toContain("connector_evt_data_quality");

    const assetDetail = container.querySelector('[aria-label="선택한 파일 자산 상세"]');
    expect(assetDetail?.textContent).toContain("roadmap.md");
    expect(assetDetail?.textContent).toContain("document status: uploaded");
    expect(assetDetail?.textContent).not.toContain("doc_repository_ready");

    const pendingAsset = Array.from(container.querySelectorAll('[role="button"][aria-pressed]')).find((candidate) =>
      candidate.textContent?.includes("blank-notes.md"),
    );
    expect(pendingAsset).toBeDefined();
    await act(async () => {
      pendingAsset?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    const updatedAssetDetail = container.querySelector('[aria-label="선택한 파일 자산 상세"]');
    expect(updatedAssetDetail?.textContent).toContain("blank-notes.md");
    expect(updatedAssetDetail?.textContent).toContain("본문 추출 대기");
    expect(updatedAssetDetail?.textContent).toContain("content extraction pending, canonical thread pending");
    expect(updatedAssetDetail?.textContent).not.toContain("thread_missing");
  });

  it("uploads workspace documents and posts document action intents through signed APIs", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const fileInput = container.querySelector('input[accept=".txt,.md,.markdown,text/plain,text/markdown"]') as HTMLInputElement | null;
    expect(fileInput).toBeTruthy();
    const file = new File(["# decision note"], "decision-note.md", { type: "text/markdown" });
    Object.defineProperty(fileInput, "files", {
      configurable: true,
      value: [file],
    });
    await act(async () => {
      fileInput?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const uploadButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("선택 문서 저장"),
    );
    expect(uploadButton).toBeDefined();
    await act(async () => {
      uploadButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const uploadCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/data/documents");
    expect(uploadCall).toBeDefined();
    const [, uploadInit] = uploadCall ?? [];
    expect(uploadInit?.method).toBe("POST");
    expect(uploadInit?.credentials).toBe("same-origin");
    expect(JSON.parse(String(uploadInit?.body))).toEqual({
      document_name: "decision-note.md",
      document_type: "text/markdown",
      document_content: "# decision note",
    });
    const uploadHeaderEntries =
      uploadInit?.headers instanceof Headers
        ? Array.from(uploadInit.headers.entries())
        : Object.entries((uploadInit?.headers as Record<string, string>) ?? {});
    const uploadHeaders = Object.fromEntries(
      uploadHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(uploadHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(uploadHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("decision-note.md");
    expect(container.textContent).toContain("의도만 기록");

    for (const buttonLabel of ["재파싱 실행", "임베딩 재생성 의도", "HWP 변환 의도"]) {
      const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
        candidate.textContent?.includes(buttonLabel),
      );
      expect(button).toBeDefined();
      await act(async () => {
        button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/reparse")).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/embedding-regeneration-intent")).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/hwp-conversion-intent")).toBe(true);
    expect(container.textContent).toContain("HWP conversion intent recorded");

    const materializeButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 문서 실행 요청"),
    );
    expect(materializeButton).toBeDefined();
    await act(async () => {
      materializeButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const materializeCall = fetchMock.mock.calls.find(([input]) => (
      String(input) === "/api/data/documents/doc_repository_ready/webdav-materialization-intent"
    ));
    expect(materializeCall).toBeDefined();
    const [, materializeInit] = materializeCall ?? [];
    expect(materializeInit?.method).toBe("POST");
    expect(materializeInit?.credentials).toBe("same-origin");
    expect(JSON.parse(String(materializeInit?.body))).toEqual({
      target_source_id: "webdav_src_primary",
      execute_provider: true,
    });
    const materializeHeaderEntries =
      materializeInit?.headers instanceof Headers
        ? Array.from(materializeInit.headers.entries())
        : Object.entries((materializeInit?.headers as Record<string, string>) ?? {});
    const materializeHeaders = Object.fromEntries(
      materializeHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(materializeHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(materializeHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("외부 쓰기 실행됨");
    expect(container.textContent).toContain("Workspace document WebDAV materialization executed");
    expect(container.textContent).not.toContain("webdav_src_primary");
    expect(container.textContent).not.toContain("etag-webdav-primary");
    expect(container.textContent).not.toContain("/Naruon/Data/roadmap.md-opaque.md");
    expect(container.textContent).not.toContain("runner_req_data_doc_1");
  });

  it("loads signed data quality surface without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const dataCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/data/quality-surface");
    expect(dataCall).toBeDefined();
    const [, init] = dataCall ?? [];
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).not.toContain("28,401");
    expect(container.textContent).not.toContain("23건");
    expect(container.textContent).not.toContain("<asset-ready@example.com>");
  });

  it("renders API-backed pipeline embedding and quality tabs", async () => {
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const pipelineTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("수집 파이프라인"),
    );
    await act(async () => {
      pipelineTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("4 emails and 3 attachments");
    expect(container.textContent).toContain("원본 근거 연결됨");
    expect(container.textContent).not.toContain("emails.embedding, attachments.embedding");

    const embeddingTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("임베딩"),
    );
    await act(async () => {
      embeddingTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("text-embedding-3-small");
    expect(container.textContent).toContain("1,536");
    expect(container.textContent).toContain("Email vectors");
    expect(container.textContent).not.toContain("text-embedding-3-large");

    const qualityTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("품질 점검"),
    );
    await act(async () => {
      qualityTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("Thread id integrity");
    expect(container.textContent).toContain("Some scoped emails need canonical thread ids.");
    expect(container.textContent).toContain("첨부 parser 형식별 현황");
    expect(container.textContent).toContain("application/octet-stream");
    expect(container.textContent).toContain("text/markdown");
    expect(container.textContent).toContain("application/pdf");
    expect(container.textContent).toContain("unsupported_content_type");
    expect(container.textContent).toContain("의도만 기록");
    expect(container.textContent).not.toContain("provider_write_executed=false");
    expect(container.textContent).not.toContain("email_attachments.content_type");
    expect(container.textContent).not.toContain("발견된 심각한 데이터 품질 문제가 없습니다.");
  });

  it("does not expose permanent ready-soon Data workspace action buttons", async () => {
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    for (const tabLabel of ["문서 저장소", "수집 파이프라인", "임베딩"]) {
      const tab = Array.from(container.querySelectorAll("button")).find((candidate) =>
        candidate.textContent?.includes(tabLabel),
      );
      expect(tab).toBeDefined();
      await act(async () => {
        tab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(container.textContent).not.toContain("준비 중");
      for (const obsoleteLabel of ["문서 업로드", "재파싱", "재실행", "임베딩 재생성", "HWP 변환"]) {
        const obsoleteDisabledButton = Array.from(container.querySelectorAll("button")).find(
          (candidate) => candidate.textContent?.includes(obsoleteLabel) && (candidate as HTMLButtonElement).disabled,
        );
        expect(obsoleteDisabledButton).toBeUndefined();
      }
    }
  });

  it("creates a signed customer-owned WebDAV writeback intent", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const accountsCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/webdav/accounts");
    expect(accountsCall).toBeDefined();
    const [, accountsInit] = accountsCall ?? [];
    expect(accountsInit?.credentials).toBe("same-origin");
    const accountsHeaderEntries =
      accountsInit?.headers instanceof Headers
        ? Array.from(accountsInit.headers.entries())
        : Object.entries((accountsInit?.headers as Record<string, string>) ?? {});
    const accountsHeaders = Object.fromEntries(
      accountsHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(accountsHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(accountsHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(accountsHeaders[publicHeader]).toBeUndefined();
    }

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const writebackCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/webdav/writeback-intent");
    expect(writebackCall).toBeDefined();
    const [, init] = writebackCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    expect(JSON.parse(String(init?.body))).toEqual({
      target_source_id: "webdav_src_primary",
    });
    expect(container.textContent).toContain("서버 확인");
    expect(container.textContent).toContain("운영 문서 원본");
    expect(container.textContent).toContain("If-Match 필요");
    expect(container.textContent).not.toContain("webdav_src_primary");
    expect(container.textContent).not.toContain("etag-webdav-primary");
    expect(container.textContent).not.toContain("https://webdav.naruon.net");
    expect(container.textContent).not.toContain("demo_user");
  });

  it("sanitizes WebDAV source labels that contain opaque source ids", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/data/quality-surface") return jsonResponse(dataQualitySurface);
      if (path === "/api/webdav/accounts") {
        void init;
        return jsonResponse([
          {
            source_id: "webdav_src_primary",
            display_label: "WebDAV source webdav_src_primary",
            writeback_enabled: true,
            etag: "etag-webdav-primary",
          },
        ]);
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/webdav/writeback-intent") {
        return jsonResponse({
          intent: "writeback",
          source_id: "webdav_src_primary",
          target_label: "WebDAV source webdav_src_primary",
          requires_if_match: true,
          if_match: "etag-webdav-primary",
          provenance: "server-authoritative",
        });
      }
      throw new Error(`Unhandled fetch: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    expect(container.textContent).toContain("WebDAV 저장소 1");
    expect(container.textContent).not.toContain("WebDAV source webdav_src_primary");
    expect(container.textContent).not.toContain("webdav_src_primary");

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("서버 확인");
    expect(container.textContent).toContain("WebDAV 저장소 1");
    expect(container.textContent).not.toContain("WebDAV source webdav_src_primary");
    expect(container.textContent).not.toContain("webdav_src_primary");
  });

  it("lets the user choose a specific WebDAV source and distinguishes If-Match conflicts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/webdav/accounts") {
        return jsonResponse([
          {
            source_id: "webdav_src_primary",
            display_label: "운영 문서 원본",
            writeback_enabled: true,
            etag: "etag-webdav-primary",
          },
          {
            source_id: "webdav_src_team",
            display_label: "팀 공유 원본",
            writeback_enabled: true,
            etag: "etag-webdav-team",
          },
        ]);
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/data/quality-surface") return jsonResponse(dataQualitySurface);
      expect(path).toBe("/api/webdav/writeback-intent");
      expect(JSON.parse(String(init?.body))).toEqual({
        target_source_id: "webdav_src_team",
      });
      return jsonResponse({ detail: "If-Match conflict" }, false, 409);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const teamSourceButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("팀 공유 원본"),
    );
    expect(teamSourceButton).toBeDefined();
    await act(async () => {
      teamSourceButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const writebackButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    await act(async () => {
      writebackButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("If-Match/ETag 충돌");
    expect(container.textContent).not.toContain("webdav_src_team");
  });

  it("keeps WebDAV writeback disabled when account loading fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/webdav/accounts") {
        throw new Error("account source fetch failed");
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/webdav/writeback-intent") throw new Error("writeback should stay disabled");
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });
    await act(async () => {
      await Promise.resolve();
    });

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    ) as HTMLButtonElement | undefined;
    expect(button).toBeDefined();
    expect(button?.disabled).toBe(true);
    button?.click();

    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/webdav/writeback-intent")).toBe(false);
    expect(container.textContent).toContain("WebDAV 원본 계정 목록을 확인하지 못했습니다.");
    expect(JSON.stringify(consoleError.mock.calls)).toContain("WebDAV accounts fetch error");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain("naruon_session");
  });

  it("creates a signed unique email thread intent without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("중복 메일 스레드 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const intentCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/emails/unique-thread-intent");
    expect(intentCall).toBeDefined();
    const [, init] = intentCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    const requestBody = JSON.parse(String(init?.body));
    expect(requestBody.candidates).toHaveLength(2);
    expect(requestBody.candidates[0]).toEqual(expect.objectContaining({
      candidate_key: "zip-q2-root",
      message_id: "q2-root@example.com",
    }));
    expect(container.textContent).toContain("감사 근거");
    expect(container.textContent).toContain("기록됨");
    expect(container.textContent).toContain("Message-ID 근거");
    expect(container.textContent).toContain("본문 fingerprint 근거");
    expect(container.textContent).not.toContain("email.unique_thread_intent.created");
    expect(container.textContent).not.toContain("thread-q2-root");
    expect(container.textContent).not.toContain("provider_write_executed=false");
  });

  it("imports email source files through signed multipart upload without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).toBeDefined();
    const emailFile = new File(["raw email"], "customer-source.eml", { type: "message/rfc822" });
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [emailFile],
    });
    await act(async () => {
      input?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const importButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("선택 파일 반입"),
    );
    expect(importButton).toBeDefined();
    await act(async () => {
      importButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const importCall = fetchMock.mock.calls.find(([inputUrl]) => String(inputUrl) === "/api/emails/import-files");
    expect(importCall).toBeDefined();
    const [, init] = importCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    expect(init?.body).toBeInstanceOf(FormData);
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders.authorization).toBeUndefined();
    expect(requestHeaders["content-type"]).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("1개 반입");
    expect(container.textContent).toContain("중복 0개");
    expect(container.textContent).toContain("첨부 1개");
    expect(container.textContent).toContain("의도만 기록");
    expect(container.textContent).not.toContain("email.file_import.completed");
    expect(container.textContent).not.toContain("imported@example.com");
  });
});
