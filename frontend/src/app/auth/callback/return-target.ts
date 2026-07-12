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

    let decoded = candidate;
    try {
      decoded = decodeURIComponent(candidate);
    } catch {
      return "/";
    }

    if (/[\u0000-\u001f\u007f\\]/.test(decoded)) {
      return "/";
    }

    // Reject paths that did not start local before URL normalization.
    if (!candidate.startsWith("/")) {
      return "/";
    }

    if (decoded.startsWith("//") || decoded.startsWith("/\\")) {
      return "/";
    }

    const safePath = url.pathname + url.search + url.hash;

    if (!safePath.startsWith("/") || safePath.startsWith("//")) {
      return "/";
    }

    return safePath;
  } catch {
    return "/";
  }
}
