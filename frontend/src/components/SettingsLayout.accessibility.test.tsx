/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  Activity: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
  Bell: () => <svg aria-hidden="true" />,
  Bot: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Cpu: () => <svg aria-hidden="true" />,
  Mail: () => <svg aria-hidden="true" />,
  Monitor: () => <svg aria-hidden="true" />,
  Network: () => <svg aria-hidden="true" />,
  Plus: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  Settings: () => <svg aria-hidden="true" />,
  Shield: () => <svg aria-hidden="true" />,
  Smartphone: () => <svg aria-hidden="true" />,
  User: () => <svg aria-hidden="true" />,
}));

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

function deferredResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function accountConfigResponse() {
  return jsonResponse({
    user_id: "default",
    smtp_server: "smtp.example.com",
    smtp_port: 587,
    smtp_username: "sender@example.com",
    has_smtp_password: true,
    imap_server: "imap.example.com",
    imap_port: 993,
    imap_username: "inbox@example.com",
    has_imap_password: true,
    pop3_server: null,
    pop3_port: null,
    pop3_username: null,
    has_pop3_password: false,
    oauth_client_id: "oauth-client-id",
    oauth_redirect_uri: "https://naruon.net/oauth/mail/callback",
    has_oauth_client_secret: true,
  });
}

describe("SettingsLayout action availability accessibility", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;
  let accountRequest: ReturnType<typeof deferredResponse>;
  let sessionRequest: ReturnType<typeof deferredResponse>;

  beforeEach(() => {
    accountRequest = deferredResponse();
    sessionRequest = deferredResponse();
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
        if (url === "/auth/session") return sessionRequest.promise;
        if (url === "/api/accounts/config") return accountRequest.promise;
        if (url === "/api/calendar/writeback-sources") return jsonResponse([]);
        if (url === "/api/webdav/accounts") return jsonResponse([]);
        if (url === "/api/llm-providers") return jsonResponse([]);
        if (url === "/api/runner-config") {
          return jsonResponse({
            workspace_id: "workspace-org-acme",
            configured: false,
            fingerprint: null,
            updated_at: null,
            connector_manifest: {
              role: "self-hosted_connector",
              network_mode: "outbound_only",
              control_plane_domain: "naruon.net",
              local_protocols: [],
              prohibited_roles: [],
              runner_usage: "ci_smoke_only",
            },
          });
        }
        if (url === "/api/observability/operational-signals") {
          return jsonResponse({
            workspace_id: "workspace-org-acme",
            audit_event: "observability.operational_signals.viewed",
            telemetry: {
              prometheus_metrics_enabled: false,
              otel_traces_enabled: false,
              otel_endpoint_configured: false,
              otel_endpoint_host: null,
            },
            connector: {
              workspace_id: "workspace-org-acme",
              registration_state: "not_registered",
              connection_state: "not_connected",
              active_connection_count: 0,
              control_plane_domain: "naruon.net",
              network_mode: "outbound_only",
              runner_usage: "ci_smoke_only",
              local_protocols: [],
              last_heartbeat_at: null,
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
            signals: [],
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

  it("keeps unavailable account and logout actions focusable with state-specific next-action help", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<SettingsLayout />);
      await Promise.resolve();
      await Promise.resolve();
    });

    const accountTab = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "연결 계정",
    );
    await act(async () => {
      accountTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    const saveButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "계정 설정 저장",
    );
    expect(saveButton).toBeTruthy();
    expect(saveButton?.hasAttribute("disabled")).toBe(false);
    expect(saveButton?.getAttribute("aria-disabled")).toBe("true");
    expect(saveButton?.getAttribute("aria-describedby")).toBe("account-save-availability");
    expect(saveButton?.getAttribute("title")).toBeNull();
    expect(container.querySelector("#account-save-availability")?.textContent).toBe(
      "계정 설정을 불러오는 중입니다. 잠시 후 다시 시도하세요.",
    );

    await act(async () => {
      accountRequest.resolve(accountConfigResponse());
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(saveButton?.getAttribute("aria-disabled")).toBeNull();
    expect(saveButton?.getAttribute("aria-describedby")).toBeNull();
    expect(container.querySelector("#account-save-availability")).toBeNull();

    const developerTab = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "개발자",
    );
    await act(async () => {
      developerTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    const logoutButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "로그아웃",
    );
    expect(logoutButton).toBeTruthy();
    expect(logoutButton?.hasAttribute("disabled")).toBe(false);
    expect(logoutButton?.getAttribute("aria-disabled")).toBe("true");
    expect(logoutButton?.getAttribute("aria-describedby")).toBe("oidc-logout-availability");
    expect(logoutButton?.getAttribute("title")).toBeNull();
    expect(container.querySelector("#oidc-logout-availability")?.textContent).toBe(
      "로그인 세션을 확인하는 중입니다. 잠시 후 다시 시도하세요.",
    );

    await act(async () => {
      sessionRequest.resolve(jsonResponse({
        authenticated: true,
        claims: {
          userId: "alice",
          organizationId: "org-acme",
          workspaceId: "workspace-org-acme",
        },
      }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(logoutButton?.getAttribute("aria-disabled")).toBeNull();
    expect(logoutButton?.getAttribute("aria-describedby")).toBeNull();
    expect(container.querySelector("#oidc-logout-availability")).toBeNull();
  });
});
