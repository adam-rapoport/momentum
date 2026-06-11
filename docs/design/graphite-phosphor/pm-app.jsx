// pm-app.jsx — shell: toolbar, layout, state, theme + tweaks wiring.

const { useState: apUseState, useEffect: apUseEffect, useMemo: apUseMemo, useRef: apUseRef } = React;

// ── Accent system — theme-aware derivations via color-mix ────────────────────
const PM_ACCENT_OPTIONS = ['#0F9D63', '#2563EB', '#D9622B', '#7A5AE0'];

function accentVars(hex, theme) {
  if (theme === 'dark') {
    return {
      '--accent': `color-mix(in oklab, ${hex} 78%, white)`,
      '--accent-bright': `color-mix(in oklab, ${hex} 65%, white)`,
      '--accent-fg': '#0B0D0E',
      '--accent-tint': `color-mix(in oklab, ${hex} 26%, #1A1B1E)`,
      '--accent-tint-2': `color-mix(in oklab, ${hex} 16%, #1A1B1E)`,
      '--accent-text': `color-mix(in oklab, ${hex} 55%, white)`,
    };
  }
  return {
    '--accent': hex,
    '--accent-bright': hex,
    '--accent-fg': '#FFFFFF',
    '--accent-tint': `color-mix(in oklab, ${hex} 15%, white)`,
    '--accent-tint-2': `color-mix(in oklab, ${hex} 8%, white)`,
    '--accent-text': `color-mix(in oklab, ${hex} 82%, black)`,
  };
}

// ── Toolbar ──────────────────────────────────────────────────────────────────
function Toolbar({ session, retro, contextOpen, onToggleContext }) {
  return (
    <header style={{
      height: 'var(--toolbar-h)', flexShrink: 0,
      display: 'flex', alignItems: 'center', gap: 10, padding: '0 10px 0 20px',
      borderBottom: '1px solid var(--border)', background: 'var(--bg-app)',
      WebkitAppRegion: 'drag',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
        {session ? (
          <span style={{ fontSize: 13.5, fontWeight: 650, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {session.title}
          </span>
        ) : (
          <span style={{ fontSize: 13.5, fontWeight: 650, color: 'var(--text-dim)' }}>New chat</span>
        )}
        {session?.skill && (
          <Chip tone="accent" mono title={`Skill /${session.skill.name} active — ${session.skill.phase} phase. /cancel-skill to exit.`}>
            <StatusDot tone="accent" retro={retro} size={5} pulse />
            /{session.skill.name} · {session.skill.phase}
          </Chip>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, WebkitAppRegion: 'no-drag' }}>
        {session?.model && (
          <Chip mono tone={pmModelHeavy(session.model) ? 'warn' : 'dim'} title={`Last turn ran on ${session.model}`}>
            <StatusDot tone={pmModelHeavy(session.model) ? 'warn' : 'dim'} retro={retro} size={5} />
            {pmModelName(session.model)}
          </Chip>
        )}
        {session && (
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }} title="Session cost so far">
            ${session.cost.toFixed(4)}
          </span>
        )}
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }} title="Backend connected on localhost:8000">
          <StatusDot tone="ok" retro={retro} size={6} />
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>local</span>
        </span>
        <IconBtn icon="panel" title={contextOpen ? 'Hide context panel' : 'Show context panel'} active={contextOpen} onClick={onToggleContext} />
      </div>
    </header>
  );
}

