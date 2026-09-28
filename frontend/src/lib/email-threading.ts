export interface ThreadEmailData {
  id: number;
  subject: string | null;
  sender: string;
  reply_to?: string | null;
  body: string;
  date?: string | null;
  thread_id?: string | null;
  message_id?: string | null;
  in_reply_to?: string | null;
  references?: string | null;
  thread_evidence?: Array<{
    source: "in_reply_to" | "references";
    ordinal: number;
    state: "resolved" | "unresolved" | "ambiguous" | "conflicting" | "incomplete" | "detached";
    target_message_id: string | null;
    target_email_id: number | null;
  }>;
}

export interface ReplyPayload {
  to: string;
  subject: string;
  body: string;
  in_reply_to?: string;
  references?: string;
}

export type ReplyEvidence = {
  source: "In-Reply-To" | "References" | "In-Reply-To, References";
  state: "found" | "missing" | "outside_thread" | "conflicting" | "incomplete" | "detached";
  targetEmailId?: number;
};

function headerMessageIds(value?: string | null): string[] {
  if (!value) return [];
  const bounded = value.slice(0, 8192);
  const tokens = bounded.match(/<[^>]+>/g) ?? bounded.split(/\s+/);
  return tokens
    .map((token) => token.replace(/^<|>$/g, "").replace(/\s+/g, ""))
    .filter(Boolean);
}

export function getReplyEvidence(
  email: ThreadEmailData,
  threadEmails: ThreadEmailData[],
): ReplyEvidence | null {
  if (email.thread_evidence?.length) {
    const active = email.thread_evidence.filter((edge) => edge.state !== "detached");
    const direct = active.filter((edge) => edge.source === "in_reply_to");
    const candidates = direct.length
      ? direct
      : active.filter((edge) => edge.source === "references")
          .sort((left, right) => right.ordinal - left.ordinal).slice(0, 1);
    const selected = candidates[0] ?? email.thread_evidence[0];
    const source = active.some((edge) => edge.source === "in_reply_to")
      && active.some((edge) => edge.source === "references")
      ? "In-Reply-To, References"
      : selected.source === "in_reply_to" ? "In-Reply-To" : "References";
    if (candidates.length > 1 || candidates.some((edge) => edge.state === "conflicting" || edge.state === "ambiguous")) {
      return { source, state: "conflicting" };
    }
    if (selected.state === "detached") return { source, state: "detached" };
    if (selected.state === "incomplete") return { source, state: "incomplete" };
    if (selected.state === "unresolved") return { source, state: "missing" };
    const targetEmailId = selected.target_email_id;
    return targetEmailId && threadEmails.some((candidate) => candidate.id === targetEmailId)
      ? { source, state: "found", targetEmailId }
      : { source, state: "outside_thread" };
  }
  const replyIds = headerMessageIds(email.in_reply_to);
  const references = headerMessageIds(email.references);
  const hasReply = Boolean(email.in_reply_to?.trim());
  const hasReferences = Boolean(email.references?.trim());
  if (!hasReply && !hasReferences) return null;

  const referenceId = references.at(-1);
  const source = hasReply && hasReferences
    ? "In-Reply-To, References"
    : hasReply ? "In-Reply-To" : "References";
  if (
    (email.in_reply_to?.length ?? 0) > 8192 ||
    (email.references?.length ?? 0) > 8192 ||
    replyIds.length > 64 || references.length > 64 || (!replyIds.length && !references.length)
  ) {
    return { source, state: "incomplete" };
  }
  if (replyIds.length > 1 || (replyIds.length && referenceId && replyIds[0] !== referenceId)) {
    return { source, state: "conflicting" };
  }

  const targetId = replyIds[0] ?? referenceId;
  const target = targetId && threadEmails.find((candidate) =>
    candidate.id !== email.id && headerMessageIds(candidate.message_id).includes(targetId),
  );
  return target
    ? { source, state: "found", targetEmailId: target.id }
    : { source, state: "missing" };
}

function extractMailbox(value: string): string {
  const angleMatch = value.match(/<([^>]+)>/);
  return (angleMatch?.[1] ?? value).trim();
}

function buildReferences(email: ThreadEmailData): string | undefined {
  const references = email.references?.trim();
  const messageId = email.message_id?.trim();

  if (!references) return messageId || undefined;
  if (!messageId) return references;

  const normalizedMessageId = messageId.replace(/^<|>$/g, "");
  const referenceTokens =
    references.match(/<[^>]+>/g)?.map((token) => token.replace(/^<|>$/g, "")) ??
    references.split(/\s+/).map((token) => token.replace(/^<|>$/g, ""));

  if (referenceTokens.includes(normalizedMessageId)) return references;

  return `${references} ${messageId}`;
}

export function formatEmailDate(value?: string | null): string {
  if (!value) return "Unknown date";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";

  return date.toLocaleString();
}

export function buildThreadUrl(apiUrl: string, threadId: string): string {
  // If no base URL is required (handled by apiClient), return relative path
  if (!apiUrl) {
    return `/api/emails/thread/${encodeURIComponent(threadId)}`;
  }
  return `${apiUrl}/api/emails/thread/${encodeURIComponent(threadId)}`;
}

export function getConversationMessages<T extends ThreadEmailData>(
  selectedEmail: T,
  threadEmails: T[],
): T[] {
  const hasSelectedEmail = threadEmails.some(
    (threadEmail) =>
      threadEmail.id === selectedEmail.id ||
      (!!selectedEmail.message_id && threadEmail.message_id === selectedEmail.message_id),
  );

  return hasSelectedEmail ? threadEmails : [selectedEmail];
}

export function buildReplyPayload(
  email: ThreadEmailData,
  draft: string,
): ReplyPayload {
  const to = email.reply_to?.trim()
    ? extractMailbox(email.reply_to)
    : extractMailbox(email.sender);
  const subject = email.subject?.startsWith("Re:")
    ? email.subject
    : `Re: ${email.subject || ""}`;
  const references = buildReferences(email);

  return {
    to,
    subject,
    body: draft,
    in_reply_to: email.message_id || undefined,
    references,
  };
}
