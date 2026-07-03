// pm-onboarding.jsx — first-launch wizard, full-window takeover.
// Welcome → Light model → Heavy model → Connect tools → Done.

const { useState: obUseState } = React;

function ObStepperBar({ steps, idx, retro }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 36 }}>
      {steps.map((s, i) => {
        const done = i < idx, current = i === idx;
        return (
          <React.Fragment key={s.key}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{
                width: 20, height: 20, flexShrink: 0,
                borderRadius: retro >= 2 ? 4 : 999,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: done ? 'var(--accent)' : current ? 'var(--accent-tint)' : 'var(--bg-inset)',
                color: done ? 'var(--accent-fg)' : current ? 'var(--accent-text)' : 'var(--text-dim)',
                border: '1px solid ' + (done || current ? 'var(--accent)' : 'var(--border-strong)'),
                fontSize: 10.5, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}>
                {done ? <PixelIcon name="check" size={10} /> : i + 1}
              </span>
              <span style={{
                fontSize: 12, fontWeight: current ? 700 : 500,
                color: current ? 'var(--text)' : 'var(--text-dim)', whiteSpace: 'nowrap',
              }}>{s.label}</span>
            </div>
            {i < steps.length - 1 && <div style={{ flex: 1, height: 1, background: 'var(--border)' }}></div>}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function ObWelcome({ onNext, retro }) {
  return (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, padding: '24px 0' }}>
      <PmLogo size={44} />
      {retro > 0
        ? <div className="pixel" style={{ fontSize: 22, letterSpacing: '0.06em' }}>MOMENTUM</div>
        : <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em' }}>Momentum</div>}
      <div style={{ fontSize: 14.5, color: 'var(--text-muted)', maxWidth: 420, lineHeight: 1.6 }}>
        An AI agent for product management work — PRDs, stakeholder updates, meeting prep —
        with persistent memory, running entirely on your Mac.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
        <Btn kind="primary" size="lg" onClick={onNext}>Set up in 2 minutes</Btn>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
          you'll need one free API key · no account, no cloud
        </span>
      </div>
    </div>
  );
}

function ObModelStep({ tier, slot, setSlot, retro }) {
  const providers = Object.values(PM_PROVIDERS).filter((p) => p.tier === tier || p.tier === 'both');
  const chosen = slot.providerId ? PM_PROVIDERS[slot.providerId] : null;
  const keyOk = chosen && slot.draftKey && slot.draftKey.startsWith(chosen.keyPrefix || '') && slot.draftKey.length >= (chosen.keyLength ? chosen.keyLength[0] : 8);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <PxLabel retro={retro} color="var(--accent-text)">{tier === 'light' ? 'Step 2 · Light model' : 'Step 3 · Heavy model'}</PxLabel>
        <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em', marginTop: 6 }}>
          {tier === 'light' ? 'Pick a fast everyday model' : 'Pick a smarter model for the big asks'}
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.55 }}>
          {tier === 'light'
            ? 'Handles chat, memory recall, and tool calls. Free tiers are plenty.'
            : 'Used when you draft PRDs and long documents. Optional — skip and the light model covers everything.'}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {providers.map((p) => {
          const sel = slot.providerId === p.id;
          return (
            <button
              key={p.id} type="button" disabled={!p.available} className="focusable"
              onClick={() => setSlot({ ...slot, providerId: p.id })}
              style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', textAlign: 'left',
                borderRadius: 12, border: '1px solid ' + (sel ? 'var(--accent)' : 'var(--border)'),
                background: sel ? 'var(--accent-tint-2)' : 'var(--bg-surface)',
                boxShadow: sel ? '0 0 0 3px var(--accent-tint)' : 'var(--shadow-card)',
                opacity: p.available ? 1 : 0.5, cursor: p.available ? 'pointer' : 'not-allowed',
                transition: 'border-color .12s ease, box-shadow .12s ease',
              }}
            >
              <span style={{
                width: 16, height: 16, flexShrink: 0, borderRadius: retro >= 2 ? 3 : 999,
                border: '2px solid ' + (sel ? 'var(--accent)' : 'var(--border-strong)'),
                background: sel ? 'var(--accent)' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {sel && <span style={{ width: 5, height: 5, background: 'var(--accent-fg)', borderRadius: retro >= 2 ? 0 : 999 }}></span>}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 700 }}>{p.name}</span>
                  <Chip tone={p.badgeKind === 'ok' ? 'ok' : 'dim'}>{p.badge}</Chip>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{p.description}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 3 }}>{p.pricing}</div>
              </div>
            </button>
          );
        })}
      </div>

      {chosen && (
        <div>
          <input
            value={slot.draftKey || ''} onChange={(e) => setSlot({ ...slot, draftKey: e.target.value })}
            placeholder={chosen.keyHint}
            aria-label={`${chosen.name} API key`}
            style={{
              width: '100%', height: 40, padding: '0 13px', fontSize: 13, fontFamily: 'var(--font-mono)',
              border: '1px solid ' + (keyOk ? 'var(--ok)' : 'var(--border-strong)'), borderRadius: 10,
              background: 'var(--bg-surface)', outline: 'none', color: 'var(--text)',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: keyOk ? 'var(--ok)' : 'var(--text-dim)', marginTop: 6 }}>
            {keyOk && <PixelIcon name="check" size={10} />}
            {keyOk ? 'Format looks right — we\u2019ll verify on first use.' : chosen.helpText}
          </div>
        </div>
      )}
    </div>
  );
}

