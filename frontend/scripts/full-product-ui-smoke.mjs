import { spawn } from "node:child_process";
import { mkdir, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "@playwright/test";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");
const baseUrl = process.env.NARUON_FULL_PRODUCT_BASE_URL || "http://127.0.0.1:3001";
const screenshotDir = process.env.NARUON_FULL_PRODUCT_SCREENSHOT_DIR || "/tmp/naruon-full-product-smoke";
const ALLOWED_FULL_PRODUCT_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

export const FULL_PRODUCT_ROUTES = [
  { path: "/", name: "home", expectedText: "Naruon" },
  { path: "/mail", name: "mail", expectedText: "메일" },
  { path: "/search", name: "search", expectedText: "맥락 검색" },
  { path: "/calendar", name: "calendar", expectedText: "일정" },
  { path: "/tasks", name: "tasks", expectedText: "작업" },
  { path: "/projects", name: "projects", expectedText: "프로젝트" },
  { path: "/data", name: "data", expectedText: "데이터" },
  { path: "/ai-hub", name: "ai-hub", expectedText: "AI 허브" },
  { path: "/security", name: "security", expectedText: "보안" },
  { path: "/settings", name: "settings", expectedText: "설정" },
];

export const FULL_PRODUCT_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1024 },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

export const FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES = [
  "mail",
  "search",
  "calendar",
  "tasks",
  "projects",
  "data",
  "ai-hub",
  "security",
  "settings",
];
export const FULL_PRODUCT_CRITICAL_INTERACTION_VIEWPORT_NAMES = ["desktop", "mobile"];
export const FULL_PRODUCT_DESKTOP_INTERACTION_ROUTE_NAMES = FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES;
export const FULL_PRODUCT_ACCESSIBILITY_CHECK_NAMES = [
  "visible-duplicate-id",
  "visible-interactive-accessible-name",
  "keyboard-tab-focus-entry",
];

export function resolveFullProductBaseUrl(rawBaseUrl) {
  const fullProductBaseUrl = new URL(rawBaseUrl);
  if (!ALLOWED_FULL_PRODUCT_HOSTS.has(fullProductBaseUrl.hostname)) {
    throw new Error(`Full product smoke must run only against localhost targets, got: ${fullProductBaseUrl.hostname}`);
  }
  return fullProductBaseUrl;
}

resolveFullProductBaseUrl(baseUrl);

export function resolveFullProductViewportSpecs(rawViewports = "desktop") {
  const viewportByName = new Map(FULL_PRODUCT_VIEWPORTS.map((viewport) => [viewport.name, viewport]));
  const requestedNames = rawViewports
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
  const expandedNames = requestedNames.flatMap((name) => {
    if (name === "all") return FULL_PRODUCT_VIEWPORTS.map((viewport) => viewport.name);
    return [name];
  });
  if (expandedNames.length === 0) {
    throw new Error("At least one full-product viewport is required");
  }

  const seen = new Set();
  return expandedNames.map((name) => {
    const viewport = viewportByName.get(name);
    if (!viewport) {
      throw new Error(`Unknown full-product viewport '${name}'. Expected one of: ${FULL_PRODUCT_VIEWPORTS.map((item) => item.name).join(", ")}`);
    }
    if (seen.has(name)) {
      throw new Error(`Duplicate full-product viewport '${name}'`);
    }
    seen.add(name);
    return viewport;
  });
}

export function fullProductScreenshotName(routeSpec, viewportSpec, viewportCount = 1) {
  if (viewportCount === 1 && viewportSpec.name === "desktop") return `${routeSpec.name}.png`;
  return `${viewportSpec.name}-${routeSpec.name}.png`;
}

function log(message) {
  process.stdout.write(`${message}\n`);
}

async function isServerReady(url) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    return response.status < 500;
  } catch {
    return false;
  }
}

