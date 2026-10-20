import { muscleGroupLabel, type SessionInput } from "./api/types";

/** Activity-specific results shared by the editor and event details. */
export function activityStats(activity: SessionInput["activity"]) {
  const running = activity.endsWith("_run") || activity === "race";
  return {
    duration: activity !== "rest",
    distance: running || activity === "cycle" || activity === "hike",
    heartRate: running || activity === "cycle",
    elevation: activity === "cycle" || activity === "hike",
    pace: running || activity === "hike",
    calories: activity !== "rest",
  };
}

/** Parse minutes or elapsed mm:ss / hh:mm:ss; NaN marks an invalid duration. */
export function parseDuration(value: string): number | null {
  const text = value.trim();
  if (text === "") return null;
  let minutes: number;
  if (/^\d+(?:\.\d+)?$/.test(text)) {
    minutes = Number(text);
  } else if (/^\d+:[0-5]\d$/.test(text)) {
    const [wholeMinutes, seconds] = text.split(":").map(Number);
    minutes = wholeMinutes + seconds / 60;
  } else if (/^\d+:[0-5]\d:[0-5]\d$/.test(text)) {
    const [hours, wholeMinutes, seconds] = text.split(":").map(Number);
    minutes = hours * 60 + wholeMinutes + seconds / 60;
  } else {
    return NaN;
  }
  return Number.isFinite(minutes) && minutes <= 1440 ? minutes : NaN;
}

/** Derive average pace from recorded total time; missing/zero inputs have no pace. */
export function averagePace(distance: number | null, minutes: number | null): string | null {
  if (distance == null || minutes == null || distance <= 0 || minutes <= 0 ||
      !Number.isFinite(distance) || !Number.isFinite(minutes)) return null;
  const seconds = Math.round(minutes * 60 / distance);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} /km`;
}

/** Keep completed results separate from upcoming targets in compact cards. */
export function sessionOverview(session: SessionInput): string {
  const muscles = session.activity === "gym" && session.muscle_groups?.length
    ? session.muscle_groups.map(muscleGroupLabel).join(", ") : null;
  if (session.status !== "completed") {
    return [
      muscles,
      session.duration_min != null ? `${session.duration_min} min planned` : null,
      session.hr_zone_min != null ? (session.hr_zone_min === session.hr_zone_max
        ? `Target Z${session.hr_zone_min}` : `Target Z${session.hr_zone_min}-${session.hr_zone_max}`) : null,
    ].filter(Boolean).join(" · ");
  }
  const stats = activityStats(session.activity);
  return [
    muscles,
    stats.distance && session.distance_km != null ? `${session.distance_km} km` : null,
    stats.duration && session.actual_duration_min != null ? `${session.actual_duration_min} min` : null,
    stats.pace ? averagePace(session.distance_km, session.actual_duration_min) : null,
    stats.elevation && session.elevation_gain_m != null ? `↑ ${session.elevation_gain_m} m` : null,
  ].filter(Boolean).join(" · ");
}
