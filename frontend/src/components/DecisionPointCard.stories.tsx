import { useState } from "react"

import type { Meta, StoryObj } from "@storybook/nextjs-vite"

import { Button } from "@/components/ui/button"
import { DecisionPointCard } from "./DecisionPointCard"

const meta = {
  title: "Analysis/DecisionPointCard",
  component: DecisionPointCard,
  parameters: {
    layout: "padded",
  },
  args: {
    title: "맥락 종합",
    children: "출시 리뷰 메일의 핵심 맥락입니다.",
    showConfidence: true,
    confidence: 0.82,
  },
} satisfies Meta<typeof DecisionPointCard>

export default meta
type Story = StoryObj<typeof meta>

function expectText(canvasElement: HTMLElement, text: string) {
  if (!canvasElement.textContent?.includes(text)) {
    throw new Error(`Expected visible text: ${text}`)
  }
}

function expectMissing(canvasElement: HTMLElement, text: string) {
  if (canvasElement.textContent?.includes(text)) {
    throw new Error(`Did not expect visible text: ${text}`)
  }
}

function clickByText(canvasElement: HTMLElement, text: string) {
  const button = Array.from(canvasElement.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(text),
  )
  if (!button) {
    throw new Error(`Missing button: ${text}`)
  }
  button.click()
  return button
}

export const SourceOpen: Story = {
  name: "Scene / source open",
  render: function SourceOpenScene() {
    const [open, setOpen] = useState(false)
    return (
      <div className="w-[min(100%,42rem)] space-y-3">
        <DecisionPointCard title="맥락 종합" showConfidence confidence={0.86} provenance="mail-thread">
          <div className="flex flex-col gap-2">
            <p>근거 원본을 확인해야 하는 맥락 종합입니다.</p>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="self-end rounded bg-primary/5 px-2 py-1 text-[10px] font-bold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              근거 원본 보기
            </button>
          </div>
        </DecisionPointCard>
        {open ? (
          <aside role="dialog" aria-label="맥락 종합 근거" className="rounded-xl border border-border bg-card p-4 text-sm">
            메일 원문과 스레드가 근거입니다.
          </aside>
        ) : null}
      </div>
    )
  },
  play: async ({ canvasElement }) => {
    clickByText(canvasElement, "근거 원본 보기")
    expectText(canvasElement, "메일 원문과 스레드가 근거입니다.")
  },
}

export const DraftReview: Story = {
  name: "Scene / draft review",
  args: {
    title: "답장 초안",
    showConfidence: false,
    provenance: "사용자 확인 필요",
    children: (
      <label className="block text-sm">
        답장 초안
        <textarea aria-label="답장 초안" className="mt-2 min-h-24 w-full rounded-xl border border-border bg-background p-3" defaultValue="검토 의견을 반영해 정중히 답장합니다." />
      </label>
    ),
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "답장 초안")
    const draft = canvasElement.querySelector('textarea[aria-label="답장 초안"]')
    if (!(draft instanceof HTMLTextAreaElement) || !draft.value.includes("정중히 답장")) {
      throw new Error("draft review surface missing")
    }
  },
}

export const CalendarReflect: Story = {
  name: "Scene / calendar reflect",
  render: function CalendarReflectScene() {
    const [status, setStatus] = useState<string | null>(null)
    return (
      <DecisionPointCard
        title="실행 항목"
        showConfidence
        confidence={0.82}
        executionState="ready"
        footerActions={
          <>
            <Button size="sm" onClick={() => setStatus("1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.")}>
              일정 반영
            </Button>
            {status ? <span className="self-center text-xs text-primary">{status}</span> : null}
          </>
        }
      >
        캘린더에 출시 리뷰 일정을 반영
      </DecisionPointCard>
    )
  },
  play: async ({ canvasElement }) => {
    clickByText(canvasElement, "일정 반영")
    expectText(canvasElement, "1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.")
  },
}

