/** Transport contracts matching the FastAPI session and planning schemas. */
export const activities = [
  "gym", "recovery_run", "easy_run", "long_run", "tempo_run", "interval_run",
  "hard_endurance_run", "race", "hike", "cycle", "rest",
] as const;
export const statuses = ["planned", "confirmed", "completed", "skipped"] as const;

export interface SessionInput {
  day: string;
  activity: typeof activities[number];
  status: typeof statuses[number];
  duration_min: number | null;
  actual_duration_min: number | null;
  distance_km: number | null;
  average_hr_bpm: number | null;
  elevation_gain_m: number | null;
  active_calories_kcal: number | null;
  effort: number | null;
  notes: string;
  hr_zone_min: number | null;
  hr_zone_max: number | null;
}

export interface Session extends SessionInput {
  id: number | null;
}

export interface ProposalMove {
  original_day: string;
  session: SessionInput;
}

export interface PlanningRequest {
  week_start: string;
  weeks: number;
  blocked: string[];
  moves?: ProposalMove[];
  dismissed?: string[];
}
