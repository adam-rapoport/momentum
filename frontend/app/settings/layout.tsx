import Link from "next/link";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen flex flex-col bg-neutral-50">
      <header className="h-14 shrink-0 border-b border-neutral-200 bg-white px-4 flex items-center gap-3">
        <Link href="/chat" className="text-sm text-neutral-600 hover:text-neutral-900">
          ← Back to chat
        </Link>
        <div className="text-neutral-300">›</div>
        <div className="text-sm font-semibold">Settings</div>
      </header>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