async function waitForServer(url, child) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 30_000) {
    if (child?.exitCode !== null && child?.exitCode !== undefined) {
      throw new Error(`Next dev server exited before becoming ready with code ${child.exitCode}`);
    }
    if (await isServerReady(url)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function startServerIfNeeded() {
  if (await isServerReady(baseUrl)) return null;

  const url = new URL(baseUrl);
  if (url.hostname !== "127.0.0.1" && url.hostname !== "localhost") {
    throw new Error(`Server is not reachable and cannot be auto-started for non-local URL: ${baseUrl}`);
  }

  const child = spawn(
    "pnpm",
    ["dev", "--hostname", url.hostname, "--port", url.port || "3001"],
    {
      cwd: frontendDir,
      env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    },
  );
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  await waitForServer(baseUrl, child);
  return child;
}

async function stopServerProcess(child) {
  if (!child || child.exitCode !== null) return;

  const waitForExit = new Promise((resolve) => {
    child.once("exit", resolve);
  });
  const timeout = (ms) => new Promise((resolve) => setTimeout(resolve, ms, "timeout"));

  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }

  if ((await Promise.race([waitForExit, timeout(5_000)])) !== "timeout") return;

  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    child.kill("SIGKILL");
  }
  await Promise.race([waitForExit, timeout(2_000)]);
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const fallbackPath =
      process.env.PLAYWRIGHT_CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
    await access(fallbackPath);
    log(`Using system Chrome fallback because bundled Playwright browser is unavailable: ${error.message.split("\n")[0]}`);
    return chromium.launch({ headless: true, executablePath: fallbackPath });
  }
}

const sourceEmail = {
  id: 23,
  message_id: "<full-product-smoke@example.com>",
  thread_id: "full-product-thread",
  sender: "pm@example.com",
  recipients: "user@example.com",
  subject: "20B smoke source",
  date: "2026-05-19T09:00:00Z",
  snippet: "20억 판매 검토용 맥락 종합입니다.",
  body: "Private body stays in route mock only.",
  reply_count: 1,
};

const task = {
  id: "task-public-20b",
  title: "20억 판매 검토 실행 항목",
  status: "open",
  priority: "high",
  source_type: "email",
  source_email_id: String(sourceEmail.id),
  related_thread_id: sourceEmail.thread_id,
  updated_at: "2026-07-02T05:00:00Z",
};

const calendarWritebackSource = {
  source_id: "calendar-source-20b",
  provider: "caldav",
  protocol: "caldav",
  owner_id: "smoke-user",
  organization_id: "org-acme",
  capabilities: ["read", "write", "etag"],
  writeback_enabled: true,
  etag: "calendar-etag-20b",
};

const projectFolder = {
  folder_uid: "project-20b",
  project_name: "Naruon 20B Readiness",
  webdav_path: "/Projects/Naruon_20B_Readiness",
};

const webdavAccount = {
  source_id: "webdav-source-20b",
  display_label: "20B readiness WebDAV",
  provider: "webdav",
  protocol: "webdav",
  owner_id: "smoke-user",
  organization_id: "org-acme",
  webdav_path: "/Projects/Naruon_20B_Readiness",
  capabilities: ["read", "write", "etag"],
  writeback_enabled: true,
  etag: "webdav-etag-20b",
};

