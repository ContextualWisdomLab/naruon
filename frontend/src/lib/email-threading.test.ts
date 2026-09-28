import { describe, expect, it } from "vitest";

import {
  buildThreadUrl,
  buildReplyPayload,
  formatEmailDate,
  getConversationMessages,
  getReplyEvidence,
} from "./email-threading";

const baseEmail = {
  id: 1,
  subject: "Quarterly plan",
  sender: "Alice Example <alice@example.com>",
  reply_to: "reply@example.com",
  body: "Root body",
  date: "2026-04-27T10:00:00Z",
  thread_id: "root@example.com",
  message_id: "<root@example.com>",
  references: "<root@example.com>",
};

describe("email threading UI helpers", () => {
  it("shows source-backed reply evidence and keeps missing or conflicting targets explicit", () => {
    const reply = {
      ...baseEmail,
      id: 2,
      message_id: "<reply@example.com>",
      in_reply_to: "<root@example.com>",
    };
    expect(getReplyEvidence(reply, [baseEmail, reply])).toEqual({
      source: "In-Reply-To, References",
      state: "found",
      targetEmailId: 1,
    });
    expect(getReplyEvidence(reply, [reply])?.state).toBe("missing");
    expect(getReplyEvidence({ ...reply, references: "<other@example.com>" }, [baseEmail, reply])?.state)
      .toBe("conflicting");
    expect(getReplyEvidence({ ...reply, references: "<root@example.com>".repeat(65) }, [baseEmail, reply])?.state)
      .toBe("incomplete");
  });
  it("uses stored relationship state before interpreting the original headers", () => {
    const reply = {
      ...baseEmail,
      id: 2,
      message_id: "reply@example.com",
      in_reply_to: "<root@example.com>",
      thread_evidence: [{
        source: "in_reply_to" as const,
        ordinal: 0,
        state: "detached" as const,
        target_message_id: "root@example.com",
        target_email_id: 1,
      }],
    };
    expect(getReplyEvidence(reply, [baseEmail, reply])?.state).toBe("detached");
    const resolved = { ...reply, thread_evidence: [{ ...reply.thread_evidence[0], state: "resolved" as const }] };
    expect(getReplyEvidence(resolved, [baseEmail, resolved])?.targetEmailId).toBe(1);
    expect(getReplyEvidence(resolved, [resolved])?.state).toBe("outside_thread");
    const ambiguous = { ...reply, thread_evidence: [{ ...reply.thread_evidence[0], state: "ambiguous" as const, target_email_id: null }] };
    expect(getReplyEvidence(ambiguous, [baseEmail, ambiguous])?.state).toBe("ambiguous");
  });
  it("builds a reply payload with safe recipient and threading headers", () => {
    expect(buildReplyPayload(baseEmail, "Thanks")).toEqual({
      to: "reply@example.com",
      subject: "Re: Quarterly plan",
      body: "Thanks",
      in_reply_to: "<root@example.com>",
      references: "<root@example.com>",
    });
  });

  it("extracts the mailbox from display-name Reply-To headers", () => {
    const emailWithDisplayReplyTo = {
      ...baseEmail,
      reply_to: "Alice Replies <alice-replies@example.com>",
    };

    expect(buildReplyPayload(emailWithDisplayReplyTo, "Thanks").to).toBe(
      "alice-replies@example.com",
    );
  });

  it("appends the selected message id to existing references", () => {
    const replyEmail = {
      ...baseEmail,
      message_id: "<reply@example.com>",
      references: "<root@example.com>",
    };

    expect(buildReplyPayload(replyEmail, "Thanks").references).toBe(
      "<root@example.com> <reply@example.com>",
    );
  });

  it("uses exact reference tokens when deciding whether to append the selected message id", () => {
    const replyEmail = {
      ...baseEmail,
      message_id: "reply@example.com",
      references: "<parent-reply@example.com>",
    };

    expect(buildReplyPayload(replyEmail, "Thanks").references).toBe(
      "<parent-reply@example.com> reply@example.com",
    );
  });

  it("falls back to sender mailbox when Reply-To is absent", () => {
    const emailWithoutReplyTo = { ...baseEmail, reply_to: undefined };

    expect(buildReplyPayload(emailWithoutReplyTo, "Thanks").to).toBe(
      "alice@example.com",
    );
  });

  it("falls back to the selected email when the thread response is empty", () => {
    expect(getConversationMessages(baseEmail, [])).toEqual([baseEmail]);
  });

  it("falls back to the selected email when a stale thread response is for another message", () => {
    const staleThread = [{ ...baseEmail, id: 2, message_id: "<other@example.com>" }];

    expect(getConversationMessages(baseEmail, staleThread)).toEqual([baseEmail]);
  });

  it("returns a stable label for invalid or missing dates", () => {
    expect(formatEmailDate(undefined)).toBe("Unknown date");
    expect(formatEmailDate("not-a-date")).toBe("Unknown date");
  });

  it("encodes reserved characters in thread URLs", () => {
    expect(buildThreadUrl("http://localhost:8000", "root/part?x@example.com")).toBe(
      "http://localhost:8000/api/emails/thread/root%2Fpart%3Fx%40example.com",
    );
  });

  it("builds a full reply payload when subject is empty", () => {
    const emptySubjectEmail = {
      ...baseEmail,
      subject: null,
    };
    expect(buildReplyPayload(emptySubjectEmail, "Thanks")).toEqual({
      to: "reply@example.com",
      subject: "Re: ",
      body: "Thanks",
      in_reply_to: "<root@example.com>",
      references: "<root@example.com>",
    });
  });

  it("uses whitespace to split reference tokens if there are no angle brackets", () => {
    const replyEmail = {
      ...baseEmail,
      message_id: "<reply@example.com>",
      references: "root@example.com parent-reply@example.com",
    };
    expect(buildReplyPayload(replyEmail, "Thanks").references).toBe(
      "root@example.com parent-reply@example.com <reply@example.com>",
    );
  });

  it("returns formatted date for a valid date string", () => {
    const testDate = "2026-04-27T10:00:00Z";
    expect(formatEmailDate(testDate)).toBe(new Date(testDate).toLocaleString());
  });

  it("returns relative thread URL if apiUrl is empty", () => {
    expect(buildThreadUrl("", "threadId")).toBe("/api/emails/thread/threadId");
  });

  it("returns messageId if references is missing", () => {
    const noRefEmail = { ...baseEmail, references: undefined };
    expect(buildReplyPayload(noRefEmail, "Thanks").references).toBe("<root@example.com>");
  });

  it("returns undefined if both references and messageId are missing", () => {
    const noRefNoIdEmail = { ...baseEmail, references: undefined, message_id: undefined };
    expect(buildReplyPayload(noRefNoIdEmail, "Thanks").references).toBeUndefined();
  });

  it("returns thread when message_id matches despite selected email id mismatch", () => {
    const thread = [{ ...baseEmail, id: 999 }];
    expect(getConversationMessages(baseEmail, thread)).toEqual(thread);
  });

  it("extracts mailbox using the raw value when angleMatch fails", () => {
    const rawEmail = { ...baseEmail, reply_to: "raw-email@example.com" };
    expect(buildReplyPayload(rawEmail, "Thanks").to).toBe("raw-email@example.com");
  });

  it("does not add Re: if subject already starts with it", () => {
    const reEmail = { ...baseEmail, subject: "Re: Original Subject" };
    expect(buildReplyPayload(reEmail, "Thanks").subject).toBe("Re: Original Subject");
  });

  it("returns references if messageId is missing", () => {
    const noMsgIdEmail = { ...baseEmail, message_id: undefined, references: "<some-ref@example.com>" };
    expect(buildReplyPayload(noMsgIdEmail, "Thanks").references).toBe("<some-ref@example.com>");
  });
});
