"""Core domain types shared by the application, planner, and storage layer."""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Activity(str, Enum):
    """Represent the workout categories supported by the starter planner."""

    GYM = "gym"
    EASY_RUN = "easy_run"
    RECOVERY_RUN = "recovery_run"
    TEMPO_RUN = "tempo_run"
    INTERVAL_RUN = "interval_run"
    HARD_ENDURANCE_RUN = "hard_endurance_run"
    RACE = "race"
    LONG_RUN = "long_run"
    HIKE = "hike"
    CYCLE = "cycle"
    REST = "rest"


class Status(str, Enum):
    """Represent a saved workout's planning or completion status."""

    PLANNED = "planned"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class Session:
    """Container representing a workout or an unsaved workout suggestion.

    day
        Calendar date of the workout.
    activity
        Workout category.
    status
        Planned, confirmed (committed but upcoming), completed, or skipped status.
    duration_min
        Optional duration in minutes; None means unknown.
    effort
        Optional RPE from 1 to 10; None means unknown.
    notes
        User notes or the starter suggestion explanation.
    id
        Database identifier; None indicates an unsaved session.
    """

    day: date
    activity: Activity
    status: Status = Status.PLANNED
    duration_min: int | None = None
    effort: int | None = None
    notes: str = ""
    id: int | None = None
    # Planned main-set targets in the five-zone model, not measured average HR.
    hr_zone_min: int | None = None
    hr_zone_max: int | None = None
