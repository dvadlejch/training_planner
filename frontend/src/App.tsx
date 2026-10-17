import { useEffect, useState, type FormEvent, type ReactElement } from "react";
import { acceptProposals, deleteSession, generateProposals, listSessions, saveSession } from "./api/client";
import { activities, statuses, type PlanningRequest, type Session, type SessionInput } from "./api/types";
import WeeklyCalendar from "./components/WeeklyCalendar";
import HeartRateCalculator from "./components/HeartRateCalculator";
import { activityLabel, runPresets } from "./running";

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

/** Render the weekly calendar list, session form, and manual proposal workflow.
 *
 * Returns
 * -------
 * ReactElement
 *     Local planner interface with loading, validation, and preview states.
 */
export default function App(): ReactElement {
  const [activity, setActivity] = useState<SessionInput["activity"]>("easy_run");
  const [duration, setDuration] = useState("30");
  const [zone, setZone] = useState("2-2");
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

  async function run(operation: () => Promise<void>): Promise<void> {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function submitSession(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const optionalNumber = (name: string): number | null => {
      const value = String(fields.get(name) ?? "").trim();
      return value === "" ? null : Number(value);
    };
    const session: SessionInput = {
      day: String(fields.get("day")),
      activity: fields.get("activity") as SessionInput["activity"],
      status: fields.get("status") as SessionInput["status"],
      duration_min: optionalNumber("duration"), effort: optionalNumber("effort"),
      notes: String(fields.get("notes") ?? ""),
      hr_zone_min: zone ? Number(zone.split("-")[0]) : null,
      hr_zone_max: zone ? Number(zone.split("-")[1]) : null,
    };
    await run(async () => {
      await saveSession(session);
      setRevision((value) => value + 1);
      setPreview(null);
      setNotice("Session saved. Generate suggestions when you are ready.");
      form.reset();
    });
  }

  async function removeSession(session: Session): Promise<void> {
    if (busy || session.id === null) return;
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
        <label>Week beginning (Monday)<input type="date" value={week} disabled={busy} required
          onChange={(event) => {
            setWeek(event.target.value); setBlocked([]); setPreview(null); setError(""); setNotice("");
          }} /></label>
        <label>Planning horizon<select value={weeks} disabled={busy} onChange={(event) => {
          const next = Number(event.target.value);
          setWeeks(next);
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
              key={index}
              weekStart={addDays(week, index * 7)}
              sessions={sessions}
              onDelete={removeSession}
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
      <section aria-labelledby="log-heading">
        <h2 id="log-heading">Log or schedule a session</h2>
        {runPresets[activity] && <p>{runPresets[activity]?.description}</p>}
        <p className="muted">Plan by total duration and main-set HR zone. Effort / RPE records perceived effort separately.</p>
        <form onSubmit={submitSession}><fieldset disabled={busy} className="form-grid">
          <label>Date<input name="day" type="date" defaultValue={localDate(new Date())} required /></label>
          <label>Activity<select name="activity" value={activity} onChange={(event) => {
            const next = event.target.value as SessionInput["activity"];
            const preset = runPresets[next];
            setActivity(next);
            setDuration(preset?.minutes == null ? "" : String(preset.minutes));
            setZone(preset?.low == null ? "" : `${preset.low}-${preset.high}`);
          }}>{activities.map((value) =>
            <option key={value} value={value}>{activityLabel(value)}</option>)}</select></label>
          <label>Target heart-rate zone (main set)<select value={zone}
            onChange={(event) => setZone(event.target.value)}>
            <option value="">Unspecified</option>
            {[1, 2, 3, 4, 5].flatMap((low) => Array.from({ length: 6 - low }, (_, i) => {
              const high = low + i;
              return <option key={`${low}-${high}`} value={`${low}-${high}`}>
                {low === high ? `Z${low}` : `Z${low}-${high}`}
              </option>;
            }))}
          </select></label>
          <label>Status<select name="status">{statuses.map((value) =>
            <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Duration in minutes (optional)<input name="duration" type="number" min="0" max="1440" step="1"
            value={duration} onChange={(event) => setDuration(event.target.value)} /></label>
          <label>Effort / RPE (optional)<input name="effort" type="number" min="1" max="10" step="1" /></label>
          <label>Notes (optional)<input name="notes" type="text" /></label>
          <button type="submit">Save session</button>
        </fieldset></form>
      </section>
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
        <button disabled={busy || !validWeek || loading} onClick={generate}>Generate suggestions</button>
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

                <button disabled={busy || selectedCount === 0} onClick={accept}>
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
