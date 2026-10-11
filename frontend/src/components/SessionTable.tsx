import type { ReactElement } from "react";
import type { Session } from "../api/types";

/** Optional selection controls for the current whole-day proposal list. */
interface SessionSelection {
  selectedDays: readonly string[];
  onChange: (day: string, selected: boolean) => void;
  disabled?: boolean;
}

/** Workouts to display and optional controlled selection state. */
interface SessionTableProps {
  sessions: Session[];
  selection?: SessionSelection;
}

/** Display workouts with optional proposal selection and preserve unknown metrics.
 *
 * Parameters
 * ----------
 * props : SessionTableProps
 *     Workouts to display. When selection is supplied, show controlled checkboxes
 *     keyed by date; this assumes at most one selectable proposal per date.
 *
 * Returns
 * -------
 * ReactElement
 *     Accessible table, or an empty-state message.
 */
export default function SessionTable({
  sessions,
  selection,
}: SessionTableProps): ReactElement {
  if (sessions.length === 0) return <p className="muted">No sessions in this list.</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead><tr>
          {selection && <th scope="col">Select</th>}
          <th scope="col">Date</th>
          <th scope="col">Activity</th>
          <th scope="col">Status</th>
          <th scope="col">Minutes</th>
          <th scope="col">RPE</th>
          <th scope="col">Notes</th>
        </tr></thead>
        <tbody>{sessions.map((session) => (
          <tr key={session.id ?? `${session.day}-${session.activity}`}>
            {selection && <td>
              <input
                type="checkbox"
                aria-label={`Select ${session.day} ${session.activity.replaceAll("_", " ")}`}
                checked={selection.selectedDays.includes(session.day)}
                disabled={selection.disabled}
                onChange={(event) => selection.onChange(session.day, event.target.checked)}
              />
            </td>}
            <td>{session.day}</td><td>{session.activity.replaceAll("_", " ")}</td>
            <td>{session.status}</td><td>{session.duration_min ?? "—"}</td>
            <td>{session.effort ?? "—"}</td><td>{session.notes || "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
