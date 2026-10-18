import type { SessionInput } from "../api/types";
import { zoneLabel } from "../running";
import { activityStats, averagePace } from "../sessionStats";

/** Labeled targets and optional recorded results for an expanded event. */
export default function SessionDetails({ session }: { session: SessionInput }) {
  const stats = activityStats(session.activity);
  const results: [string, string | null][] = [
    ["Actual duration", stats.duration && session.actual_duration_min != null ? `${session.actual_duration_min} min` : null],
    ["Distance", stats.distance && session.distance_km != null ? `${session.distance_km} km` : null],
    ["Average pace", stats.pace ? averagePace(session.distance_km, session.actual_duration_min) : null],
    ["Average HR", stats.heartRate && session.average_hr_bpm != null ? `${session.average_hr_bpm} bpm` : null],
    ["Elevation gain", stats.elevation && session.elevation_gain_m != null ? `${session.elevation_gain_m} m` : null],
    ["Active calories", stats.calories && session.active_calories_kcal != null ? `${session.active_calories_kcal} kcal` : null],
    ["Recorded RPE", session.effort != null ? `${session.effort}/10` : null],
  ];
  const recorded = results.filter(([, value]) => value !== null);
  return <div className="session-details">
    {(session.duration_min != null || session.hr_zone_min != null) && <section>
      <h5>Training targets</h5><dl>
        {session.duration_min != null && <><dt>Planned duration</dt><dd>{session.duration_min} min</dd></>}
        {session.hr_zone_min != null && <><dt>Main-set HR</dt><dd>{zoneLabel(session.hr_zone_min, session.hr_zone_max)}</dd></>}
      </dl>
    </section>}
    {recorded.length > 0 && <section><h5>Recorded results</h5><dl>
      {recorded.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl></section>}
    {session.notes && <section><h5>{session.activity === "gym" ? "Workout notes" : "Notes"}</h5>
      <p className="calendar-card-notes">{session.notes}</p></section>}
  </div>;
}
