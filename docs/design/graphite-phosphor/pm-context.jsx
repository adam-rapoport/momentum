// pm-context.jsx — right panel: tabbed Memory / Documents (merged context panel).

const { useState: cxUseState, useMemo: cxUseMemo } = React;

function ContextTabs({ tab, setTab, retro }) {
  const tabs = [
    { key: 'memory', label: 'Memory', icon: 'brain' },
    { key: 'documents', label: 'Documents', icon: 'doc' },
  ];
  return (
    <div role="tablist" aria-label="Context panel" style={{
      display: 'flex', gap: 4, padding: 3, borderRadius: 9,
      background: 'var(--bg-inset)', margin: '0 12px',
    }}>
      {tabs.map((t) => {
        const active = tab === t.key;
        return (
          <button
            key={t.key} role="tab" aria-selected={active} className="focusable"
            onClick={() => setTab(t.key)}
            style={{
              flex: 1, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              borderRadius: 7, fontSize: 12.5, fontWeight: active ? 600 : 500,
              background: active ? 'var(--bg-surface)' : 'transparent',
              color: active ? 'var(--text)' : 'var(--text-muted)',
              boxShadow: active ? 'var(--shadow-card)' : 'none',
              transition: 'background .12s ease',
            }}
          >
            <PixelIcon name={t.icon} size={12} />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function MemoryList({ retro }) {
  const [selectedId, setSelectedId] = cxUseState(null);
  const grouped = cxUseMemo(() => {
    const out = {};
    for (const m of PM_MEMORIES) (out[m.type] ||= []).push(m);
    return out;
  }, []);
  const selected = PM_MEMORIES.find((m) => m.id === selectedId);
  const typeOrder = Object.keys(PM_MEMORY_TYPES);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '10px 0' }}>
        {typeOrder.filter((t) => grouped[t]?.length).map((t) => (
          <div key={t} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 16px 4px', color: 'var(--text-dim)' }}>
              <PixelIcon name={PM_MEMORY_TYPES[t].icon} size={10} />
              <PxLabel retro={retro}>{PM_MEMORY_TYPES[t].label}</PxLabel>
              <span style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>{grouped[t].length}</span>
            </div>
            {grouped[t].map((m) => {
              const active = m.id === selectedId;
              return (
                <button
                  key={m.id} type="button" className="focusable"
                  onClick={() => setSelectedId(active ? null : m.id)}
                  style={{
                    display: 'block', width: 'calc(100% - 16px)', margin: '0 8px', textAlign: 'left',
                    padding: '7px 10px', borderRadius: 7,
                    background: active ? 'var(--bg-surface)' : 'transparent',
                    boxShadow: active ? 'var(--shadow-card)' : 'none',
                    transition: 'background .1s ease',
                  }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--bg-raised)'; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}
                >
                  <div style={{ fontSize: 12.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.title}</div>
                  <div style={{
                    fontSize: 11.5, color: 'var(--text-muted)', marginTop: 1,
                    display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  }}>{m.summary}</div>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {selected && (
        <div style={{
          borderTop: '1px solid var(--border)', background: 'var(--bg-surface)',
          maxHeight: '46%', overflowY: 'auto', flexShrink: 0,
        }}>
          <div style={{
            position: 'sticky', top: 0, background: 'var(--bg-surface)',
            padding: '10px 14px 8px', borderBottom: '1px solid var(--border-faint)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {selected.title}
            </div>
            <IconBtn icon="x" size={11} title="Close memory detail" onClick={() => setSelectedId(null)} style={{ width: 24, height: 24 }} />
          </div>
          <div style={{ padding: '10px 14px 14px' }}>
            {selected.tags?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 8 }}>
                {selected.tags.map((tag) => <Chip key={tag} mono>{tag}</Chip>)}
              </div>
            )}
            <div style={{ fontSize: 12.5, lineHeight: 1.55 }}>
              <Markdownish text={selected.body} />
            </div>
            <div style={{ marginTop: 10, fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              Updated {selected.updated}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DocumentsList({ retro }) {
  const grouped = cxUseMemo(() => {
    const out = {};
    for (const d of PM_DOCUMENTS) (out[d.backend] ||= []).push(d);
    return out;
  }, []);
  const labels = { google_docs: 'Google Docs', local: 'On this Mac' };

  return (
    <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '10px 0' }}>
      {['google_docs', 'local'].filter((b) => grouped[b]?.length).map((b) => (
        <div key={b} style={{ marginBottom: 14 }}>
          <div style={{ padding: '0 16px 4px' }}>
            <PxLabel retro={retro}>{labels[b]}</PxLabel>
          </div>
          {grouped[b].map((d) => (
            <div
              key={d.id}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 9,
                margin: '0 8px', padding: '7px 10px', borderRadius: 7,
                transition: 'background .1s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-raised)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ color: 'var(--text-dim)', marginTop: 2 }}>
                <PixelIcon name="doc" size={12} />
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.title}</div>
                <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginTop: 1 }}>{d.updated}</div>
              </div>
              {d.url ? (
                <a
                  href={d.url} onClick={(e) => e.preventDefault()}
                  title="Open in Google Docs"
                  style={{
                    flexShrink: 0, fontSize: 10.5, fontWeight: 600, color: 'var(--accent-text)',
                    textDecoration: 'none', border: '1px solid var(--border)', borderRadius: 5,
                    padding: '1px 6px', background: 'var(--bg-surface)',
                  }}
                >Open ↗</a>
              ) : (
                <span style={{ flexShrink: 0, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginTop: 3 }}>local</span>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ContextPanel({ onClose, retro }) {
  const [tab, setTab] = cxUseState('memory');
  return (
    <aside style={{
      width: 'var(--context-w)', flexShrink: 0, height: '100%',
      background: 'var(--bg-panel)', borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{ height: 'var(--toolbar-h)', display: 'flex', alignItems: 'center', padding: '0 8px 0 16px', gap: 8, flexShrink: 0 }}>
        <PxLabel retro={retro} color="var(--text-muted)">Context</PxLabel>
        <span style={{ flex: 1 }}></span>
        <IconBtn icon="x" size={11} title="Close context panel" onClick={onClose} />
      </div>
      <ContextTabs tab={tab} setTab={setTab} retro={retro} />
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, marginTop: 6 }}>
        {tab === 'memory' ? <MemoryList retro={retro} /> : <DocumentsList retro={retro} />}
      </div>
    </aside>
  );
}

Object.assign(window, { ContextPanel });
