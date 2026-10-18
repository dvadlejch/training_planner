import { useEffect, useRef, useState, type ReactElement } from "react";
import { statuses, type Session, type SessionInput } from "../api/types";
import { activityLabel } from "../running";
import { sessionOverview } from "../sessionStats";
import SessionDetails from "./SessionDetails";

/** Calendar data and optional controls for confirming draft suggestions. */
interface WeeklyCalendarProps {
    weekStart: string;
    /** A month switches to compact cards and complete month rows. */
    month?: string;
    dayCount?: number;
    sessions: readonly Session[];
    proposals?: readonly Session[];
    blocked?: readonly string[];
    onAvailabilityChange?: (day: string, unavailable: boolean) => void;
    onConfirmProposal?: (session: Session) => void;
    onDelete?: (session: Session) => void;
    onStatusChange?: (session: Session, status: SessionInput["status"]) => void;
    onAdd?: (day: string) => void;
    onEdit?: (session: Session) => void;
    onMove?: (session: Session, day: string) => void;
    onMoveProposal?: (session: Session, day: string) => void;
    onEditProposal?: (session: Session) => void;
    onRemoveProposal?: (session: Session) => void;
    editor?: { day: string; content?: ReactElement };
    disabled?: boolean;
}

/**
 * Display a week or a full month with saved workouts and draft suggestions.
 *
 * Parameters
 * ----------
 * props : WeeklyCalendarProps
 *     Valid Monday date in YYYY-MM-DD format, saved sessions, optional
 *     proposals, unavailable dates, and direct proposal confirmation.
 *
 * Returns
 * -------
 * ReactElement
 *     Calendar with empty days and optional confirmation controls.
 *
 * Raises
 * ------
 * RangeError
 *     If weekStart cannot be parsed as a valid calendar date.
 */
