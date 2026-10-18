import { useState, type FormEvent, type ReactElement } from "react";
import { activities, statuses, type Session, type SessionInput } from "../api/types";
import { activityLabel, runPresets } from "../running";

interface SessionFormProps {
  day: string;
  session: Session | null;
  disabled: boolean;
  error: string;
  onSave: (input: SessionInput) => Promise<void>;
  onCancel: () => void;
}

/** Calendar tools-panel editor; persisted values are preserved until explicitly changed. */
export default function SessionForm({
  day, session, disabled, error, onSave, onCancel,
}: SessionFormProps): ReactElement {
  const [activity, setActivity] = useState<SessionInput["activity"]>(session?.activity ?? "easy_run");
  const [duration, setDuration] = useState(session ? String(session.duration_min ?? "") : "30");
  const [zone, setZone] = useState(session
    ? (session.hr_zone_min === null ? "" : `${session.hr_zone_min}-${session.hr_zone_max}`)
    : "2-2");

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const optionalNumber = (name: string): number | null => {
      const value = String(fields.get(name) ?? "").trim();
      return value === "" ? null : Number(value);
    };
    await onSave({
      day: String(fields.get("day")), activity,
      status: fields.get("status") as SessionInput["status"],
      duration_min: optionalNumber("duration"), effort: optionalNumber("effort"),
      notes: String(fields.get("notes") ?? ""),
      hr_zone_min: zone ? Number(zone.split("-")[0]) : null,
      hr_zone_max: zone ? Number(zone.split("-")[1]) : null,
    });
  }

  return (
    <form className="calendar-editor" aria-label={session ? "Edit training" : "Add training"}
      onSubmit={submit}>
      <h4>{session ? "Edit training" : "Add training"}</h4>
      <p>Plan by total duration and main-set HR zone. Effort / RPE is recorded separately.</p>
      {runPresets[activity] && <p>{runPresets[activity]?.description}</p>}
      {error && <p className="message error" role="alert">{error}</p>}
      <fieldset disabled={disabled} className="calendar-editor-fields">
        <label>Date<input name="day" type="date" defaultValue={session?.day ?? day} required autoFocus /></label>
        <label>Activity<select name="activity" value={activity} onChange={(event) => {
          const next = event.target.value as SessionInput["activity"];
          const preset = runPresets[next];
          setActivity(next);
          setDuration(preset?.minutes == null ? "" : String(preset.minutes));
          setZone(preset?.low == null ? "" : `${preset.low}-${preset.high}`);
        }}>{activities.map((value) => <option key={value} value={value}>{activityLabel(value)}</option>)}</select></label>
        <label>Status<select name="status" defaultValue={session?.status ?? "planned"}>
          {statuses.map((value) => <option key={value} value={value}>{value}</option>)}
        </select></label>
        <label>Duration in minutes (optional)<input name="duration" type="number" min="0" max="1440" step="1"
          value={duration} onChange={(event) => setDuration(event.target.value)} /></label>
        <label>Target heart-rate zone (main set)<select value={zone} onChange={(event) => setZone(event.target.value)}>
          <option value="">Unspecified</option>
          {[1, 2, 3, 4, 5].flatMap((low) => Array.from({ length: 6 - low }, (_, offset) => {
            const high = low + offset;
            return <option key={`${low}-${high}`} value={`${low}-${high}`}>
              {low === high ? `Z${low}` : `Z${low}-${high}`}
            </option>;
          }))}
        </select></label>
        <label>Effort / RPE (optional)<input name="effort" type="number" min="1" max="10" step="1"
          defaultValue={session?.effort ?? ""} /></label>
        <label className="calendar-editor-notes">Notes (optional)<textarea name="notes" rows={2}
          defaultValue={session?.notes ?? ""} /></label>
        <div className="calendar-editor-actions">
          <button type="submit">{disabled ? "Saving?" : "Save training"}</button>
          <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  );
}
