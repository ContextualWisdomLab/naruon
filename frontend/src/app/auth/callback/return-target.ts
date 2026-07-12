export function toSafeReturnTo(returnTo: string | null | undefined) {
  try {
    const candidate = returnTo?.trim() ?? "";
    if (!candidate) return "/";

    const url = new URL(candidate, "http://localhost");

    if (url.origin !== "http://localhost") {
      return "/";
    }

    if (/[\u0000-\u001f\u007f\\]/.test(candidate)) {
      return "/";
    }

    // Reject paths that did not start local before URL normalization.
    if (!candidate.startsWith("/")) {
      return "/";
    }

    const safePath = url.pathname + url.search + url.hash;
    const decodedSafePath = decodeURIComponent(safePath);

    if (
      !safePath.startsWith("/") ||
      safePath.startsWith("//") ||
      decodedSafePath.startsWith("//") ||
      /[\u0000-\u001f\u007f\\]/.test(decodedSafePath)
    ) {
      return "/";
    }

    return safePath;
  } catch {
    return "/";
  }
}