const aiHubSurface = {
  summary_cards: [
    {
      summary_key: "prompt_templates",
      label_text: "프롬프트",
      value_text: "2",
      detail_text: "원본 근거 템플릿",
      state_code: "ready",
    },
    {
      summary_key: "ai_providers",
      label_text: "판단 보조",
      value_text: "1/1",
      detail_text: "활성 조직 모델 연결",
      state_code: "ready",
    },
  ],
  prompt_cards: [
    {
      prompt_key: "prompt_safe",
      prompt_title: "의사결정 로그 맥락 종합",
      description_text: "메일에서 판단 포인트를 추출합니다.",
      shared_scope: false,
      owner_label: "alice",
      updated_at: "2026-05-29T09:30:00Z",
    },
  ],
  workflow_cards: [
    {
      workflow_key: "workflow_prompt_safe",
      workflow_title: "의사결정 로그 자동 작성",
      trigger_source: "workflow_definition",
      state_code: "ready",
      evidence_text: "2 persisted workflow steps",
    },
  ],
  agent_cards: [
    {
      agent_key: "agent_primary",
      agent_title: "Primary OpenAI",
      model_label: "openai",
      state_code: "active",
      configured: true,
      governance_text: "조직 LLM 모델 연결 registry",
    },
  ],
  evaluation_metrics: [
    {
      metric_key: "provider_readiness",
      metric_label: "Provider 준비도",
      score_value: 100,
      trend_text: "활성 모델 연결 1/1",
    },
  ],
  run_events: [
    {
      event_key: "agent_run_prompt_safe",
      event_title: "워크플로우 실행",
      state_code: "completed",
      evidence_source: "agent_run_records",
      observed_at: "2026-05-29T09:30:00Z",
      detail_text: "3개 판단 포인트를 추출했습니다.",
    },
  ],
};

const securitySurface = {
  scope_kind: "organization",
  viewer: {
    role: "tenant_admin",
    scope_kind: "organization",
  },
  sources: [
    {
      source_type: "webdav_repository",
      source_label: "WebDAV repository",
      scope_kind: "organization",
      capabilities: ["read", "write", "etag"],
      writeback_enabled: true,
      last_observed_at: "2026-05-28T04:00:00Z",
      policy_decision: {
        resource_label: "WebDAV repository",
        resource_type: "webdav_repository",
        allowed: true,
        reason: "allowed",
        evidence_label: "webdav_source_evidence",
      },
    },
  ],
  connector_events: [
    {
      state_code: "heartbeat",
      evidence_label: "connector_observation_evidence",
      observed_at: "2026-05-28T04:00:00Z",
    },
  ],
  durable_audit_events: [
    {
      actor_role: "tenant_admin",
      scope_kind: "organization",
      event_action: "update",
      resource_type: "llm_provider",
      evidence_label: "server_audit_evidence",
      observed_at: "2026-05-28T04:02:00Z",
    },
  ],
  policy_decisions: [
    {
      resource_label: "WebDAV repository",
      resource_type: "webdav_repository",
      allowed: true,
      reason: "allowed",
      evidence_label: "webdav_source_evidence",
    },
    {
      resource_label: "Cross-organization provider secret",
      resource_type: "provider_secret",
      allowed: false,
      reason: "organization_denied",
      evidence_label: "policy_engine_evidence",
    },
  ],
  external_share_reviews: [
    {
      source_type: "webdav_repository",
      review_label: "WebDAV repository writeback boundary",
      exposure_level: "external_writeback",
      decision_reason: "allowed",
    },
  ],
  policy_order: [
    {
      display_name: "Signed session identity",
      evidence_label: "signed_session_evidence",
    },
    {
      display_name: "RBAC allow after ABAC denies",
      evidence_label: "policy_engine_evidence",
    },
  ],
};

