import type { ReactElement } from "react";
import type { Session } from "../api/types";

/** Controlled selection for the planner's one-proposal-per-day preview. */
interface CalendarSelection {
    selectedDays: readonly string[];
    disabled: boolean;
    onChange: (day: string, selected: boolean) => void;
}

/** Calendar data and optional controls for selecting draft suggestions. */
interface WeeklyCalendarProps {
    weekStart: string;
    sessions: readonly Session[];
    proposals?: readonly Session[];
    blocked?: readonly string[];
    selection?: CalendarSelection;
}

/**
 * Display seven calendar days with saved workouts and draft suggestions.
 *
 * Parameters
 * ----------
 * props : WeeklyCalendarProps
 *     Valid Monday date in YYYY-MM-DD format, saved sessions, optional
 *     proposals, unavailable dates, and controlled proposal selection.
 *     Selection is keyed by date because the current planner generates
 *     at most one proposal per day.
 *
 * Returns
 * -------
 * ReactElement
 *     Weekly calendar with empty days and optional selection controls.
 *
 * Raises
 * ------
 * RangeError
 *     If weekStart cannot be parsed as a valid calendar date.
 */
export default function WeeklyCalendar({
    weekStart,
    sessions,
    proposals = [],
    blocked = [],
    selection,
}: WeeklyCalendarProps): ReactElement {
    const today = new Date();
    const weekdayFormat = new Intl.DateTimeFormat(undefined, {
        weekday: "long",
    });
    const dateFormat = new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
    });

    const days = Array.from({ length: 7 }, (_, offset) => {
        // Advance local calendar days rather than adding fixed 24-hour intervals.
        // Local noon avoids UTC date shifts and most daylight-saving boundaries.
        const date = new Date(`${weekStart}T12:00:00`);
        date.setDate(date.getDate() + offset);

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const dayOfMonth = String(date.getDate()).padStart(2, "0");

        return {
            date,
            day: `${year}-${month}-${dayOfMonth}`,
            isToday: date.toDateString() === today.toDateString(),
        };
    });

    return (
        <ol
            className="weekly-calendar"
            aria-label={`Week beginning ${weekStart}`}
        >
            {days.map(({ date, day, isToday }) => {
                // Track proposal ownership explicitly; both drafts and saved workouts
                // can have the "planned" status.
                const items = [
                    ...sessions
                        .filter((session) => session.day === day)
                        .map((session) => ({ session, isProposal: false })),
                    ...proposals
                        .filter((session) => session.day === day)
                        .map((session) => ({ session, isProposal: true })),
                ];

                return (
                    <li
                        key={day}
                        className={`calendar-day${isToday ? " calendar-day--today" : ""}`}
                    >
                        <h3 className="calendar-day-heading">
                            <time dateTime={day} aria-current={isToday ? "date" : undefined}>
                                {weekdayFormat.format(date)}
                                <small>{dateFormat.format(date)}</small>
                            </time>
                        </h3>

                        {isToday && <p className="calendar-day-label">Today</p>}
                        {blocked.includes(day) && (
                            <p className="calendar-day-label">
                                Unavailable for suggestions
                            </p>
                        )}

                        {items.length === 0 && (
                            <p className="calendar-empty">No sessions</p>
                        )}

                        {items.map(({ session, isProposal }, index) => (
                            <article
                                key={
                                    isProposal
                                        ? `proposal-${day}-${session.activity}-${index}`
                                        : `session-${session.id ?? `${day}-${index}`}`
                                }
                                className={
                                    "calendar-card " +
                                    (isProposal
                                        ? "calendar-card--proposal"
                                        : `calendar-card--${session.status}`)
                                }
                            >
                                <h4>{session.activity.replaceAll("_", " ")}</h4>
                                <p className="calendar-card-status">
                                    {isProposal ? "Suggestion" : session.status}
                                </p>

                                {session.duration_min !== null && (
                                    <p>{session.duration_min} min</p>
                                )}
                                {session.effort !== null && (
                                    <p>RPE {session.effort}/10</p>
                                )}
                                {session.notes && (
                                    <p className="calendar-card-notes">{session.notes}</p>
                                )}

                                {isProposal && selection && (
                                    <label className="calendar-selection">
                                        <input
                                            type="checkbox"
                                            aria-label={`Select ${day} ${session.activity.replaceAll("_", " ")}`}
                                            checked={selection.selectedDays.includes(day)}
                                            disabled={selection.disabled}
                                            onChange={(event) =>
                                                selection.onChange(day, event.target.checked)
                                            }
                                        />
                                        Select
                                    </label>
                                )}
                            </article>
                        ))}
                    </li>
                );
            })}
        </ol>
    );
}