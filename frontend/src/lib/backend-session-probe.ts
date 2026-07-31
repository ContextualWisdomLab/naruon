import { fetchTrustedBackend } from "@/lib/backend-request";
import { trustedBackendOrigin } from "@/lib/backend-url";

const BACKEND_SESSION_PROBE_TIMEOUT_MS = 15_000;

export async function fetchTrustedBackendSession(
  token: string,
): Promise<unknown | null> {
  try {
    const target = new URL("/api/auth/session", trustedBackendOrigin());
    const response = await fetchTrustedBackend(target, {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(BACKEND_SESSION_PROBE_TIMEOUT_MS),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
