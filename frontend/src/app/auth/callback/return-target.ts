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

    // Security check: Decode candidate explicitly to prevent bypass of prefix checks
    // using URL-encoded sequences (e.g. /%5C%5C or /%2F%2F) that browsers evaluate as scheme-relative
    let decoded: string;
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

    // Reject decoded variants of protocol-relative payloads
    if (decoded.startsWith("//") || decoded.startsWith("/\\")) {
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
