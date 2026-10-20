/** Transport contracts matching the FastAPI session and planning schemas. */
export const activities = [
  "gym", "recovery_run", "easy_run", "long_run", "tempo_run", "interval_run",
  "hard_endurance_run", "race", "hike", "cycle", "rest",
] as const;
export const statuses = ["planned", "confirmed", "completed", "skipped"] as const;

export const muscleGroupCategories = [
  { label: "Large muscle groups", groups: ["chest", "legs", "back"] },
  { label: "Small muscle groups", groups: ["biceps", "triceps", "shoulders"] },
  { label: "Core", groups: ["abs"] },
] as const;
export type MuscleGroup = typeof muscleGroupCategories[number]["groups"][number];
export const muscleGroupLabel = (group: MuscleGroup): string => group[0].toUpperCase() + group.slice(1);

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
  muscle_groups: MuscleGroup[];
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

export interface TrainingTargets {
  gym: number;
  runs: number;
  /** Included within total runs. */
  intervals: number;
}

export interface ProposalKey {
  day: string;
  activity: SessionInput["activity"];
}

export interface ActivityWeekdays {
  /** Monday = 0, Sunday = 6. Empty arrays disable that activity's suggestions. */
  gym: number[];
  running: number[];
}

export interface PlanningRequest {
  /** Inclusive start of the rolling horizon; new plans use today's local date. */
  week_start: string;
  weeks: 4;
  targets: TrainingTargets;
  weekdays: ActivityWeekdays;
  excluded?: ProposalKey[];
  blocked: string[];
  moves?: ProposalMove[];
  dismissed?: string[];
}
