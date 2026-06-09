import { BootGate } from "@/components/BootGate";

// The settings UI (SettingsApp) provides its own full-screen chrome + sidebar.
// BootGate keeps it from rendering against a dead/booting backend — without
// it, every provider showed as "Not connected" while the sidecar was still
// starting (or after it crashed), which read as data loss.
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <BootGate>{children}</BootGate>;
}
