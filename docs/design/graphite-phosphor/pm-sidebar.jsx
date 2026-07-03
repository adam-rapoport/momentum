// pm-sidebar.jsx — left rail: traffic lights, new chat, search, sessions, footer.

const { useState: sbUseState, useMemo: sbUseMemo } = React;

function TrafficLights() {
  const dots = ['#FF5F57', '#FEBC2E', '#28C840'];
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }} aria-hidden="true">
      {dots.map((c) => (
        <span key={c} style={{ width: 12, height: 12, borderRadius: 999, background: c, boxShadow: 'inset 0 0 0 0.5px rgba(0,0,0,0.15)' }}></span>
      ))}
    </div>
  );
}

function SessionRow({ session, active, onSelect, onRename, onDelete, retro }) {
  const [hover, setHover] = sbUseState(false);
  const [confirming, setConfirming] = sbUseState(false);
  const [renaming, setRenaming] = sbUseState(false);
  const [draft, setDraft] = sbUseState(session.title);

  if (renaming) {
    return (
      <div style={{ padding: '2px 8px' }}>
        <input
          autoFocus value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => { setRenaming(false); if (draft.trim()) onRename(draft.trim()); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { setRenaming(false); if (draft.trim()) onRename(draft.trim()); }
            if (e.key === 'Escape') { setRenaming(false); setDraft(session.title); }
          }}
          aria-label="Session title"
          style={{
            width: '100%', height: 30, padding: '0 8px', fontSize: 13,
            border: '1px solid var(--accent)', borderRadius: 7,
            background: 'var(--bg-surface)', outline: 'none',
            boxShadow: '0 0 0 3px var(--accent-tint)',
          }}
        />
      </div>
    );
  }

  return (
    <div
      style={{ position: 'relative', padding: '0 8px' }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setConfirming(false); }}
    >
      <button
        type="button" className="focusable" onClick={onSelect}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, width: '100%',
          height: 32, padding: '0 10px', borderRadius: 7, textAlign: 'left',
          background: active ? 'var(--bg-surface)' : (hover ? 'var(--bg-raised)' : 'transparent'),
          boxShadow: active ? 'var(--shadow-card)' : 'none',
          border: active ? '1px solid var(--border-faint)' : '1px solid transparent',
          transition: 'background .1s ease',
        }}
      >
        {session.skill && <StatusDot tone="accent" retro={retro} size={6} />}
        <span style={{
          flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          fontSize: 13, fontWeight: active ? 600 : 450,
          color: active ? 'var(--text)' : 'var(--text-muted)',
          paddingRight: hover ? 44 : 0,
        }}>
          {session.title}
        </span>
      </button>
      {hover && (
        <div style={{
          position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)',
          display: 'flex', gap: 2, background: active ? 'var(--bg-surface)' : 'var(--bg-panel)',
          borderRadius: 6,
        }}>
          <button
            type="button" title="Rename" aria-label={`Rename ${session.title}`}
            onClick={() => { setDraft(session.title); setRenaming(true); }}
            style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5, color: 'var(--text-dim)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.background = 'var(--bg-inset)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <PixelIcon name="pencil" size={11} />
          </button>
          <button
            type="button"
            title={confirming ? 'Click again to delete' : 'Delete'}
            aria-label={`Delete ${session.title}`}
            onClick={() => { if (confirming) onDelete(); else setConfirming(true); }}
            style={{
              width: confirming ? 'auto' : 22, height: 22, padding: confirming ? '0 6px' : 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              borderRadius: 5, color: confirming ? '#fff' : 'var(--text-dim)',
              background: confirming ? 'var(--danger)' : 'transparent',
              fontSize: 10.5, fontWeight: 600,
            }}
            onMouseEnter={(e) => { if (!confirming) { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'var(--danger-soft)'; } }}
            onMouseLeave={(e) => { if (!confirming) { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.background = 'transparent'; } }}
          >
            {confirming ? 'Sure?' : <PixelIcon name="trash" size={11} />}
          </button>
        </div>
      )}
    </div>
  );
}

