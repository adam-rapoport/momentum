// The settings UI (SettingsApp) provides its own full-screen chrome + sidebar,
// so this layout is a passthrough.
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