// ── App ──────────────────────────────────────────────────────────────────────
function PmApp() {
  const [t, setTweak] = useTweaks({
    theme: 'light',
    accent: '#0F9D63',
    retroLevel: 'subtle',   // off | subtle | full
    bubbleStyle: 'bubble',  // (reserved)
  });
  const retro = t.retroLevel === 'off' ? 0 : t.retroLevel === 'full' ? 2 : 1;

  const [sessions, setSessions] = apUseState(() => PM_SESSIONS.map((s) => ({ ...s, messages: [...s.messages] })));
  const [activeId, setActiveId] = apUseState(null);
  const [contextOpen, setContextOpen] = apUseState(true);
  const [settingsOpen, setSettingsOpen] = apUseState(false);
  const [onboarding, setOnboarding] = apUseState(false);
  const [autoStartId, setAutoStartId] = apUseState(null);

  const [settings, setSettings] = apUseState({
    slots: {
      light: { providerId: 'groq', key: 'gsk_••••••••••••••••••••mPq3', connected: true, status: 'ok', lastUsed: '2 minutes ago' },
      heavy: { providerId: 'geminiFree', key: 'AIza••••••••••••••••V4kP', connected: true, status: 'ok', lastUsed: '14 minutes ago' },
    },
    integrations: { google: { connected: true, account: 'adam@gmail.com', lastUsed: '2 hours ago' } },
    search: { providerId: 'tavily' },
    profile: { name: 'Adam Rapoport', role: 'Product Manager', company: 'Acme' },
  });

  const active = sessions.find((s) => s.id === activeId) || null;

  // theme + accent vars on <html>
  apUseEffect(() => {
    document.documentElement.setAttribute('data-theme', t.theme);
    const vars = accentVars(t.accent, t.theme);
    for (const [k, v] of Object.entries(vars)) document.documentElement.style.setProperty(k, v);
  }, [t.theme, t.accent]);

  function updateSession(id, patch) {
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function newChat() {
    setActiveId(null);
    setAutoStartId(null);
  }

  function sendFromHome(text) {
    const id = 's-new-' + Date.now();
    const title = text.startsWith('/')
      ? text.split(' ')[0].slice(1).replace(/-/g, ' ')
      : (text.length > 34 ? text.slice(0, 34) + '…' : text);
    const s = {
      id, title: title.charAt(0).toUpperCase() + title.slice(1),
      group: 'Today', model: 'llama-4-scout', cost: 0.0004,
      skill: null, awaitingReview: null,
      messages: [{ role: 'user', text }],
    };
    setSessions((prev) => [s, ...prev]);
    setActiveId(id);
    setAutoStartId(id);
  }

  // ⌘N — new chat
  apUseEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        newChat();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div style={{ height: '100vh', display: 'flex', background: 'var(--bg-app)', overflow: 'hidden' }}>
      <Sidebar
        sessions={sessions} activeId={activeId} retro={retro}
        profileName={settings.profile.name}
        theme={t.theme}
        onToggleTheme={() => setTweak('theme', t.theme === 'dark' ? 'light' : 'dark')}
        onSelect={(id) => { setActiveId(id); setAutoStartId(null); }}
        onNew={newChat}
        onRename={(id, title) => updateSession(id, { title })}
        onDelete={(id) => {
          setSessions((prev) => prev.filter((s) => s.id !== id));
          if (id === activeId) setActiveId(null);
        }}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Toolbar
          session={active} retro={retro}
          contextOpen={contextOpen} onToggleContext={() => setContextOpen((x) => !x)}
        />
        <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
          {active ? (
            <ChatView
              key={active.id}
              session={active}
              retro={retro}
              autoStart={autoStartId === active.id}
              onAutoStarted={() => setAutoStartId(null)}
              onUpdateSession={(patch) => updateSession(active.id, patch)}
            />
          ) : (
            <HomeView onSendNew={sendFromHome} retro={retro} profileName={settings.profile.name} />
          )}
          {contextOpen && <ContextPanel onClose={() => setContextOpen(false)} retro={retro} />}
        </div>
      </main>

      <SettingsSheet
        open={settingsOpen} onClose={() => setSettingsOpen(false)}
        settings={settings} setSettings={setSettings} retro={retro}
        onReplayOnboarding={() => { setSettingsOpen(false); setOnboarding(true); }}
      />

      {onboarding && <OnboardingWizard retro={retro} onFinish={() => setOnboarding(false)} />}

      <TweaksPanel title="Tweaks">
        <TweakSection label="Appearance" />
        <TweakRadio label="Theme" value={t.theme} options={['light', 'dark']} onChange={(v) => setTweak('theme', v)} />
        <TweakColor label="Accent" value={t.accent} options={PM_ACCENT_OPTIONS} onChange={(v) => setTweak('accent', v)} />
        <TweakSection label="Retro splash" />
        <TweakRadio label="Pixel details" value={t.retroLevel} options={['off', 'subtle', 'full']} onChange={(v) => setTweak('retroLevel', v)} />
        <TweakSection label="Screens" />
        <TweakButton label="Replay onboarding" onClick={() => setOnboarding(true)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<PmApp />);
