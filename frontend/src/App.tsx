import { useEffect, useRef, useState, type ReactElement } from "react";
import { acceptProposals, deleteSession, generateProposals, listSessions, saveSession, updateSession, updateSessionStatus } from "./api/client";
import { type PlanningRequest, type Session, type SessionInput } from "./api/types";
import WeeklyCalendar from "./components/WeeklyCalendar";
import HeartRateCalculator from "./components/HeartRateCalculator";
import RescheduleDialog from "./components/RescheduleDialog";
import SessionForm from "./components/SessionForm";
import { addDays, localDate, monthRange, shiftMonth } from "./calendar";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The operation could not be completed.";
}

/** Render the editable monthly calendar and manual proposal workflow.
 *
 * Returns
 * -------
 * ReactElement
 *     Local planner interface with loading, validation, and preview states.
 */
export default function App(): ReactElement {
  const planningPanel = useRef<HTMLDetailsElement>(null);
  const [editor, setEditor] = useState<{ day: string; session: Session | null } | null>(null);
  const [proposalEditor, setProposalEditor] = useState<Session | null>(null);
  const [reschedule, setReschedule] = useState<PlanningRequest | null>(null);
  const [month, setMonth] = useState(() => localDate(new Date()).slice(0, 7));
  const range = monthRange(month);
  const monthLabel = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" })
    .format(new Date(`${month}-01T12:00:00`));
  const [weeks, setWeeks] = useState(1);
  const [blocked, setBlocked] = useState<string[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [preview, setPreview] = useState<{
    input: PlanningRequest;
    sessions: Session[];
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const editing = editor !== null || proposalEditor !== null;
  const interactionBlocked = busy || reschedule !== null;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setSessions([]);
    listSessions(range.start, range.end, controller.signal)
      .then((items) => { if (!controller.signal.aborted) setSessions(items); })
      .catch((cause: unknown) => { if (!controller.signal.aborted) setError(errorMessage(cause)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [range.start, range.end, revision]);

  async function run(operation: () => Promise<void>): Promise<boolean> {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); return true; }
    catch (cause) { setError(errorMessage(cause)); return false; }
    finally { setBusy(false); }
  }

  function confirmMove(session: Session, day: string): boolean {
    if (session.day === day || !["confirmed", "completed"].includes(session.status)) return true;
    return window.confirm(`Move ${session.status} ${session.activity} from ${session.day} to ${day}?`);
  }

  async function submitSession(input: SessionInput): Promise<void> {
    if (interactionBlocked || !editor) return;
    if (editor.session && !confirmMove(editor.session, input.day)) return;
    const moved = editor.session !== null && editor.session.day !== input.day;
    const id = editor.session?.id;
    const saved = await run(async () => {
      await (id == null ? saveSession(input) : updateSession(id, input));
      if (moved) askToReschedule();
      else setPreview(null);
      setMonth(input.day.slice(0, 7));
      setRevision((value) => value + 1);
      setNotice(`${id == null ? "Session added" : "Session updated"} for ${input.day}.`);
    });
    // A rejected save leaves the form and its draft intact for correction/retry.
    if (saved) setEditor(null);
  }

  async function changeStatus(session: Session, status: SessionInput["status"]): Promise<void> {
    if (interactionBlocked || editing || session.id === null || session.status === status) return;
    const id = session.id;
    await run(async () => {
      const updated = await updateSessionStatus(id, status);
      setSessions((current) => current.map((item) => item.id === id ? updated : item));
      setPreview(null);
      setNotice(`Session marked ${status}.`);
    });
  }

  async function moveSession(session: Session, day: string): Promise<void> {
    if (interactionBlocked || loading || editing || session.id === null || session.day === day) return;
    if (day < range.start || day > range.end) return;
    if (!confirmMove(session, day)) return;
    const { id, ...input } = session;
    await run(async () => {
      const updated = await updateSession(id, { ...input, day });
      setSessions((current) => current.map((item) => item.id === id ? updated : item));
      askToReschedule();
      setNotice(`Session moved to ${day}.`);
    });
  }

  function askToReschedule(input = preview?.input ?? {
    week_start: localDate(new Date()), weeks, blocked: [...blocked],
  }): void {
    setReschedule(input);
  }

  function moveProposal(session: Session, day: string): void {
    if (interactionBlocked || loading || editor || !preview || session.day === day) return;
    if (!preview.sessions.includes(session)) return;
    const input = preview.input;
    const end = addDays(input.week_start, input.weeks * 7 - 1);
    if (day < input.week_start || day > end || day < localDate(new Date()) ||
        input.blocked.includes(day) || sessions.some((item) => item.day === day) ||
        preview.sessions.some((item) => item !== session && item.day === day)) {
      setError("Choose a free, available date within the suggestion horizon, today or later.");
      return;
    }
    const { id: _id, ...moved } = { ...session, day };
    const previousMove = input.moves?.find((move) => move.session.day === session.day);
    const originalDay = previousMove?.original_day ?? session.day;
    const moves = (input.moves ?? []).filter((move) => move !== previousMove);
    moves.push({ original_day: originalDay, session: moved });
    const nextInput = { ...input, moves };
    setPreview({
      input: nextInput,
      sessions: preview.sessions.map((item) => item === session ? { ...item, day } : item),
    });
    setProposalEditor(null);
    setError("");
    setNotice(`Suggestion moved to ${day}. It remains unsaved until accepted.`);
    askToReschedule(nextInput);
  }

  function removeProposal(session: Session): void {
    if (interactionBlocked || loading || editing || !preview) return;
    if (!preview.sessions.includes(session)) return;
    const move = preview.input.moves?.find((item) => item.session.day === session.day);
    const dismissed = [...new Set([
      ...(preview.input.dismissed ?? []), session.day, ...(move ? [move.original_day] : []),
    ])];
    const nextInput = {
      ...preview.input, dismissed,
      moves: (preview.input.moves ?? []).filter((item) => item !== move),
    };
    setPreview({
      input: nextInput,
      sessions: preview.sessions.filter((item) => item !== session),
    });
    setError("");
    setNotice("Suggestion removed. Recalculation will keep its date free; generating a new plan resets removals.");
    askToReschedule(nextInput);
  }

  async function recalculate(): Promise<void> {
    if (busy || !reschedule) return;
    const input = reschedule;
    const success = await run(async () => {
      const proposed = await generateProposals(input);
      setPreview({ input, sessions: proposed });
      setNotice("Suggestions recalculated around your changes. Review before accepting.");
    });
    if (success) setReschedule(null);
  }

  async function removeSession(session: Session): Promise<void> {
    if (interactionBlocked || editing || session.id === null) return;
    const id = session.id;
    await run(async () => {
      await deleteSession(id);
      setSessions((current) => current.filter((item) => item.id !== id));
      setPreview(null);
      setRevision((value) => value + 1);
      setNotice("Session deleted. Generate suggestions when you are ready.");
    });
  }

  async function generate(): Promise<void> {
    if (interactionBlocked || editing || loading) return;
    const input = { week_start: localDate(new Date()), weeks, blocked: [...blocked] };
    await run(async () => {
      setPreview(null);
      const proposed = await generateProposals(input);
      setPreview({ input, sessions: proposed });
      setMonth(input.week_start.slice(0, 7));
    });
  }

  async function confirmProposal(session: Session): Promise<void> {
    if (interactionBlocked || loading || editing || !preview) return;
    if (!preview.sessions.includes(session)) return;
    await run(async () => {
      await acceptProposals(preview.input, [session], true);
      // A persisted move is now a booking, so stop sending it as an unsaved move.
      const move = preview.input.moves?.find((item) => item.session.day === session.day);
      const remaining = preview.sessions.filter((item) => item !== session);
      setPreview(remaining.length ? {
        input: {
          ...preview.input,
          moves: (preview.input.moves ?? []).filter((item) => item !== move),
          dismissed: [...new Set([
            ...(preview.input.dismissed ?? []), ...(move ? [move.original_day] : []),
          ])],
        },
        sessions: remaining,
      } : null);
      setRevision((value) => value + 1);
      setNotice(`Suggestion confirmed for ${session.day}.`);
    });
  }

  return (
    <main>
      <header className="app-header">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <path d="M6 29 17 10l7 12 4-6 7 13H6Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="m13 17 4 3 4-3M24 29l-4-7" stroke="currentColor" strokeWidth="1.8" />
          </svg>
          <div><p className="eyebrow">Adaptive Training Planner</p><h1>Your training calendar</h1></div>
        </div>
        <button className="plan-button" onClick={() => {
          if (planningPanel.current) {
            planningPanel.current.open = true;
            planningPanel.current.querySelector("summary")?.focus();
          }
        }}>Plan training <span aria-hidden="true">&#8599;</span></button>
      </header>
      <p className="app-intro">Make space for movement. Leave room for life.</p>
      {error && <p className="message error" role="alert">{error}</p>}
      {notice && <p className="message" role="status">{notice}</p>}
      <div className="planner-layout">
        <section className="calendar-section" aria-labelledby="month-heading">
          <div className="calendar-toolbar">
            <div><p className="eyebrow">Your month</p><h2 id="month-heading">{monthLabel}</h2></div>
            <nav aria-label="Calendar navigation">
              <button className="secondary" aria-label="Previous month" disabled={interactionBlocked || editing}
                onClick={() => { setMonth(shiftMonth(month, -1)); setError(""); }}>&larr;</button>
              <button className="secondary" disabled={interactionBlocked || editing}
                onClick={() => { setMonth(localDate(new Date()).slice(0, 7)); setError(""); }}>Today</button>
              <button className="secondary" aria-label="Next month" disabled={interactionBlocked || editing}
                onClick={() => { setMonth(shiftMonth(month, 1)); setError(""); }}>&rarr;</button>
            </nav>
          </div>
          <div className="calendar-subtoolbar">
            <div className="activity-legend" aria-label="Activity colours">
              <span><i className="legend-run" />Running</span><span><i className="legend-gym" />Strength</span>
              <span><i className="legend-outdoor" />Outdoors</span><span><i className="legend-rest" />Rest</span>
            </div>
            <details className="calendar-help"><summary>Using your calendar</summary>
              <p>Open a workout for details and actions. Use Confirm on a suggestion to save it as confirmed upcoming training. Other suggestions remain unsaved. Drag a move handle to another day, or click it to change the date. Confirmed and completed moves require approval.</p>
            </details>
          </div>
          {preview && (
            <div className="calendar-suggestion-toolbar" role="group" aria-label="Suggestion actions">
              {preview.sessions.length === 0 ? (
                <p role="status">{preview.input.dismissed?.length ? "No suggestions remain. Generate a new plan to start again." : "No eligible dates under the current rules and availability."}</p>
              ) : null}
              <button className="secondary" disabled={interactionBlocked || editing}
                onClick={() => {
                  setPreview(null);
                  setNotice("Remaining suggestions dismissed. No additional sessions were saved.");
                }}>Dismiss all</button>
            </div>
          )}
          {loading && <p className="calendar-loading" role="status">Loading sessions...</p>}
          <div className="month-scroll" tabIndex={0} role="region" aria-label="Full month calendar" aria-busy={loading}>
            <div className="month-weekdays" aria-hidden="true">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <span key={day}>{day}</span>)}
            </div>
            <WeeklyCalendar
                month={month}
                dayCount={range.days}
                weekStart={range.start}
                sessions={sessions}
                onDelete={removeSession}
                onStatusChange={changeStatus}
                onMove={moveSession}
                onMoveProposal={moveProposal}
                onRemoveProposal={removeProposal}
                onConfirmProposal={confirmProposal}
                onEditProposal={(session) => { setProposalEditor(session); setError(""); }}
                onAdd={(day) => { setEditor({ day, session: null }); setError(""); }}
                onEdit={(session) => { setEditor({ day: session.day, session }); setError(""); }}
                editor={editor ? {
                  day: editor.day,
                } : proposalEditor ? { day: proposalEditor.day } : undefined}
                disabled={interactionBlocked || loading}
                proposals={preview?.sessions ?? []}
                blocked={blocked}
                onAvailabilityChange={(day, unavailable) => {
                  if (interactionBlocked || loading || editing) return;
                  setBlocked((values) => unavailable
                    ? [...new Set([...values, day])]
                    : values.filter((value) => value !== day));
                  setPreview(null); setError(""); setNotice("");
                }}
              />
          </div>
        </section>
        <aside className="planner-sidebar" aria-label="Training tools">
          {editor && <div className="month-editor"><SessionForm
            key={editor.session?.id ?? editor.day}
            day={editor.day} session={editor.session} disabled={interactionBlocked} error={error}
            onSave={submitSession} onCancel={() => { setEditor(null); setError(""); }}
          /></div>}
        {proposalEditor && preview && <form className="calendar-editor month-editor"
          aria-label="Move suggestion" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            moveProposal(proposalEditor, String(data.get("day")));
          }}>
          <h2>Move suggestion</h2>
          <label>Date<input name="day" type="date" required autoFocus
            defaultValue={proposalEditor.day}
            min={[preview.input.week_start, localDate(new Date())].sort().at(-1)}
            max={addDays(preview.input.week_start, preview.input.weeks * 7 - 1)} /></label>
          <button type="submit">Move suggestion</button>
          <button type="button" className="secondary" onClick={() => setProposalEditor(null)}>Cancel</button>
        </form>}
        {reschedule && <RescheduleDialog busy={busy} error={error}
          onRecalculate={() => { void recalculate(); }} onKeep={() => setReschedule(null)} />}
        <details className="planning-panel" ref={planningPanel} open>
          <summary><span className="eyebrow">Your next chapter</span><h2 id="proposal-heading">Suggestions</h2></summary>
          <p className="muted">A little structure, on your terms. Choose your dates and make a plan that fits.</p>
          <div className="planning-controls">
            <label>Planning horizon<select value={weeks} disabled={interactionBlocked || editing} onChange={(event) => {
              const next = Number(event.target.value);
              setWeeks(next);
              setPreview(null); setError(""); setNotice("");
            }}>{[1, 2, 3, 4].map((count) => <option key={count} value={count}>
              {count} {count === 1 ? "week" : "weeks"}
            </option>)}</select></label>
          </div>
          <p className="muted">Suggestions start today and cover the next {weeks * 7} days, including today.</p>
          <p className="muted">Mark unavailable days directly in the calendar to exclude them from suggestions. Saved workouts still count toward recovery. Availability choices are temporary and last until you reload the page.</p>
          <button disabled={interactionBlocked || loading || editing} onClick={generate}>Generate suggestions</button>

        </details>
        <details className="reference-panel">
          <summary><span className="eyebrow">Training reference</span><h2 id="zones-heading">Heart-rate zone guide</h2></summary>
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
        </details>
        <p className="sidebar-note">Every plan can change.<br />Rest days belong here, too.</p>
        </aside>
      </div>
      <footer className="app-footer">Built around your life, one day at a time.</footer>
    </main>
  );
}