export const TaskCreate: Story = {
  name: "Scene / task create",
  render: function TaskCreateScene() {
    const [status, setStatus] = useState<string | null>(null)
    return (
      <DecisionPointCard
        title="실행 항목"
        showConfidence
        confidence={0.91}
        executionState="ready"
        footerActions={
          <>
            <Button size="sm" variant="outline" onClick={() => setStatus("1개 실행 항목을 티켓형 실행 항목으로 추적합니다.")}>
              실행 항목 생성
            </Button>
            {status ? <span role="status">{status}</span> : null}
          </>
        }
      >
        답장 초안 준비
      </DecisionPointCard>
    )
  },
  play: async ({ canvasElement }) => {
    clickByText(canvasElement, "실행 항목 생성")
    expectText(canvasElement, "티켓형 실행 항목으로 추적합니다.")
  },
}

export const Loading: Story = {
  name: "Edge / loading",
  args: {
    loading: true,
    children: null,
  },
  play: async ({ canvasElement }) => {
    const status = canvasElement.querySelector('[role="status"]')
    if (!status?.textContent?.includes("AI가 분석 중입니다")) {
      throw new Error("loading state missing")
    }
  },
}

export const Empty: Story = {
  name: "Edge / empty",
  args: {
    empty: true,
    emptyMessage: "이 메일에서 추출된 판단 포인트가 없습니다.",
    title: "판단 포인트",
    children: null,
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "이 메일에서 추출된 판단 포인트가 없습니다.")
    expectMissing(canvasElement, "맥락 종합을 생성하지 못했습니다.")
  },
}

export const ErrorState: Story = {
  name: "Edge / error",
  args: {
    title: "맥락 종합",
    error: "맥락 종합을 생성하지 못했습니다.",
    children: null,
  },
  play: async ({ canvasElement }) => {
    const alert = canvasElement.querySelector('[role="alert"]')
    if (!alert?.textContent?.includes("맥락 종합을 생성하지 못했습니다.")) {
      throw new Error("error state missing")
    }
    expectMissing(canvasElement, "이 메일에서 추출된 판단 포인트가 없습니다.")
  },
}

export const LowConfidence: Story = {
  name: "Edge / low confidence",
  args: {
    title: "맥락 종합",
    showConfidence: true,
    confidence: 0.42,
    children: "낮은 확신 합성",
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "신뢰도 42%")
    expectText(canvasElement, "낮은 신뢰도")
  },
}

export const MissingSource: Story = {
  name: "Edge / missing source",
  args: {
    title: "판단 포인트",
    evidenceMissing: true,
    showConfidence: true,
    children: "원본 메시지 필터가 없습니다.",
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "근거 없음")
  },
}

export const IntentOnly: Story = {
  name: "Edge / conflict intent-only",
  args: {
    title: "실행 항목",
    executionState: "intent-only",
    children: "일정 반영 의도를 기록했습니다. 공급자 쓰기는 실행되지 않았습니다.",
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "의도만 기록")
  },
}

export const BlockedExecution: Story = {
  name: "Edge / blocked execution",
  args: {
    title: "실행 항목",
    empty: true,
    emptyMessage: "실행 항목이 없습니다.",
    executionState: "blocked",
    children: null,
  },
  play: async ({ canvasElement }) => {
    expectText(canvasElement, "실행 항목이 없습니다.")
    expectText(canvasElement, "실행 차단됨")
  },
}

export const SharedScale: Story = {
  name: "Edge / 1 vs 1.01 shared scale",
  render: () => (
    <div className="grid gap-4 md:grid-cols-2">
      <DecisionPointCard title="메일 분석" showConfidence confidence={1}>
        단위 구간 1.0
      </DecisionPointCard>
      <DecisionPointCard title="검색 분석" showConfidence confidence={1.01}>
        단위 구간 1.01
      </DecisionPointCard>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const matches = canvasElement.textContent?.match(/신뢰도 100%/g) ?? []
    if (matches.length < 2) {
      throw new Error("mail and search scores must share 100%")
    }
    expectMissing(canvasElement, "신뢰도 1%")
  },
}