function Sidebar({ sessions, activeId, onSelect, onNew, onRename, onDelete, onOpenSettings, retro, profileName, theme, onToggleTheme }) {
  const [query, setQuery] = sbUseState('');

  const groups = sbUseMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q ? sessions.filter((s) => s.title.toLowerCase().includes(q)) : sessions;
    const order = ['Today', 'Yesterday', 'This week', 'Earlier'];
    const byGroup = {};
    for (const s of filtered) (byGroup[s.group] ||= []).push(s);
    return order.filter((g) => byGroup[g]?.length).map((g) => ({ name: g, items: byGroup[g] }));
  }, [sessions, query]);

  return (
    <aside style={{
      width: 'var(--sidebar-w)', flexShrink: 0, height: '100%',
      background: 'var(--bg-panel)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      {/* titlebar region — traffic lights + wordmark */}
      <div style={{ padding: '14px 16px 10px', display: 'flex', flexDirection: 'column', gap: 14, WebkitAppRegion: 'drag' }}>
        <TrafficLights />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <PmLogo size={16} />
          {retro > 0 ? (
            <span className="pixel" style={{ fontSize: 11, color: 'var(--text)', letterSpacing: '0.06em' }}>MOMENTUM</span>
          ) : (
            <span style={{ fontSize: 13.5, fontWeight: 700, letterSpacing: '-0.01em' }}>Momentum</span>
          )}
        </div>
      </div>

      {/* new chat + search */}
      <div style={{ padding: '0 12px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Btn kind="primary" onClick={onNew} style={{ width: '100%', justifyContent: 'flex-start', gap: 9 }}>
          <PixelIcon name="plus" size={12} />
          New chat
          <span style={{ marginLeft: 'auto', opacity: 0.7, fontSize: 11, fontFamily: 'var(--font-mono)' }}>⌘N</span>
        </Btn>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }}>
            <PixelIcon name="search" size={11} />
          </span>
          <input
            value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats"
            aria-label="Search chats"
            style={{
              width: '100%', height: 30, padding: '0 10px 0 28px', fontSize: 12.5,
              border: '1px solid var(--border)', borderRadius: 7,
              background: 'var(--bg-app)', color: 'var(--text)', outline: 'none',
            }}
            onFocus={(e) => { e.target.style.borderColor = 'var(--border-strong)'; }}
            onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; }}
          />
        </div>
      </div>

      {/* sessions */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingBottom: 8 }}>
        {groups.length === 0 && (
          <div style={{ padding: '16px 20px', fontSize: 12.5, color: 'var(--text-dim)' }}>
            {query ? 'No chats match.' : 'No chats yet.'}
          </div>
        )}
        {groups.map((g) => (
          <div key={g.name} style={{ marginTop: 12 }}>
            <div style={{ padding: '0 18px 4px' }}>
              <PxLabel retro={retro}>{g.name}</PxLabel>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {g.items.map((s) => (
                <SessionRow
                  key={s.id} session={s} active={s.id === activeId} retro={retro}
                  onSelect={() => onSelect(s.id)}
                  onRename={(title) => onRename(s.id, title)}
                  onDelete={() => onDelete(s.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* footer */}
      <DitherRule retro={retro} />
      <div style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <span style={{
          width: 26, height: 26, borderRadius: retro >= 2 ? 6 : 999, flexShrink: 0,
          background: 'var(--accent-tint)', color: 'var(--accent-text)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11.5, fontWeight: 700,
        }}>{(profileName || 'A')[0].toUpperCase()}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profileName}</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>local · encrypted</div>
        </div>
        <IconBtn
          icon={theme === 'dark' ? 'sun' : 'moon'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          onClick={onToggleTheme}
        />
        <IconBtn icon="gear" title="Settings" onClick={onOpenSettings} />
      </div>
    </aside>
  );
}

Object.assign(window, { Sidebar, TrafficLights });
