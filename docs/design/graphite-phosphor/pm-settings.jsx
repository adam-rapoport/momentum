// pm-settings.jsx — mac-style settings sheet: Models, Integrations,
// Web search, Profile, About. Opens as a centered modal window.

const { useState: stUseState, useEffect: stUseEffect } = React;

// ── shared bits ──────────────────────────────────────────────────────────────
function PaneTitle({ title, sub }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 16.5, fontWeight: 700, letterSpacing: '-0.01em' }}>{title}</div>
      {sub && <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 3, maxWidth: 480 }}>{sub}</div>}
    </div>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-card)', ...style,
    }}>{children}</div>
  );
}

// ── Models pane ──────────────────────────────────────────────────────────────
function ModelSlotCard({ tier, slot, onChange, retro }) {
  const [editing, setEditing] = stUseState(false);
  const [draftProvider, setDraftProvider] = stUseState(slot.providerId);
  const [draftKey, setDraftKey] = stUseState('');
  const provider = slot.providerId ? PM_PROVIDERS[slot.providerId] : null;
  const tierLabel = tier === 'light' ? 'Light model' : 'Heavy model';
  const tierHint = tier === 'light' ? 'Fast everyday turns — chat, recall, tools' : 'Big asks — drafting, long reasoning';
  const providers = Object.values(PM_PROVIDERS).filter((p) => p.tier === tier || p.tier === 'both');

  function save() {
    onChange({
      providerId: draftProvider,
      key: draftKey ? draftKey.slice(0, 6) + '••••••••••••' + draftKey.slice(-4) : slot.key,
      connected: true, status: 'ok', lastUsed: 'just now',
    });
    setEditing(false); setDraftKey('');
  }

  return (
    <Card>
      <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <span style={{ color: tier === 'light' ? 'var(--text-muted)' : 'var(--accent-text)', marginTop: 2 }}>
          <PixelIcon name={tier === 'light' ? 'bolt' : 'brain'} size={15} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13.5, fontWeight: 700 }}>{tierLabel}</span>
            {slot.connected && slot.status === 'ok' && <Chip tone="ok">connected</Chip>}
            {slot.connected && slot.status !== 'ok' && <Chip tone="danger">needs attention</Chip>}
            {!slot.connected && <Chip>not set</Chip>}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{tierHint}</div>

          {!editing && slot.connected && provider && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{provider.name}</span>
              <code style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{slot.key}</code>
              {slot.lastUsed && <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>last used {slot.lastUsed}</span>}
            </div>
          )}
          {!editing && !slot.connected && (
            <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--text-dim)' }}>
              No key yet — the {tier === 'light' ? 'fast' : 'heavy'} route falls back to {tier === 'light' ? 'nothing (required)' : 'the light model'}.
            </div>
          )}

          {editing && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {providers.map((p) => {
                  const sel = draftProvider === p.id;
                  return (
                    <button
                      key={p.id} type="button" disabled={!p.available} className="focusable"
                      onClick={() => setDraftProvider(p.id)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 7, padding: '6px 11px',
                        borderRadius: 8, fontSize: 12.5, fontWeight: 600,
                        border: '1px solid ' + (sel ? 'var(--accent)' : 'var(--border)'),
                        background: sel ? 'var(--accent-tint)' : 'var(--bg-surface)',
                        color: sel ? 'var(--accent-text)' : 'var(--text)',
                        opacity: p.available ? 1 : 0.45, cursor: p.available ? 'pointer' : 'not-allowed',
                      }}
                    >
                      {p.name}
                      <Chip tone={p.badgeKind === 'ok' ? 'ok' : 'dim'}>{p.badge}</Chip>
                    </button>
                  );
                })}
              </div>
              {draftProvider && PM_PROVIDERS[draftProvider] && (
                <div>
                  <input
                    value={draftKey} onChange={(e) => setDraftKey(e.target.value)}
                    placeholder={PM_PROVIDERS[draftProvider].keyHint || 'Paste API key'}
                    aria-label="API key"
                    style={{
                      width: '100%', height: 34, padding: '0 11px', fontSize: 12.5,
                      fontFamily: 'var(--font-mono)', border: '1px solid var(--border-strong)',
                      borderRadius: 8, background: 'var(--bg-raised)', outline: 'none', color: 'var(--text)',
                    }}
                  />
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 5 }}>
                    {PM_PROVIDERS[draftProvider].helpText} Stored encrypted on this Mac — never leaves it.
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn kind="primary" size="sm" disabled={!draftProvider || (!draftKey && !slot.connected)} onClick={save}>Save key</Btn>
                <Btn kind="ghost" size="sm" onClick={() => { setEditing(false); setDraftKey(''); }}>Cancel</Btn>
              </div>
            </div>
          )}
        </div>
        {!editing && (
          <Btn size="sm" onClick={() => { setDraftProvider(slot.providerId); setEditing(true); }}>
            {slot.connected ? 'Change' : 'Set up'}
          </Btn>
        )}
      </div>
    </Card>
  );
}

