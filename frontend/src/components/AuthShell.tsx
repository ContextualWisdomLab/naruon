import Image from "next/image";

// Canonical auth-screen frame from docs/ui-ux/mockups/mockup_18.png "01. 로그인":
// a deep-navy brand backdrop with the Naruon mark and tagline on the left, and
// a white card carrying the actual form on the right (stacked on mobile).
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-stretch bg-[#0b1026] text-white">
      <div className="relative hidden flex-1 items-center justify-center overflow-hidden lg:flex">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,#1d2b64_0%,#0b1026_55%,#070b1c_100%)]"
        />
        <div
          aria-hidden="true"
          className="absolute -left-24 top-1/3 h-96 w-96 rounded-full bg-[#2563ff]/20 blur-3xl"
        />
        <div className="relative z-10 max-w-md space-y-6 px-10">
          <div className="flex items-center gap-3">
            <Image
              src="/brand/naruon-symbol.svg"
              alt=""
              width={48}
              height={48}
              priority
            />
            <div>
              <p className="text-3xl font-semibold tracking-tight">Naruon</p>
              <p className="text-sm text-white/60">나루온</p>
            </div>
          </div>
          <p className="text-xl leading-relaxed text-white/85">
            흩어진 메일의 흐름을 건너,
            <br />더 나은 판단과 실행으로.
          </p>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm rounded-2xl bg-white p-8 text-slate-900 shadow-2xl">
          {children}
        </div>
      </div>
    </main>
  );
}

export function AuthCardHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-6 space-y-3">
      <div className="flex items-center gap-2">
        <Image src="/brand/naruon-symbol.svg" alt="" width={28} height={28} />
        <span className="text-lg font-semibold tracking-tight">Naruon</span>
      </div>
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>
    </div>
  );
}
