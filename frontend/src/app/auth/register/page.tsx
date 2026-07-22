"use client";

import { useCallback, useState } from "react";
import Link from "next/link";

import { AuthCardHeader, AuthShell } from "@/components/AuthShell";
import { startOidcLogin } from "@/lib/oidc-session";

type RegistrationPhase = "editing" | "submitting" | "registered";

const ERROR_MESSAGES: Record<string, string> = {
  email_already_registered: "이미 등록된 이메일입니다. 바로 로그인해 주세요.",
  invalid_email_address: "이메일 주소 형식을 확인해 주세요.",
  invalid_registration_request: "입력값을 확인해 주세요.",
  invalid_password: "비밀번호에 사용할 수 없는 문자가 있습니다.",
  registration_rate_limited: "요청이 많습니다. 잠시 후 다시 시도해 주세요.",
  registration_unavailable:
    "지금은 가입을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.",
};

const INPUT_CLASS =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-[#2563ff] focus:outline-none focus:ring-2 focus:ring-[#2563ff]/20";
const LABEL_CLASS = "text-sm font-medium text-slate-700";

function errorMessageFrom(payload: unknown): string {
  const detail =
    payload && typeof payload === "object"
      ? (payload as { detail?: { error_code?: string } }).detail
      : undefined;
  const errorCode = detail?.error_code;
  return (
    (errorCode && ERROR_MESSAGES[errorCode]) ||
    ERROR_MESSAGES.registration_unavailable
  );
}

export default function RegisterPage() {
  const [phase, setPhase] = useState<RegistrationPhase>("editing");
  const [emailAddress, setEmailAddress] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setFormError(null);
      if (password !== passwordConfirm) {
        setFormError("비밀번호가 서로 다릅니다.");
        return;
      }
      if (password.length < 10) {
        setFormError("비밀번호는 10자 이상이어야 합니다.");
        return;
      }
      setPhase("submitting");
      try {
        const trimmedName = displayName.trim();
        const [firstName, ...restName] = trimmedName.split(/\s+/);
        const response = await fetch("/auth/register/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            email_address: emailAddress,
            initial_password: password,
            first_name: firstName || null,
            last_name: restName.join(" ") || null,
          }),
        });
        if (!response.ok) {
          setFormError(errorMessageFrom(await response.json().catch(() => null)));
          setPhase("editing");
          return;
        }
        setPhase("registered");
      } catch {
        setFormError(ERROR_MESSAGES.registration_unavailable);
        setPhase("editing");
      }
    },
    [displayName, emailAddress, password, passwordConfirm],
  );

  const handleContinueToLogin = useCallback(async () => {
    try {
      await startOidcLogin({ returnTo: "/" });
    } catch {
      setFormError("로그인을 시작하지 못했습니다. 홈에서 다시 시도해 주세요.");
    }
  }, []);

  if (phase === "registered") {
    return (
      <AuthShell>
        <AuthCardHeader
          title="가입 완료"
          subtitle="이제 로그인하면서 패스키를 등록합니다."
        />
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            패스키(지문·얼굴·PIN) 등록이 끝나면 다음 로그인부터는 비밀번호 없이
            패스키만 사용합니다.
          </p>
          <button
            type="button"
            onClick={handleContinueToLogin}
            className="w-full rounded-lg bg-[#2563ff] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1d4fd7]"
          >
            로그인하고 패스키 등록하기
          </button>
          {formError ? (
            <p className="text-xs text-red-600" role="alert">
              {formError}
            </p>
          ) : null}
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <AuthCardHeader
        title="Naruon 가입"
        subtitle="이메일로 계정을 만들고, 첫 로그인에서 패스키를 등록합니다."
      />
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1 text-left">
          <label htmlFor="register-email" className={LABEL_CLASS}>
            이메일
          </label>
          <input
            id="register-email"
            type="email"
            required
            autoComplete="email"
            value={emailAddress}
            onChange={(event) => setEmailAddress(event.target.value)}
            className={INPUT_CLASS}
          />
        </div>
        <div className="space-y-1 text-left">
          <label htmlFor="register-name" className={LABEL_CLASS}>
            이름 <span className="font-normal text-slate-400">(선택)</span>
          </label>
          <input
            id="register-name"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className={INPUT_CLASS}
          />
        </div>
        <div className="space-y-1 text-left">
          <label htmlFor="register-password" className={LABEL_CLASS}>
            초기 비밀번호
          </label>
          <input
            id="register-password"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={INPUT_CLASS}
          />
          <p className="text-xs text-slate-500">
            첫 로그인에만 쓰는 임시 비밀번호입니다(10자 이상). 패스키 등록 후에는
            자동으로 회수됩니다.
          </p>
        </div>
        <div className="space-y-1 text-left">
          <label htmlFor="register-password-confirm" className={LABEL_CLASS}>
            비밀번호 확인
          </label>
          <input
            id="register-password-confirm"
            type="password"
            required
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            className={INPUT_CLASS}
          />
        </div>
        {formError ? (
          <p className="text-xs text-red-600" role="alert">
            {formError}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={phase === "submitting"}
          className="w-full rounded-lg bg-[#2563ff] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1d4fd7] disabled:opacity-60"
        >
          {phase === "submitting" ? "가입 처리 중…" : "가입하기"}
        </button>
      </form>
      <p className="mt-6 border-t border-slate-100 pt-4 text-center text-xs text-slate-500">
        이미 계정이 있으신가요?{" "}
        <Link href="/" className="font-semibold text-[#2563ff] hover:underline">
          로그인으로 이동
        </Link>
      </p>
    </AuthShell>
  );
}
