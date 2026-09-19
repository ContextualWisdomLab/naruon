import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const settingsLayoutSource = readFileSync(
  fileURLToPath(new URL("./SettingsLayout.tsx", import.meta.url)),
  "utf8",
);

function sourceBetween(startMarker: string, endMarker: string): string {
  const startIndex = settingsLayoutSource.indexOf(startMarker);
  const endIndex = settingsLayoutSource.indexOf(endMarker, startIndex);

  expect(startIndex).toBeGreaterThanOrEqual(0);
  expect(endIndex).toBeGreaterThan(startIndex);

  return settingsLayoutSource.slice(startIndex, endIndex);
}

describe("SettingsLayout OIDC pending feedback contract", () => {
  it("sets and clears login/logout pending state around the actual async calls", () => {
    const loginHandler = sourceBetween(
      "const handleOidcLogin = async () => {",
      "const handleOidcLogout = async () => {",
    );
    const logoutHandler = sourceBetween(
      "const handleOidcLogout = async () => {",
      "const handleAccountSave = async",
    );

    expect(loginHandler).toContain("setOidcLoginPending(true)");
    expect(loginHandler).toContain("await startOidcLogin({ returnTo: window.location.pathname })");
    expect(loginHandler).toContain("finally");
    expect(loginHandler).toContain("setOidcLoginPending(false)");

    expect(logoutHandler).toContain("setOidcLogoutPending(true)");
    expect(logoutHandler).toContain("await clearOidcSession({ postLogoutRedirectUri: window.location.origin })");
    expect(logoutHandler).toContain("finally");
    expect(logoutHandler).toContain("setOidcLogoutPending(false)");
  });

  it("binds pending state to duplicate-click prevention, aria-busy, spinner, and visible labels", () => {
    const oidcSection = sourceBetween(
      '<section aria-label="OIDC 인증 세션"',
      "{oidcActionError ? (",
    );

    expect(oidcSection).toContain("disabled={!oidcBrowserConfig || oidcLoginPending}");
    expect(oidcSection).toContain("aria-busy={oidcLoginPending}");
    expect(oidcSection).toContain("{oidcLoginPending && <Loader2");
    expect(oidcSection).toContain("{oidcLoginPending ? '로그인 중' : 'OIDC 로그인'}");

    expect(oidcSection).toContain("disabled={!oidcSessionClaims.userId || oidcLogoutPending}");
    expect(oidcSection).toContain("aria-busy={oidcLogoutPending}");
    expect(oidcSection).toContain("{oidcLogoutPending && <Loader2");
    expect(oidcSection).toContain("{oidcLogoutPending ? '로그아웃 중' : '로그아웃'}");

    expect(oidcSection).not.toContain("aria-disabled={oidcLoginPending}");
    expect(oidcSection).not.toContain("aria-disabled={oidcLogoutPending}");
  });
});
