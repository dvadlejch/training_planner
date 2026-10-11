import type { ReactElement } from "react";
import type { Session } from "../api/types";

/** Display stored workouts or proposals without replacing unknown metrics.
 *
 * Parameters
 * ----------
 * props : { sessions: Session[] }
 *     Workouts or proposals to display.
 *
 * Returns
 * -------
 * ReactElement
 *     Accessible table, or an empty-state message.
 */
export default function SessionTable({ sessions }: { sessions: Session[] }): ReactElement {
  if (sessions.length === 0) return <p className="muted">No sessions in this list.</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead><tr><th>Date</th><th>Activity</th><th>Status</th><th>Minutes</th><th>RPE</th><th>Notes</th></tr></thead>
        <tbody>{sessions.map((session) => (
          <tr key={session.id ?? `${session.day}-${session.activity}`}>
            <td>{session.day}</td><td>{session.activity.replaceAll("_", " ")}</td>
            <td>{session.status}</td><td>{session.duration_min ?? "—"}</td>
            <td>{session.effort ?? "—"}</td><td>{session.notes || "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
