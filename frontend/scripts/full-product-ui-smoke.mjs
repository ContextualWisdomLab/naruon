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

const projectFolder = {
  folder_uid: "project-20b",
  project_name: "Naruon 20B Readiness",
  webdav_path: "/Projects/Naruon_20B_Readiness",
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
    if (endpoint.startsWith("/api/tasks/")) return routeJson(route, { ...task, status: "done" });
    if (endpoint === "/api/tasks/reply-sla-escalations") {
      return routeJson(route, {
        evaluated: 1,
        created: 1,
        policy: { overdue_hours: 48 },
        tasks: [task],
      });
    }
    if (endpoint === "/api/calendar/writeback-sources") return routeJson(route, []);
    if (endpoint === "/api/calendar/writeback-intent") return routeJson(route, { intent_id: "calendar-intent-1", provider_write_executed: false });
    if (endpoint === "/api/webdav/folders") return routeJson(route, [projectFolder]);
    if (endpoint === "/api/webdav/accounts") return routeJson(route, []);
    if (endpoint === "/api/webdav/writeback-intent") return routeJson(route, { intent: "writeback", provider_write_executed: false });
    if (endpoint === "/api/webdav/knowledge-materialization-intent") return routeJson(route, { intent: "knowledge_materialization", provider_write_executed: false });
    if (endpoint === "/api/data/quality-surface") return routeJson(route, dataQualitySurface);
    if (endpoint === "/api/data/documents") return routeJson(route, { document_id: "doc-smoke", status: "stored" });
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
  const screenshotPath = path.join(screenshotDir, fullProductScreenshotName(routeSpec, viewportSpec, viewportCount));
  await page.screenshot({ path: screenshotPath, fullPage: false });
  await page.close();
  return screenshotPath;
}

async function main() {
  let serverProcess = null;
  let browser = null;
  try {
    await mkdir(screenshotDir, { recursive: true });
    serverProcess = await startServerIfNeeded();
    browser = await launchBrowser();
    const screenshots = [];
    const viewportSpecs = resolveFullProductViewportSpecs(process.env.NARUON_FULL_PRODUCT_VIEWPORTS || "desktop");
    for (const viewportSpec of viewportSpecs) {
      const context = await browser.newContext({
        viewport: { width: viewportSpec.width, height: viewportSpec.height },
        isMobile: Boolean(viewportSpec.isMobile),
      });
      for (const routeSpec of FULL_PRODUCT_ROUTES) {
        screenshots.push(await runRouteSmoke(context, routeSpec, viewportSpec, viewportSpecs.length));
      }
      await context.close();
    }
    log("Naruon full-product route smoke passed.");
    log(`Routes: ${FULL_PRODUCT_ROUTES.map((route) => route.path).join(", ")}`);
    log(`Viewports: ${viewportSpecs.map((viewport) => `${viewport.name}(${viewport.width}x${viewport.height})`).join(", ")}`);
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
