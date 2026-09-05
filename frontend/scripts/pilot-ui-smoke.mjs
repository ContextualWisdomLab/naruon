import { spawn } from "node:child_process";
import { access, mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "@playwright/test";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");
const nextCliPath = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const requestedBaseUrl = process.env.NARUON_PILOT_BASE_URL || "http://127.0.0.1:3001";
const requestedMailScreenshot = process.env.NARUON_PILOT_MAIL_SCREENSHOT;
const requestedSearchScreenshot = process.env.NARUON_PILOT_SEARCH_SCREENSHOT;
const DEFAULT_PILOT_MAIL_SCREENSHOT = "/tmp/naruon-pilot-mail.png";
const DEFAULT_PILOT_SEARCH_SCREENSHOT = "/tmp/naruon-pilot-search.png";
const PILOT_SERVER_READY_TIMEOUT_MS = 90_000;

export function resolvePilotBaseUrl(rawBaseUrl) {
  switch (rawBaseUrl) {
    case "http://127.0.0.1:3001":
    case "http://127.0.0.1:3001/":
      return new URL("http://127.0.0.1:3001");
    case "http://localhost:3001":
    case "http://localhost:3001/":
      return new URL("http://localhost:3001");
    case "http://[::1]:3001":
    case "http://[::1]:3001/":
      return new URL("http://[::1]:3001");
    default:
      throw new Error("Pilot smoke must run only against approved localhost targets on port 3001");
  }
}

export function resolvePilotChromePath(rawChromePath, platform = process.platform) {
  if (rawChromePath !== undefined) {
    switch (rawChromePath) {
      case "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
      case "/usr/bin/google-chrome":
        return "/usr/bin/google-chrome";
      case "/usr/bin/google-chrome-stable":
        return "/usr/bin/google-chrome-stable";
      case "/usr/bin/chromium":
        return "/usr/bin/chromium";
      case "/usr/bin/chromium-browser":
        return "/usr/bin/chromium-browser";
      case "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe":
        return "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
      default:
        throw new Error("PLAYWRIGHT_CHROME_PATH must name an approved Chrome executable");
    }
  }

  if (platform === "darwin") return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  if (platform === "win32") return "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  return "/usr/bin/google-chrome";
}

function validatePilotArtifactProfile(rawMailScreenshot, rawSearchScreenshot) {
  if (rawMailScreenshot !== undefined && rawMailScreenshot !== DEFAULT_PILOT_MAIL_SCREENSHOT) {
    throw new Error("NARUON_PILOT_MAIL_SCREENSHOT must select the approved artifact profile");
  }
  if (rawSearchScreenshot !== undefined && rawSearchScreenshot !== DEFAULT_PILOT_SEARCH_SCREENSHOT) {
    throw new Error("NARUON_PILOT_SEARCH_SCREENSHOT must select the approved artifact profile");
  }
}

export async function createPilotArtifactDirectory(rawMailScreenshot, rawSearchScreenshot) {
  validatePilotArtifactProfile(rawMailScreenshot, rawSearchScreenshot);
  return mkdtemp(path.join(tmpdir(), "naruon-pilot-smoke-"));
}

export function createPilotServerLaunchSpec(rawBaseUrl) {
  const safeBaseUrl = resolvePilotBaseUrl(rawBaseUrl);
  return {
    executable: process.execPath,
    args: [nextCliPath, "dev", "--webpack", "--hostname", safeBaseUrl.hostname, "--port", safeBaseUrl.port],
  };
}

export function resolvePilotArtifactPath(artifactDirectory, fileName) {
  if (!path.isAbsolute(artifactDirectory) || !/^[a-z0-9]+(?:-[a-z0-9]+)*\.png$/u.test(fileName)) {
    throw new Error("Pilot smoke artifacts require an absolute directory and a safe file name");
  }
  const artifactPath = path.resolve(artifactDirectory, fileName);
  const relativePath = path.relative(artifactDirectory, artifactPath);
  if (relativePath.startsWith(`..${path.sep}`) || relativePath === ".." || path.isAbsolute(relativePath)) {
    throw new Error("Pilot smoke artifact path escaped its private directory");
  }
  return artifactPath;
}

const baseUrl = resolvePilotBaseUrl(requestedBaseUrl).href;

const sensitiveMailBody = "Sensitive source body must stay out of analytics payloads.";
const sensitiveDraftBody = "상용 파일럿 답장 초안입니다. 내부 원문은 이벤트에 남지 않아야 합니다.";
const rawSearchQuery = "계약";

const sourceEmail = {
  id: 23,
  message_id: "<source-drawer@example.com>",
  thread_id: "source-thread",
  sender: "source@example.com",
  recipients: "user@example.com",
  subject: "Source Drawer",
  date: "2026-05-19T09:00:00Z",
  snippet: "근거 원본을 확인해야 하는 맥락 종합입니다.",
  body: sensitiveMailBody,
  reply_count: 1,
};

function log(message) {
  process.stdout.write(`${message}\n`);
}

async function isServerReady(url) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    const response = await fetch(url, { redirect: "manual", signal: controller.signal });
    clearTimeout(timeout);
    return response.status < 500;
  } catch {
    return false;
  }
}

