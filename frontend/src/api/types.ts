/** Transport contracts matching the FastAPI session and planning schemas. */
export const activities = [
  "gym", "recovery_run", "easy_run", "long_run", "tempo_run", "interval_run",
  "hard_endurance_run", "race", "hike", "cycle", "rest",
] as const;
export const statuses = ["planned", "completed", "skipped"] as const;

export interface SessionInput {
  day: string;
  activity: typeof activities[number];
  status: typeof statuses[number];
  duration_min: number | null;
  effort: number | null;
  notes: string;
  hr_zone_min: number | null;
  hr_zone_max: number | null;
}

export interface Session extends SessionInput {
  id: number | null;
}

export interface PlanningRequest {
  week_start: string;
  weeks: number;
  blocked: string[];
}
