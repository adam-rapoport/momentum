// pm-composer.jsx — the floating input: autosizing textarea, slash-command
// menu, send/stop control, model routing hint.

const { useState: cpUseState, useEffect: cpUseEffect, useRef: cpUseRef, useMemo: cpUseMemo } = React;

const PM_CMD_RE = /^\/[a-z0-9-]*$/i;

function Composer({ onSend, onCancel, isStreaming, retro, big, autoFocus, seed }) {
  const [value, setValue] = cpUseState('');
  const [selected, setSelected] = cpUseState(0);
  const [dismissed, setDismissed] = cpUseState(false);
  const taRef = cpUseRef(null);

  // seed: external prefill (home-screen skill chips)
  cpUseEffect(() => {
    if (seed && seed.text != null) {
      setValue(seed.text);
      setDismissed(true);
      const el = taRef.current;
      if (el) { el.focus(); }
    }
  }, [seed]);

  // autosize
  cpUseEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 220) + 'px';
  }, [value]);

  const matches = cpUseMemo(() => {
    if (dismissed || isStreaming) return [];
    if (!PM_CMD_RE.test(value)) return [];
    const q = value.slice(1).toLowerCase();
    return PM_COMMANDS.filter((c) => c.command.toLowerCase().startsWith(q));
  }, [value, dismissed, isStreaming]);

  const menuOpen = matches.length > 0;
  const selIdx = Math.min(selected, matches.length - 1);

  function choose(cmd) {
    setValue(`/${cmd.command} `);
    setDismissed(true);
    setSelected(0);
    taRef.current?.focus();
  }

  function submit() {
    const t = value.trim();
    if (!t || isStreaming) return;
    onSend(t);
    setValue('');
    setDismissed(false);
  }

  function handleKeyDown(e) {
    if (menuOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((i) => (i + 1) % matches.length); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((i) => (i - 1 + matches.length) % matches.length); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); choose(matches[selIdx]); return; }
      if (e.key === 'Escape') { e.preventDefault(); setDismissed(true); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  }

  const isCommand = value.startsWith('/') && value.length > 1;

  return (
    <div style={{ position: 'relative' }}>
      {menuOpen && (
        <div className="pm-enter" style={{
          position: 'absolute', bottom: '100%', marginBottom: 8, left: 0, right: 0, zIndex: 20,
          maxHeight: 280, overflowY: 'auto',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 12, boxShadow: 'var(--shadow-pop)', padding: 5,
        }}>
          <div style={{ padding: '4px 10px 6px' }}>
            <PxLabel retro={retro}>Skills &amp; commands</PxLabel>
          </div>
          {matches.map((cmd, i) => (
            <button
              key={cmd.command} type="button"
              onMouseDown={(e) => { e.preventDefault(); choose(cmd); }}
              onMouseEnter={() => setSelected(i)}
              style={{
                display: 'flex', alignItems: 'baseline', gap: 10, width: '100%',
                padding: '7px 10px', borderRadius: 8, textAlign: 'left',
                background: i === selIdx ? 'var(--accent-tint)' : 'transparent',
              }}
            >
              <code style={{
                fontSize: 12.5, fontWeight: 600, flexShrink: 0,
                color: i === selIdx ? 'var(--accent-text)' : 'var(--text)',
              }}>/{cmd.command}</code>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {cmd.description}
              </span>
            </button>
          ))}
        </div>
      )}

      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid ' + (isCommand ? 'var(--accent)' : 'var(--border)'),
        borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-composer)',
        padding: big ? '14px 16px 10px' : '10px 14px 8px',
        transition: 'border-color .15s ease',
      }}>
        <textarea
          ref={taRef} value={value} rows={big ? 2 : 1} autoFocus={autoFocus}
          onChange={(e) => { setValue(e.target.value); setDismissed(false); setSelected(0); }}
          onKeyDown={handleKeyDown}
          placeholder={isStreaming ? 'Responding…' : 'Message Momentum — or type / for skills'}
          aria-label="Message Momentum"
          style={{
            width: '100%', resize: 'none', border: 'none', outline: 'none',
            background: 'transparent', fontSize: 14, lineHeight: 1.5,
            fontFamily: isCommand ? 'var(--font-mono)' : 'inherit',
            color: isCommand ? 'var(--accent-text)' : 'var(--text)',
            padding: 0, display: 'block',
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>
            {isCommand ? 'skill turn → routes to heavy model' : ''}
          </span>
          <span style={{ flex: 1 }}></span>
          <span style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>
            <Kbd>⏎</Kbd> send · <Kbd>⇧⏎</Kbd> newline
          </span>
          {isStreaming ? (
            <button
              type="button" onClick={onCancel} title="Stop responding" className="focusable"
              style={{
                width: 32, height: 32, borderRadius: retro >= 2 ? 8 : 999, flexShrink: 0,
                background: 'var(--text)', color: 'var(--bg-app)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <PixelIcon name="stop" size={12} />
            </button>
          ) : (
            <button
              type="button" onClick={submit} disabled={!value.trim()} title="Send" className="focusable"
              style={{
                width: 32, height: 32, borderRadius: retro >= 2 ? 8 : 999, flexShrink: 0,
                background: value.trim() ? 'var(--accent)' : 'var(--bg-inset)',
                color: value.trim() ? 'var(--accent-fg)' : 'var(--text-dim)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: value.trim() ? 'pointer' : 'not-allowed',
                transition: 'background .12s ease',
              }}
            >
              <PixelIcon name="arrowUp" size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Composer });
