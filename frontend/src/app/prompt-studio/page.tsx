'use client';

import React, { useMemo, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Code,
  History,
  LayoutTemplate,
  ListChecks,
  Loader2,
  MoreHorizontal,
  Play,
  RefreshCw,
  Rocket,
  Save,
  SlidersHorizontal,
  Sparkles,
  Variable,
} from 'lucide-react';

type PromptFormData = {
  title: string;
  description: string;
  content: string;
  is_shared: boolean;
};

type VariableValues = Record<string, string>;

const DEFAULT_CONTENT = '핵심 맥락을 종합해주세요: {{email}}';
const PLACEHOLDER_PATTERN = /\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}/g;

function createVariableValueMap(entries: Iterable<readonly [string, string]> = []): VariableValues {
  const values = Object.create(null) as VariableValues;
  for (const [key, value] of entries) {
    values[key] = value;
  }
  return values;
}

const DEFAULT_VARIABLE_VALUES = createVariableValueMap([
  ['email', '메일 내용 예시입니다.'],
]);

const SAMPLE_VARIABLE_VALUES = createVariableValueMap([
  ['email', '지난 분기 매출은 전년 대비 18% 증가했고, 고객 이탈률은 3.2%로 낮아졌습니다. 핵심 원인은 자동화 기능 도입입니다.'],
  ['name', '김나루'],
  ['project_name', 'Naruon Knowledge Hub'],
  ['topic', 'AI 업무 자동화'],
]);

function getOwnVariableValue(values: VariableValues, key: string) {
  return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : undefined;
}

function extractPromptVariables(content: string) {
  const variables = new Set<string>();
  for (const match of content.matchAll(PLACEHOLDER_PATTERN)) {
    variables.add(match[1]);
  }
  return Array.from(variables);
}

function renderPromptPreview(content: string, variables: VariableValues) {
  return content.replace(PLACEHOLDER_PATTERN, (placeholder, name: string) => {
    const value = getOwnVariableValue(variables, name);
    return value?.trim() ? value : placeholder;
  });
}

function syncVariableValues(variableNames: string[], currentValues: VariableValues) {
  const nextValues = createVariableValueMap();
  for (const variableName of variableNames) {
    nextValues[variableName] =
      getOwnVariableValue(currentValues, variableName) ??
      getOwnVariableValue(DEFAULT_VARIABLE_VALUES, variableName) ??
      '';
  }
  return nextValues;
}