async function waitForServer(url, child) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < PILOT_SERVER_READY_TIMEOUT_MS) {
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

  const launchSpec = createPilotServerLaunchSpec(baseUrl);
  const child = spawn(
    launchSpec.executable,
    launchSpec.args,
    {
      cwd: frontendDir,
      env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  await waitForServer(baseUrl, child);
  return child;
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const fallbackPath = resolvePilotChromePath(process.env.PLAYWRIGHT_CHROME_PATH);
    await access(fallbackPath);
    log(`Using system Chrome fallback because bundled Playwright browser is unavailable: ${error.message.split("\n")[0]}`);
    return chromium.launch({ headless: true, executablePath: fallbackPath });
  }
}

async function installRoutes(page) {
  await page.route("**/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ claims: {} }),
    });
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname;
    const respond = (body, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (endpoint === "/api/network/graph") {
      return respond({
        nodes: [
          { id: "source", label: "source@example.com" },
          { id: "thread", label: "source-thread" },
        ],
        edges: [{ from: "source", to: "thread" }],
      });
    }

    if (endpoint === "/api/emails" && request.method() === "GET") {
      return respond({ emails: [sourceEmail] });
    }
    if (endpoint === "/api/emails/23") return respond(sourceEmail);
    if (endpoint === "/api/emails/thread/source-thread") return respond({ thread: [sourceEmail] });
    if (endpoint === "/api/llm/summarize") {
      return respond({
        summary: "근거 원본을 확인해야 하는 맥락 종합입니다.",
        todos: ["원본 확인"],
        confidence: 86,
        provenance: "mail-thread",
      });
    }
    if (endpoint === "/api/llm/draft") return respond({ draft: sensitiveDraftBody });
    if (endpoint === "/api/emails/send") return respond({ simulated: true });
    if (endpoint === "/api/tasks/from-email") return respond({ created: 1 });
    if (endpoint === "/api/calendar/writeback-intent") {
      return respond({
        intent_id: "calendar-intent-1",
        target_source_id: "calendar-source-1",
        provider_write_executed: false,
      });
    }

    if (endpoint === "/api/search" && request.method() === "POST") {
      const body = request.postDataJSON?.() ?? JSON.parse(request.postData() || "{}");
      const isContractSearch = body.query === rawSearchQuery;
      return respond({
        results: [{
          id: isContractSearch ? 202 : 101,
          source_message_id: isContractSearch ? "<contract-source@example.com>" : "<launch-source@example.com>",
          subject: isContractSearch ? "계약 검토 결과" : "런칭 캠페인 결과",
          sender: "pm@example.com",
          date: "2026-05-20T09:00:00Z",
          snippet: "검색 결과에서 관계 캡처 액션을 실행할 수 있습니다.",
          thread_id: isContractSearch ? "thread-contract" : "thread-launch",
          reply_count: 2,
          score: 0.93,
        }],
      });
    }
    if (endpoint === "/api/ontology/relationships" && request.method() === "GET") return respond([]);
    if (endpoint === "/api/ontology/relationships/capture-source") {
      return respond({
        sender_email: "pm@example.com",
        parent_sender_email: null,
        source_message_id: "<contract-source@example.com>",
        source_thread_id: "thread-contract",
        relationship_type: "sender_context",
        confidence_score: 0.91,
        next_action: "계약 검토 담당자를 확인합니다.",
        action_reason: "검색 결과 원본 메시지의 후속 조치입니다.",
      });
    }

    if (endpoint === "/api/tasks") return respond([]);
    if (endpoint === "/api/calendar/writeback-sources") return respond([]);
    if (endpoint === "/api/webdav/folders") return respond([]);
    return respond({ ok: true });
  });
}

