import React, { ReactNode } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw, Info } from "lucide-react";
import {
  confidenceLabel,
  confidenceState,
  confidenceToneClass,
  EVIDENCE_MISSING_LABEL,
  EXECUTION_BLOCKED_LABEL,
  EXECUTION_INTENT_ONLY_LABEL,
  isLowConfidence,
  LOW_CONFIDENCE_LABEL,
  toConfidencePercent,
} from "@/lib/confidence";

export type AnalysisExecutionState = "ready" | "blocked" | "intent-only";

export interface DecisionPointCardProps {
  title: string;
  ariaLabel?: string;
  icon?: ReactNode;
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  provenance?: string;
  confidence?: number;
  showConfidence?: boolean;
  evidenceMissing?: boolean;
  executionState?: AnalysisExecutionState;
  children: ReactNode;
  footerActions?: ReactNode;
}

export function DecisionPointCard({
  title,
  ariaLabel,
  icon,
  loading,
  error,
  empty,
  emptyMessage = "데이터가 없습니다.",
  onRetry,
  provenance,
  confidence,
  showConfidence = false,
  evidenceMissing = false,
  executionState,
  children,
  footerActions,
}: DecisionPointCardProps) {
  const percent = toConfidencePercent(confidence);
  const displayConfidence = !loading && !error && (showConfidence || percent !== undefined);
  const analysisState = loading
    ? "loading"
    : error
      ? "error"
      : empty
        ? "empty"
        : isLowConfidence(percent)
          ? "low-confidence"
          : "ready";
  const showFooter =
    !loading &&
    !error &&
    Boolean(footerActions || executionState === "blocked" || executionState === "intent-only");

  return (
    <article
      data-decision-point-card="true"
      data-analysis-state={analysisState}
      data-confidence-state={displayConfidence ? confidenceState(percent) : undefined}
      data-evidence-state={evidenceMissing ? "missing" : undefined}
      data-execution-state={executionState}
      aria-label={ariaLabel ?? title}
    >
      <Card className="flex h-full flex-col border-border bg-card shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border bg-secondary/40 px-4 pb-3 pt-4">
          <CardTitle role="heading" aria-level={3} className="flex items-center gap-2 text-sm font-bold">
            {icon && <span className="text-primary">{icon}</span>}
            {title}
          </CardTitle>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {displayConfidence && (
                <div
                  className={`flex items-center rounded-full border px-2 py-1 text-[10px] font-medium ${confidenceToneClass(percent)}`}
                  title="AI 판단 확신도"
                >
                  <span>{confidenceLabel(percent)}</span>
                  {isLowConfidence(percent) ? (
                    <span className="ml-1 font-bold">{LOW_CONFIDENCE_LABEL}</span>
                  ) : null}
                </div>
              )}
              {evidenceMissing ? (
                <div className="rounded-full border border-border bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground">
                  {EVIDENCE_MISSING_LABEL}
                </div>
              ) : null}
              {provenance && (
                <div className="flex items-center rounded-full border border-border bg-muted px-2 py-1 text-[10px] text-muted-foreground" title="출처/사용된 모델">
                  <Info className="mr-1 h-3 w-3 text-primary/70" />
                  {provenance}
                </div>
              )}
            </div>
          </CardHeader>

        <CardContent className="flex-1 overflow-auto p-4">
          {loading ? (
            <div role="status" aria-live="polite" className="flex h-32 flex-col items-center justify-center space-y-3">
              <div className="relative flex items-center justify-center" aria-hidden="true">
                <div className="absolute inset-0 h-8 w-8 animate-spin rounded-full border-t-2 border-primary opacity-70 motion-reduce:animate-none"></div>
                <div className="absolute inset-2 rounded-full bg-primary/20 blur-sm"></div>
              </div>
              <span className="text-xs font-medium tracking-wide text-muted-foreground">AI가 분석 중입니다...</span>
            </div>
          ) : error ? (
            <div role="alert" className="flex h-32 flex-col items-center justify-center space-y-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-center">
              <div className="rounded-full bg-destructive/10 p-2" aria-hidden="true">
                <AlertCircle className="h-5 w-5 text-destructive" />
              </div>
              <span className="text-sm font-medium text-destructive">{error}</span>
              {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry} className="mt-2 h-8 text-xs">
                  <RefreshCw className="mr-1.5 h-3 w-3" aria-hidden="true" /> 다시 시도
                </Button>
              )}
            </div>
          ) : empty ? (
            <div role="status" aria-live="polite" className="flex h-32 flex-col items-center justify-center space-y-2 rounded-xl border border-dashed border-border bg-muted/40 p-4 text-center text-sm text-muted-foreground">
              <Info className="h-5 w-5 text-muted-foreground/50" aria-hidden="true" />
              <span>{emptyMessage}</span>
            </div>
          ) : (
            <div className="text-sm leading-relaxed text-foreground">
              {children}
            </div>
          )}
        </CardContent>

        {showFooter ? (
          <CardFooter className="flex justify-end gap-2 border-t border-border bg-muted/30 px-4 pb-3 pt-3">
            {executionState === "blocked" ? (
              <span className="self-center text-xs font-semibold text-muted-foreground">{EXECUTION_BLOCKED_LABEL}</span>
            ) : null}
            {executionState === "intent-only" ? (
              <span className="self-center text-xs font-semibold text-accent-foreground">{EXECUTION_INTENT_ONLY_LABEL}</span>
            ) : null}
            {footerActions}
          </CardFooter>
        ) : null}
      </Card>
    </article>
  );
}