function getSafeErrorSummary(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

const TEMPLATE_GROUPS = [
  {
    name: '업무 종합',
    items: [
      { id: 'summary', title: '문서 종합/초안 작성', favorite: true },
      { id: 'insight', title: '데이터 분석 판단 포인트' },
      { id: 'mail', title: '이메일 작성' },
      { id: 'automation', title: '업무 자동화 제안' },
    ],
  },
  {
    name: '회의/리포트',
    items: [
      { id: 'meeting', title: '회의록 작성' },
      { id: 'decision', title: '의사결정 핵심 맥락' },
      { id: 'weekly', title: '주간 보고서 작성' },
    ],
  },
  {
    name: '고객 응대',
    items: [
      { id: 'customer', title: '고객 문의 답변' },
      { id: 'faq', title: 'FAQ 생성' },
      { id: 'claim', title: '클레임 대응' },
    ],
  },
  {
    name: '개발/기술',
    items: [
      { id: 'code', title: '코드 설명/주석' },
      { id: 'bug', title: '버그 분석' },
      { id: 'spec', title: '요구사항 생성' },
    ],
  },
];

const PROMPT_TABS = [
  { id: 'system', label: '시스템' },
  { id: 'user', label: '사용자' },
  { id: 'assistant', label: '어시스턴트 예시' },
] as const;

const MODEL_OPTIONS = [
  { label: 'Naruon GPT-4o Enterprise', value: 'gpt-4o' },
  { label: 'Naruon Local Gemma', value: 'gemma-3-27b-it' },
  { label: 'OpenAI Compatible', value: 'provider-default' },
];
const RESPONSE_STYLES = ['전문적이고 간결하게', '친근하고 상세하게', '실행 항목 중심'];
const OUTPUT_FORMATS = ['마크다운 (Markdown)', 'JSON 구조화', '짧은 종합'];

const QUALITY_CHECKS = ['요구사항 충족', '구조 및 가독성', '정확성/사실성', '근거/출처 포함', '톤 & 스타일 일관성'];

const VERSION_HISTORY = [
  { version: 'v1.3', status: '현재', date: '2024.05.25 10:23', author: '김나루' },
  { version: 'v1.2', status: '이전', date: '2024.05.24 16:08', author: '이도윤' },
  { version: 'v1.1', status: '백지', date: '2024.05.24 10:31', author: '박지민' },
  { version: 'v1.0', status: '내부 테스트', date: '2024.05.23 17:12', author: '김나루' },
];

const RECENT_TEST_RESULTS = [
  { time: '2024.05.25 10:22', case: '분기 성과 보고서 종합', result: '성공', score: 92, tokens: '1,024', duration: '2.8초' },
  { time: '2024.05.25 10:18', case: '고객 피드백 분석', result: '성공', score: 88, tokens: '1,156', duration: '3.1초' },
  { time: '2024.05.25 10:12', case: '경쟁사 분석 리포트', result: '부분 성공', score: 76, tokens: '1,432', duration: '3.6초' },
  { time: '2024.05.25 10:05', case: '제품 출시 계획 종합', result: '성공', score: 95, tokens: '987', duration: '2.6초' },
];

const DEPLOYMENT_HISTORY = [
  { version: 'v1.3', state: '운영 중', target: 'Naruon PM 외 3', date: '2024.05.25 10:23', author: '김나루' },
  { version: 'v1.2', state: '운영 중', target: '프로덕트팀 전체', date: '2024.05.24 16:08', author: '이준호' },
  { version: 'v1.1', state: '비활성', target: '파일럿 그룹', date: '2024.05.24 10:31', author: '박지민' },
];

const METRIC_CARDS = [
  { label: '총 실행 수', value: '1,248', delta: '+18.3%' },
  { label: '성공률', value: '94.2%', delta: '+4.8%' },
  { label: '평균 품질 점수', value: '88.6', delta: '+6.1%' },
  { label: '평균 응답 시간', value: '2.6초', delta: '-0.3초' },
];

type PromptSettings = {
  model: string;
  temperature: string;
  responseStyle: string;
  outputFormat: string;
};

const MODEL_LABEL_MAP = new Map(MODEL_OPTIONS.map((m) => [m.value, m.label]));

function getModelLabel(modelValue: string) {
  return MODEL_LABEL_MAP.get(modelValue) ?? modelValue;
}

export default function PromptStudioPage() {
  const [formData, setFormData] = useState<PromptFormData>({
    title: '',
    description: '',
    content: DEFAULT_CONTENT,
    is_shared: false,
  });
  const [activeTemplateId, setActiveTemplateId] = useState('summary');
  const [activePromptTab, setActivePromptTab] = useState<(typeof PROMPT_TABS)[number]['id']>('system');
  const [promptSettings, setPromptSettings] = useState<PromptSettings>({
    model: MODEL_OPTIONS[0].value,
    temperature: '0.3',
    responseStyle: RESPONSE_STYLES[0],
    outputFormat: OUTPUT_FORMATS[0],
  });
  const [showTemplateCounts, setShowTemplateCounts] = useState(true);
  const promptVariables = useMemo(() => extractPromptVariables(formData.content), [formData.content]);
  const [variableValues, setVariableValues] = useState<VariableValues>(() =>
    createVariableValueMap(Object.entries(DEFAULT_VARIABLE_VALUES)),
  );
  const [testResult, setTestResult] = useState('');
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const previewText = useMemo(
    () => renderPromptPreview(formData.content, variableValues),
    [formData.content, variableValues],
  );

  const setFormField = <Key extends keyof PromptFormData>(field: Key, value: PromptFormData[Key]) => {
    setError(null);
    setSaveStatus(null);
    setFormData((current) => ({ ...current, [field]: value }));
  };

  const setPromptContent = (content: string) => {
    setError(null);
    setSaveStatus(null);
    setTestResult('');
    setFormData((current) => ({ ...current, content }));
    setVariableValues((currentValues) => syncVariableValues(extractPromptVariables(content), currentValues));
  };

  const selectTemplate = (templateId: string, title: string) => {
    setActiveTemplateId(templateId);
    setFormData((current) => ({
      ...current,
      title,
      description: `${title} 템플릿을 기반으로 저장 전 테스트합니다.`,
    }));
    setError(null);
    setSaveStatus(null);
    setTestResult('');
  };

  const setPromptSetting = (field: keyof typeof promptSettings, value: string) => {
    setPromptSettings((current) => ({ ...current, [field]: value }));
    setTestResult('');
  };

  const buildVariablesPayload = () => {
    const payload = createVariableValueMap();
    for (const variableName of promptVariables) {
      payload[variableName] = getOwnVariableValue(variableValues, variableName) ?? '';
    }
    return payload;
  };

  const buildPromptTestSettings = () => ({
    model: promptSettings.model,
    temperature: Number.parseFloat(promptSettings.temperature),
    response_style: promptSettings.responseStyle,
    output_format: promptSettings.outputFormat,
  });

  const loadSampleInput = () => {
    setVariableValues(() => {
      const nextValues = createVariableValueMap();
      for (const variableName of promptVariables) {
        nextValues[variableName] =
          getOwnVariableValue(SAMPLE_VARIABLE_VALUES, variableName) ??
          `${variableName} 샘플 값`;
      }
      return nextValues;
    });
    setError(null);
    setSaveStatus(null);
    setTestResult('');
  };

  const validateForSave = () => {
    if (!formData.title.trim()) {
      setError('프롬프트 이름을 입력하세요.');
      return false;
    }
    if (!formData.content.trim()) {
      setError('프롬프트 내용을 입력하세요.');
      return false;
    }
    return true;
  };

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    setSaveStatus(null);
    try {
      const data = await apiClient.post<{ result?: string }>('/api/prompts/test', {
        content: formData.content,
        variables: buildVariablesPayload(),
        settings: buildPromptTestSettings(),
      });
      setTestResult(data.result || '응답이 없습니다.');
    } catch (err: unknown) {
      setError(getSafeErrorSummary(err, '테스트 실패'));
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!validateForSave()) return;
    setSaving(true);
    setError(null);
    setSaveStatus(null);
    try {
      await apiClient.post<{ result?: string }>('/api/prompts', {
        title: formData.title.trim(),
        description: formData.description.trim() || null,
        content: formData.content,
        is_shared: formData.is_shared,
      });
      setSaveStatus('프롬프트가 저장되었습니다. AI 허브에서 실행 후보와 평가 근거로 연결됩니다.');
    } catch (err: unknown) {
      setError(getSafeErrorSummary(err, '저장 실패'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-6 p-4 pb-[calc(6rem+env(safe-area-inset-bottom))] md:p-6">
        <section className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="gap-1 border-primary/20 bg-primary/10 font-black text-primary">
                <Sparkles className="size-3" aria-hidden="true" />
                AI Hub source
              </Badge>
              <Badge variant={formData.is_shared ? 'default' : 'secondary'} className="font-black">
                {formData.is_shared ? '워크스페이스 공유' : '개인 초안'}
              </Badge>
              <Badge variant="outline" className="font-black">
                {getModelLabel(promptSettings.model)}
              </Badge>
            </div>
            <h1 className="mt-3 flex items-center gap-3 text-2xl font-black md:text-3xl">
              <Code className="size-7 text-primary" aria-hidden="true" />
              Prompt Studio
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              프롬프트를 설계, 테스트, 배포하는 작업 공간입니다.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleSave} disabled={saving || testing} className="font-black">
              {saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" data-testid="loader" /> : <Save className="size-4" aria-hidden="true" />}
              {saving ? '저장 중...' : '프롬프트 저장 (Save)'}
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing || saving || !formData.content.trim()} className="font-black">
              {testing ? <Loader2 className="size-4 animate-spin" aria-hidden="true" data-testid="loader" /> : <Play className="size-4" aria-hidden="true" />}
              {testing ? '테스트 중...' : '실행 (Test)'}
            </Button>
            <a
              href="/ai-hub"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <Rocket className="size-4" aria-hidden="true" />
              게시
            </a>
          </div>
        </section>

        {error && (
          <Card role="alert" className="border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-200">
            <CardContent className="flex items-center gap-3 py-4">
              <AlertCircle className="size-5 shrink-0" aria-hidden="true" />
              <p className="font-bold">{error}</p>
            </CardContent>
          </Card>
        )}

        {saveStatus && (
          <Card role="status" aria-live="polite" className="border-green-200 bg-green-50 text-green-700 dark:border-green-500/30 dark:bg-green-500/15 dark:text-green-200">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-5 shrink-0" aria-hidden="true" />
                <p className="font-bold">{saveStatus}</p>
              </div>
              <a href="/ai-hub" className="text-sm font-black text-current underline underline-offset-4">
                AI 허브 열기
              </a>
            </CardContent>
          </Card>
        )}

        <section className="grid min-h-0 gap-5 xl:grid-cols-[18rem_minmax(0,1fr)_minmax(23rem,0.9fr)]">
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-base font-black">
                  <LayoutTemplate className="size-4 text-primary" aria-hidden="true" />
                  프롬프트 템플릿
                </CardTitle>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="템플릿 개수 표시 전환"
                  aria-pressed={showTemplateCounts}
                  title="템플릿 개수 표시 전환"
                  onClick={() => setShowTemplateCounts((current) => !current)}
                >
                  <MoreHorizontal className="size-4" aria-hidden="true" />
                </Button>
              </div>
              <Input aria-label="템플릿 검색" placeholder="템플릿 검색..." />
            </CardHeader>
            <CardContent className="grid gap-3">
              {TEMPLATE_GROUPS.map((group) => (
                <div key={group.name} className="grid gap-1">
                  <div className="flex items-center justify-between px-1 text-xs font-black text-muted-foreground">
                    <span>{group.name}</span>
                    {showTemplateCounts ? <span>{group.items.length}</span> : null}
                  </div>
                  {group.items.map((item) => {
                    const active = item.id === activeTemplateId;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => selectTemplate(item.id, item.title)}
                        className={`flex min-h-9 items-center justify-between gap-2 rounded-lg px-3 text-left text-sm font-bold transition-colors ${
                          active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                        }`}
                      >
                        <span className="min-w-0 truncate">{item.title}</span>
                        {item.favorite ? <Sparkles className="size-3.5 text-primary" aria-label="즐겨찾기" /> : null}
                      </button>
                    );
                  })}
                </div>
              ))}
              <a href="/ai-hub" className="mt-2 rounded-xl border border-border bg-background p-3 text-sm font-black text-primary">
                템플릿 마켓플레이스
              </a>
            </CardContent>
          </Card>

          <div className="grid min-w-0 gap-5">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="font-black">프롬프트 에디터</CardTitle>
                    <CardDescription className="mt-1">시스템, 사용자, 어시스턴트 예시를 한 작업면에서 조율합니다.</CardDescription>
                  </div>
                  <Badge variant="outline" className="font-black">{promptVariables.length} variables</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs value={activePromptTab} onValueChange={(value) => setActivePromptTab(value as typeof activePromptTab)} className="grid gap-4">
                  <TabsList className="w-full justify-start overflow-x-auto">
                    {PROMPT_TABS.map((tab) => (
                      <TabsTrigger key={tab.id} value={tab.id}>
                        {tab.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <TabsContent value="system" className="mt-0 grid gap-4">
                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_16rem]">
                      <div className="space-y-1.5">
                        <label htmlFor="prompt-title" className="text-sm font-bold">프롬프트 이름</label>
                        <Input
                          id="prompt-title"
                          aria-invalid={!formData.title.trim() && Boolean(error)}
                          placeholder="프롬프트 이름"
                          value={formData.title}
                          onChange={e => setFormField('title', e.target.value)}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label htmlFor="prompt-scope" className="text-sm font-bold">저장 범위</label>
                        <div id="prompt-scope" className="flex min-h-10 items-center gap-2 rounded-xl border border-border bg-background px-3">
                          <Checkbox
                            id="is_shared"
                            checked={formData.is_shared}
                            onCheckedChange={(checked) => setFormField('is_shared', Boolean(checked))}
                          />
                          <label htmlFor="is_shared" className="text-sm font-bold leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            워크스페이스에 공유하기
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="prompt-description" className="text-sm font-bold">설명</label>
                      <Input
                        id="prompt-description"
                        placeholder="설명"
                        value={formData.description}
                        onChange={e => setFormField('description', e.target.value)}
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="prompt-content" className="text-sm font-bold">시스템 프롬프트</label>
                      <Textarea
                        id="prompt-content"
                        aria-describedby="prompt-content-help"
                        className="min-h-[15rem] font-mono text-sm"
                        value={formData.content}
                        onChange={e => setPromptContent(e.target.value)}
                      />
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-muted-foreground">
                        <p id="prompt-content-help">
                          변수는 <code className="rounded bg-secondary px-1 py-0.5">{'{{email}}'}</code> 형식으로 작성합니다.
                        </p>
                        <span>문자 수 {formData.content.length.toLocaleString()} / 8,000</span>
                      </div>
                    </div>
                  </TabsContent>
                  <TabsContent value="user" className="mt-0">
                    <div className="rounded-xl border border-border bg-secondary/30 p-4 text-sm leading-6">
                      샘플 입력은 오른쪽 라이브 미리보기에서 관리합니다. 입력 변수와 실제 테스트 payload가 함께 전달됩니다.
                    </div>
                  </TabsContent>
                  <TabsContent value="assistant" className="mt-0">
                    <div className="rounded-xl border border-border bg-secondary/30 p-4 text-sm leading-6">
                      어시스턴트 예시는 품질 기준, 톤, 출력 구조를 Publisher가 검수할 때 사용하는 reference response입니다.
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-black">
                  <SlidersHorizontal className="size-4 text-primary" aria-hidden="true" />
                  모델 및 설정
                </CardTitle>
                <CardDescription>테스트 실행 전에 모델과 응답 형식을 확인합니다.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="prompt-model" className="text-sm font-bold">모델</label>
                  <select
                    id="prompt-model"
                    value={promptSettings.model}
                    onChange={(event) => setPromptSetting('model', event.target.value)}
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  >
                    {MODEL_OPTIONS.map((model) => <option key={model.value} value={model.value}>{model.label}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="prompt-temperature" className="text-sm font-bold">Temperature</label>
                  <div className="flex h-10 items-center gap-3 rounded-xl border border-input bg-background px-3">
                    <span className="w-8 text-sm font-black">{promptSettings.temperature}</span>
                    <input
                      id="prompt-temperature"
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={promptSettings.temperature}
                      onChange={(event) => setPromptSetting('temperature', event.target.value)}
                      className="w-full accent-primary"
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="prompt-response-style" className="text-sm font-bold">응답 스타일</label>
                  <select
                    id="prompt-response-style"
                    value={promptSettings.responseStyle}
                    onChange={(event) => setPromptSetting('responseStyle', event.target.value)}
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  >
                    {RESPONSE_STYLES.map((style) => <option key={style}>{style}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="prompt-output-format" className="text-sm font-bold">출력 형식</label>
                  <select
                    id="prompt-output-format"
                    value={promptSettings.outputFormat}
                    onChange={(event) => setPromptSetting('outputFormat', event.target.value)}
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  >
                    {OUTPUT_FORMATS.map((format) => <option key={format}>{format}</option>)}
                  </select>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid h-fit gap-5">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2 font-black">
                      <Variable className="size-4 text-primary" aria-hidden="true" />
                      라이브 미리보기
                    </CardTitle>
                    <CardDescription className="mt-1">샘플 입력과 생성 결과를 함께 봅니다.</CardDescription>
                  </div>
                  <Badge variant="outline" className="gap-1 font-black text-green-700 dark:text-green-300">
                    <CheckCircle2 className="size-3" aria-hidden="true" />
                    미리보기 동기화됨
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-black">샘플 입력</p>
                    <Button variant="outline" size="sm" onClick={loadSampleInput} disabled={promptVariables.length === 0}>
                      <Variable className="size-3.5" aria-hidden="true" />
                      새 예시
                    </Button>
                  </div>
                  {promptVariables.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-border bg-secondary/30 p-4 text-sm font-semibold text-muted-foreground">
                      등록된 변수가 없습니다. 프롬프트 내용에 변수를 추가하면 입력 필드가 생성됩니다.
                    </div>
                  ) : (
                    promptVariables.map((variableName) => (
                      <div key={variableName} className="space-y-1.5">
                        <label htmlFor={`prompt-variable-${variableName}`} className="text-sm font-bold">
                          {`{{${variableName}}}`}
                        </label>
                        <Textarea
                          id={`prompt-variable-${variableName}`}
                          className="min-h-20"
                          placeholder={`${variableName} 변수 값`}
                          value={getOwnVariableValue(variableValues, variableName) ?? ''}
                          onChange={(event) => {
                            const value = event.target.value;
                            setVariableValues((current) => {
                              const nextValues = createVariableValueMap(Object.entries(current));
                              nextValues[variableName] = value;
                              return nextValues;
                            });
                            setError(null);
                            setTestResult('');
                          }}
                        />
                      </div>
                    ))
                  )}
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <p className="text-sm font-black">생성된 결과</p>
                    <Button variant="outline" size="sm" onClick={handleTest} disabled={testing || saving || !formData.content.trim()}>
                      {testing ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" data-testid="loader" /> : <RefreshCw className="size-3.5" aria-hidden="true" />}
                      다시 생성
                    </Button>
                  </div>
                  <div
                    role={testResult ? 'status' : undefined}
                    aria-live="polite"
                    className="min-h-52 rounded-xl border border-border bg-card p-4 text-sm leading-6"
                  >
                    {testResult ? (
                      <p className="whitespace-pre-wrap">{testResult}</p>
                    ) : (
                      <pre className="whitespace-pre-wrap font-sans text-sm text-muted-foreground">{previewText || '프롬프트 내용이 비어 있습니다.'}</pre>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-5">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base font-black">
                    <ListChecks className="size-4 text-primary" aria-hidden="true" />
                    품질 체크리스트
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-2">
                  {QUALITY_CHECKS.map((item) => (
                    <div key={item} className="flex items-center gap-2 text-sm font-semibold">
                      <CheckCircle2 className="size-4 text-green-600" aria-hidden="true" />
                      {item}
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base font-black">
                    <History className="size-4 text-primary" aria-hidden="true" />
                    버전 히스토리
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3">
                  {VERSION_HISTORY.map((item) => (
                    <div key={item.version} className="flex items-start justify-between gap-3 text-sm">
                      <div>
                        <p className="font-black">{item.version} <span className="font-semibold text-muted-foreground">{item.status}</span></p>
                        <p className="text-xs text-muted-foreground">{item.date} · {item.author}</p>
                      </div>
                      <span className="mt-1 size-2 rounded-full bg-primary" aria-hidden="true" />
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(24rem,0.9fr)]">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 font-black">
                    <Clock3 className="size-4 text-primary" aria-hidden="true" />
                    최근 테스트 결과
                  </CardTitle>
                  <CardDescription>Publisher가 배포 전 품질과 응답 시간을 확인합니다.</CardDescription>
                </div>
                <a href="/ai-hub" className="text-sm font-black text-primary underline underline-offset-4">전체 보기</a>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[42rem] text-left text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="py-2 pr-3 font-black">실행 시간</th>
                    <th className="py-2 pr-3 font-black">테스트 케이스</th>
                    <th className="py-2 pr-3 font-black">결과</th>
                    <th className="py-2 pr-3 font-black">품질 점수</th>
                    <th className="py-2 pr-3 font-black">토큰</th>
                    <th className="py-2 font-black">소요 시간</th>
                  </tr>
                </thead>
                <tbody>
                  {RECENT_TEST_RESULTS.map((item) => (
                    <tr key={`${item.time}-${item.case}`} className="border-b border-border/60 last:border-0">
                      <td className="py-3 pr-3 text-muted-foreground">{item.time}</td>
                      <td className="py-3 pr-3 font-semibold">{item.case}</td>
                      <td className="py-3 pr-3">
                        <Badge variant={item.result === '성공' ? 'secondary' : 'outline'} className="font-black">{item.result}</Badge>
                      </td>
                      <td className="py-3 pr-3 font-black">{item.score}</td>
                      <td className="py-3 pr-3 text-muted-foreground">{item.tokens}</td>
                      <td className="py-3 text-muted-foreground">{item.duration}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="grid gap-5">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-black">
                  <Rocket className="size-4 text-primary" aria-hidden="true" />
                  배포 이력
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full min-w-[30rem] text-left text-sm">
                  <thead className="text-xs text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="py-2 pr-3 font-black">버전</th>
                      <th className="py-2 pr-3 font-black">상태</th>
                      <th className="py-2 pr-3 font-black">대상</th>
                      <th className="py-2 font-black">배포자</th>
                    </tr>
                  </thead>
                  <tbody>
                    {DEPLOYMENT_HISTORY.map((item) => (
                      <tr key={`${item.version}-${item.date}`} className="border-b border-border/60 last:border-0">
                        <td className="py-3 pr-3 font-black">{item.version}</td>
                        <td className="py-3 pr-3"><Badge variant="outline" className="font-black">{item.state}</Badge></td>
                        <td className="py-3 pr-3 text-muted-foreground">{item.target}</td>
                        <td className="py-3 text-muted-foreground">{item.author}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-black">
                  <BarChart3 className="size-4 text-primary" aria-hidden="true" />
                  활용 지표
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2">
                  {METRIC_CARDS.map((metric) => (
                    <div key={metric.label} className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs font-bold text-muted-foreground">{metric.label}</p>
                      <div className="mt-2 flex items-end justify-between gap-3">
                        <p className="text-xl font-black">{metric.value}</p>
                        <p className="text-xs font-black text-green-600">{metric.delta}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </div>
  );
}
