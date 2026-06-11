// pm-kit.jsx — shared primitives: pixel icons, buttons, chips, toggles.
// Everything exports to window at the bottom.

const { useState: kitUseState, useEffect: kitUseEffect, useRef: kitUseRef } = React;

// ── PixelIcon ────────────────────────────────────────────────────────────────
// Icons are 9×9 bitmaps; each string row uses '#' for a filled cell.
// Rendered as SVG rects so they stay crisp at any size — the retro splash.
const PM_BITMAPS = {
  plus: [
    '         ',
    '    #    ',
    '    #    ',
    '    #    ',
    ' ####### ',
    '    #    ',
    '    #    ',
    '    #    ',
    '         ',
  ],
  search: [
    '  ####   ',
    ' #    #  ',
    '#      # ',
    '#      # ',
    '#      # ',
    ' #    #  ',
    '  ####at ',
    '      ## ',
    '       ##',
  ],
  gear: [
    '   ###   ',
    ' # ### # ',
    '#########',
    ' ##   ## ',
    ' #     # ',
    ' ##   ## ',
    '#########',
    ' # ### # ',
    '   ###   ',
  ],
  send: [
    '         ',
    '    #    ',
    '   ###   ',
    '  # # #  ',
    ' #  #  # ',
    '    #    ',
    '    #    ',
    '    #    ',
    '         ',
  ],
  stop: [
    '         ',
    '         ',
    '  #####  ',
    '  #####  ',
    '  #####  ',
    '  #####  ',
    '  #####  ',
    '         ',
    '         ',
  ],
  check: [
    '         ',
    '         ',
    '       # ',
    '      ## ',
    ' #   ##  ',
    ' ## ##   ',
    '  ###    ',
    '   #     ',
    '         ',
  ],
  x: [
    '         ',
    ' ##   ## ',
    '  ## ##  ',
    '   ###   ',
    '    #    ',
    '   ###   ',
    '  ## ##  ',
    ' ##   ## ',
    '         ',
  ],
  chevR: [
    '         ',
    '   #     ',
    '    #    ',
    '     #   ',
    '      #  ',
    '     #   ',
    '    #    ',
    '   #     ',
    '         ',
  ],
  chevD: [
    '         ',
    '         ',
    '         ',
    ' #     # ',
    '  #   #  ',
    '   # #   ',
    '    #    ',
    '         ',
    '         ',
  ],
  doc: [
    ' #####   ',
    ' #    #  ',
    ' #     # ',
    ' ####### ',
    ' #     # ',
    ' #  ## # ',
    ' #     # ',
    ' #  ## # ',
    ' ####### ',
  ],
  mail: [
    '         ',
    ' ####### ',
    ' #     # ',
    ' ##   ## ',
    ' # # # # ',
    ' #  #  # ',
    ' #     # ',
    ' ####### ',
    '         ',
  ],
  calendar: [
    '  #   #  ',
    ' ####### ',
    ' #     # ',
    ' ####### ',
    ' # # # # ',
    ' #     # ',
    ' # # # # ',
    ' #     # ',
    ' ####### ',
  ],
  sparkle: [
    '    #    ',
    '    #    ',
    '   ###   ',
    '    #    ',
    '#### ####',
    '    #    ',
    '   ###   ',
    '    #    ',
    '    #    ',
  ],
  tag: [
    '         ',
    ' ####    ',
    ' #  ##   ',
    ' # # ##  ',
    ' #    ## ',
    ' ##    # ',
    '  ##   # ',
    '   ##### ',
    '         ',
  ],
  user: [
    '         ',
    '   ###   ',
    '  #   #  ',
    '  #   #  ',
    '   ###   ',
    '  #####  ',
    ' #     # ',
    ' #     # ',
    '         ',
  ],
  users: [
    '         ',
    '  ##  ## ',
    ' #  ##  #',
    ' #  ##  #',
    '  ##  ## ',
    ' ### ### ',
    '#   #   #',
    '#   #   #',
    '         ',
  ],
  box: [
    '         ',
    '  #####  ',
    ' ##   ## ',
    '#########',
    '#   #   #',
    '#   #   #',
    '#   #   #',
    '#########',
    '         ',
  ],
  link: [
    '         ',
    '  ###    ',
    ' #   #   ',
    ' #   #   ',
    '  ### ## ',
    '   ##  # ',
    '   #   # ',
    '    ###  ',
    '         ',
  ],
  brain: [
    '         ',
    '  ## ##  ',
    ' ####### ',
    '#########',
    '#### ####',
    '#########',
    ' ####### ',
    '   ###   ',
    '         ',
  ],
  globe: [
    '  #####  ',
    ' #  #  # ',
    '#   #   #',
    '#########',
    '#   #   #',
    '#   #   #',
    ' #  #  # ',
    '  #####  ',
    '         ',
  ],
  clock: [
    '  #####  ',
    ' #     # ',
    '#   #   #',
    '#   #   #',
    '#   ##  #',
    '#       #',
    ' #     # ',
    '  #####  ',
    '         ',
  ],
  floppy: [
    '######## ',
    '#  ##  ##',
    '#  ##   #',
    '#       #',
    '# ##### #',
    '# #   # #',
    '# #   # #',
    '# #   # #',
    '#########',
    ],
  panel: [
    '#########',
    '#     # #',
    '#     # #',
    '#     # #',
    '#     # #',
    '#     # #',
    '#     # #',
    '#     # #',
    '#########',
  ],
  sidebar: [
    '#########',
    '# #     #',
    '# #     #',
    '# #     #',
    '# #     #',
    '# #     #',
    '# #     #',
    '# #     #',
    '#########',
  ],
  pencil: [
    '         ',
    '      ## ',
    '     # # ',
    '    #  # ',
    '   #  #  ',
    '  #  #   ',
    ' ## #    ',
    ' ###     ',
    '         ',
  ],
  trash: [
    '   ###   ',
    ' ####### ',
    '  #   #  ',
    '  # # #  ',
    '  # # #  ',
    '  # # #  ',
    '  # # #  ',
    '   ###   ',
    '         ',
  ],
  arrowUp: [
    '         ',
    '    #    ',
    '   ###   ',
    '  # # #  ',
    ' #  #  # ',
    '    #    ',
    '    #    ',
    '    #    ',
    '         ',
  ],
  bolt: [
    '     ##  ',
    '    ##   ',
    '   ##    ',
    '  #####  ',
    '    ##   ',
    '   ##    ',
    '  ##     ',
    ' ##      ',
    '         ',
  ],
  plug: [
    '  #  #   ',
    '  #  #   ',
    ' ####### ',
    ' #     # ',
    '  #   #  ',
    '   ###   ',
    '    #    ',
    '    #    ',
    '         ',
  ],
  sun: [
    '    #    ',
    ' #     # ',
    '   ###   ',
    '  #####  ',
    '# ##### #',
    '  #####  ',
    '   ###   ',
    ' #     # ',
    '    #    ',
  ],
  moon: [
    '   ###   ',
    '  ##     ',
    ' ##      ',
    ' ##      ',
    ' ##      ',
    ' ##      ',
    '  ##   # ',
    '   ##### ',
    '         ',
  ],
};
// fix accidental chars in search bitmap
PM_BITMAPS.search[6] = '  ####   ';

