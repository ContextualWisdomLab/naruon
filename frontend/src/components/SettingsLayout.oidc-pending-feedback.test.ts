/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", async () => {
  const { createElement } = await import("react");
  const HiddenIcon = () => createElement("svg", { "aria-hidden": "true" });
  return {
    Activity: HiddenIcon,
    AlertCircle: HiddenIcon,
    Loader2: HiddenIcon,
    Bell: HiddenIcon,
    Bot: HiddenIcon,
    CheckCircle2: HiddenIcon,
    Cpu: HiddenIcon,
    Mail: HiddenIcon,
    Monitor: HiddenIcon,
    Network: HiddenIcon,
    Plus: HiddenIcon,
    RefreshCw: HiddenIcon,
    Settings: HiddenIcon,
    Shield: HiddenIcon,
    Smartphone: HiddenIcon,
    User: HiddenIcon,
  };
});

const oidcMocks = vi.hoisted(() => ({
  clearOidcSession: vi.fn(),
  getOidcBrowserConfig: vi.fn(),
  startOidcLogin: vi.fn(),
}));

vi.mock("@/lib/oidc-session", () => ({
  clearOidcSession: oidcMocks.clearOidcSession,
  getOidcBrowserConfig: oidcMocks.getOidcBrowserConfig,
  startOidcLogin: oidcMocks.startOidcLogin,
}));

import { SettingsLayout } from "./SettingsLayout";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function buttonByText(container: HTMLElement, label: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll<HTMLButtonElement>("button")).find(
    (candidate) => candidate.textContent === label,
  );
  expect(button, `button ${label}`).toBeTruthy();
  return button as HTMLButtonElement;
}

