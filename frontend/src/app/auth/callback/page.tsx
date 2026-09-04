"use client";

import type { OidcPopupResultMessage } from '@/lib/oidc-session';
import { broadcastOidcPopupResult, completeOidcRedirect, isOidcPopupFlow } from '@/lib/oidc-session';
import { useEffect, useState } from 'react';
import { toSafeReturnTo } from './return-target';

export default function AuthCallbackPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const { isPopup, flowId } = isOidcPopupFlow();
    completeOidcRedirect()
      .then(({ returnTo }) => {
        if (cancelled) return;
        const safeTarget = toSafeReturnTo(returnTo);
        if (isPopup && flowId) {
          const message: OidcPopupResultMessage = { source: 'naruon-oidc', flowId, status: 'success', returnTo: safeTarget };
          broadcastOidcPopupResult(message);
          window.close();
          return;
        }
        window.location.replace(safeTarget);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'OIDC callback failed';
        setError(message);
        if (isPopup && flowId) {
          const popupMessage: OidcPopupResultMessage = { source: 'naruon-oidc', flowId, status: 'error', message };
          broadcastOidcPopupResult(popupMessage);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <section aria-label="OIDC 로그인 콜백" className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-sm">
        <h1 className="text-lg font-bold text-foreground">OIDC 로그인 확인</h1>
        {error ? (
          <p role="alert" className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</p>
        ) : (
          <p role="status" className="mt-3 text-sm font-semibold text-muted-foreground">세션을 확인하는 중입니다.</p>
        )}
      </section>
    </main>
  );
}
