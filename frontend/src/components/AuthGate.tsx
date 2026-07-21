"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { getOidcBrowserConfig, startOidcLogin } from "@/lib/oidc-session";

type AuthGateStatus = "checking" | "authenticated" | "unauthenticated";

// /auth/* must render without a session: the OIDC callback pages are exactly
// how an anonymous browser becomes authenticated.
const PUBLIC_PATH_PREFIX = "/auth";

async function probeSession(): Promise<boolean> {
  const response = await fetch("/auth/session", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) return false;
  const payload = (await response.json()) as { authenticated?: boolean };
  return payload.authenticated === true;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPath = pathname?.startsWith(PUBLIC_PATH_PREFIX) ?? false;
  const [status, setStatus] = useState<AuthGateStatus>("checking");
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    if (isPublicPath) return;
    let cancelled = false;
    probeSession()
      .then((authenticated) => {
        if (!cancelled) setStatus(authenticated ? "authenticated" : "unauthenticated");
      })
      .catch(() => {
        if (!cancelled) setStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, [isPublicPath, pathname]);

  const handleLogin = useCallback(async () => {
    setLoginError(null);
    try {
      await startOidcLogin({ returnTo: pathname ?? "/" });
    } catch (error) {
      setLoginError(
        error instanceof Error ? error.message : "로그인을 시작하지 못했습니다.",
      );
    }
  }, [pathname]);

  if (isPublicPath) return <>{children}</>;

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground" role="status">
          세션 확인 중…
        </p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    const oidcConfigured = getOidcBrowserConfig() !== null;
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-sm space-y-6 text-center">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Naruon</h1>
            <p className="text-sm text-muted-foreground">
              메일, 일정, 관계, 판단 포인트를 하나의 맥락으로 연결하는 AI 메일
              워크스페이스
            </p>
          </div>
          {oidcConfigured ? (
            <div className="space-y-3">
              <button
                type="button"
                onClick={handleLogin}
                className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                조직 계정으로 로그인
              </button>
              <p className="text-xs text-muted-foreground">
                조직 IdP(OIDC)로 이동해 패스키 또는 조직 자격 증명으로 로그인합니다.
              </p>
              {loginError ? (
                <p className="text-xs text-destructive" role="alert">
                  {loginError}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              로그인 구성이 없습니다. 운영자가 NEXT_PUBLIC_OIDC_ISSUER_URL과
              NEXT_PUBLIC_OIDC_CLIENT_ID를 빌드에 주입해야 합니다.
            </p>
          )}
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
