/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUsePathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

const mockStartOidcLogin = vi.fn(async (_options: unknown) => {});
const mockGetOidcBrowserConfig = vi.fn(() => ({}) as unknown);
vi.mock("@/lib/oidc-session", () => ({
  startOidcLogin: (options: unknown) => mockStartOidcLogin(options),
  getOidcBrowserConfig: () => mockGetOidcBrowserConfig(),
}));

import { AuthGate } from "./AuthGate";

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

function sessionResponse(authenticated: boolean) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ authenticated }),
  } as Response;
}

describe("AuthGate", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockUsePathname.mockReturnValue("/");
    mockGetOidcBrowserConfig.mockReturnValue({});
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    mockStartOidcLogin.mockClear();
  });

  it("shows the login screen instead of children when the session is anonymous", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sessionResponse(false)),
    );

    await act(async () => {
      root.render(
        <AuthGate>
          <div data-testid="protected">protected content</div>
        </AuthGate>,
      );
    });
    await flushAsyncWork();

    expect(container.querySelector('[data-testid="protected"]')).toBeNull();
    expect(container.textContent).toContain("로그인");
    const loginButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("로그인"),
    );
    expect(loginButton).toBeTruthy();

    await act(async () => {
      loginButton!.click();
    });
    expect(mockStartOidcLogin).toHaveBeenCalledTimes(1);
  });

  it("renders children once the session is authenticated", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sessionResponse(true)),
    );

    await act(async () => {
      root.render(
        <AuthGate>
          <div data-testid="protected">protected content</div>
        </AuthGate>,
      );
    });
    await flushAsyncWork();

    expect(container.querySelector('[data-testid="protected"]')).not.toBeNull();
  });

  it("does not fire data requests or block rendering on /auth paths", async () => {
    mockUsePathname.mockReturnValue("/auth/callback");
    const fetchSpy = vi.fn(async () => sessionResponse(false));
    vi.stubGlobal("fetch", fetchSpy);

    await act(async () => {
      root.render(
        <AuthGate>
          <div data-testid="callback">callback page</div>
        </AuthGate>,
      );
    });
    await flushAsyncWork();

    expect(container.querySelector('[data-testid="callback"]')).not.toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("explains how to enable login when the OIDC browser config is missing", async () => {
    mockGetOidcBrowserConfig.mockReturnValue(null);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sessionResponse(false)),
    );

    await act(async () => {
      root.render(
        <AuthGate>
          <div data-testid="protected">protected content</div>
        </AuthGate>,
      );
    });
    await flushAsyncWork();

    expect(container.querySelector('[data-testid="protected"]')).toBeNull();
    expect(container.textContent).toContain("NEXT_PUBLIC_OIDC");
  });

  it("keeps children hidden and shows the login screen when the session probe fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );

    await act(async () => {
      root.render(
        <AuthGate>
          <div data-testid="protected">protected content</div>
        </AuthGate>,
      );
    });
    await flushAsyncWork();

    expect(container.querySelector('[data-testid="protected"]')).toBeNull();
    expect(container.textContent).toContain("로그인");
  });
});