function PixelIcon({ name, size = 14, color = 'currentColor', style }) {
  const rows = PM_BITMAPS[name] || PM_BITMAPS.box;
  const n = rows.length;
  const rects = [];
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < rows[y].length; x++) {
      if (rows[y][x] === '#') rects.push(<rect key={`${x}-${y}`} x={x} y={y} width="1" height="1"></rect>);
    }
  }
  return (
    <svg width={size} height={size} viewBox={`0 0 ${n} ${n}`} fill={color} style={{ display: 'block', flexShrink: 0, ...style }} aria-hidden="true" shapeRendering="crispEdges">
      {rects}
    </svg>
  );
}

// ── Logo mark: pixel double-chevron "momentum" ──────────────────────────────
function PmLogo({ size = 18 }) {
  const rows = [
    '#    #   ',
    '##   ##  ',
    ' ##   ## ',
    '  ##   ##',
    '   ##   #',
    '  ##   ##',
    ' ##   ## ',
    '##   ##  ',
    '#    #   ',
  ];
  const rects = [];
  for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
    if (rows[y][x] === '#') rects.push(<rect key={`${x}-${y}`} x={x} y={y} width="1" height="1"></rect>);
  }
  return (
    <svg width={size} height={size} viewBox="0 0 9 9" fill="var(--accent-bright)" style={{ display: 'block', flexShrink: 0 }} aria-hidden="true" shapeRendering="crispEdges">
      {rects}
    </svg>
  );
}

