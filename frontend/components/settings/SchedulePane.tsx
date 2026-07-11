"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Banner, Btn } from "@/components/pm";
import { api } from "@/lib/api";
import type { ScheduledTaskRecord, ScheduleSpec } from "@/lib/types";
import { useUiStore } from "@/lib/uiStore";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HOUR_CHOICES = [1, 2, 3, 4, 6, 8, 12, 24];

function describeSchedule(s: ScheduleSpec): string {
  if (s.kind === "every_n_hours") {
    const n = s.every_hours ?? 6;
    return n === 1 ? "Every hour" : `Every ${n} hours`;
  }
  const at = s.time ?? "09:00";
  if (s.kind === "weekdays") return `Weekdays at ${at}`;
  if (s.kind === "weekly") return `${WEEKDAYS[s.weekday ?? 0]}s at ${at}`;
  return `Daily at ${at}`;
}

function fmtWhen(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface FormState {
  name: string;
  prompt: string;
  kind: ScheduleSpec["kind"];
  time: string;
  weekday: number;
  everyHours: number;
  catchUp: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  prompt: "",
  kind: "daily",
  time: "09:00",
  weekday: 0,
  everyHours: 6,
  catchUp: true,
};

export function SchedulePane() {
  const router = useRouter();
  const closeSettings = useUiStore((s) => s.closeSettings);

  const [tasks, setTasks] = useState<ScheduledTaskRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  // null = list view; "new" = creating; otherwise the id being edited
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [runKicked, setRunKicked] = useState<Record<string, boolean>>({});

  const load = useCallback(() => {
    api
      .listScheduledTasks()
      .then((rows) => {
        setTasks(rows);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    load();
    // A run finishes in the background — light poll keeps "Last run" honest
    // while the pane is open (runs use the heavy model; seconds to minutes).
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  function openEdit(task: ScheduledTaskRecord) {
    setEditing(task.id);
    setForm({
      name: task.name,
      prompt: task.prompt,
      kind: task.schedule.kind,
      time: task.schedule.time ?? "09:00",
      weekday: task.schedule.weekday ?? 0,
      everyHours: task.schedule.every_hours ?? 6,
      catchUp: task.catch_up_missed,
    });
  }

  async function save() {
    setSaving(true);
    setError(null);
    const schedule: ScheduleSpec = {
      kind: form.kind,
      time: form.time,
      weekday: form.weekday,
      every_hours: form.everyHours,
    };
    try {
      if (editing && editing !== "new") {
        await api.updateScheduledTask(editing, {
          name: form.name.trim(),
          prompt: form.prompt.trim(),
          schedule,
          catch_up_missed: form.catchUp,
        });
      } else {
        await api.createScheduledTask({
          name: form.name.trim(),
          prompt: form.prompt.trim(),
          schedule,
          catch_up_missed: form.catchUp,
        });
      }
      setEditing(null);
      setForm(EMPTY_FORM);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggle(task: ScheduledTaskRecord) {
    try {
      await api.updateScheduledTask(task.id, { enabled: !task.enabled });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function runNow(task: ScheduledTaskRecord) {
    setRunKicked((s) => ({ ...s, [task.id]: true }));
    try {
      await api.runScheduledTaskNow(task.id);
      setTimeout(load, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTimeout(() => setRunKicked((s) => ({ ...s, [task.id]: false })), 4000);
    }
  }

  async function remove(task: ScheduledTaskRecord) {
    try {
      await api.deleteScheduledTask(task.id);
      setConfirmingDeleteId(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function viewResult(task: ScheduledTaskRecord) {
    if (!task.last_session_id) return;
    closeSettings();
    router.push(`/chat?s=${task.last_session_id}`);
  }

  return (
    <div>
      <h2 className="text-[16.5px] font-bold text-ink">Scheduled tasks</h2>
      <p className="mb-4 mt-1 text-[12.5px] text-ink-muted">
        Momentum runs these prompts on a schedule while the app is running (it keeps running in
        the menu bar when the window is closed). Results land in your chat list, marked ⏰.
        Anything that would send email or invites still waits for your approval, and scheduled
        runs use your API keys like any other chat.
      </p>

      {error && (
        <div className="mb-3">
          <Banner kind="danger" title="Something went wrong">
            {error}
          </Banner>
        </div>
      )}

      {editing !== null ? (
        <div className="rounded-[12px] border border-line bg-surface p-4 shadow-card">
          <div className="mb-3 text-[14px] font-semibold text-ink">
            {editing === "new" ? "New scheduled task" : "Edit scheduled task"}
          </div>
          <div className="flex flex-col gap-3">
            <Field label="Name">
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Morning briefing"
                className="h-9 w-full rounded-[8px] border border-line-strong bg-surface px-3 text-[13px] text-ink outline-none placeholder:text-ink-dim focus:border-accent"
              />
            </Field>
            <Field label="Prompt">
              <textarea
                value={form.prompt}
                onChange={(e) => setForm((f) => ({ ...f, prompt: e.target.value }))}
                placeholder="What should Momentum do each time? e.g. Review my memories of yesterday's decisions and draft a short standup update."
                rows={4}
                className="w-full resize-y rounded-[8px] border border-line-strong bg-surface px-3 py-2 text-[13px] leading-relaxed text-ink outline-none placeholder:text-ink-dim focus:border-accent"
              />
            </Field>
            <Field label="Frequency">
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={form.kind}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, kind: e.target.value as ScheduleSpec["kind"] }))
                  }
                  className="h-9 rounded-[8px] border border-line-strong bg-surface px-2 text-[13px] text-ink outline-none focus:border-accent"
                >
                  <option value="daily">Daily</option>
                  <option value="weekdays">Weekdays (Mon–Fri)</option>
                  <option value="weekly">Weekly</option>
                  <option value="every_n_hours">Every few hours</option>
                </select>
                {form.kind === "weekly" && (
                  <select
                    value={form.weekday}
                    onChange={(e) => setForm((f) => ({ ...f, weekday: Number(e.target.value) }))}
                    className="h-9 rounded-[8px] border border-line-strong bg-surface px-2 text-[13px] text-ink outline-none focus:border-accent"
                  >
                    {WEEKDAYS.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                )}
                {form.kind === "every_n_hours" ? (
                  <select
                    value={form.everyHours}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, everyHours: Number(e.target.value) }))
                    }
                    className="h-9 rounded-[8px] border border-line-strong bg-surface px-2 text-[13px] text-ink outline-none focus:border-accent"
                  >
                    {HOUR_CHOICES.map((n) => (
                      <option key={n} value={n}>
                        {n === 1 ? "every hour" : `every ${n} hours`}
                      </option>
                    ))}
                  </select>
                ) : (
                  <>
                    <span className="text-[12.5px] text-ink-muted">at</span>
                    <input
                      type="time"
                      value={form.time}
                      onChange={(e) => setForm((f) => ({ ...f, time: e.target.value }))}
                      className="h-9 rounded-[8px] border border-line-strong bg-surface px-2 text-[13px] text-ink outline-none focus:border-accent"
                    />
                  </>
                )}
              </div>
            </Field>
            <label className="flex cursor-pointer items-start gap-2.5 pl-[110px] text-[12.5px] text-ink-muted">
              <input
                type="checkbox"
                checked={form.catchUp}
                onChange={(e) => setForm((f) => ({ ...f, catchUp: e.target.checked }))}
                className="mt-0.5 accent-[var(--accent)]"
              />
              <span>
                If Momentum wasn&apos;t running at the scheduled time, run once when it next
                opens (marked as late).
              </span>
            </label>
          </div>
          <div className="mt-4 flex items-center justify-end gap-2.5">
            <Btn
              size="sm"
              onClick={() => {
                setEditing(null);
                setForm(EMPTY_FORM);
              }}
              disabled={saving}
            >
              Cancel
            </Btn>
            <Btn
              kind="primary"
              size="sm"
              onClick={save}
              disabled={saving || !form.name.trim() || !form.prompt.trim()}
            >
              {saving ? "Saving…" : "Save task"}
            </Btn>
          </div>
        </div>
      ) : (
        <>
          <div className="mb-3 flex justify-end">
            <Btn kind="primary" size="sm" onClick={() => setEditing("new")}>
              New task…
            </Btn>
          </div>

          {tasks.length === 0 ? (
            <div className="rounded-[12px] border border-dashed border-line-strong bg-raised p-5 text-center text-[12.5px] text-ink-muted">
              No scheduled tasks yet. Try a morning briefing: &quot;Summarize recent decisions
              and draft my standup notes&quot; — daily at 08:30.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {tasks.map((t) => (
                <div
                  key={t.id}
                  className="rounded-[12px] border border-line bg-surface p-4 shadow-card"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[14px] font-semibold text-ink">
                          {t.name}
                        </span>
                        {!t.enabled && (
                          <span className="rounded-full border border-line bg-raised px-2 py-0.5 text-[10.5px] font-medium text-ink-dim">
                            paused
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-[12px] text-ink-muted">
                        {describeSchedule(t.schedule)}
                        {t.enabled && t.next_run_at && <> · next {fmtWhen(t.next_run_at)}</>}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Btn size="sm" onClick={() => void runNow(t)} disabled={!!runKicked[t.id]}>
                        {runKicked[t.id] ? "Started…" : "Run now"}
                      </Btn>
                      <Btn size="sm" onClick={() => toggle(t)}>
                        {t.enabled ? "Pause" : "Resume"}
                      </Btn>
                      <Btn size="sm" onClick={() => openEdit(t)}>
                        Edit
                      </Btn>
                      {confirmingDeleteId === t.id ? (
                        <>
                          <Btn size="sm" onClick={() => setConfirmingDeleteId(null)}>
                            Cancel
                          </Btn>
                          <Btn size="sm" kind="danger" onClick={() => void remove(t)}>
                            Delete
                          </Btn>
                        </>
                      ) : (
                        <Btn size="sm" kind="danger" onClick={() => setConfirmingDeleteId(t.id)}>
                          Delete…
                        </Btn>
                      )}
                    </div>
                  </div>
                  {(t.last_run_at || t.last_status) && (
                    <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line-faint pt-2.5 text-[12px] text-ink-muted">
                      <span>
                        Last run{t.last_run_at ? ` ${fmtWhen(t.last_run_at)}` : ""}:{" "}
                        <span
                          className={
                            t.last_status?.startsWith("error")
                              ? "text-danger"
                              : t.last_status?.includes("review")
                                ? "text-accent-text"
                                : ""
                          }
                        >
                          {t.last_status ?? "—"}
                        </span>
                      </span>
                      {t.last_session_id && (
                        <button
                          type="button"
                          onClick={() => viewResult(t)}
                          className="font-medium text-accent-text underline-offset-2 hover:underline"
                        >
                          View result →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid items-start gap-3" style={{ gridTemplateColumns: "110px 1fr" }}>
      <label className="pt-2 text-[12.5px] font-medium text-ink-muted">{label}</label>
      {children}
    </div>
  );
}