describe("SettingsLayout OIDC pending feedback", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  beforeEach(() => {
    window.history.pushState({}, "", "/settings");
    oidcMocks.getOidcBrowserConfig.mockReturnValue({
      issuerUrl: "https://login.example.com/realms/naruon",
      clientId: "naruon-web",
      redirectUri: "https://app.example.com/auth/callback",
      scope: "openid profile email",
      authorizationEndpoint: "https://login.example.com/realms/naruon/protocol/openid-connect/auth",
      tokenEndpoint: "https://login.example.com/realms/naruon/protocol/openid-connect/token",
      endSessionEndpoint: "https://login.example.com/realms/naruon/protocol/openid-connect/logout",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/auth/session") {
          return jsonResponse({
            authenticated: true,
            claims: {
              userId: "alice",
              organizationId: "org-acme",
              workspaceId: "workspace-org-acme",
            },
          });
        }
        if (url === "/api/runner-config") {
          return jsonResponse({
            workspace_id: "workspace-org-acme",
            configured: true,
            fingerprint: "***abc12345",
            updated_at: "2026-09-19T01:00:00Z",
            connector_manifest: {
              role: "self-hosted_connector",
              network_mode: "outbound_only",
              control_plane_domain: "naruon.net",
              local_protocols: ["imap", "pop3", "smtp", "caldav", "carddav", "webdav"],
              prohibited_roles: ["smtp_server", "imap_server", "mx_host"],
              runner_usage: "ci_smoke_only",
            },
          });
        }
        if (url === "/api/observability/operational-signals") {
          return jsonResponse({
            workspace_id: "workspace-org-acme",
            audit_event: "observability.operational_signals.viewed",
            telemetry: {
              prometheus_metrics_enabled: true,
              otel_traces_enabled: true,
              otel_endpoint_configured: false,
              otel_endpoint_host: null,
            },
            connector: {
              workspace_id: "workspace-org-acme",
              registration_state: "registration_configured",
              connection_state: "connected",
              active_connection_count: 1,
              control_plane_domain: "naruon.net",
              network_mode: "outbound_only",
              runner_usage: "ci_smoke_only",
              local_protocols: ["imap", "pop3", "smtp", "caldav", "carddav", "webdav"],
              last_heartbeat_at: "2026-09-19T01:00:00Z",
              last_disconnect_at: null,
              queue_depth_state: "healthy",
              queue_depth: {
                pending_count: 0,
                running_count: 0,
                failed_count: 0,
                total_count: 0,
                next_retry_at: null,
              },
              recent_events: [],
            },
            signals: [],
          });
        }
        if (url === "/api/calendar/writeback-sources" || url === "/api/webdav/accounts") {
          return jsonResponse([]);
        }
        if (url === "/api/llm-providers") {
          return jsonResponse([]);
        }
        if (url === "/api/accounts/config") {
          return jsonResponse({
            user_id: "default",
            smtp_server: "",
            smtp_port: 587,
            smtp_username: "",
            has_smtp_password: false,
            imap_server: "",
            imap_port: 993,
            imap_username: "",
            has_imap_password: false,
            pop3_server: "",
            pop3_port: 995,
            pop3_username: "",
            has_pop3_password: false,
            oauth_client_id: "",
            oauth_redirect_uri: "",
            has_oauth_client_secret: false,
          });
        }
        return jsonResponse({});
      }),
    );
  });

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  async function renderDeveloperSettings() {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(React.createElement(SettingsLayout));
      await Promise.resolve();
      await Promise.resolve();
    });

    const developerTab = buttonByText(container, "개발자");
    await act(async () => {
      developerTab.click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("OIDC 인증 세션");
    return container;
  }

  it("renders login pending state, blocks duplicate activation, and restores the control", async () => {
    const pendingLogin = deferred<void>();
    oidcMocks.startOidcLogin.mockReturnValue(pendingLogin.promise);
    const rendered = await renderDeveloperSettings();

    const loginButton = buttonByText(rendered, "OIDC 로그인");
    await act(async () => {
      loginButton.click();
      await Promise.resolve();
    });

    const pendingButton = buttonByText(rendered, "로그인 중");
    expect(pendingButton.disabled).toBe(true);
    expect(pendingButton.getAttribute("aria-busy")).toBe("true");
    expect(pendingButton.querySelector('svg[aria-hidden="true"]')).toBeTruthy();
    expect(oidcMocks.startOidcLogin).toHaveBeenCalledTimes(1);
    expect(oidcMocks.startOidcLogin).toHaveBeenCalledWith({ returnTo: "/settings" });

    await act(async () => {
      pendingButton.click();
      await Promise.resolve();
    });
    expect(oidcMocks.startOidcLogin).toHaveBeenCalledTimes(1);

    await act(async () => {
      pendingLogin.resolve(undefined);
      await pendingLogin.promise;
      await Promise.resolve();
    });

    const restoredButton = buttonByText(rendered, "OIDC 로그인");
    expect(restoredButton.disabled).toBe(false);
    expect(restoredButton.getAttribute("aria-busy")).toBe("false");
  });

  it("clears logout pending state and surfaces the error after a rejected request", async () => {
    const pendingLogout = deferred<void>();
    oidcMocks.clearOidcSession.mockReturnValue(pendingLogout.promise);
    const rendered = await renderDeveloperSettings();

    const logoutButton = buttonByText(rendered, "로그아웃");
    await act(async () => {
      logoutButton.click();
      await Promise.resolve();
    });

    const pendingButton = buttonByText(rendered, "로그아웃 중");
    expect(pendingButton.disabled).toBe(true);
    expect(pendingButton.getAttribute("aria-busy")).toBe("true");
    expect(pendingButton.querySelector('svg[aria-hidden="true"]')).toBeTruthy();
    expect(oidcMocks.clearOidcSession).toHaveBeenCalledTimes(1);
    expect(oidcMocks.clearOidcSession).toHaveBeenCalledWith({
      postLogoutRedirectUri: "http://localhost:3000",
    });

    await act(async () => {
      pendingLogout.reject(new Error("provider logout failed"));
      await Promise.resolve();
      await Promise.resolve();
    });

    const restoredButton = buttonByText(rendered, "로그아웃");
    expect(restoredButton.disabled).toBe(false);
    expect(restoredButton.getAttribute("aria-busy")).toBe("false");
    expect(rendered.textContent).toContain("provider logout failed");
  });
});
