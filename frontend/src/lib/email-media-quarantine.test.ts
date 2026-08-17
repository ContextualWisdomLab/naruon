import { describe, expect, it } from "vitest";

import {
  TRACKING_PIXEL_NEXT_ACTION,
  UNSUPPORTED_MEDIA_NEXT_ACTION,
  UNRESOLVED_CID_NEXT_ACTION,
  customerNextActionForAdmissionErrorCode,
  readEmailMediaQuarantineRecords,
} from "./email-media-quarantine";

describe("email media quarantine buyer copy", () => {
  it("maps the three persisted admission codes to the buyer next action", () => {
    expect(customerNextActionForAdmissionErrorCode("tracking_pixel")).toBe(
      TRACKING_PIXEL_NEXT_ACTION,
    );
    expect(customerNextActionForAdmissionErrorCode("unsupported_media")).toBe(
      UNSUPPORTED_MEDIA_NEXT_ACTION,
    );
    expect(customerNextActionForAdmissionErrorCode("unresolved_cid_reference")).toBe(
      UNRESOLVED_CID_NEXT_ACTION,
    );
    expect(TRACKING_PIXEL_NEXT_ACTION).toBe(
      "This inline image was withheld as a tracking pixel. It was not sent to a model.",
    );
    expect(UNSUPPORTED_MEDIA_NEXT_ACTION).toBe(
      "This inline part is unsupported and was withheld. It was not sent to a model.",
    );
    expect(UNRESOLVED_CID_NEXT_ACTION).toBe(
      "This cid: image could not be resolved from the same message and was withheld. It was not sent to a model.",
    );
  });

  it("fails closed for unknown codes and empty payloads", () => {
    expect(customerNextActionForAdmissionErrorCode("document_image")).toBeNull();
    expect(customerNextActionForAdmissionErrorCode("tracking-pixel")).toBeNull();
    expect(readEmailMediaQuarantineRecords(undefined)).toEqual([]);
    expect(readEmailMediaQuarantineRecords(null)).toEqual([]);
    expect(readEmailMediaQuarantineRecords({ quarantine_records: [] })).toEqual([]);
    expect(
      readEmailMediaQuarantineRecords({
        quarantine_records: [
          { admission_error_code: "document_image" },
          { admission_error_code: "not_a_quarantine" },
          { admission_error_code: 31 },
          "not-a-record",
        ],
      }),
    ).toEqual([]);
    expect(readEmailMediaQuarantineRecords({ quarantine_records: {} })).toEqual([]);
  });
});