const dataQualitySurface = {
  workspace_id: "workspace-org-acme",
  organization_id: "org-acme",
  audit_event: "data.quality_surface.viewed",
  provider_write_executed: false,
  repositories: [
    {
      source_id: "document_repository",
      repository_type: "workspace_document",
      display_name: "20B readiness documents",
      object_count: 2,
      writeback_enabled: null,
      evidence_source: "documents",
      provider_write_executed: false,
    },
  ],
  repository_assets: [
    {
      asset_key: "doc_repository_ready",
      asset_type: "workspace_document",
      display_name: "20b-readiness.md",
      source_label: "Workspace document",
      state_code: "ready",
      detail_text: "document status: uploaded",
      content_chars: 128,
      captured_at: "2026-05-28T05:46:00Z",
      evidence_source: "documents.document_status",
      thread_key: "workspace_document",
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
  ],
  quality_checks: [
    {
      check_key: "thread_id_integrity",
      display_name: "Thread id integrity",
      status_code: "ready",
      issue_count: 0,
      total_count: 4,
      evidence_source: "emails.thread_id",
      detail_text: "Scoped emails have canonical thread ids.",
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

const accountConfig = {
  user_id: "smoke-user",
  smtp_server: null,
  smtp_port: null,
  smtp_username: null,
  has_smtp_password: false,
  imap_server: null,
  imap_port: null,
  imap_username: null,
  has_imap_password: false,
  pop3_server: null,
  pop3_port: null,
  pop3_username: null,
  has_pop3_password: false,
  oauth_client_id: null,
  oauth_redirect_uri: null,
  has_oauth_client_secret: false,
};

const runnerConfig = {
  workspace_id: "workspace-org-acme",
  configured: true,
  fingerprint: "runner-smoke",
  updated_at: "2026-05-28T05:45:00Z",
  connector_manifest: {
    role: "outbound_connector",
    network_mode: "outbound_only",
    control_plane_domain: "naruon.net",
    local_protocols: ["imap", "smtp", "caldav", "webdav"],
    prohibited_roles: ["mailbox_host", "mx_server"],
    runner_usage: "customer_owned_connector",
  },
};

const operationalSignals = {
  workspace_id: "workspace-org-acme",
  audit_event: "observability.operational_signals.viewed",
  telemetry: {
    prometheus_metrics_enabled: true,
    otel_traces_enabled: true,
    otel_endpoint_configured: true,
    otel_endpoint_host: "otel.example.com",
  },
  connector: {
    workspace_id: "workspace-org-acme",
    registration_state: "registration_configured",
    connection_state: "connected",
    active_connection_count: 1,
    control_plane_domain: "naruon.net",
    network_mode: "outbound_only",
    runner_usage: "customer_owned_connector",
    local_protocols: ["imap", "smtp", "caldav", "webdav"],
    last_heartbeat_at: "2026-05-28T05:45:00Z",
    last_disconnect_at: null,
    queue_depth_state: "clear",
    queue_depth: {
      pending_count: 0,
      running_count: 0,
      failed_count: 0,
      total_count: 0,
      next_retry_at: null,
    },
    recent_events: [],
  },
  signals: [
    {
      signal_key: "frontend",
      display_name: "Frontend health",
      state: "ready",
      evidence_source: "full-product-smoke",
      detail: "Route rendered",
      provider_write_executed: false,
    },
  ],
};

function routeJson(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installRoutes(page) {
  await page.route("**/auth/session", (route) => routeJson(route, { claims: {} }));
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const endpoint = new URL(request.url()).pathname;

    if (endpoint === "/api/emails") return routeJson(route, { emails: [sourceEmail] });
    if (endpoint === "/api/emails/pending-replies") return routeJson(route, { emails: [sourceEmail] });
    if (endpoint === "/api/emails/23") return routeJson(route, sourceEmail);
    if (endpoint === "/api/emails/thread/full-product-thread") return routeJson(route, { thread: [sourceEmail] });
    if (endpoint === "/api/search") {
      return routeJson(route, {
        results: [
          {
            id: 202,
            source_message_id: "<full-product-smoke@example.com>",
            subject: "20B readiness result",
            sender: "pm@example.com",
            date: "2026-05-20T09:00:00Z",
            snippet: "맥락 검색 결과에서 관계 캡처 액션을 실행할 수 있습니다.",
            thread_id: "full-product-thread",
            reply_count: 1,
            score: 0.93,
          },
        ],
      });
    }
    if (endpoint === "/api/llm/summarize") return routeJson(route, { summary: "20억 판매 검토용 맥락 종합입니다.", todos: ["근거 확인"], confidence: 0.86 });
    if (endpoint === "/api/llm/draft") return routeJson(route, { draft: "검토 가능한 답장 초안입니다." });
    if (endpoint === "/api/llm/translate") return routeJson(route, { translation: "번역된 맥락입니다." });
    if (endpoint === "/api/emails/send") return routeJson(route, { simulated: true });
    if (endpoint === "/api/tasks") return routeJson(route, [task]);
    if (endpoint === "/api/tasks/from-email") return routeJson(route, { created: 1 });
    if (endpoint === "/api/tasks/reply-sla-escalations") {
      return routeJson(route, {
        evaluated: 1,
        created: 1,
        policy: { overdue_hours: 48 },
        tasks: [task],
      });
    }
    if (endpoint.startsWith("/api/tasks/")) return routeJson(route, { ...task, status: "done" });
    if (endpoint === "/api/calendar/writeback-sources") return routeJson(route, [calendarWritebackSource]);
    if (endpoint === "/api/calendar/writeback-intent") {
      return routeJson(route, {
        workspace_id: "workspace-org-acme",
        target_source_id: calendarWritebackSource.source_id,
        protocol: calendarWritebackSource.protocol,
        writeback_mode: "customer_owned",
        requires_if_match: true,
        if_match: calendarWritebackSource.etag,
        provenance: { source: "full-product-smoke" },
        audit_event: "calendar.writeback_intent.created",
        provider_write_executed: false,
        status: "intent_ready",
        runner_request_id: null,
        provider_status: null,
        error_code: null,
      });
    }
    if (endpoint === "/api/webdav/folders") return routeJson(route, [projectFolder]);
    if (endpoint === "/api/webdav/accounts") return routeJson(route, [webdavAccount]);
    if (endpoint === "/api/webdav/writeback-intent") {
      return routeJson(route, {
        intent: "writeback",
        source_id: webdavAccount.source_id,
        target_label: webdavAccount.display_label,
        requires_if_match: true,
        if_match: webdavAccount.etag,
        provenance: "server-authoritative",
        audit_event: "webdav.writeback_intent.created",
        provider_write_executed: false,
      });
    }
    if (endpoint === "/api/webdav/knowledge-materialization-intent") return routeJson(route, { intent: "knowledge_materialization", provider_write_executed: false });
    if (endpoint === "/api/data/quality-surface") return routeJson(route, dataQualitySurface);
    if (endpoint === "/api/data/documents") return routeJson(route, { document_id: "doc-smoke", status: "stored" });
    if (endpoint === "/api/data/documents/doc_repository_ready/embedding-regeneration-intent") {
      return routeJson(route, {
        action_id: "doc-embedding-smoke",
        document_name: "20b-readiness.md",
        message: "Embedding regeneration intent recorded; no provider write executed.",
        provider_write_executed: false,
      });
    }
    if (endpoint === "/api/data/documents/doc_repository_ready/hwp-conversion-intent") {
      return routeJson(route, {
        action_id: "doc-hwp-smoke",
        document_name: "20b-readiness.md",
        message: "HWP conversion intent recorded; no provider write executed.",
        provider_write_executed: false,
      });
    }
    if (endpoint === "/api/data/documents/doc_repository_ready/webdav-materialization-intent") {
      return routeJson(route, {
        action_id: "doc-webdav-smoke",
        document_name: "20b-readiness.md",
        message: "WebDAV materialization intent recorded; no provider write executed.",
        provider_write_executed: false,
      });
    }
    if (endpoint.startsWith("/api/data/documents/")) return routeJson(route, { action_id: "doc-action-smoke", status: "accepted" });
    if (endpoint === "/api/ai-hub/surface") return routeJson(route, aiHubSurface);
    if (endpoint === "/api/security/access-surface") return routeJson(route, securitySurface);
    if (endpoint === "/api/accounts/config") return routeJson(route, accountConfig);
    if (endpoint === "/api/llm-providers") return routeJson(route, []);
    if (endpoint.startsWith("/api/llm-providers/")) return routeJson(route, { id: 1, configured: true });
    if (endpoint === "/api/runner-config") return routeJson(route, runnerConfig);
    if (endpoint === "/api/runner-config/rotate") return routeJson(route, runnerConfig);
    if (endpoint === "/api/observability/operational-signals") return routeJson(route, operationalSignals);
    if (endpoint === "/api/network/graph") return routeJson(route, { nodes: [{ id: "mail", label: "mail" }], edges: [] });
    if (endpoint === "/api/ontology/relationships") return routeJson(route, []);
    if (endpoint === "/api/ontology/relationships/capture-source") {
      return routeJson(route, {
        sender_email: "pm@example.com",
        parent_sender_email: null,
        source_message_id: "<full-product-smoke@example.com>",
        source_thread_id: "full-product-thread",
        relationship_type: "sender_context",
        confidence_score: 0.91,
        next_action: "계약 검토 담당자를 확인합니다.",
        action_reason: "검색 결과 원본 메시지의 후속 조치입니다.",
      });
    }
    if (endpoint === "/api/tools") return routeJson(route, []);
    if (endpoint.startsWith("/api/tools/")) return routeJson(route, { output: "ok", status: "success" });
    if (endpoint === "/api/runtime-config") return routeJson(route, {});

    return routeJson(route, { ok: true });
  });
}

async function runCriticalInteractionSmoke(page, routeSpec, viewportSpec) {
  if (!FULL_PRODUCT_CRITICAL_INTERACTION_ROUTE_NAMES.includes(routeSpec.name)) return [];
  const evidence = (name) => `${viewportSpec.name}:${name}`;

  if (routeSpec.name === "mail") {
    await page.getByText("20B smoke source", { exact: true }).first().click();
    const createTaskButton = page.getByRole("button", { name: "실행 항목 생성" }).first();
    await createTaskButton.waitFor({ state: "visible", timeout: 10_000 });
    await createTaskButton.click();
    await page.getByText("1개 실행 항목을 티켓형 실행 항목으로 추적합니다.").waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("mail:select-message"), evidence("mail:create-source-linked-task")];
  }

  if (routeSpec.name === "search") {
    await page.getByText("20B readiness result", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "관계 캡처", exact: true }).click();
    await page.getByText("계약 검토 담당자를 확인합니다.").waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("search:select-result"), evidence("search:capture-sender-relationship")];
  }

  if (routeSpec.name === "calendar") {
    await page.getByRole("button", { name: "새 일정 intent 점검", exact: true }).click();
    await page.getByText("기록됨", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("calendar:create-writeback-intent")];
  }

  if (routeSpec.name === "tasks") {
    await page.getByRole("button", { name: "보낸 메일 미답변 팔로업 작업 생성" }).click();
    await page.getByText("미답변 팔로업 결과가 보드에 반영되었습니다.").waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("tasks:create-reply-sla-followup")];
  }

  if (routeSpec.name === "projects") {
    await page.getByRole("button", { name: "프로젝트 의사결정 추가" }).first().click();
    await page.getByRole("region", { name: "프로젝트 내용" }).getByText("작업 흐름 반영", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("projects:open-decision-log")];
  }

  if (routeSpec.name === "data") {
    await page.getByRole("button", { name: "임베딩 재생성 의도", exact: true }).click();
    await page.getByText("Embedding regeneration intent recorded", { exact: false }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "품질 점검", exact: true }).click();
    await page.getByRole("heading", { name: "Thread id integrity", exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("data:create-embedding-regeneration-intent"), evidence("data:open-quality-checks")];
  }

  if (routeSpec.name === "ai-hub") {
    await page.getByRole("tab", { name: "실행 이력", exact: true }).click();
    await page.getByRole("tabpanel", { name: "실행 이력", exact: true }).getByText("agent_run_records", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("ai-hub:open-run-history")];
  }

  if (routeSpec.name === "security") {
    await page.getByRole("button", { name: "외부 공유", exact: true }).click();
    await page.getByText("외부 공유 / 쓰기 경계", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "정책", exact: true }).click();
    await page.getByText("차단 우선 정책 순서", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    return [evidence("security:open-sharing-review"), evidence("security:open-policy-order")];
  }

  if (routeSpec.name === "settings") {
    await page.getByRole("button", { name: "AI 모델", exact: true }).click();
    await page.getByText("/api/llm-providers", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "워크스페이스", exact: true }).click();
    const calendarStartupButton = page.locator("button").filter({ hasText: "일정 관리" }).last();
    await calendarStartupButton.click();
    const calendarStartupClass = await calendarStartupButton.getAttribute("class");
    if (!calendarStartupClass?.includes("border-primary")) {
      throw new Error("Settings startup view selector did not mark the calendar option as active");
    }
    return [evidence("settings:switch-ai-model-tab"), evidence("settings:select-calendar-startup-view")];
  }

  return [];
}