async function preparePage(context, consoleIssues) {
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => consoleIssues.push(`pageerror: ${error.message}`));
  await page.addInitScript(() => {
    window.__naruonEvents = [];
    window.addEventListener("naruon:product-event", (event) => {
      window.__naruonEvents.push(event.detail);
    });
  });
  await installRoutes(page);
  return page;
}

function assertNoSensitiveEventText(eventText, forbiddenValues) {
  for (const value of forbiddenValues) {
    if (eventText.includes(value)) {
      throw new Error(`Sensitive text leaked into product event payload: ${value}`);
    }
  }
}

async function runMailFlow(context, consoleIssues, mailScreenshotPath) {
  const page = await preparePage(context, consoleIssues);
  await page.goto(new URL("/mail", baseUrl).href, { waitUntil: "domcontentloaded" });

  const desktopMailRegion = page.getByRole("region", { name: "데스크톱 메일 작업공간" });
  await desktopMailRegion.waitFor({ state: "visible", timeout: 20_000 });

  const mailListItem = desktopMailRegion.locator("button", { hasText: "Source Drawer" });
  await mailListItem.waitFor({ state: "visible", timeout: 20_000 });
  if (await mailListItem.count() !== 1) throw new Error("Expected exactly one pilot inbox item");
  await mailListItem.click();

  await desktopMailRegion
    .locator("text=근거 원본을 확인해야 하는 맥락 종합입니다.")
    .first()
    .waitFor({ state: "visible", timeout: 20_000 });

  const sourceButtonCandidates = desktopMailRegion
    .locator("button", { hasText: "근거 원본 보기" });
  const sourceButtonCount = await sourceButtonCandidates.count();
  if (sourceButtonCount === 0) {
    throw new Error("Could not find any source drawer button candidates");
  }
  const sourceButton = sourceButtonCandidates.first();
  if (await sourceButton.count() === 0) throw new Error("Could not locate source drawer button after normalization");
  if (!(await sourceButton.first().isVisible())) {
    await sourceButton.first().scrollIntoViewIfNeeded();
  }

  if (!(await sourceButton.first().isVisible())) {
    const sourceDrawerCandidates = await page
      .getByRole("button", { name: /근거 원본 보기/ })
      .allTextContents();
    throw new Error(`Source drawer button is not visible; candidates: ${JSON.stringify(sourceDrawerCandidates)}`);
  }
  await sourceButton.first().click();

  const dialog = page.getByRole("dialog", { name: "맥락 종합 근거" });
  await dialog.waitFor({ state: "visible", timeout: 10_000 });
  const drawerState = await page.evaluate(() => ({
    activeLabel: document.activeElement?.getAttribute("aria-label"),
    ariaModal: document.querySelector("[role=\"dialog\"]")?.getAttribute("aria-modal"),
  }));
  if (drawerState.activeLabel !== "근거 원본 닫기") throw new Error("Source drawer did not focus the close button");
  if (drawerState.ariaModal !== "true") throw new Error("Source drawer is missing aria-modal=true");
  await page.getByRole("button", { name: "근거 원본 닫기" }).click();
  await dialog.waitFor({ state: "hidden", timeout: 10_000 });
  await sourceButton.click();
  await dialog.waitFor({ state: "visible", timeout: 10_000 });
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden", timeout: 10_000 });

  await desktopMailRegion.getByRole("button", { name: "답장 초안 생성" }).click();
  const draftTextarea = desktopMailRegion.getByRole("textbox", { name: "답장 초안", exact: true });
  await draftTextarea.waitFor({ state: "visible", timeout: 10_000 });
  await page.waitForFunction((expectedDraft) => {
    const textarea = document.querySelector("textarea[aria-label=\"답장 초안\"]");
    return textarea?.value === expectedDraft;
  }, sensitiveDraftBody);

  await desktopMailRegion.getByRole("button", { name: "답장 보내기" }).click();
  await desktopMailRegion
    .getByText("개발 모드에서 답장을 시뮬레이션했습니다. 실제 메일은 전송되지 않았습니다.", { exact: true })
    .waitFor({ state: "visible", timeout: 10_000 });

  await desktopMailRegion.getByRole("button", { name: "실행 항목 생성" }).click();
  await desktopMailRegion
    .getByText("1개 실행 항목을 티켓형 실행 항목으로 추적합니다.", { exact: true })
    .waitFor({ state: "visible", timeout: 10_000 });

  await desktopMailRegion.getByRole("button", { name: "일정 반영" }).click();
  await desktopMailRegion
    .getByText("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.", { exact: true })
    .waitFor({ state: "visible", timeout: 10_000 });

  await page.screenshot({ path: mailScreenshotPath, fullPage: false });
  const eventState = await page.evaluate(() => ({
    events: window.__naruonEvents,
    eventText: JSON.stringify(window.__naruonEvents),
  }));
  const requiredEvents = [
    "context_synthesis_viewed",
    "source_chip_opened",
    "draft_reply_generated",
    "draft_reply_inserted",
    "draft_reply_sent",
    "action_item_created",
    "calendar_reflected",
  ];
  for (const eventName of requiredEvents) {
    if (!eventState.events.some((event) => event.name === eventName)) {
      throw new Error(`Missing mail product event: ${eventName}`);
    }
  }
  assertNoSensitiveEventText(eventState.eventText, [sensitiveMailBody, sensitiveDraftBody]);
  await page.close();
  return requiredEvents;
}