function ModelsPane({ slots, setSlots, retro }) {
  return (
    <div>
      <PaneTitle
        title="Models"
        sub="Momentum routes each turn: quick turns go to the light model, drafting and skills go to the heavy one."
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <ModelSlotCard tier="light" slot={slots.light} retro={retro} onChange={(s) => setSlots({ ...slots, light: { ...slots.light, ...s } })} />
        <ModelSlotCard tier="heavy" slot={slots.heavy} retro={retro} onChange={(s) => setSlots({ ...slots, heavy: { ...slots.heavy, ...s } })} />
      </div>
    </div>
  );
}

// ── Integrations pane ────────────────────────────────────────────────────────
function IntegrationsPane({ integrations, setIntegrations, retro }) {
  return (
    <div>
      <PaneTitle title="Integrations" sub="Connect the tools your work lives in. Each connection is optional and revocable." />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Object.values(PM_INTEGRATIONS).map((intg) => {
          const cur = integrations[intg.id] || { connected: false };
          return (
            <Card key={intg.id}>
              <div style={{ padding: '13px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}><PixelIcon name="plug" size={15} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13.5, fontWeight: 700 }}>{intg.name}</span>
                    <span style={{ fontSize: 11.5, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{intg.sub}</span>
                    {!intg.available && <Chip>Soon</Chip>}
                    {cur.connected && <Chip tone="ok">connected</Chip>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{intg.description}</div>
                  {cur.connected && cur.account && (
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                      {cur.account} · last used {cur.lastUsed}
                    </div>
                  )}
                </div>
                {intg.available ? (
                  cur.connected ? (
                    <Btn size="sm" kind="danger" onClick={() => setIntegrations({ ...integrations, [intg.id]: { connected: false } })}>Disconnect</Btn>
                  ) : (
                    <Btn size="sm" onClick={() => setIntegrations({ ...integrations, [intg.id]: { connected: true, account: 'adam@gmail.com', lastUsed: 'just now' } })}>Connect</Btn>
                  )
                ) : (
                  <Btn size="sm" disabled>Connect</Btn>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── Web search pane ──────────────────────────────────────────────────────────
function SearchPane({ search, setSearch, retro }) {
  return (
    <div>
      <PaneTitle title="Web search" sub="Give the agent live web access for research skills like /competitive-analysis." />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {PM_SEARCH_PROVIDERS.map((p) => {
          const active = search.providerId === p.id;
          return (
            <Card key={p.id}>
              <div style={{ padding: '13px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}><PixelIcon name="globe" size={15} /></span>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13.5, fontWeight: 700 }}>{p.name}</span>
                    <Chip tone={p.id === 'tavily' ? 'ok' : 'dim'}>{p.badge}</Chip>
                    {active && <Chip tone="accent">active</Chip>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{p.detail}</div>
                </div>
                <Btn size="sm" kind={active ? 'ghost' : 'default'} onClick={() => setSearch({ providerId: active ? null : p.id })}>
                  {active ? 'Remove' : 'Use'}
                </Btn>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── Profile pane ─────────────────────────────────────────────────────────────
function ProfilePane({ profile, setProfile, onReplayOnboarding }) {
  return (
    <div>
      <PaneTitle title="Profile" sub="Used to personalize drafts — your name in updates, your role in framing." />
      <Card style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Display name</span>
          <TextInput value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
          <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Role</span>
          <TextInput value={profile.role} onChange={(v) => setProfile({ ...profile, role: v })} />
          <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Company</span>
          <TextInput value={profile.company} onChange={(v) => setProfile({ ...profile, company: v })} />
        </div>
      </Card>
      <Card style={{ padding: '14px 18px', marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Run setup again</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Replay the first-launch onboarding wizard.</div>
        </div>
        <Btn size="sm" onClick={onReplayOnboarding}>Replay onboarding</Btn>
      </Card>
    </div>
  );
}

// ── About pane ───────────────────────────────────────────────────────────────
function AboutPane({ retro }) {
  const lines = [
    ['Version', '0.5.0-dev'],
    ['Shell', 'Tauri 2 · macOS arm64'],
    ['Backend', 'FastAPI sidecar · localhost:8000'],
    ['Data', '~/Library/Application Support/Momentum'],
    ['Keys', 'Fernet-encrypted local vault'],
  ];
  return (
    <div>
      <PaneTitle title="About" />
      <Card style={{ padding: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
          <PmLogo size={26} />
          {retro > 0
            ? <span className="pixel" style={{ fontSize: 15 }}>MOMENTUM</span>
            : <span style={{ fontSize: 17, fontWeight: 700 }}>Momentum</span>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {lines.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, fontSize: 12.5 }}>
              <span style={{ color: 'var(--text-muted)' }}>{k}</span>
              <code style={{ fontSize: 11.5, color: 'var(--text)', textAlign: 'right' }}>{v}</code>
            </div>
          ))}
        </div>
        <DitherRule retro={retro} style={{ margin: '14px 0' }} />
        <div style={{ fontSize: 11.5, color: 'var(--text-dim)', lineHeight: 1.6 }}>
          Everything stays on this Mac: conversations, memory, and documents live in a local SQLite
          database. Model providers see only the turns you send.
        </div>
      </Card>
    </div>
  );
}

// ── Settings window ──────────────────────────────────────────────────────────
function SettingsSheet({ open, onClose, settings, setSettings, retro, onReplayOnboarding }) {
  const [pane, setPane] = stUseState('models');

  stUseEffect(() => {
    if (!open) return;
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const items = [
    { key: 'models', label: 'Models', icon: 'bolt' },
    { key: 'integrations', label: 'Integrations', icon: 'plug' },
    { key: 'search', label: 'Web search', icon: 'globe' },
    { key: 'profile', label: 'Profile', icon: 'user' },
    { key: 'about', label: 'About', icon: 'box' },
  ];

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Settings"
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(10, 12, 14, 0.45)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32,
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="pm-enter" style={{
        width: 'min(820px, 100%)', height: 'min(560px, 100%)',
        background: 'var(--bg-app)', borderRadius: 14, overflow: 'hidden',
        boxShadow: 'var(--shadow-pop)', border: '1px solid var(--border)',
        display: 'flex',
      }}>
        {/* nav rail */}
        <div style={{
          width: 186, flexShrink: 0, background: 'var(--bg-panel)',
          borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '14px 16px 10px' }}>
            <TrafficLights />
          </div>
          <div style={{ padding: '4px 16px 10px' }}>
            <PxLabel retro={retro}>Settings</PxLabel>
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '0 8px' }}>
            {items.map((it) => {
              const active = pane === it.key;
              return (
                <button
                  key={it.key} type="button" className="focusable" onClick={() => setPane(it.key)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 9, height: 32, padding: '0 10px',
                    borderRadius: 7, fontSize: 13, fontWeight: active ? 600 : 500, textAlign: 'left',
                    background: active ? 'var(--bg-surface)' : 'transparent',
                    color: active ? 'var(--text)' : 'var(--text-muted)',
                    boxShadow: active ? 'var(--shadow-card)' : 'none',
                  }}
                >
                  <span style={{ color: active ? 'var(--accent-text)' : 'var(--text-dim)' }}>
                    <PixelIcon name={it.icon} size={13} />
                  </span>
                  {it.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* pane content */}
        <div style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '26px 30px', position: 'relative' }}>
          <div style={{ position: 'absolute', top: 14, right: 14 }}>
            <IconBtn icon="x" size={11} title="Close settings" onClick={onClose} />
          </div>
          {pane === 'models' && <ModelsPane slots={settings.slots} setSlots={(s) => setSettings({ ...settings, slots: s })} retro={retro} />}
          {pane === 'integrations' && <IntegrationsPane integrations={settings.integrations} setIntegrations={(s) => setSettings({ ...settings, integrations: s })} retro={retro} />}
          {pane === 'search' && <SearchPane search={settings.search} setSearch={(s) => setSettings({ ...settings, search: s })} retro={retro} />}
          {pane === 'profile' && <ProfilePane profile={settings.profile} setProfile={(p) => setSettings({ ...settings, profile: p })} onReplayOnboarding={onReplayOnboarding} />}
          {pane === 'about' && <AboutPane retro={retro} />}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { SettingsSheet });
