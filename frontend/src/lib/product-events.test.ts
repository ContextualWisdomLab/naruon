/* @vitest-environment jsdom */
import { describe, expect, it } from "vitest";
import {
  bucketSearchRank,
  bucketTextLength,
  clearRecordedProductEvents,
  createProductEventId,
  getRecordedProductEvents,
  getProductEventContract,
  isProductEventName,
  PRODUCT_EVENT_CONTRACTS,
  PRODUCT_EVENT_NAMES,
  PRODUCT_EVENT_TIMEZONE,
  recordProductEvent,
  type ProductEventName,
} from "./product-events";

const REQUIRED_EVENTS: ProductEventName[] = [
  "context_synthesis_viewed",
  "decision_point_viewed",
  "source_chip_opened",
  "action_item_created",
  "calendar_reflected",
  "draft_reply_generated",
  "draft_reply_inserted",
  "draft_reply_sent",
  "context_search_submitted",
  "context_search_result_opened",
  "context_search_result_action_created",
  "latency_guardrail_recorded",
  "model_quality_guardrail_recorded",
  "trust_safety_guardrail_triggered",
];

describe("product event contracts", () => {
  it("contains every required design-to-analytics event exactly once", () => {
    expect(new Set(PRODUCT_EVENT_NAMES).size).toBe(PRODUCT_EVENT_NAMES.length);
    expect(PRODUCT_EVENT_NAMES).toEqual(REQUIRED_EVENTS);
  });

  it("defines timezone, owner, denominator, payload, and caveat for every event", () => {
    for (const eventName of PRODUCT_EVENT_NAMES) {
      const contract = PRODUCT_EVENT_CONTRACTS[eventName];

      expect(contract.timezone).toBe(PRODUCT_EVENT_TIMEZONE);
      expect(contract.owner).toMatch(/^(frontend|backend|analytics|security|model-quality)$/);
      expect(contract.trigger.length).toBeGreaterThan(20);
      expect(contract.denominatorGrain.length).toBeGreaterThan(0);
      expect(contract.entityIds.length).toBeGreaterThan(0);
      expect(contract.payloadFields.some((field) => field.name === "workspace_id" && field.required)).toBe(true);
      expect(contract.payloadFields.some((field) => field.name === "occurred_at" && field.required)).toBe(true);
      expect(contract.qualityCaveat.length).toBeGreaterThan(30);
    }
  });

  it("keeps sensitive body and raw query text out of analytics payload fields", () => {
    const fieldNames = Object.values(PRODUCT_EVENT_CONTRACTS)
      .flatMap((contract) => contract.payloadFields.map((field) => field.name));

    expect(fieldNames).not.toContain("email_body");
    expect(fieldNames).not.toContain("draft_body");
    expect(fieldNames).not.toContain("raw_query");
    expect(fieldNames).toContain("query_length_bucket");
    expect(fieldNames).toContain("character_count_bucket");
  });

  it("exposes a type guard and contract getter for instrumentation call sites", () => {
    expect(isProductEventName("source_chip_opened")).toBe(true);
    expect(isProductEventName("source_chip_clicked")).toBe(false);
    expect(getProductEventContract("calendar_reflected").denominatorGrain).toBe("calendar_candidate");
  });

  it("records local no-op events without a network destination", () => {
    clearRecordedProductEvents();

    const event = recordProductEvent("source_chip_opened", {
      workspace_id: "workspace-1",
      actor_user_id: "user-1",
      surface: "mail_detail",
      source_chip_id: "chip-1",
      ai_output_id: "synthesis-1",
      source_id: "message-1",
      source_type: "mail",
      opened_from: "synthesis_card",
    });

    expect(event.name).toBe("source_chip_opened");
    expect(event.payload.event_id).toEqual(expect.stringContaining("source_chip_opened_"));
    expect(event.payload.occurred_at).toEqual(expect.any(String));
    expect(getRecordedProductEvents()).toEqual([event]);
  });

  it("dispatches a browser-local event for UI integration hooks", () => {
    clearRecordedProductEvents();
    const received: unknown[] = [];
    const listener = (event: Event) => {
      received.push((event as CustomEvent).detail);
    };
    window.addEventListener("naruon:product-event", listener);

    const event = recordProductEvent("draft_reply_generated", {
      surface: "mail_detail",
      draft_reply_id: "draft-1",
      thread_id: "thread-1",
      message_id: "message-1",
      instruction_present: true,
      generation_state: "success",
    });

    window.removeEventListener("naruon:product-event", listener);
    expect(received).toEqual([event]);
  });

  it("rejects raw body and raw query payload keys", () => {
    expect(() =>
      recordProductEvent("context_search_submitted", {
        surface: "context_search",
        search_session_id: "search-1",
        query: "raw query must not be recorded",
        query_length_bucket: "1_20",
        filter_count: 0,
      }),
    ).toThrow("blocked");

    expect(() =>
      recordProductEvent("draft_reply_inserted", {
        surface: "mail_detail",
        draft_reply_id: "draft-1",
        thread_id: "thread-1",
        message_id: "message-1",
        insert_source: "generated",
        draft_body: "raw draft must not be recorded",
      }),
    ).toThrow("blocked");
  });

  it("rejects fields that are not part of the event contract", () => {
    expect(() =>
      recordProductEvent("context_synthesis_viewed", {
        surface: "mail_detail",
        thread_id: "thread-1",
        message_id: "message-1",
        view_state: "loaded",
        emailBody: "raw body under a non-contract key must not be recorded",
      }),
    ).toThrow("not in the context_synthesis_viewed contract");
  });

  it("requires contract fields before accepting an event", () => {
    expect(() =>
      recordProductEvent("calendar_reflected", {
        surface: "mail_detail",
        calendar_candidate_id: "candidate-1",
      }),
    ).toThrow("missing required fields");
  });

  it("provides safe derived buckets for query and draft lengths", () => {
    expect(createProductEventId("test")).toContain("test_");
    expect(bucketTextLength("")).toBe("empty");
    expect(bucketTextLength("런칭 캠페인")).toBe("1_20");
    expect(bucketTextLength("a".repeat(90))).toBe("81_200");
    expect(bucketTextLength("a".repeat(300))).toBe("201_plus");
    expect(bucketSearchRank(0)).toBe("top_1");
    expect(bucketSearchRank(2)).toBe("top_3");
    expect(bucketSearchRank(9)).toBe("top_10");
    expect(bucketSearchRank(10)).toBe("below_10");
  });
});