// ── Buttons ──────────────────────────────────────────────────────────────────
function Btn({ children, kind = 'default', size = 'md', disabled, onClick, title, style, autoFocus }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
    fontWeight: 500, whiteSpace: 'nowrap', userSelect: 'none',
    borderRadius: 8, transition: 'background .12s ease, border-color .12s ease, opacity .12s ease',
    border: '1px solid transparent',
    opacity: disabled ? 0.45 : 1, cursor: disabled ? 'not-allowed' : 'pointer',
  };
  const sizes = {
    sm: { height: 28, padding: '0 10px', fontSize: 12.5 },
    md: { height: 34, padding: '0 14px', fontSize: 13.5 },
    lg: { height: 42, padding: '0 20px', fontSize: 14.5, borderRadius: 10 },
  };
  const kinds = {
    default: { background: 'var(--bg-surface)', borderColor: 'var(--border-strong)', color: 'var(--text)' },
    primary: { background: 'var(--accent)', borderColor: 'var(--accent)', color: 'var(--accent-fg)', fontWeight: 600 },
    ghost: { background: 'transparent', color: 'var(--text-muted)' },
    danger: { background: 'transparent', color: 'var(--danger)' },
  };
  const [hover, setHover] = kitUseState(false);
  const hoverStyles = {
    default: { background: 'var(--bg-raised)' },
    primary: { filter: 'brightness(1.06)' },
    ghost: { background: 'var(--bg-raised)', color: 'var(--text)' },
    danger: { background: 'var(--danger-soft)' },
  };
  return (
    <button
      type="button" className="focusable" title={title} disabled={disabled} onClick={onClick} autoFocus={autoFocus}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...sizes[size], ...kinds[kind], ...(hover && !disabled ? hoverStyles[kind] : {}), ...style }}
    >
      {children}
    </button>
  );
}

// Icon-only toolbar button
function IconBtn({ icon, size = 15, onClick, title, active, style }) {
  const [hover, setHover] = kitUseState(false);
  return (
    <button
      type="button" className="focusable" title={title} onClick={onClick} aria-label={title}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        width: 30, height: 30, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 7, color: active ? 'var(--accent-text)' : (hover ? 'var(--text)' : 'var(--text-muted)'),
        background: active ? 'var(--accent-tint)' : (hover ? 'var(--bg-raised)' : 'transparent'),
        transition: 'background .12s ease, color .12s ease', flexShrink: 0, ...style,
      }}
    >
      <PixelIcon name={icon} size={size} />
    </button>
  );
}

// ── Chips & tags ─────────────────────────────────────────────────────────────
function Chip({ children, tone = 'dim', mono, title, style }) {
  const tones = {
    dim: { background: 'var(--bg-raised)', color: 'var(--text-muted)', border: '1px solid var(--border-faint)' },
    accent: { background: 'var(--accent-tint)', color: 'var(--accent-text)', border: '1px solid transparent' },
    warn: { background: 'var(--warn-soft)', color: 'var(--warn)', border: '1px solid transparent' },
    ok: { background: 'var(--ok-soft)', color: 'var(--ok)', border: '1px solid transparent' },
    danger: { background: 'var(--danger-soft)', color: 'var(--danger)', border: '1px solid transparent' },
  };
  return (
    <span title={title} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, height: 20, padding: '0 8px',
      borderRadius: 999, fontSize: 11, fontWeight: 500, letterSpacing: '0.01em',
      whiteSpace: 'nowrap', fontFamily: mono ? 'var(--font-mono)' : 'inherit',
      ...tones[tone], ...style,
    }}>
      {children}
    </span>
  );
}

// Tiny pixel-font label — the retro eyebrow. Falls back to mono when retro = 0.
function PxLabel({ children, retro, color = 'var(--text-muted)', size = 10.5, style }) {
  return (
    <span style={{
      fontFamily: retro > 0 ? 'var(--font-pixel)' : 'var(--font-mono)',
      fontSize: retro > 0 ? size : size + 1.5,
      textTransform: 'uppercase', letterSpacing: retro > 0 ? '0.005em' : '0.06em',
      color, fontWeight: retro > 0 ? 700 : 600, whiteSpace: 'nowrap', ...style,
    }}>
      {children}
    </span>
  );
}

// Status dot — square at retro 2, round below
function StatusDot({ tone = 'ok', retro = 1, size = 7, pulse }) {
  const colors = { ok: 'var(--ok)', warn: 'var(--warn)', danger: 'var(--danger)', dim: 'var(--text-dim)', accent: 'var(--accent-bright)' };
  return (
    <span className={pulse ? 'pm-pulse' : undefined} style={{
      width: size, height: size, flexShrink: 0, display: 'inline-block',
      borderRadius: retro >= 2 ? 0 : 999, background: colors[tone],
    }}></span>
  );
}

