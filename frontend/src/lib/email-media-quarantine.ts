export const TRACKING_PIXEL_NEXT_ACTION =
  "This inline image was withheld as a tracking pixel. It was not sent to a model.";
export const UNSUPPORTED_MEDIA_NEXT_ACTION =
  "This inline part is unsupported and was withheld. It was not sent to a model.";
export const UNRESOLVED_CID_NEXT_ACTION =
  "This cid: image could not be resolved from the same message and was withheld. It was not sent to a model.";

const BUYER_VISIBLE_NEXT_ACTIONS: Record<string, string> = {
  tracking_pixel: TRACKING_PIXEL_NEXT_ACTION,
  unsupported_media: UNSUPPORTED_MEDIA_NEXT_ACTION,
  unresolved_cid_reference: UNRESOLVED_CID_NEXT_ACTION,
};

export type EmailMediaQuarantineRecord = {
  admission_error_code: string;
  customer_next_action: string;
  content_id_value?: string | null;
};

type EmailMediaQuarantinePayload = {
  quarantine_records?: unknown;
};

export function customerNextActionForAdmissionErrorCode(
  errorCode: string,
): string | null {
  return BUYER_VISIBLE_NEXT_ACTIONS[errorCode] ?? null;
}

export function readEmailMediaQuarantineRecords(
  payload: unknown,
): EmailMediaQuarantineRecord[] {
  if (!payload || typeof payload !== "object") {
    return [];
  }

  const records = (payload as EmailMediaQuarantinePayload).quarantine_records;
  if (!Array.isArray(records)) {
    return [];
  }

  const visibleRecords: EmailMediaQuarantineRecord[] = [];
  for (const record of records) {
    if (!record || typeof record !== "object") {
      continue;
    }
    const errorCode = (record as { admission_error_code?: unknown }).admission_error_code;
    if (typeof errorCode !== "string") {
      continue;
    }
    const customerNextAction = customerNextActionForAdmissionErrorCode(errorCode);
    if (customerNextAction === null) {
      continue;
    }
    const contentIdValue = (record as { content_id_value?: unknown }).content_id_value;
    visibleRecords.push({
      admission_error_code: errorCode,
      customer_next_action: customerNextAction,
      content_id_value: typeof contentIdValue === "string" ? contentIdValue : null,
    });
  }
  return visibleRecords;
}
