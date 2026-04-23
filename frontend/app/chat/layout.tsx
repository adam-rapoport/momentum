import { DocumentsPanel } from "@/components/DocumentsPanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { Sidebar } from "@/components/Sidebar";
import { WsProvider } from "@/components/WsProvider";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <WsProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">{children}</main>
        <DocumentsPanel />
        <MemoryPanel />
      </div>
    </WsProvider>
  );
}
