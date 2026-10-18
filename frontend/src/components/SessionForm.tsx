import { useState, type FormEvent, type ReactElement } from "react";
import { activities, statuses, type Session, type SessionInput } from "../api/types";
import { activityLabel, runPresets, zoneLabel } from "../running";
import { activityStats, averagePace } from "../sessionStats";

interface SessionFormProps {
  day: string;
  session: Session | null;
  disabled: boolean;
  error: string;
  onSave: (input: SessionInput) => Promise<void>;
  onCancel: () => void;
}

/** Status-specific editor; hidden plan and result drafts survive status changes. */
export default function SessionForm({
  day, session, disabled, error, onSave, onCancel,
}: SessionFormProps): ReactElement {
  const [activity, setActivity] = useState<SessionInput["activity"]>(session?.activity ?? "easy_run");
  const [status, setStatus] = useState<SessionInput["status"]>(session?.status ?? "planned");
  const [duration, setDuration] = useState(session ? String(session.duration_min ?? "") : "30");
  const [zone, setZone] = useState(session
    ? (session.hr_zone_min === null ? "" : `${session.hr_zone_min}-${session.hr_zone_max}`)
    : "2-2");
  const [planEdited, setPlanEdited] = useState(false);
  const [notes, setNotes] = useState(session?.notes ?? "");
  const [results, setResults] = useState({
    actual_duration_min: String(session?.actual_duration_min ?? ""),
    distance_km: String(session?.distance_km ?? ""),
    average_hr_bpm: String(session?.average_hr_bpm ?? ""),
    elevation_gain_m: String(session?.elevation_gain_m ?? ""),
    active_calories_kcal: String(session?.active_calories_kcal ?? ""),
    effort: String(session?.effort ?? ""),
  });
  const planning = status === "planned" || status === "confirmed";
  const completed = status === "completed";
  const stats = activityStats(activity);
  const optionalNumber = (value: string): number | null => value.trim() === "" ? null : Number(value);
  const pace = averagePace(optionalNumber(results.distance_km), optionalNumber(results.actual_duration_min));
  // Defaults help planning but must not fabricate a plan for a directly logged result.
  const keepTargets = planning || session !== null || planEdited;
  const plannedDuration = keepTargets ? optionalNumber(duration) : null;
  const zoneMin = keepTargets && zone ? Number(zone.split("-")[0]) : null;
  const zoneMax = keepTargets && zone ? Number(zone.split("-")[1]) : null;
  const resultFields = [
    { name: "actual_duration_min", label: "Actual duration (min)", visible: stats.duration, min: 0, max: 1440 },
    { name: "distance_km", label: "Distance (km)", visible: stats.distance, min: 0 },
    { name: "average_hr_bpm", label: "Average heart rate (bpm)", visible: stats.heartRate, min: 1, max: 300, step: 1 },
    { name: "elevation_gain_m", label: "Elevation gain (m)", visible: stats.elevation, min: 0 },
    { name: "active_calories_kcal", label: "Active calories (kcal)", visible: stats.calories, min: 0 },
    { name: "effort", label: "Recorded effort / RPE (optional)", visible: true, min: 1, max: 10, step: 1 },
  ] satisfies { name: keyof typeof results; label: string; visible: boolean; min: number; max?: number; step?: number }[];

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    // Read hidden values from draft state, so changing status never clears saved data.
    await onSave({
      day: String(fields.get("day")), activity, status,
      duration_min: plannedDuration, hr_zone_min: zoneMin, hr_zone_max: zoneMax,
      actual_duration_min: optionalNumber(results.actual_duration_min),
      distance_km: optionalNumber(results.distance_km),
      average_hr_bpm: optionalNumber(results.average_hr_bpm),
      elevation_gain_m: optionalNumber(results.elevation_gain_m),
      active_calories_kcal: optionalNumber(results.active_calories_kcal),
      effort: optionalNumber(results.effort), notes,
    });
  }

  return (
    <form className="calendar-editor" aria-label={session ? "Edit training" : "Add training"}
      onSubmit={submit}>
      <h4>{session ? "Edit training" : "Add training"}</h4>
      {planning && <p>Set your training targets. All targets are optional.</p>}
      {completed && <p>Record what you did. All results are optional.</p>}
      {planning && runPresets[activity] && <p>{runPresets[activity]?.description}</p>}
      {error && <p className="message error" role="alert">{error}</p>}
      <fieldset disabled={disabled} className="calendar-editor-fields">
        <label>Date<input name="day" type="date" defaultValue={session?.day ?? day} required autoFocus /></label>
        <label>Activity<select name="activity" value={activity} onChange={(event) => {
          const next = event.target.value as SessionInput["activity"];
          setActivity(next);
          if (planning) {
            const preset = runPresets[next];
            setDuration(preset?.minutes == null ? "" : String(preset.minutes));
            setZone(preset?.low == null ? "" : `${preset.low}-${preset.high}`);
          }
        }}>{activities.map((value) => <option key={value} value={value}>{activityLabel(value)}</option>)}</select></label>
        <label>Status<select name="status" value={status}
          onChange={(event) => setStatus(event.target.value as SessionInput["status"])}>
          {statuses.map((value) => <option key={value} value={value}>{value}</option>)}
        </select></label>
        {planning && <>
          <h5 className="session-section-heading">Training targets</h5>
          <label>Planned duration (min)<input name="duration" type="number" min="0" max="1440" step="1"
            value={duration} onChange={(event) => { setDuration(event.target.value); setPlanEdited(true); }} /></label>
          <label>Target heart-rate zone (main set)<select value={zone}
            onChange={(event) => { setZone(event.target.value); setPlanEdited(true); }}>
            <option value="">Unspecified</option>
            {[1, 2, 3, 4, 5].flatMap((low) => Array.from({ length: 6 - low }, (_, offset) => {
              const high = low + offset;
              return <option key={`${low}-${high}`} value={`${low}-${high}`}>
                {low === high ? `Z${low}` : `Z${low}-${high}`}
              </option>;
            }))}
          </select></label>
        </>}
        {completed && <>
          {(plannedDuration !== null || zoneMin !== null) && <details className="session-original-plan">
            <summary>Original plan</summary>
            {plannedDuration !== null && <p>Planned duration: {plannedDuration} min</p>}
            {zoneMin !== null && <p>{zoneLabel(zoneMin, zoneMax)}</p>}
          </details>}
          <h5 className="session-section-heading">Recorded results</h5>
          {resultFields.filter((field) => field.visible).map((field) => (
            <label key={field.name}>{field.label}<input name={field.name} type="number"
              min={field.min} max={field.max} step={field.step ?? "any"} value={results[field.name]}
              onChange={(event) => setResults((current) => ({ ...current, [field.name]: event.target.value }))} /></label>
          ))}
          {stats.pace && pace && <p className="session-pace">Average pace: {pace} (from actual time)</p>}
        </>}
        {status !== "skipped" && <label className="calendar-editor-notes">
          {planning ? "Planning notes (optional)" : activity === "gym"
            ? "Workout notes: exercises, weights and repetitions" : "Notes (optional)"}
          <textarea name="notes" rows={completed && activity === "gym" ? 5 : 2}
            placeholder={completed && activity === "gym" ? "Bench press: 60 kg — 3 × 8\nPull-ups: bodyweight — 8, 7, 6" : undefined}
            value={notes} onChange={(event) => setNotes(event.target.value)} />
        </label>}
        <div className="calendar-editor-actions">
          <button type="submit">{disabled ? "Saving…" : "Save training"}</button>
          <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  );
}
