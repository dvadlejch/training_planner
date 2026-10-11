/** Transport contracts matching the FastAPI session and planning schemas. */
export const activities = [
  "gym", "easy_run", "quality_run", "long_run", "hike", "cycle", "rest",
] as const;
export const statuses = ["planned", "completed", "skipped"] as const;

export interface SessionInput {
  day: string;
  activity: typeof activities[number];
  status: typeof statuses[number];
  duration_min: number | null;
  effort: number | null;
  notes: string;
}

export interface Session extends SessionInput {
  id: number | null;
}

export interface PlanningRequest {
  week_start: string;
  blocked: string[];
}
