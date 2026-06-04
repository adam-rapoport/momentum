import { BootGate } from "@/components/BootGate";
import { DocumentsPanel } from "@/components/DocumentsPanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { Sidebar } from "@/components/Sidebar";
import { WsProvider } from "@/components/WsProvider";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  // BootGate waits for the backend to be ready (showing a loading screen) and
  // routes first-run users to onboarding, so everything below it — the
  // WebSocket connection and all the on-mount data fetches — only runs once
  // the backend is actually serving.
  return (
    <BootGate>
      <WsProvider>
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 flex flex-col min-w-0">{children}</main>
          <DocumentsPanel />
          <MemoryPanel />
        </div>
      </WsProvider>
    </BootGate>
  );
}
