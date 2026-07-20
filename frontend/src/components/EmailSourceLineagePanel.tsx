import React from "react";

import { formatEmailDate } from "@/lib/email-threading";

export type EmailSourceLineage = {
  schema_version: 1;
  source_kind: "rfc822";
  source_filename: string;
  raw_content_sha256: string;
  production_time: {
    selected_value: string | null;
    selected_source: "embedded_date_header" | null;
    embedded_status: "parsed" | "missing" | "invalid";
    evidence_precedence: [
      "embedded_metadata",
      "explicit_filename_date",
      "filesystem_created_at",
      "filesystem_modified_at",
    ];
  };
  message_identity: {
    selected_source: "embedded_message_id" | "raw_content_sha256";
    embedded_status: "embedded" | "missing" | "invalid";
  };
};

const EVIDENCE_LABELS: Record<
  EmailSourceLineage["production_time"]["evidence_precedence"][number],
  string
> = {
  embedded_metadata: "내장 메타데이터",
  explicit_filename_date: "명시적 파일명 날짜 (검토 필요)",
  filesystem_created_at: "파일시스템 생성일",
  filesystem_modified_at: "파일시스템 수정일",
};

function productionStatusLabel(
  status: EmailSourceLineage["production_time"]["embedded_status"],
) {
  if (status === "parsed") return "내장 Date 헤더 확인";
  if (status === "missing") return "내장 Date 헤더 없음";
  return "내장 Date 헤더 해석 불가";
}

function identitySourceLabel(
  source: EmailSourceLineage["message_identity"]["selected_source"],
) {
  return source === "embedded_message_id"
    ? "내장 Message-ID"
    : "원본 바이트 SHA-256";
}

export function EmailSourceLineagePanel({
  lineage,
  displayedDate,
}: {
  lineage: EmailSourceLineage;
  displayedDate?: string | null;
}) {
  const productionTime = lineage.production_time;
  const hasEmbeddedProductionTime =
    productionTime.embedded_status === "parsed" &&
    productionTime.selected_source === "embedded_date_header" &&
    Boolean(productionTime.selected_value);

  return (
    <section
      aria-label="원본 계보"
      className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-black uppercase tracking-wide text-sky-700">
            Data lineage
          </p>
          <h3 className="mt-1 text-sm font-black text-foreground">원본 계보</h3>
        </div>
        <span className="rounded-full border border-sky-500/20 bg-background px-2.5 py-1 text-[10px] font-bold text-sky-700">
          {productionStatusLabel(productionTime.embedded_status)}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-background p-3">
          <dt className="font-bold text-muted-foreground">원본 파일</dt>
          <dd className="mt-1 break-all font-semibold text-foreground">
            {lineage.source_filename}
          </dd>
        </div>
        <div className="rounded-xl border border-border bg-background p-3">
          <dt className="font-bold text-muted-foreground">생산 시점 근거</dt>
          <dd className="mt-1 font-semibold text-foreground">
            {hasEmbeddedProductionTime
              ? `${formatEmailDate(productionTime.selected_value)} · 내장 Date 헤더`
              : "확정된 내장 생산 시점 없음"}
          </dd>
        </div>
        <div className="rounded-xl border border-border bg-background p-3">
          <dt className="font-bold text-muted-foreground">메시지 식별 근거</dt>
          <dd className="mt-1 font-semibold text-foreground">
            {identitySourceLabel(lineage.message_identity.selected_source)}
          </dd>
        </div>
        <div className="rounded-xl border border-border bg-background p-3">
          <dt className="font-bold text-muted-foreground">원본 SHA-256</dt>
          <dd className="mt-1 break-all font-mono text-[10px] text-foreground">
            {lineage.raw_content_sha256}
          </dd>
        </div>
      </dl>

      {!hasEmbeddedProductionTime ? (
        <p className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs font-semibold leading-5 text-amber-900">
          화면 표시 시각{displayedDate ? ` (${formatEmailDate(displayedDate)})` : ""}은
          저장용 fallback이며 생산일 근거가 아닙니다. 파일명 날짜도 자동 승격하지 않습니다.
        </p>
      ) : null}

      <div className="mt-3">
        <p className="text-[11px] font-bold text-muted-foreground">생산 시점 증거 우선순위</p>
        <ol className="mt-2 flex flex-wrap gap-2" aria-label="생산 시점 증거 우선순위">
          {productionTime.evidence_precedence.map((source, index) => (
            <li
              key={source}
              className="rounded-full border border-border bg-background px-2.5 py-1 text-[10px] font-semibold text-foreground"
            >
              {index + 1}. {EVIDENCE_LABELS[source]}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