export default function WeeklyCalendar({
    weekStart,
    month,
    dayCount = 7,
    sessions,
    proposals = [],
    blocked = [],
    onAvailabilityChange,
    onConfirmProposal,
    onDelete,
    onStatusChange,
    onAdd,
    onEdit,
    onMove,
    onMoveProposal,
    onEditProposal,
    onRemoveProposal,
    editor,
    disabled = false,
}: WeeklyCalendarProps): ReactElement {
    const dragged = useRef<{ session: Session; isProposal: boolean } | null>(null);
    const [dropDay, setDropDay] = useState<string | null>(null);
    const canMove = Boolean(onMove || onMoveProposal) && !disabled && editor === undefined;

    useEffect(() => {
        dragged.current = null;
        setDropDay(null);
    }, [weekStart, month, disabled, editor]);

    function clearDrag(): void {
        dragged.current = null;
        setDropDay(null);
    }

    function draggedSession(day: string): { session: Session; isProposal: boolean } | undefined {
        const source = dragged.current;
        if (!canMove || !source) return;
        const session = source.isProposal
            ? proposals.find((item) => item === source.session)
            : sessions.find((item) => item.id === source.session.id);
        if (session && session.day !== day) return { session, isProposal: source.isProposal };
    }

    const today = new Date();
    const weekdayFormat = new Intl.DateTimeFormat(undefined, {
        weekday: "long",
    });
    const dateFormat = new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
    });

    const days = Array.from({ length: dayCount }, (_, offset) => {
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
            className={`weekly-calendar${month ? " monthly-calendar" : ""}`}
            aria-label={month ? `Month ${month}` : `Week beginning ${weekStart}`}
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
                        className={`calendar-day${editor?.day === day ? " calendar-day--selected" : ""}${isToday ? " calendar-day--today" : ""}${editor?.day === day && !month ? " calendar-day--editing" : ""}${month && !day.startsWith(month) ? " calendar-day--outside" : ""}${canMove && dropDay === day ? " calendar-day--drop-target" : ""}`}
                        onDragOver={(event) => {
                            if (!draggedSession(day)) return;
                            event.preventDefault();
                            event.dataTransfer.dropEffect = "move";
                            setDropDay(day);
                        }}
                        onDragLeave={(event) => {
                            if (!(event.relatedTarget instanceof Node) ||
                                !event.currentTarget.contains(event.relatedTarget)) {
                                setDropDay((current) => current === day ? null : current);
                            }
                        }}
                        onDrop={(event) => {
                            const session = draggedSession(day);
                            if (dragged.current !== null) event.preventDefault();
                            clearDrag();
                            if (session?.isProposal) onMoveProposal?.(session.session, day);
                            else if (session) onMove?.(session.session, day);
                        }}
                    >
                        <h3 className="calendar-day-heading">
                            <time dateTime={day} aria-current={isToday ? "date" : undefined}>
                                {month ? <>
                                    <span className="calendar-date-number">{date.getDate()}</span>
                                    <span className="calendar-mobile-date">{weekdayFormat.format(date)} &middot; {dateFormat.format(date)}</span>
                                </> : weekdayFormat.format(date)}
                                {!month && <small>{dateFormat.format(date)}</small>}
                                {month && <span className="sr-only"> {dateFormat.format(date)}</span>}
                            </time>
                        </h3>

                        {isToday && <p className="calendar-day-label">Today</p>}
                        {onAvailabilityChange ? (
                            <label className="calendar-availability">
                                <input type="checkbox"
                                    aria-label={`Unavailable for suggestions on ${day}`}
                                    checked={blocked.includes(day)}
                                    disabled={disabled || editor !== undefined}
                                    onChange={(event) => onAvailabilityChange(day, event.target.checked)} />
                                Unavailable
                            </label>
                        ) : blocked.includes(day) && (
                            <p className="calendar-day-label">
                                Unavailable for suggestions
                            </p>
                        )}

                        {onAdd && (
                            <button type="button" className="calendar-action secondary"
                                aria-label={`Add training on ${day}`}
                                disabled={disabled || editor !== undefined}
                                onClick={() => onAdd(day)}>
                                {month ? "+ Add" : "+ Add training"}
                            </button>
                        )}
                        {!month && editor?.day === day && editor.content}

                        {items.length === 0 && (
                            <p className="calendar-empty">Open day</p>
                        )}

                        {items.map(({ session, isProposal }, index) => (
                            <article
                                key={
                                    isProposal
                                        ? `proposal-${day}-${session.activity}-${index}`
                                        : `session-${session.id ?? `${day}-${index}`}`
                                }
                                className={
                                    `calendar-card calendar-card--activity-${session.activity} ` +
                                    (isProposal
                                        ? "calendar-card--proposal"
                                        : `calendar-card--${session.status}`)
                                }
                            >
                                {((isProposal && onMoveProposal) || (!isProposal && session.id !== null && onMove)) && (
                                    <button
                                        type="button"
                                        className="calendar-drag-handle"
                                        aria-label={`Move ${day} ${activityLabel(session.activity)}`}
                                        title="Drag to another day, or click to edit the date"
                                        draggable={canMove}
                                        disabled={!canMove}
                                        onClick={() => isProposal ? onEditProposal?.(session) : onEdit?.(session)}
                                        onDragStart={(event) => {
                                            if (!canMove) { event.preventDefault(); return; }
                                            dragged.current = { session, isProposal };
                                            event.dataTransfer.effectAllowed = "move";
                                            event.dataTransfer.setData("text/plain", isProposal ? `proposal-${session.day}` : String(session.id));
                                            // The browser's drag image floats outside scrollable cells.
                                            const card = event.currentTarget.closest("article");
                                            if (card) event.dataTransfer.setDragImage(card, 12, 12);
                                        }}
                                        onDragEnd={clearDrag}
                                    >
                                        <span aria-hidden="true">&#x283f;</span>
                                    </button>
                                )}
                                <details open={month ? undefined : true}>
                                    <summary>
                                        <h4>{activityLabel(session.activity)}</h4>
                                        <span className="calendar-card-overview">
                                            {sessionOverview(session)}
                                        </span>
                                        <span className={`status-badge status-badge--${isProposal ? "proposal" : session.status}`}>
                                            {isProposal ? "Suggestion" : session.status}
                                        </span>
                                    </summary>
                                    <SessionDetails session={session} />

                                    {!isProposal && session.id !== null && onStatusChange && (
                                        <>
                                            <label className="calendar-status-control">Status
                                                <select
                                                    aria-label={`Status for ${day} ${activityLabel(session.activity)}`}
                                                    value={session.status}
                                                    disabled={disabled || editor !== undefined}
                                                    onChange={(event) => onStatusChange(
                                                        session, event.target.value as SessionInput["status"],
                                                    )}
                                                >
                                                    {statuses.map((status) => (
                                                        <option key={status} value={status}>{status}</option>
                                                    ))}
                                                </select>
                                            </label>
                                            {session.status === "planned" && (
                                                <button type="button" className="calendar-action"
                                                    aria-label={`Confirm ${day} ${activityLabel(session.activity)}`}
                                                    disabled={disabled || editor !== undefined}
                                                    onClick={() => onStatusChange(session, "confirmed")}>
                                                    Confirm
                                                </button>
                                            )}
                                        </>
                                    )}

                                    {!isProposal && session.id !== null && onEdit && (
                                        <button type="button" className="calendar-action secondary"
                                            aria-label={`Edit ${day} ${activityLabel(session.activity)}`}
                                            disabled={disabled || editor !== undefined}
                                            onClick={() => onEdit(session)}>
                                            Edit
                                        </button>
                                    )}

                                    {!isProposal && session.id !== null && onDelete && (
                                        <button
                                            type="button"
                                            className="calendar-delete"
                                            aria-label={`Delete ${day} ${activityLabel(session.activity)}`}
                                            disabled={disabled || editor !== undefined}
                                            onClick={() => {
                                                if (window.confirm(
                                                    `Delete saved ${activityLabel(session.activity)} on ${day} (${session.status})? This cannot be undone.`,
                                                )) onDelete(session);
                                            }}
                                        >
                                            Delete
                                        </button>
                                    )}
                                </details>
                                {isProposal && onConfirmProposal && (
                                    <button type="button" className="calendar-action"
                                        aria-label={`Confirm suggestion ${day} ${activityLabel(session.activity)}`}
                                        disabled={disabled || editor !== undefined}
                                        onClick={() => onConfirmProposal(session)}>
                                        Confirm
                                    </button>
                                )}
                                {isProposal && onRemoveProposal && (
                                    <button type="button" className="calendar-action secondary"
                                        aria-label={`Remove suggestion ${day} ${activityLabel(session.activity)}`}
                                        disabled={disabled || editor !== undefined}
                                        onClick={() => onRemoveProposal(session)}>
                                        Remove
                                    </button>
                                )}
                            </article>
                        ))}
                    </li>
                );
            })}
        </ol>
    );
}
