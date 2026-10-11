"""Transparent default planning rules; keep suggestions distinct from confirmed sessions."""

from datetime import date, timedelta

from training_planner.domain.models import Activity, Session


def suggest_week(
    week_start: date,
    existing: list[Session],
    blocked: set[date] | None = None,
    *,
    not_before: date,
) -> list[Session]:
    """Suggest unoccupied days in one Monday-to-Sunday week.

    The starter policy uses fixed gym weekdays, a Monday easy run, and weekend
    endurance. It does not infer fatigue or account for daypart availability.

    Parameters
    ----------
    week_start : date
        Monday starting the requested week.
    existing : list[Session]
        Saved workouts whose dates must remain occupied.
    blocked : set[date] or None
        Additional dates unavailable for suggestions.
    not_before : date
        Earliest eligible date, inclusive. Supplied explicitly to keep rules deterministic.


    Returns
    -------
    list[Session]
        Unsaved suggestions ordered by date, possibly empty.

    Raises
    ------
    ValueError
        If week_start is not a Monday.
    """
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    blocked = blocked or set()
    occupied = {s.day for s in existing} | blocked
    proposals: list[Session] = []

    def add(offset: int, activity: Activity, minutes: int | None = None) -> None:
        day = week_start + timedelta(days=offset)
        if day >= not_before and day not in occupied:
            proposals.append(
                Session(
                    day=day,
                    activity=activity,
                    duration_min=minutes,
                    notes="Suggested — review before confirming",
                )
            )
            occupied.add(day)

    for offset in (1, 2, 4):
        add(offset, Activity.GYM, 75)
    add(0, Activity.EASY_RUN, 30)
    # Quality running is introduced later, after consistent easy running.
    add(5, Activity.HIKE, 180)
    # Skip automatic Sunday running when Saturday is marked high effort.
    saturday = week_start + timedelta(days=5)
    hard_saturday = any(s.day == saturday and (s.effort or 0) >= 7 for s in existing)
    if not hard_saturday:
        add(6, Activity.LONG_RUN, 45)
    return sorted(proposals, key=lambda s: s.day)
