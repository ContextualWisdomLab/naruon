/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockStartOidcLogin = vi.fn(async (options: unknown) => {
  void options;
});
vi.mock("@/lib/oidc-session", () => ({
  startOidcLogin: (options: unknown) => mockStartOidcLogin(options),
}));

import RegisterPage from "./page";

async function flushAsyncWork() {
  for (let round = 0; round < 3; round += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function fillInput(container: HTMLElement, id: string, value: string) {
  const input = container.querySelector<HTMLInputElement>(`#${id}`)!;
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  )!.set!;
  nativeSetter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("RegisterPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(<RegisterPage />);
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    mockStartOidcLogin.mockClear();
  });

  async function submitValidForm() {
    fillInput(container, "register-email", "new.user@example.com");
    fillInput(container, "register-name", "홍 길동");
    fillInput(container, "register-password", "bootstrap-pass-1");
    fillInput(container, "register-password-confirm", "bootstrap-pass-1");
    await act(async () => {
      container.querySelector("form")!.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );
    });
    await flushAsyncWork();
  }

  it("submits the signup to the same-origin relay and offers passkey login", async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ email_address: "new.user@example.com" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await submitValidForm();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/auth/register/submit");
    const payload = JSON.parse(String(init.body));
    expect(payload.email_address).toBe("new.user@example.com");
    expect(payload.first_name).toBe("홍");
    expect(payload.last_name).toBe("길동");
    expect(container.textContent).toContain("가입 완료");

    const continueButton = Array.from(
      container.querySelectorAll("button"),
    ).find((button) => button.textContent?.includes("패스키"));
    await act(async () => {
      continueButton!.click();
    });
    expect(mockStartOidcLogin).toHaveBeenCalledTimes(1);
  });

  it("shows the duplicate-email message from the deterministic error code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: { error_code: "email_already_registered" } }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await submitValidForm();

    expect(container.textContent).toContain("이미 등록된 이메일");
  });

  it("blocks mismatched passwords before any network call", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    fillInput(container, "register-email", "new.user@example.com");
    fillInput(container, "register-password", "bootstrap-pass-1");
    fillInput(container, "register-password-confirm", "different-pass-2");

    await act(async () => {
      container.querySelector("form")!.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(container.textContent).toContain("비밀번호가 서로 다릅니다");
  });
});
