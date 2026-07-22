"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { resolveOidcBrowserConfig, startOidcLogin } from "@/lib/oidc-session";

type AuthGateStatus = "checking" | "authenticated" | "unauthenticated";
type OidcAvailability = "checking" | "configured" | "missing";

// /auth/* must render without a session: the OIDC callback pages are exactly
// how an anonymous browser becomes authenticated.
const PUBLIC_PATH_PREFIX = "/auth";

async function probeSession(): Promise<boolean> {
  const response = await fetch("/auth/session", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) return false;
  const payload = (await response.json()) as {
    authenticated?: boolean;
    claims?: { userId?: string | null };
  };
  // The live route reports `authenticated`; older fixtures only carry claims,
  // so a concrete userId is accepted as equivalent session evidence.
  if (payload.authenticated === true) return true;
  return typeof payload.claims?.userId === "string" && payload.claims.userId.length > 0;
}

function SetupGuide() {
  return (
    <div className="space-y-4 text-left">
      <p className="text-sm text-muted-foreground">
        Naruon이 실행 중이지만 아직 로그인에 사용할 조직 계정(OIDC) 연결이
        없습니다. 연결이 끝나면 이 화면이 자동으로 로그인 버튼으로 바뀝니다.
      </p>
      <ol className="list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
        <li>조직 IdP(예: Keycloak, Entra ID)에 Naruon용 공개 클라이언트를 만듭니다.</li>
        <li>발급된 발급자 주소와 클라이언트 ID를 서버 환경 변수로 넣고 재시작합니다.</li>
        <li>이 페이지를 새로 고치면 로그인 버튼이 나타납니다.</li>
      </ol>
      <details className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        <summary className="cursor-pointer font-medium">운영자용 상세 설정</summary>
        <div className="mt-2 space-y-1">
          <p>
            frontend 컨테이너의 <strong>런타임 환경 변수</strong>로 설정하면 되며,
            이미지 재빌드는 필요 없습니다.
          </p>
          <pre className="overflow-x-auto rounded bg-background p-2">
{`NEXT_PUBLIC_OIDC_ISSUER_URL=https://idp.example.com/realms/<realm>
NEXT_PUBLIC_OIDC_CLIENT_ID=naruon-web`}
          </pre>
          <p>자세한 내용은 저장소의 docs/operations 문서를 참고하세요.</p>
        </div>
      </details>
    </div>
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPath = pathname?.startsWith(PUBLIC_PATH_PREFIX) ?? false;
  const [status, setStatus] = useState<AuthGateStatus>("checking");
  const [oidcAvailability, setOidcAvailability] = useState<OidcAvailability>("checking");
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

  useEffect(() => {
    if (isPublicPath || status !== "unauthenticated") return;
    let cancelled = false;
    resolveOidcBrowserConfig()
      .then((config) => {
        if (!cancelled) setOidcAvailability(config ? "configured" : "missing");
      })
      .catch(() => {
        if (!cancelled) setOidcAvailability("missing");
      });
    return () => {
      cancelled = true;
    };
  }, [isPublicPath, status]);

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
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-background">
        <p className="text-lg font-semibold tracking-tight">Naruon</p>
        <p className="text-sm text-muted-foreground" role="status">
          세션 확인 중…
        </p>
      </div>
    );
  }

  if (status === "unauthenticated") {
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
          {oidcAvailability === "checking" ? (
            <p className="text-sm text-muted-foreground" role="status">
              로그인 방법 확인 중…
            </p>
          ) : oidcAvailability === "configured" ? (
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
              <p className="text-xs text-muted-foreground">
                처음이신가요?{" "}
                <a
                  href="/auth/register"
                  className="font-medium text-primary hover:underline"
                >
                  회원가입
                </a>
              </p>
            </div>
          ) : (
            <SetupGuide />
          )}
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
