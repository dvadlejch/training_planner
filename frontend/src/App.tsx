import { useEffect, useState, type ReactElement } from "react";
import { acceptProposals, deleteSession, generateProposals, listSessions, saveSession, updateSession, updateSessionStatus } from "./api/client";
import { type PlanningRequest, type Session, type SessionInput } from "./api/types";
import WeeklyCalendar from "./components/WeeklyCalendar";
import HeartRateCalculator from "./components/HeartRateCalculator";
import SessionForm from "./components/SessionForm";

function localDate(date: Date): string {
  // Calendar dates are local dates: converting to UTC could change the day.
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(day: string, count: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + count);
  return localDate(date);
}

function initialMonday(): string {
  const today = new Date();
  today.setDate(today.getDate() - (today.getDay() + 6) % 7);
  return localDate(today);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The operation could not be completed.";
}

/** Render the editable weekly calendar and manual proposal workflow.
 *
 * Returns
 * -------
 * ReactElement
 *     Local planner interface with loading, validation, and preview states.
 */
export default function App(): ReactElement {
  const [editor, setEditor] = useState<{ day: string; session: Session | null } | null>(null);
  const [week, setWeek] = useState(initialMonday);
  const [weeks, setWeeks] = useState(1);
  const [blocked, setBlocked] = useState<string[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [preview, setPreview] = useState<{
    input: PlanningRequest;
    sessions: Session[];
    selectedDays: string[];
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const validWeek = Boolean(week) && new Date(`${week}T12:00:00`).getDay() === 1;
  const selectedCount = preview?.selectedDays.length ?? 0;

  useEffect(() => {
    if (!validWeek) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    listSessions(week, addDays(week, weeks * 7 - 1), controller.signal)
      .then(setSessions)
      .catch((cause: unknown) => { if (!controller.signal.aborted) setError(errorMessage(cause)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [week, weeks, revision, validWeek]);

  async function run(operation: () => Promise<void>): Promise<boolean> {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); return true; }
    catch (cause) { setError(errorMessage(cause)); return false; }
    finally { setBusy(false); }
  }

  async function submitSession(input: SessionInput): Promise<void> {
    if (busy || !editor) return;
    const id = editor.session?.id;
    const saved = await run(async () => {
      await (id == null ? saveSession(input) : updateSession(id, input));
      setPreview(null);
      setRevision((value) => value + 1);
      setNotice(`${id == null ? "Session added" : "Session updated"} for ${input.day}.`);
    });
    // A rejected save leaves the form and its draft intact for correction/retry.
    if (saved) setEditor(null);
  }

  async function changeStatus(session: Session, status: SessionInput["status"]): Promise<void> {
    if (busy || editor || session.id === null || session.status === status) return;
    const id = session.id;
    await run(async () => {
      const updated = await updateSessionStatus(id, status);
      setSessions((current) => current.map((item) => item.id === id ? updated : item));
      setPreview(null);
      setNotice(`Session marked ${status}.`);
    });
  }

  async function removeSession(session: Session): Promise<void> {
    if (busy || session.id === null) return;
    const id = session.id;
    await run(async () => {
      await deleteSession(id);
      setSessions((current) => current.filter((item) => item.id !== id));
      if (editor?.session?.id === id) setEditor(null);
      setPreview(null);
      setRevision((value) => value + 1);
      setNotice("Session deleted. Generate suggestions when you are ready.");
    });
  }

  async function generate(): Promise<void> {
    const input = { week_start: week, weeks, blocked: [...blocked] };
    await run(async () => {
      setPreview(null);
      const proposed = await generateProposals(input);
      // Start unchecked so acceptance reflects an explicit user selection.
      setPreview({ input, sessions: proposed, selectedDays: [] });
    });
  }

  async function accept(): Promise<void> {
    if (!preview) return;
    const selected = preview.sessions.filter((session) =>
      preview.selectedDays.includes(session.day));
    if (selected.length === 0) return;

    await run(async () => {
      await acceptProposals(preview.input, selected);
      setPreview(null);
      setRevision((value) => value + 1);
      setNotice(`${selected.length} suggestion(s) accepted.`);
    });
  }

  return (
    <main>
      <header><p className="eyebrow">Adaptive Training Planner</p><h1>Make room for training.</h1>
        <p>Record workouts and review suggestions around your availability.</p></header>
      {error && <p className="message error" role="alert">{error}</p>}
      {notice && <p className="message" role="status">{notice}</p>}
      <section aria-labelledby="week-heading">
        <h2 id="week-heading">Your week</h2>
        <p className="muted">Add training on any day, or edit a saved activity directly below. Changing the date moves it to that day.</p>
        <label>Week beginning (Monday)<input type="date" value={week} disabled={busy || editor !== null} required
          onChange={(event) => {
            setWeek(event.target.value); setEditor(null); setBlocked([]); setPreview(null); setError(""); setNotice("");
          }} /></label>
        <label>Planning horizon<select value={weeks} disabled={busy || editor !== null} onChange={(event) => {
          const next = Number(event.target.value);
          setWeeks(next);
          setEditor(null);
          setBlocked((days) => days.filter((day) => day <= addDays(week, next * 7 - 1)));
          setPreview(null);
          setError(""); setNotice("");
        }}>{[1, 2, 3, 4].map((count) => <option key={count} value={count}>
          {count} {count === 1 ? "week" : "weeks"}
        </option>)}</select></label>
        {!validWeek && <p role="alert">Select a Monday to view a week.</p>}
        {validWeek && (
          loading ? (
            <p role="status">Loading sessions…</p>
          ) : (
            Array.from({ length: weeks }, (_, index) => <WeeklyCalendar
              key={addDays(week, index * 7)}
              weekStart={addDays(week, index * 7)}
              sessions={sessions}
              onDelete={removeSession}
              onStatusChange={changeStatus}
              onAdd={(day) => { setEditor({ day, session: null }); setError(""); }}
              onEdit={(session) => { setEditor({ day: session.day, session }); setError(""); }}
              editor={editor ? {
                day: editor.day,
                content: <SessionForm
                  key={editor.session?.id ?? editor.day}
                  day={editor.day}
                  session={editor.session}
                  disabled={busy}
                  error={error}
                  onSave={submitSession}
                  onCancel={() => { setEditor(null); setError(""); }}
                />,
              } : undefined}
              disabled={busy}
              proposals={preview?.sessions ?? []}
              blocked={blocked}
              selection={preview ? {
                selectedDays: preview.selectedDays,
                disabled: busy,
                onChange: (day, selected) => {
                  setPreview((current) => current ? {
                    ...current,
                    selectedDays: selected
                      ? [...new Set([...current.selectedDays, day])]
                      : current.selectedDays.filter((value) => value !== day),
                  } : null);
                },
              } : undefined}
            />)
          )
        )}      </section>
      <section aria-labelledby="zones-heading">
        <h2 id="zones-heading">Heart-rate zone guide</h2>
        <p>Five-zone model based on maximum heart rate: Z1 50-60% (very light),
          Z2 60-70% (easy), Z3 70-80% (moderate), Z4 80-90% (hard), Z5 90-100% (very hard).</p>
        <HeartRateCalculator />
        <p>Zone systems differ. Calculated ranges use the percentage model above;
          they are estimates rather than measured thresholds. Use individually calibrated
          zones and conversational effort for easy runs. The calculator is optional.</p>
        <p>Durations are editable examples. Interval targets apply to hard repetitions,
          with easy warm-up, recoveries and cool-down included in the total time.</p>
        <p>Scheduling keeps long endurance away from known demanding days. Generic gym
          entries do not yet identify heavy leg sessions; review those conflicts yourself.</p>
        <p><a href="https://www.polar.com/us-en/guide/endurance-training">Polar: endurance zones</a>
          {" | "}<a href="https://www.polar.com/us-en/guide/anaerobic-training">Polar: higher zones</a>
          {" | "}<a href="https://www.ntnu.edu/cerg/advice">NTNU: interval guidance</a>
          {" | "}<a href="https://www.polar.com/blog/power-vs-running-is-heart-rate-training-old-news/">Heart-rate response lag</a></p>
      </section>
      <section aria-labelledby="proposal-heading">
        <h2 id="proposal-heading">Suggestions</h2>
        <p className="muted">Choose unavailable days across the entire horizon. They still count toward recovery; availability choices are temporary.</p>
        <fieldset disabled={busy || !validWeek}><legend>Unavailable days</legend>
          <div className="days">{validWeek && Array.from({ length: weeks * 7 }, (_, index) => {
            const day = addDays(week, index);
            return <label className="check" key={day}><input type="checkbox" checked={blocked.includes(day)}
              onChange={(event) => {
                setBlocked((values) => event.target.checked ? [...values, day] : values.filter((value) => value !== day));
                setPreview(null);
              }} />{day}</label>;
          })}</div>
        </fieldset>
        <button disabled={busy || !validWeek || loading || editor !== null} onClick={generate}>Generate suggestions</button>
        {preview && (
          <div className="preview">
            <h3>Review your proposal</h3>

            {preview.sessions.length === 0 ? (
              <p>No eligible dates under the current rules and availability.</p>
            ) : (
              <>
                <p>
                  Select suggestions in the calendar above, then accept them.
                  Unchecked suggestions remain unsaved.
                </p>

                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => setPreview((current) => current ? {
                    ...current,
                    selectedDays: current.sessions.map((session) => session.day),
                  } : null)}
                >
                  Select all
                </button>

                <button disabled={busy || selectedCount === 0 || editor !== null} onClick={accept}>
                  Accept selected ({selectedCount})
                </button>
              </>
            )}

            <button
              className="secondary"
              disabled={busy}
              onClick={() => {
                setPreview(null);
                setNotice("Preview dismissed. No suggestions were saved.");
              }}
            >
              Dismiss all
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
