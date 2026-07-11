import React, { useEffect, useId, useRef } from "react";
import { ExternalLink, FileText, X } from "lucide-react";

export interface SourceDrawerProps {
  open: boolean;
  title: string;
  sourceLabel: string;
  sourceType: string;
  sourceId: string;
  summary: string;
  provenance?: string;
  confidence?: number;
  onClose: () => void;
  onOpenOriginal?: () => void;
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function SourceDrawer({
  open,
  title,
  sourceLabel,
  sourceType,
  sourceId,
  summary,
  provenance,
  confidence,
  onClose,
  onOpenOriginal,
}: SourceDrawerProps) {
  const drawerRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const sourceDrawerId = useId();

  useEffect(() => {
    if (!open) return;

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab" || !drawerRef.current) return;

      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((node) => !node.hasAttribute("disabled") && node.getAttribute("aria-hidden") !== "true");

      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeElement = document.activeElement;

      if (event.shiftKey && activeElement === first) {
        event.preventDefault();
        last.focus();
        return;
      }

      if (!event.shiftKey && activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;

  const titleId = `source-drawer-title-${sourceDrawerId}`;
  const descriptionId = `source-drawer-description-${sourceDrawerId}`;

  return (
    <div className="fixed inset-0 z-50">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-slate-950/30 backdrop-blur-[1px]"
        onMouseDown={onClose}
      />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="absolute right-0 top-0 flex h-full w-full max-w-[440px] flex-col border-l border-border bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-wide text-primary">
              근거 원본
            </p>
            <h2 id={titleId} className="mt-1 break-words text-lg font-black text-foreground">
              {title}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="근거 원본 닫기"
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-background text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <section
            id={descriptionId}
            className="rounded-xl border border-primary/20 bg-primary/5 p-4"
          >
            <div className="flex items-start gap-3">
              <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                <FileText className="size-5" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <p className="break-words text-sm font-black text-foreground">
                  {sourceLabel}
                </p>
                <p className="mt-1 break-all text-xs font-semibold text-muted-foreground">
                  {sourceType} · {sourceId}
                </p>
              </div>
            </div>
          </section>

          <section className="mt-5 space-y-3">
            <h3 className="text-sm font-black text-foreground">증거 요약</h3>
            <p className="rounded-xl border border-border bg-background p-4 text-sm leading-6 text-foreground">
              {summary}
            </p>
          </section>

          <section className="mt-5 grid gap-3 text-xs font-semibold text-muted-foreground">
            {provenance ? (
              <div className="rounded-lg border border-border bg-background px-3 py-2">
                <span className="font-black text-foreground">생성 근거</span>
                <span className="ml-2">{provenance}</span>
              </div>
            ) : null}
            {confidence !== undefined ? (
              <div className="rounded-lg border border-border bg-background px-3 py-2">
                <span className="font-black text-foreground">신뢰도</span>
                <span className="ml-2">{confidence}%</span>
              </div>
            ) : null}
          </section>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border bg-background/80 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-border bg-card px-3 text-xs font-bold hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            닫기
          </button>
          {onOpenOriginal ? (
            <button
              type="button"
              onClick={onOpenOriginal}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-xs font-bold text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <ExternalLink className="size-3.5" aria-hidden="true" />
              스레드 원문으로 이동
            </button>
          ) : null}
        </footer>
      </aside>
    </div>
  );
}
