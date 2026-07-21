import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { DashboardLayout } from "@/components/DashboardLayout";
import "./globals.css";

export const metadata: Metadata = {
  title: "Naruon | AI Email Workspace",
  description: "메일, 일정, 관계, 판단 포인트를 하나의 맥락으로 연결하는 AI 메일 워크스페이스",
  icons: {
    icon: "/brand/naruon-app-icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <AuthGate>
          <DashboardLayout>{children}</DashboardLayout>
        </AuthGate>
      </body>
    </html>
  );
}