async function runAccessibilitySmoke(page, routeSpec) {
  const findings = await page.evaluate(() => {
    function isVisible(element) {
      if (!(element instanceof HTMLElement) && !(element instanceof SVGElement)) return false;
      if (element.closest("[hidden], [aria-hidden='true']")) return false;
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
      return element.getClientRects().length > 0;
    }

    function textFromIdRefs(value) {
      return value
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent?.trim() || "")
        .filter(Boolean)
        .join(" ")
        .trim();
    }

    function accessibleName(element) {
      const ariaLabel = element.getAttribute("aria-label")?.trim();
      if (ariaLabel) return ariaLabel;
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        const label = textFromIdRefs(labelledBy);
        if (label) return label;
      }
      if ("labels" in element && element.labels?.length) {
        const label = Array.from(element.labels)
          .map((item) => item.textContent?.trim() || "")
          .filter(Boolean)
          .join(" ")
          .trim();
        if (label) return label;
      }
      const title = element.getAttribute("title")?.trim();
      if (title) return title;
      const text = element.textContent?.replace(/\s+/g, " ").trim();
      if (text) return text;
      return "";
    }

    const visibleIds = new Map();
    for (const element of Array.from(document.querySelectorAll("[id]"))) {
      if (!isVisible(element)) continue;
      const id = element.getAttribute("id");
      if (!id) continue;
      visibleIds.set(id, (visibleIds.get(id) || 0) + 1);
    }
    const duplicateIds = Array.from(visibleIds.entries())
      .filter(([, count]) => count > 1)
      .map(([id, count]) => `${id}(${count})`);

    const selector = [
      "button",
      "a[href]",
      "input",
      "select",
      "textarea",
      "[role='button']",
      "[role='link']",
      "[role='tab']",
      "[role='searchbox']",
      "[role='menuitem']",
    ].join(",");
    const unnamedInteractive = Array.from(document.querySelectorAll(selector))
      .filter((element) => isVisible(element))
      .filter((element) => !element.hasAttribute("disabled"))
      .filter((element) => element.getAttribute("aria-disabled") !== "true")
      .filter((element) => !accessibleName(element))
      .slice(0, 10)
      .map((element) => {
        const tag = element.tagName.toLowerCase();
        const role = element.getAttribute("role");
        const type = element.getAttribute("type");
        return [tag, role ? `role=${role}` : "", type ? `type=${type}` : ""].filter(Boolean).join("[") + (role || type ? "]" : "");
      });

    return { duplicateIds, unnamedInteractive };
  });

  if (findings.duplicateIds.length > 0) {
    throw new Error(`Route ${routeSpec.path} has visible duplicate IDs: ${findings.duplicateIds.join(", ")}`);
  }
  if (findings.unnamedInteractive.length > 0) {
    throw new Error(`Route ${routeSpec.path} has visible interactive controls without accessible names: ${findings.unnamedInteractive.join(", ")}`);
  }

  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });
  let focusTarget = null;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    await page.keyboard.press("Tab");
    focusTarget = await page.evaluate(() => {
      const element = document.activeElement;
      if (!element) return null;
      return {
        tagName: element.tagName,
        role: element.getAttribute("role"),
        ariaLabel: element.getAttribute("aria-label"),
        text: element.textContent?.replace(/\s+/g, " ").trim().slice(0, 80) || "",
      };
    });
    if (focusTarget && focusTarget.tagName !== "BODY" && focusTarget.tagName !== "HTML") break;
  }
  if (!focusTarget || focusTarget.tagName === "BODY" || focusTarget.tagName === "HTML") {
    throw new Error(`Route ${routeSpec.path} did not expose a keyboard focus target after pressing Tab`);
  }

  return [`${routeSpec.name}:a11y-basics`];
}

