"""Deterministic proposals over an explicit horizon, with calendar-day recovery."""

from datetime import date, timedelta

from training_planner.domain.models import Activity, Session, Status
from training_planner.domain.running import recovery_days, workload_duration


def _is_short_monday_easy_run(session: Session) -> bool:
    """Identify the easy recovery exception from workout data, regardless of origin."""
    duration = workload_duration(session)
    return (
        session.activity == Activity.EASY_RUN
        and session.day.weekday() == 0
        and duration is not None
        and duration <= 20
        and recovery_days(session) == 0
    )


def recovery_conflict(candidate: Session, other: Session) -> bool:
    """Protect endurance in either insertion order; ordinary gym load is unknown."""
    if other.status == Status.SKIPPED or other.activity == Activity.REST:
        return False
    if other.activity == Activity.GYM and recovery_days(other) == 0:
        return False
    # Monday recovery runs must remain compatible after acceptance as well as
    # during generation; database identity and proposal order do not change load.
    if _is_short_monday_easy_run(candidate) or _is_short_monday_easy_run(other):
        return False
    return abs((candidate.day - other.day).days) < max(
        recovery_days(candidate), recovery_days(other)
    )


def suggest_week(
    week_start: date,
    existing: list[Session],
    blocked: set[date] | None = None,
    *,
    not_before: date,
    weeks: int = 1,
) -> list[Session]:
    """Plan 1-4 weeks, preserving bookings and using blocked dates as recovery time.

    Hikes keep their Saturday slot. Long runs prefer Sunday, then search the next
    six days within the requested horizon. Reserve endurance before default gym
    and Monday easy sessions. Long-run suggestions stay at least seven days apart
    from saved or proposed long runs, avoiding deferred runs piling up.
    """
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    if not 1 <= weeks <= 4:
        raise ValueError("weeks must be between 1 and 4")
    end = week_start + timedelta(days=7 * weeks - 1)
    occupied = {s.day for s in existing} | (blocked or set())
    proposals: list[Session] = []

    def available(day: date) -> bool:
        return max(week_start, not_before) <= day <= end and day not in occupied

    def add(session: Session) -> bool:
        if not available(session.day):
            return False
        proposals.append(session)
        occupied.add(session.day)
        return True

    # All hikes are reserved first, including later weeks, so fallback runs
    # cannot force a hike onto a weekday or conflict with another proposal.
    for week in range(weeks):
        hike = Session(
            week_start + timedelta(days=7 * week + 5),
            Activity.HIKE,
            duration_min=180,
            notes="Long hike; counts as demanding endurance.",
        )
        if not any(recovery_conflict(hike, s) for s in existing + proposals):
            add(hike)

    for week in range(weeks):
        sunday = week_start + timedelta(days=7 * week + 6)
        for delay in range(7):
            day = sunday + timedelta(days=delay)
            if not available(day):
                continue
            run = Session(
                day,
                Activity.LONG_RUN,
                duration_min=45,
                hr_zone_min=2,
                hr_zone_max=2,
                notes=(
                    "Long easy Z2 run; editable starting duration, "
                    "not a personalized long-run target."
                )
                + (
                    " Moved from Sunday to an available day with recovery spacing."
                    if delay
                    else ""
                ),
            )
            load = existing + proposals
            if any(
                s.activity == Activity.LONG_RUN
                and s.status != Status.SKIPPED
                and abs((s.day - day).days) < 7
                for s in load
            ):
                continue
            if not any(recovery_conflict(run, s) for s in load):
                add(run)
                break

    for week in range(weeks):
        monday = week_start + timedelta(days=7 * week)
        nearby = any(
            abs((s.day - monday).days) < recovery_days(s) for s in existing + proposals
        )
        # Short easy work remains an explicit exception to the endurance buffer.
        add(
            Session(
                monday,
                Activity.EASY_RUN,
                duration_min=20 if nearby else 30,
                hr_zone_min=2,
                hr_zone_max=2,
                notes=(
                    "Easy Z2 conversational running; "
                    "shortened around nearby demanding training."
                )
                if nearby
                else "Easy Z2 conversational running to build aerobic consistency.",
            )
        )
        for offset in (1, 2, 4):
            add(
                Session(
                    monday + timedelta(days=offset),
                    Activity.GYM,
                    duration_min=75,
                    notes="Suggested session; review before confirming",
                )
            )
    return sorted(proposals, key=lambda s: s.day)
