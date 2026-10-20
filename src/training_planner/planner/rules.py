"""Deterministic proposals over an explicit horizon, with calendar-day recovery."""

from datetime import date, timedelta

from training_planner.domain.models import (
    Activity,
    ActivityWeekdays,
    GymSplit,
    Session,
    Status,
    TrainingTargets,
)
from training_planner.domain.running import (
    leg_endurance_conflict,
    recovery_days,
    workload_duration,
)
from training_planner.planner.gym import assign_gym_targets


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
    """Protect endurance and identified leg sessions in either insertion order."""
    if candidate.status == Status.SKIPPED or other.status == Status.SKIPPED:
        return False
    if leg_endurance_conflict(candidate, other):
        return True
    if other.activity == Activity.REST:
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


PLANNING_DAYS = 28
RUN_ACTIVITIES = {activity for activity in Activity if activity.value.endswith("_run")}
RUN_ACTIVITIES.add(Activity.RACE)


def suggest_week(
    week_start: date,
    existing: list[Session],
    blocked: set[date] | None = None,
    *,
    not_before: date,
    targets: TrainingTargets = TrainingTargets(),
    weekdays: ActivityWeekdays = ActivityWeekdays(),
    excluded: set[tuple[date, Activity]] | None = None,
    gym_split: GymSplit = GymSplit(),
) -> list[Session]:
    """Fill soft targets over four seven-day periods without changing saved work.

    Periods start on the requested date, avoiding partial-week catch-up quotas.
    Keep the starter Saturday hikes and Sunday/fallback long runs where feasible.
    Targets include planned, confirmed and completed sessions. Skipped work does
    not occupy capacity or satisfy targets. Automatic pairing is limited to an
    ordinary gym session and an easy/recovery run, with at most two items a day.
    Recurring allowed weekdays restrict new gym/running suggestions; saved work
    outside those days is preserved and still counts toward the targets.
    Gym muscle targets rotate chronologically using the selected accessory split
    and any known primary targets on saved workouts.
    """
    end = week_start + timedelta(days=PLANNING_DAYS - 1)
    blocked = blocked or set()
    excluded = excluded or set()
    active = [s for s in existing if s.status != Status.SKIPPED]
    proposals: list[Session] = []
    periods = [week_start + timedelta(days=offset) for offset in range(0, 28, 7)]

    def load() -> list[Session]:
        return active + proposals

    def in_period(session: Session, start: date) -> bool:
        return start <= session.day < start + timedelta(days=7)

    def count(start: date, activities: set[Activity]) -> int:
        return sum(in_period(s, start) and s.activity in activities for s in load())

    def period_for(day: date) -> date:
        return week_start + timedelta(days=((day - week_start).days // 7) * 7)

    def add(session: Session) -> bool:
        day = session.day
        if (
            not max(week_start, not_before) <= day <= end
            or day in blocked
            or not weekdays.allows(day, session.activity)
            or (day, session.activity) in excluded
        ):
            return False
        others = [s for s in load() if s.day == day]
        if others:
            # Same-day suggestions are limited to a light run plus ordinary gym.
            pair = {session.activity, others[0].activity}
            if (
                len(others) >= 2
                or len(pair) != 2
                or Activity.GYM not in pair
                or not pair & {Activity.EASY_RUN, Activity.RECOVERY_RUN}
                or any(recovery_days(s) for s in [session, *others])
            ):
                return False
        if session.activity != Activity.GYM and any(
            recovery_conflict(session, s) for s in load()
        ):
            return False
        proposals.append(session)
        return True

    def ranked_days(start: date, weekdays: tuple[int, ...]) -> list[date]:
        return sorted(
            (start + timedelta(days=i) for i in range(7)),
            key=lambda day: weekdays.index(day.weekday()),
        )

    # Preserve weekend outdoors, while checking all neighboring saved workload.
    for offset in range(PLANNING_DAYS):
        day = week_start + timedelta(days=offset)
        if day.weekday() == 5:
            add(
                Session(
                    day,
                    Activity.HIKE,
                    duration_min=180,
                    notes="Long hike; counts as demanding endurance.",
                )
            )

    # Intervals are part of the run total, never an additional quota.
    for start in periods:
        for day in ranked_days(start, (3, 1, 2, 4, 0, 6, 5)):
            if (
                count(start, {Activity.INTERVAL_RUN}) >= targets.intervals
                or count(start, RUN_ACTIVITIES) >= targets.runs
            ):
                break
            add(
                Session(
                    day,
                    Activity.INTERVAL_RUN,
                    duration_min=45,
                    hr_zone_min=4,
                    hr_zone_max=5,
                    notes="Interval run toward your weekly target; "
                    "review intensity and duration.",
                )
            )

    # A single weekly run stays easy and can pair with gym on a busy day.
    # Keep long runs at least seven days apart across period boundaries.
    for offset in range(PLANNING_DAYS):
        sunday = week_start + timedelta(days=offset)
        if sunday.weekday() != 6 or targets.runs < 2:
            continue
        for delay in range(7):
            day = sunday + timedelta(days=delay)
            if day > end:
                break
            if count(period_for(day), RUN_ACTIVITIES) >= targets.runs:
                continue
            if any(
                s.activity == Activity.LONG_RUN and abs((s.day - day).days) < 7
                for s in load()
            ):
                continue
            run = Session(
                day,
                Activity.LONG_RUN,
                duration_min=45,
                hr_zone_min=2,
                hr_zone_max=2,
                notes="Long easy Z2 run; editable starting duration, "
                "not a personalized long-run target.",
            )
            if add(run):
                break

    for start in periods:
        for day in ranked_days(start, (0, 3, 2, 4, 1, 6, 5)):
            if count(start, RUN_ACTIVITIES) >= targets.runs:
                break
            # Constant durations keep draft contents stable after partial acceptance.
            # The existing Monday recovery exception remains data-based.
            add(
                Session(
                    day,
                    Activity.EASY_RUN,
                    duration_min=20 if day.weekday() == 0 else 30,
                    hr_zone_min=2,
                    hr_zone_max=2,
                    notes="Easy Z2 conversational running toward your weekly target.",
                )
            )
        # Prefer separate training days over familiar gym weekdays. Consecutive
        # gym days are allowed; pair with an easy run only after trying empty days.
        gym_days = ranked_days(start, (1, 2, 4, 0, 3, 6, 5))
        occupied_days = {s.day for s in load()}
        gym_days.sort(key=lambda day: day in occupied_days)
        for day in gym_days:
            if count(start, {Activity.GYM}) >= targets.gym:
                break
            add(
                Session(
                    day,
                    Activity.GYM,
                    duration_min=75,
                    notes="Gym session toward your weekly target; "
                    "review before confirming.",
                )
            )
    return assign_gym_targets(
        proposals, active, gym_split, start=max(week_start, not_before)
    )