// ── Dither divider — retro horizontal rule ──────────────────────────────────
function DitherRule({ retro, style }) {
  if (retro === 0) return <div style={{ height: 1, background: 'var(--border)', ...style }}></div>;
  return <div className="dither" style={{ height: retro >= 2 ? 4 : 2, color: 'var(--border-strong)', opacity: 0.8, ...style }}></div>;
}

// ── Toggle switch ────────────────────────────────────────────────────────────
function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button" role="switch" aria-checked={checked} aria-label={label} className="focusable"
      onClick={() => onChange(!checked)}
      style={{
        width: 36, height: 21, borderRadius: 999, position: 'relative', flexShrink: 0,
        background: checked ? 'var(--accent)' : 'var(--bg-inset)',
        border: '1px solid ' + (checked ? 'var(--accent)' : 'var(--border-strong)'),
        transition: 'background .15s ease',
      }}
    >
      <span style={{
        position: 'absolute', top: 2, left: checked ? 17 : 2, width: 15, height: 15,
        borderRadius: 999, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
        transition: 'left .15s ease',
      }}></span>
    </button>
  );
}

// ── Text input ───────────────────────────────────────────────────────────────
function TextInput({ value, onChange, placeholder, mono, autoFocus, onKeyDown, type = 'text', style }) {
  return (
    <input
      type={type} value={value} placeholder={placeholder} autoFocus={autoFocus}
      onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown}
      style={{
        width: '100%', height: 36, padding: '0 12px',
        border: '1px solid var(--border-strong)', borderRadius: 8,
        background: 'var(--bg-surface)', color: 'var(--text)',
        fontSize: 13, fontFamily: mono ? 'var(--font-mono)' : 'inherit',
        outline: 'none', transition: 'border-color .12s ease, box-shadow .12s ease', ...style,
      }}
      onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px var(--accent-tint)'; }}
      onBlur={(e) => { e.target.style.borderColor = 'var(--border-strong)'; e.target.style.boxShadow = 'none'; }}
    />
  );
}

// ── Kbd hint ─────────────────────────────────────────────────────────────────
function Kbd({ children }) {
  return (
    <kbd style={{
      fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--text-dim)',
      border: '1px solid var(--border)', borderBottomWidth: 2, borderRadius: 4,
      padding: '0 4px', background: 'var(--bg-raised)',
    }}>{children}</kbd>
  );
}

// ── Mini markdown renderer (bold, lists, headers, code, strikethrough) ──────
function renderInline(text, keyBase) {
  // split on **bold**, `code`, ~~strike~~, *italic*
  const parts = [];
  let rest = text, k = 0;
  const re = /(\*\*[^*]+\*\*|`[^`]+`|~~[^~]+~~|\*[^*\n]+\*)/;
  while (rest) {
    const m = rest.match(re);
    if (!m) { parts.push(rest); break; }
    if (m.index > 0) parts.push(rest.slice(0, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) parts.push(<strong key={`${keyBase}-${k++}`}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith('`')) parts.push(<code key={`${keyBase}-${k++}`}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith('~~')) parts.push(<s key={`${keyBase}-${k++}`}>{tok.slice(2, -2)}</s>);
    else parts.push(<em key={`${keyBase}-${k++}`}>{tok.slice(1, -1)}</em>);
    rest = rest.slice(m.index + tok.length);
  }
  return parts;
}

function Markdownish({ text }) {
  const blocks = String(text || '').split(/\n\n+/);
  return (
    <div className="pm-md">
      {blocks.map((block, bi) => {
        const lines = block.split('\n');
        const isList = lines.every((l) => /^\s*[-•]|^\s*\d+\./.test(l) || l.trim() === '');
        if (isList && lines.some((l) => l.trim() !== '')) {
          const ordered = /^\s*\d+\./.test(lines[0]);
          const items = lines.filter((l) => l.trim() !== '').map((l) => l.replace(/^\s*[-•]\s?|^\s*\d+\.\s?/, ''));
          const ListTag = ordered ? 'ol' : 'ul';
          return (
            <ListTag key={bi}>
              {items.map((it, ii) => <li key={ii}>{renderInline(it, `${bi}-${ii}`)}</li>)}
            </ListTag>
          );
        }
        return <p key={bi}>{lines.map((l, li) => (
          <React.Fragment key={li}>{li > 0 && <br />}{renderInline(l, `${bi}-${li}`)}</React.Fragment>
        ))}</p>;
      })}
    </div>
  );
}

Object.assign(window, {
  PixelIcon, PmLogo, Btn, IconBtn, Chip, PxLabel, StatusDot, DitherRule,
  Toggle, TextInput, Kbd, Markdownish,
});
