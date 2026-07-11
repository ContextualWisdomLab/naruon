/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  AlertCircle: () => <svg aria-hidden="true" />,
  BarChart3: () => <svg aria-hidden="true" />,
  CheckIcon: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Clock3: () => <svg aria-hidden="true" />,
  Code: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  History: () => <svg aria-hidden="true" />,
  LayoutTemplate: () => <svg aria-hidden="true" />,
  ListChecks: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" data-testid="loader" />,
  MoreHorizontal: () => <svg aria-hidden="true" />,
  Play: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  Rocket: () => <svg aria-hidden="true" />,
  Save: () => <svg aria-hidden="true" />,
  Share2: () => <svg aria-hidden="true" />,
  SlidersHorizontal: () => <svg aria-hidden="true" />,
  Sparkles: () => <svg aria-hidden="true" />,
  Variable: () => <svg aria-hidden="true" />,
}));

import PromptStudioPage from "./page";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function getButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(label),
  );
  expect(button).toBeInstanceOf(HTMLButtonElement);
  return button as HTMLButtonElement;
}

function setControlValue(control: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = control instanceof HTMLTextAreaElement
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  const valueSetter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  act(() => {
    valueSetter?.call(control, value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function defaultPromptTestSettings() {
  return {
    model: "gpt-4o",
    temperature: 0.3,
    response_style: "전문적이고 간결하게",
    output_format: "마크다운 (Markdown)",
  };
}

function lowerCaseHeaders(headers: HeadersInit | undefined) {
  if (!headers) return {};
  if (headers instanceof Headers) {
    return Object.fromEntries(
      Array.from(headers.entries()).map(([key, value]) => [
        key.toLowerCase(),
        value,
      ]),
    );
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(
      headers.map(([key, value]) => [key.toLowerCase(), value]),
    );
  }
  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]),
  );
}

function expectNoPublicIdentityHeaders(headers: HeadersInit | undefined) {
  const lowerHeaders = lowerCaseHeaders(headers);
  expect(lowerHeaders.authorization).toBeUndefined();
  for (const headerName of [
    "x-user-id",
    "x-organization-id",
    "x-group-id",
    "x-group-ids",
    "x-user-role",
    "x-dev-auth-token",
  ]) {
    expect(lowerHeaders[headerName]).toBeUndefined();
  }
}

describe("PromptStudioPage", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  async function renderPage() {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<PromptStudioPage />);
    });
    return container;
  }

  it("associates labels with editable prompt fields", async () => {
    const page = await renderPage();

    for (const fieldId of [
      "prompt-title",
      "prompt-description",
      "prompt-content",
      "prompt-variable-email",
      "is_shared",
    ]) {
      expect(page.querySelector(`#${fieldId}`)).not.toBeNull();
      expect(page.querySelector(`label[for="${fieldId}"]`)).not.toBeNull();
    }
  });

  it("renders the full Prompt Studio surface from the UI/UX reference", async () => {
    const page = await renderPage();

    for (const section of [
      "프롬프트 템플릿",
      "프롬프트 에디터",
      "모델 및 설정",
      "라이브 미리보기",
      "품질 체크리스트",
      "버전 히스토리",
      "최근 테스트 결과",
      "배포 이력",
      "활용 지표",
    ]) {
      expect(page.textContent).toContain(section);
    }
  });

  it("shows disabled loading feedback while testing a prompt", async () => {
    const promptTest = deferred<Response>();
    const fetchMock = vi.fn(() => promptTest.promise);
    vi.stubGlobal("fetch", fetchMock);
    const page = await renderPage();

    act(() => {
      getButton(page, "실행 (Test)").click();
    });

    expect(getButton(page, "테스트 중...").disabled).toBe(true);
    expect(page.querySelector("[data-testid='loader']")).not.toBeNull();

    await act(async () => {
      promptTest.resolve(jsonResponse({ result: "맥락 종합 결과" }));
      await promptTest.promise;
    });
    await flushAsyncWork();

    expect(getButton(page, "실행 (Test)").disabled).toBe(false);
    expect(page.textContent).toContain("맥락 종합 결과");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/prompts/test",
      expect.objectContaining({
        body: JSON.stringify({
          content: "핵심 맥락을 종합해주세요: {{email}}",
          variables: { email: "메일 내용 예시입니다." },
          settings: defaultPromptTestSettings(),
        }),
        credentials: "same-origin",
        method: "POST",
      }),
    );
    expectNoPublicIdentityHeaders((fetchMock.mock.calls[0] as unknown as [RequestInfo, RequestInit?])?.[1]?.headers);

    act(() => {
      getButton(page, "데이터 분석 인사이트").click();
    });
    expect(page.textContent).not.toContain("맥락 종합 결과");
  });

  it("loads a fresh sample input from the preview panel", async () => {
    const page = await renderPage();
    const variableInput = page.querySelector<HTMLTextAreaElement>("#prompt-variable-email");
    expect(variableInput).toBeInstanceOf(HTMLTextAreaElement);
    expect(variableInput?.value).toBe("메일 내용 예시입니다.");

    act(() => {
      getButton(page, "새 예시").click();
    });

    expect(variableInput?.value).toContain("지난 분기 매출");
  });

  it("shows disabled loading feedback while saving a prompt", async () => {
    const promptSave = deferred<Response>();
    const fetchMock = vi.fn(() => promptSave.promise);
    vi.stubGlobal("fetch", fetchMock);
    const page = await renderPage();
    setControlValue(page.querySelector<HTMLInputElement>("#prompt-title")!, "맥락 종합 프롬프트");

    act(() => {
      getButton(page, "프롬프트 저장 (Save)").click();
    });

    expect(getButton(page, "저장 중...").disabled).toBe(true);
    expect(page.querySelector("[data-testid='loader']")).not.toBeNull();

    await act(async () => {
      promptSave.resolve(jsonResponse({}));
      await promptSave.promise;
    });
    await flushAsyncWork();

    expect(getButton(page, "프롬프트 저장 (Save)").disabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/prompts",
      expect.objectContaining({
        body: JSON.stringify({
          title: "맥락 종합 프롬프트",
          description: null,
          content: "핵심 맥락을 종합해주세요: {{email}}",
          is_shared: false,
        }),
        credentials: "same-origin",
        method: "POST",
      }),
    );
    expectNoPublicIdentityHeaders((fetchMock.mock.calls[0] as unknown as [RequestInfo, RequestInit?])?.[1]?.headers);
    expect(page.textContent).toContain("AI 허브에서 실행 후보와 평가 근거로 연결됩니다.");
  });

  it("keeps prototype-like variable names as own payload fields", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ result: "안전한 실행 결과" })));
    vi.stubGlobal("fetch", fetchMock);
    const page = await renderPage();

    setControlValue(page.querySelector<HTMLTextAreaElement>("#prompt-content")!, "검토: {{__proto__}}");
    const variableInput = page.querySelector<HTMLTextAreaElement>("#prompt-variable-__proto__");
    expect(variableInput).toBeInstanceOf(HTMLTextAreaElement);
    expect(variableInput?.value).toBe("");

    setControlValue(variableInput!, "프로토타입 안전 값");
    act(() => {
      getButton(page, "실행 (Test)").click();
    });
    await flushAsyncWork();

    const requestInit = (fetchMock.mock.calls[0] as unknown as [RequestInfo, RequestInit])?.[1];
    const payload = JSON.parse(String(requestInit.body));
    expect(Object.prototype.hasOwnProperty.call(payload.variables, "__proto__")).toBe(true);
    expect(payload.variables["__proto__"]).toBe("프로토타입 안전 값");
    expectNoPublicIdentityHeaders(requestInit.headers);
  });

  it("blocks save before required prompt metadata is present", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const page = await renderPage();

    act(() => {
      getButton(page, "프롬프트 저장 (Save)").click();
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(page.querySelector("[role='alert']")?.textContent).toContain("프롬프트 이름을 입력하세요.");
  });
});
