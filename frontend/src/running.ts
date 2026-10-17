import type { SessionInput } from "./api/types";

type Activity = SessionInput["activity"];
interface RunPreset {
  label: string;
  minutes: number | null;
  low: number | null;
  high: number | null;
  description: string;
}

export const runPresets: Partial<Record<Activity, RunPreset>> = {
  recovery_run: { label: "Recovery run", minutes: 20, low: 1, high: 2,
    description: "Very gentle Z1-2 running. Rest is also an option when tired." },
  easy_run: { label: "Easy run", minutes: 30, low: 2, high: 2,
    description: "Z2, comfortable conversational effort. Adjust duration to your training history." },
  long_run: { label: "Long easy run", minutes: 45, low: 2, high: 2,
    description: "Z2 endurance. Long is relative to your recent runs; 45 min is an editable starting value." },
  tempo_run: { label: "Tempo / threshold run", minutes: 40, low: 3, high: 4,
    description: "Controlled sustained effort, not all-out. Example: 10 min Z1-2 + 20 min Z3-4 + 10 min Z1-2 (40 min total)." },
  interval_run: { label: "VO2 max intervals", minutes: 45, low: 4, high: 5,
    description: "Example: 10 min Z1-2 + 4 x 4 min hard with 3 x 3 min easy between + 10 min Z1-2 (45 min total). Z4-5 applies only to work bouts; build toward roughly 85-95% HRmax. HR lags effort: do not sprint to chase the zone." },
  hard_endurance_run: { label: "Hard endurance run", minutes: 60, low: 3, high: 4,
    description: "Demanding sustained endurance, not a maximum-effort test. Z3-4 is the main-set target; include easy warm-up and cool-down in the total duration." },
  race: { label: "Race / maximum-effort test", minutes: null, low: null, high: null,
    description: "An explicitly chosen performance event. Set duration for the event; no universal HR zone applies across race lengths. Allow extra recovery." },
};

export function activityLabel(activity: Activity): string {
  return runPresets[activity]?.label ?? activity.replaceAll("_", " ");
}

export function zoneLabel(low: number | null, high: number | null): string {
  return low === null || high === null ? "Target zone unspecified"
    : low === high ? `Target Z${low}` : `Main-set target Z${low}-${high}`;
}