function ObIntegrations({ connected, setConnected, retro }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <PxLabel retro={retro} color="var(--accent-text)">Step 4 · Optional</PxLabel>
        <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em', marginTop: 6 }}>Connect your tools — or do this later</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
          None of these are required. Everything is available later in Settings.
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.values(PM_INTEGRATIONS).map((intg) => (
          <div key={intg.id} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
            borderRadius: 12, border: '1px solid var(--border)', background: 'var(--bg-surface)',
            boxShadow: 'var(--shadow-card)', opacity: intg.available ? 1 : 0.55,
          }}>
            <span style={{ color: 'var(--text-muted)' }}><PixelIcon name="plug" size={14} /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13.5, fontWeight: 700 }}>{intg.name}</span>
                <span style={{ fontSize: 11.5, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{intg.sub}</span>
                {!intg.available && <Chip>Soon</Chip>}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{intg.description}</div>
            </div>
            {intg.available ? (
              connected[intg.id]
                ? <Chip tone="ok">connected</Chip>
                : <Btn size="sm" onClick={() => setConnected({ ...connected, [intg.id]: true })}>Connect</Btn>
            ) : (
              <Btn size="sm" disabled>Connect</Btn>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ObDone({ state, onFinish, retro }) {
  const light = state.light.providerId ? PM_PROVIDERS[state.light.providerId] : null;
  const heavy = state.heavy.providerId ? PM_PROVIDERS[state.heavy.providerId] : null;
  const rows = [
    ['Light model', light ? light.name : 'Not set'],
    ['Heavy model', heavy ? heavy.name : 'Falls back to light'],
    ['Google', state.connected.google ? 'Connected' : 'Skipped'],
    ['Memory & data', 'On this Mac, encrypted'],
  ];
  return (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, padding: '12px 0' }}>
      <span style={{
        width: 52, height: 52, borderRadius: retro >= 2 ? 10 : 999,
        background: 'var(--accent-tint)', color: 'var(--accent-text)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <PixelIcon name="check" size={24} />
      </span>
      <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em' }}>You're set</div>
      <div style={{
        width: '100%', maxWidth: 380, textAlign: 'left',
        border: '1px solid var(--border)', borderRadius: 12, background: 'var(--bg-surface)',
        boxShadow: 'var(--shadow-card)', padding: '14px 18px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
            <span style={{ color: 'var(--text-muted)' }}>{k}</span>
            <span style={{ fontWeight: 600 }}>{v}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--text-muted)', maxWidth: 400, lineHeight: 1.55 }}>
        Try <code>what do you know about Sarah?</code> or kick off <code>/write-prd</code> with a feature idea.
      </div>
      <Btn kind="primary" size="lg" onClick={onFinish}>Start working →</Btn>
    </div>
  );
}

function OnboardingWizard({ onFinish, retro }) {
  const [idx, setIdx] = obUseState(0);
  const [state, setState] = obUseState({
    light: { providerId: null, draftKey: '' },
    heavy: { providerId: null, draftKey: '' },
    connected: {},
  });
  const steps = [
    { key: 'welcome', label: 'Welcome' },
    { key: 'light', label: 'Light model' },
    { key: 'heavy', label: 'Heavy model' },
    { key: 'tools', label: 'Tools' },
    { key: 'done', label: 'Done' },
  ];
  const step = steps[idx];

  function canAdvance() {
    if (step.key === 'light') {
      const p = state.light.providerId ? PM_PROVIDERS[state.light.providerId] : null;
      return p && state.light.draftKey.startsWith(p.keyPrefix || '') && state.light.draftKey.length >= (p.keyLength ? p.keyLength[0] : 8);
    }
    return true;
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 90, background: 'var(--bg-app)', overflowY: 'auto' }}>
      <div style={{ height: 38, WebkitAppRegion: 'drag', display: 'flex', alignItems: 'center', padding: '0 16px', position: 'sticky', top: 0 }}>
        <TrafficLights />
      </div>
      <div style={{ maxWidth: 640, margin: '0 auto', padding: '28px 32px 60px' }}>
        {idx > 0 && idx < steps.length - 1 && <ObStepperBar steps={steps} idx={idx} retro={retro} />}

        {step.key === 'welcome' && <ObWelcome retro={retro} onNext={() => setIdx(1)} />}
        {step.key === 'light' && <ObModelStep tier="light" retro={retro} slot={state.light} setSlot={(s) => setState({ ...state, light: s })} />}
        {step.key === 'heavy' && <ObModelStep tier="heavy" retro={retro} slot={state.heavy} setSlot={(s) => setState({ ...state, heavy: s })} />}
        {step.key === 'tools' && <ObIntegrations retro={retro} connected={state.connected} setConnected={(c) => setState({ ...state, connected: c })} />}
        {step.key === 'done' && <ObDone state={state} retro={retro} onFinish={onFinish} />}

        {idx > 0 && idx < steps.length - 1 && (
          <div style={{ marginTop: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Btn kind="ghost" onClick={() => setIdx((i) => Math.max(0, i - 1))}>← Back</Btn>
            <div style={{ display: 'flex', gap: 8 }}>
              {(step.key === 'tools' || step.key === 'heavy') && (
                <Btn onClick={() => setIdx((i) => i + 1)}>Skip for now</Btn>
              )}
              <Btn kind="primary" disabled={!canAdvance()} onClick={() => setIdx((i) => i + 1)}>
                {step.key === 'tools' ? 'Finish setup →' : 'Continue →'}
              </Btn>
            </div>
          </div>
        )}
        {step.key === 'welcome' && (
          <div style={{ textAlign: 'center', marginTop: 18 }}>
            <button type="button" onClick={onFinish} style={{ fontSize: 12, color: 'var(--text-dim)', textDecoration: 'underline', textUnderlineOffset: 3 }}>
              Skip — explore with no key
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { OnboardingWizard });