async function runRouteSmoke(context, routeSpec, viewportSpec, viewportCount) {
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
  await installRoutes(page);
  await page.goto(`${baseUrl}${routeSpec.path}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  await page.locator("body").waitFor({ state: "visible", timeout: 20_000 });
  const bodyText = await page.locator("body").innerText({ timeout: 10_000 });
  const expectedTexts = Array.isArray(routeSpec.expectedText) ? routeSpec.expectedText : [routeSpec.expectedText];
  if (!expectedTexts.some((expectedText) => bodyText.includes(expectedText))) {
    const bodySnippet = bodyText.replace(/\s+/g, " ").trim().slice(0, 500);
    throw new Error(
      `Route ${routeSpec.path} did not render expected text: ${expectedTexts.join(" or ")}. Body snippet: ${bodySnippet}`,
    );
  }
  if (bodyText.includes("404") || bodyText.includes("This page could not be found")) {
    throw new Error(`Route ${routeSpec.path} rendered a not-found page`);
  }
  if (consoleErrors.length > 0) {
    throw new Error(`Route ${routeSpec.path} emitted console errors:\n${consoleErrors.join("\n")}`);
  }
  const interactionEvidence = await runCriticalInteractionSmoke(page, routeSpec, viewportSpec);
  const accessibilityEvidence = await runAccessibilitySmoke(page, routeSpec);
  const screenshotPath = path.join(screenshotDir, fullProductScreenshotName(routeSpec, viewportSpec, viewportCount));
  await page.screenshot({ path: screenshotPath, fullPage: false });
  await page.close();
  return { screenshotPath, interactionEvidence, accessibilityEvidence };
}

async function main() {
  let serverProcess = null;
  let browser = null;
  try {
    await mkdir(screenshotDir, { recursive: true });
    serverProcess = await startServerIfNeeded();
    browser = await launchBrowser();
    const screenshots = [];
    const interactions = [];
    const accessibility = [];
    const viewportSpecs = resolveFullProductViewportSpecs(process.env.NARUON_FULL_PRODUCT_VIEWPORTS || "desktop");
    for (const viewportSpec of viewportSpecs) {
      const context = await browser.newContext({
        viewport: { width: viewportSpec.width, height: viewportSpec.height },
        isMobile: Boolean(viewportSpec.isMobile),
      });
      for (const routeSpec of FULL_PRODUCT_ROUTES) {
        const result = await runRouteSmoke(context, routeSpec, viewportSpec, viewportSpecs.length);
        screenshots.push(result.screenshotPath);
        interactions.push(...result.interactionEvidence);
        accessibility.push(...result.accessibilityEvidence);
      }
      await context.close();
    }
    log("Naruon full-product route smoke passed.");
    log(`Routes: ${FULL_PRODUCT_ROUTES.map((route) => route.path).join(", ")}`);
    log(`Viewports: ${viewportSpecs.map((viewport) => `${viewport.name}(${viewport.width}x${viewport.height})`).join(", ")}`);
    if (interactions.length > 0) {
      log(`Critical interactions: ${interactions.join(", ")}`);
    }
    log(`Accessibility checks: ${accessibility.join(", ")}`);
    log(`Screenshots: ${screenshots.join(", ")}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (serverProcess) await stopServerProcess(serverProcess);
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