async function runSearchFlow(context, consoleIssues, searchScreenshotPath) {
  const page = await preparePage(context, consoleIssues);
  await page.goto(new URL("/search", baseUrl).href, { waitUntil: "domcontentloaded" });

  const searchDetail = page.getByLabel("맥락 검색 결과 상세");
  await searchDetail.getByRole("heading", { name: "런칭 캠페인 결과" }).waitFor({ state: "visible", timeout: 20_000 });

  const searchInput = page.getByRole("searchbox", { name: "맥락 검색어 입력" });
  if (await searchInput.count() !== 1) throw new Error("Expected exactly one context search input");
  await searchInput.fill(rawSearchQuery);

  const searchForm = page.locator("form").filter({ has: searchInput });
  if (await searchForm.count() !== 1) throw new Error("Expected exactly one context search form");
  const submitButton = searchForm.getByRole("button", { name: "맥락 검색", exact: true });
  if (await submitButton.count() !== 1) throw new Error("Expected exactly one context search submit button");
  await submitButton.click();

  await searchDetail.getByRole("heading", { name: "계약 검토 결과" }).waitFor({ state: "visible", timeout: 20_000 });
  const captureButton = page.getByRole("button", { name: "발신자 관계 캡처" });
  await captureButton.waitFor({ state: "visible", timeout: 10_000 });
  if (await captureButton.count() !== 1) throw new Error("Expected exactly one relationship capture button");
  await captureButton.click();

  await page.getByText("계약 검토 담당자를 확인합니다.", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
  await page.screenshot({ path: searchScreenshotPath, fullPage: false });

  const eventState = await page.evaluate(() => ({
    events: window.__naruonEvents,
    eventText: JSON.stringify(window.__naruonEvents),
  }));
  const requiredEvents = [
    "context_search_submitted",
    "context_search_result_opened",
    "context_search_result_action_created",
  ];
  for (const eventName of requiredEvents) {
    if (!eventState.events.some((event) => event.name === eventName)) {
      throw new Error(`Missing search product event: ${eventName}`);
    }
  }
  assertNoSensitiveEventText(eventState.eventText, [rawSearchQuery]);
  await page.close();
  return requiredEvents;
}

async function main() {
  let serverProcess = null;
  let browser = null;
  try {
    const artifactDirectory = await createPilotArtifactDirectory(
      requestedMailScreenshot,
      requestedSearchScreenshot,
    );
    const mailScreenshotPath = resolvePilotArtifactPath(artifactDirectory, "mail.png");
    const searchScreenshotPath = resolvePilotArtifactPath(artifactDirectory, "search.png");
    serverProcess = await startServerIfNeeded();
    browser = await launchBrowser();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1024 } });
    const consoleIssues = [];

    const mailEvents = await runMailFlow(context, consoleIssues, mailScreenshotPath);
    const searchEvents = await runSearchFlow(context, consoleIssues, searchScreenshotPath);

    if (consoleIssues.length > 0) {
      throw new Error(`Console issues detected:\n${consoleIssues.join("\n")}`);
    }

    await context.close();
    log("Naruon pilot smoke passed.");
    log(`Mail events: ${mailEvents.join(", ")}`);
    log(`Search events: ${searchEvents.join(", ")}`);
    log(`Screenshots: ${mailScreenshotPath}, ${searchScreenshotPath}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (serverProcess) serverProcess.kill("SIGTERM");
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
