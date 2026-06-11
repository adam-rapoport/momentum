// pm-chat.jsx — conversation view: messages, tool calls, approval bar,
// streaming simulation, and the empty home state.

const { useState: chUseState, useEffect: chUseEffect, useRef: chUseRef, useMemo: chUseMemo } = React;

// ── Tool call block ──────────────────────────────────────────────────────────
const PM_TOOL_ICONS = {
  WebSearch: 'globe', WebFetch: 'globe', SaveMemory: 'floppy', RecallMemory: 'brain',
  SearchMemories: 'brain', DraftMessage: 'mail', QueryTickets: 'tag', TimeCheck: 'clock',
  Calendar: 'calendar', CreateDocument: 'doc',
};

function compactInput(input) {
  const entries = Object.entries(input || {}).filter(([, v]) => v != null && v !== '');
  return entries.map(([k, v]) => {
    const s = typeof v === 'string' ? v : JSON.stringify(v);
    return `${k}: ${s.length > 48 ? s.slice(0, 48) + '…' : s}`;
  }).join('  ·  ');
}

function ToolBlock({ name, input, output, status = 'done', isError, retro }) {
  const [expanded, setExpanded] = chUseState(!!isError);
  const running = status === 'running';
  const tone = isError || status === 'error' ? 'danger' : running ? 'warn' : 'ok';
  const label = isError || status === 'error' ? 'error' : running ? 'running' : 'done';

  return (
    <div className="pm-enter" style={{
      border: '1px solid var(--border-faint)', borderRadius: 9,
      background: 'var(--bg-raised)', overflow: 'hidden', margin: '2px 0',
    }}>
      <button
        type="button" className="focusable" onClick={() => setExpanded((x) => !x)}
        aria-expanded={expanded}
        style={{
          display: 'flex', alignItems: 'center', gap: 9, width: '100%',
          padding: '6px 10px', textAlign: 'left', fontFamily: 'var(--font-mono)', fontSize: 11.5,
        }}
      >
        <span style={{ color: running ? 'var(--warn)' : isError ? 'var(--danger)' : 'var(--text-muted)' }}>
          <PixelIcon name={PM_TOOL_ICONS[name] || 'gear'} size={12} />
        </span>
        <span style={{ fontWeight: 600, color: 'var(--text)' }}>{name}</span>
        <span style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0 }}>
          {compactInput(input)}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          <StatusDot tone={tone} retro={retro} size={6} pulse={running} />
          <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-dim)' }}>{label}</span>
          <span style={{ color: 'var(--text-dim)', transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform .12s ease', display: 'inline-flex' }}>
            <PixelIcon name="chevD" size={10} />
          </span>
        </span>
      </button>
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border-faint)', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <PxLabel retro={retro}>input</PxLabel>
            <pre style={{
              margin: '4px 0 0', fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.55,
              whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-muted)',
              background: 'var(--bg-inset)', borderRadius: 6, padding: '6px 9px',
            }}>{JSON.stringify(input, null, 2)}</pre>
          </div>
          {output && (
            <div>
              <PxLabel retro={retro}>output</PxLabel>
              <pre style={{
                margin: '4px 0 0', fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.55,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-muted)',
                background: 'var(--bg-inset)', borderRadius: 6, padding: '6px 9px', maxHeight: 180, overflowY: 'auto',
              }}>{output}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Message rows ─────────────────────────────────────────────────────────────
function UserMessage({ text }) {
  return (
    <div className="pm-enter" style={{ display: 'flex', justifyContent: 'flex-end', margin: '14px 0' }}>
      <div style={{
        maxWidth: '78%', background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: '14px 14px 4px 14px', padding: '9px 14px',
        fontSize: 14, boxShadow: 'var(--shadow-card)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {text}
      </div>
    </div>
  );
}

function AssistantMessage({ text, streaming, retro }) {
  return (
    <div className="pm-enter" style={{ display: 'flex', gap: 12, margin: '16px 0', alignItems: 'flex-start' }}>
      <span style={{
        width: 26, height: 26, flexShrink: 0, marginTop: 1,
        borderRadius: retro >= 2 ? 6 : 8, background: 'var(--bg-surface)',
        border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <PmLogo size={13} />
      </span>
      <div style={{ flex: 1, minWidth: 0, fontSize: 14.5, lineHeight: 1.62, paddingTop: 2 }}>
        <Markdownish text={text} />
        {streaming && <span className="pm-cursor" aria-hidden="true"></span>}
      </div>
    </div>
  );
}

function ThinkingRow({ retro }) {
  return (
    <div className="pm-enter" style={{ display: 'flex', gap: 12, margin: '16px 0', alignItems: 'center' }}>
      <span style={{
        width: 26, height: 26, flexShrink: 0,
        borderRadius: retro >= 2 ? 6 : 8, background: 'var(--bg-surface)',
        border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span className="pm-pulse"><PmLogo size={13} /></span>
      </span>
      <span className="mono" style={{ fontSize: 12, color: 'var(--text-dim)' }}>thinking…</span>
    </div>
  );
}

// ── Approval bar ─────────────────────────────────────────────────────────────
function ApprovalCard({ review, onApprove, onRevise, onRestart, retro }) {
  const [mode, setMode] = chUseState('idle');
  const [revision, setRevision] = chUseState('');
  const kind = review.kind || 'deliverable';

  const headline = kind === 'send_email' ? 'Approve to send this email'
    : kind === 'create_event' ? 'Approve to send these invites'
    : 'Ready for your review';
  const approveLabel = kind === 'send_email' ? 'Send email'
    : kind === 'create_event' ? 'Send invites'
    : 'Looks good';

  function submitRevise() {
    const t = revision.trim();
    if (!t) return;
    onRevise(t);
    setRevision(''); setMode('idle');
  }

  return (
    <div className="pm-enter" style={{
      border: '1px solid var(--accent)', borderRadius: 'var(--radius-lg)',
      background: 'var(--bg-surface)', boxShadow: 'var(--shadow-composer)', overflow: 'hidden',
    }}>
      <div className={retro > 0 ? 'dither' : undefined} style={{
        height: retro > 0 ? 5 : 3, color: 'var(--accent)',
        background: retro > 0 ? undefined : 'var(--accent)',
      }}></div>
      <div style={{ padding: '12px 16px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap', minWidth: 0 }}>
          <StatusDot tone="accent" retro={retro} size={7} pulse />
          <span style={{ fontSize: 13.5, fontWeight: 700 }}>{headline}</span>
          {kind === 'deliverable' && review.deliverable_kind && (
            <Chip tone="accent" mono>{review.deliverable_kind.replace(/_/g, ' ')}</Chip>
          )}
        </div>

        {kind === 'deliverable' && (
          <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            {review.summary}
            {review.docTitle && (
              <div style={{
                marginTop: 8, display: 'flex', alignItems: 'center', gap: 9,
                border: '1px solid var(--border)', borderRadius: 8, padding: '7px 10px',
                background: 'var(--bg-raised)',
              }}>
                <PixelIcon name="doc" size={13} style={{ color: 'var(--text-muted)' }} />
                <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {review.docTitle}
                </span>
                <a href={review.url || '#'} onClick={(e) => e.preventDefault()} style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--accent-text)', textDecoration: 'none', flexShrink: 0 }}>
                  Open in Google Docs ↗
                </a>
              </div>
            )}
          </div>
        )}

        {kind === 'send_email' && review.preview && (
          <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '9px 12px', background: 'var(--bg-raised)', fontSize: 12.5 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '56px 1fr', rowGap: 3 }}>
              <span style={{ color: 'var(--text-dim)' }}>To</span><span className="mono" style={{ fontSize: 12 }}>{review.preview.to.join(', ')}</span>
              {review.preview.cc?.length > 0 && (<React.Fragment><span style={{ color: 'var(--text-dim)' }}>Cc</span><span className="mono" style={{ fontSize: 12 }}>{review.preview.cc.join(', ')}</span></React.Fragment>)}
              <span style={{ color: 'var(--text-dim)' }}>Subject</span><span style={{ fontWeight: 600 }}>{review.preview.subject}</span>
            </div>
            <div style={{ marginTop: 7, paddingTop: 7, borderTop: '1px solid var(--border-faint)', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {review.preview.body}
            </div>
          </div>
        )}

        {mode === 'idle' ? (
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <Btn kind="primary" onClick={onApprove}>
              <PixelIcon name="check" size={11} />
              {approveLabel}
            </Btn>
            <Btn onClick={() => setMode('revise')}>Make changes</Btn>
            <Btn kind="ghost" onClick={onRestart}>{kind === 'deliverable' ? 'Start over' : 'Cancel'}</Btn>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'flex-end' }}>
            <textarea
              value={revision} autoFocus rows={2}
              onChange={(e) => setRevision(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitRevise(); }
                if (e.key === 'Escape') { setMode('idle'); setRevision(''); }
              }}
              placeholder={kind === 'send_email' ? "e.g. 'make the tone friendlier' or 'add Carol to cc'" : "e.g. 'add a non-goals section' or 'tighten the metrics'"}
              style={{
                flex: 1, resize: 'none', borderRadius: 8, border: '1px solid var(--accent)',
                boxShadow: '0 0 0 3px var(--accent-tint)', outline: 'none',
                background: 'var(--bg-surface)', padding: '8px 11px', fontSize: 13, lineHeight: 1.5,
              }}
            />
            <Btn kind="primary" disabled={!revision.trim()} onClick={submitRevise}>Send revision</Btn>
            <Btn kind="ghost" onClick={() => { setMode('idle'); setRevision(''); }}>Back</Btn>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Streaming simulation hook ────────────────────────────────────────────────
// Drives: thinking → tool running → tool done → text streaming → commit.
function useStreamSim({ onCommit }) {
  const [phase, setPhase] = chUseState('idle'); // idle|thinking|tool|streaming
  const [tool, setTool] = chUseState(null);
  const [streamText, setStreamText] = chUseState('');
  const timersRef = chUseRef([]);
  const stateRef = chUseRef({ full: '', i: 0, tool: null });
  // Keep the latest onCommit — timer callbacks capture `finish` from the render
  // where start() was called, whose closure would otherwise hold a stale
  // session.messages snapshot (dropping the just-sent user message on commit).
  const onCommitRef = chUseRef(onCommit);
  onCommitRef.current = onCommit;

  function clearTimers() {
    timersRef.current.forEach((t) => { clearTimeout(t); clearInterval(t); });
    timersRef.current = [];
  }
  chUseEffect(() => clearTimers, []);

  function start(response) {
    clearTimers();
    stateRef.current = { full: response.text, i: 0, tool: response.tool || null };
    setStreamText('');
    setTool(null);
    setPhase('thinking');

    let delay = 700;
    if (response.tool) {
      timersRef.current.push(setTimeout(() => {
        setPhase('tool');
        setTool({ ...response.tool, status: 'running', output: undefined });
      }, delay));
      delay += 1100;
      timersRef.current.push(setTimeout(() => {
        setTool({ ...response.tool, status: 'done' });
      }, delay));
      delay += 350;
    }
    timersRef.current.push(setTimeout(() => {
      setPhase('streaming');
      const interval = setInterval(() => {
        const st = stateRef.current;
        st.i = Math.min(st.full.length, st.i + 3 + Math.floor(Math.random() * 4));
        setStreamText(st.full.slice(0, st.i));
        if (st.i >= st.full.length) {
          clearInterval(interval);
          finish(false);
        }
      }, 24);
      timersRef.current.push(interval);
    }, delay));
  }

  function finish(stopped) {
    clearTimers();
    const st = stateRef.current;
    const text = stopped ? st.full.slice(0, st.i) : st.full;
    const toolMsg = st.tool && !stopped ? { role: 'tool', ...st.tool } : (st.tool && st.i > 0 ? { role: 'tool', ...st.tool } : st.tool ? { role: 'tool', ...st.tool } : null);
    setPhase('idle'); setTool(null); setStreamText('');
    onCommitRef.current({ toolMsg, text, stopped });
  }

  function cancel() {
    if (phase === 'idle') return;
    finish(true);
  }

  return { phase, tool, streamText, start, cancel, isActive: phase !== 'idle' };
}

// ── Chat view ────────────────────────────────────────────────────────────────
function ChatView({ session, onUpdateSession, retro, onModelTurn, autoStart, onAutoStarted }) {
  const [stopped, setStopped] = chUseState(false);
  const scrollRef = chUseRef(null);
  const pinnedRef = chUseRef(true);
  const [unpinned, setUnpinned] = chUseState(false);

  const sim = useStreamSim({
    onCommit: ({ toolMsg, text, stopped: wasStopped }) => {
      const additions = [];
      if (toolMsg) additions.push(toolMsg);
      if (text) additions.push({ role: 'assistant', text });
      onUpdateSession({ messages: [...session.messages, ...additions] });
      setStopped(wasStopped);
    },
  });

  // auto-start the simulated reply for sessions created from the home screen
  const autoRef = chUseRef(false);
  chUseEffect(() => {
    if (autoStart && !autoRef.current) {
      autoRef.current = true;
      sim.start(PM_SIM_RESPONSE);
      if (onAutoStarted) onAutoStarted();
    }
  }, [autoStart]);

  // autoscroll while pinned
  chUseEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [session.messages.length, sim.streamText, sim.phase]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    pinnedRef.current = nearBottom;
    setUnpinned(!nearBottom);
  }

  function jumpToLatest() {
    const el = scrollRef.current;
    if (!el) return;
    pinnedRef.current = true; setUnpinned(false);
    el.scrollTop = el.scrollHeight;
  }

  function send(text) {
    setStopped(false);
    onUpdateSession({ messages: [...session.messages, { role: 'user', text }] });
    if (onModelTurn) onModelTurn();
    sim.start(PM_SIM_RESPONSE);
  }

  function approvalSend(text, responseText) {
    setStopped(false);
    onUpdateSession({
      messages: [...session.messages, { role: 'user', text }],
      awaitingReview: null,
    });
    sim.start({ text: responseText });
  }

  const review = session.awaitingReview;

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
      <div ref={scrollRef} onScroll={handleScroll} style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '18px 28px 24px' }}>
          {session.messages.map((m, i) => {
            if (m.role === 'user') return <UserMessage key={i} text={m.text} />;
            if (m.role === 'assistant') return <AssistantMessage key={i} text={m.text} retro={retro} />;
            return <ToolBlock key={i} name={m.name} input={m.input} output={m.output} isError={m.isError} status="done" retro={retro} />;
          })}

          {sim.phase === 'thinking' && <ThinkingRow retro={retro} />}
          {sim.tool && <ToolBlock name={sim.tool.name} input={sim.tool.input} output={sim.tool.status === 'done' ? sim.tool.output : undefined} status={sim.tool.status} retro={retro} />}
          {sim.phase === 'streaming' && sim.streamText && <AssistantMessage text={sim.streamText} streaming retro={retro} />}

          {stopped && !sim.isActive && (
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-dim)', margin: '8px 0 0 38px' }}>
              ■ Stopped by you
            </div>
          )}
        </div>
      </div>

      {unpinned && (
        <button
          type="button" onClick={jumpToLatest} className="focusable"
          style={{
            position: 'absolute', bottom: review ? 220 : 130, left: '50%', transform: 'translateX(-50%)',
            borderRadius: 999, background: 'var(--text)', color: 'var(--bg-app)',
            fontSize: 11.5, fontWeight: 600, padding: '5px 13px', boxShadow: 'var(--shadow-pop)', zIndex: 5,
          }}
        >
          ↓ Jump to latest
        </button>
      )}

      <div style={{ flexShrink: 0, padding: '0 28px 18px' }}>
        <div style={{ maxWidth: 760, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {review && !sim.isActive ? (
            <ApprovalCard
              review={review} retro={retro}
              onApprove={() => approvalSend('/approve',
                review.kind === 'send_email'
                  ? 'Sent. Sarah and you are on the thread — I\u2019ll flag her reply when it lands.\n\nI also noted in memory that this update format (impact first, under 200 words) is the one she gets.'
                  : 'Approved and filed. The PRD is final in Google Drive and I\u2019ve added it to your Documents.\n\nNext step when you\u2019re ready: `/user-story` to break the checklist into stories for Marcus\u2019s team.')}
              onRevise={(t) => approvalSend(`/revise ${t}`,
                'On it — revising the draft with that change. I\u2019ll stage the updated version for your review in a moment.')}
              onRestart={() => approvalSend(review.kind === 'deliverable' ? '/restart' : '/cancel',
                review.kind === 'deliverable'
                  ? 'Starting fresh. Same skill, blank slate — tell me the angle you want this time.'
                  : 'Cancelled — nothing was sent.')}
            />
          ) : (
            <Composer
              onSend={send}
              onCancel={() => sim.cancel()}
              isStreaming={sim.isActive}
              retro={retro}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Home (no session) ────────────────────────────────────────────────────────
function HomeView({ onSendNew, retro, profileName }) {
  const [seed, setSeed] = chUseState(null);
  const hour = new Date().getHours();
  const greeting = hour < 5 ? 'Working late' : hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ width: '100%', maxWidth: 640, margin: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 22 }}>
          <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <PmLogo size={retro >= 2 ? 36 : 28} />
            <h1 style={{ margin: 0, fontSize: 27, fontWeight: 700, letterSpacing: '-0.02em' }}>
              {greeting}, {profileName.split(' ')[0]}
            </h1>
            <div style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>
              What are we moving forward today?
            </div>
          </div>

          <Composer onSend={onSendNew} isStreaming={false} retro={retro} big autoFocus seed={seed} />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
            {PM_SKILL_SHORTCUTS.map((s) => (
              <button
                key={s.command} type="button" className="focusable"
                onClick={() => setSeed({ text: `/${s.command} `, t: Date.now() })}
                style={{
                  display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', minWidth: 0,
                  border: '1px solid var(--border)', borderRadius: 10,
                  background: 'var(--bg-surface)', textAlign: 'left',
                  fontSize: 12.5, fontWeight: 550, color: 'var(--text)',
                  boxShadow: 'var(--shadow-card)', transition: 'border-color .12s ease, transform .08s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
              >
                <span style={{ color: 'var(--accent-text)' }}><PixelIcon name={s.icon} size={13} /></span>
                {s.label}
              </button>
            ))}
          </div>

          <div style={{ textAlign: 'center', fontSize: 11.5, color: 'var(--text-dim)' }}>
            Type <Kbd>/</Kbd> in the composer to see all 10 skills
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ChatView, HomeView, ToolBlock, ApprovalCard });
