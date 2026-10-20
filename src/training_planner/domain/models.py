"""Core domain types shared by the application, planner, and storage layer."""

from dataclasses import dataclass, field
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


class MuscleGroup(str, Enum):
    """Optional muscle targets for a gym workout."""

    CHEST = "chest"
    LEGS = "legs"
    BACK = "back"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    SHOULDERS = "shoulders"
    ABS = "abs"


def validate_muscle_groups(activity: Activity, groups: list[MuscleGroup]) -> None:
    """Keep gym targets unique and prevent targets on other activity types."""
    if groups and activity != Activity.GYM:
        raise ValueError("Muscle groups can only be selected for gym sessions")
    if any(not isinstance(group, MuscleGroup) for group in groups):
        raise ValueError("Unknown muscle group")
    if len(groups) != len(set(groups)):
        raise ValueError("Muscle groups must be unique")


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
        Optional planned duration in minutes; None means unknown.
    effort
        Optional RPE from 1 to 10; None means unknown.
    notes
        User notes or the starter suggestion explanation.
    muscle_groups
        Optional gym muscle targets; empty means unspecified.
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
    muscle_groups: list[MuscleGroup] = field(default_factory=list)
    # Planned main-set targets in the five-zone model, not measured average HR.
    hr_zone_min: int | None = None
    hr_zone_max: int | None = None
    # Recorded results remain independent of training targets.
    actual_duration_min: float | None = None
    distance_km: float | None = None
    average_hr_bpm: int | None = None
    elevation_gain_m: float | None = None
    active_calories_kcal: float | None = None


@dataclass
class ProposalMove:
    """Keep a user-positioned draft and exclude its original suggestion date."""

    original_day: date
    session: Session


@dataclass(frozen=True)
class TrainingTargets:
    """Soft session counts per rolling seven-day period, including saved work."""

    gym: int = 3
    runs: int = 2
    intervals: int = 0

    def __post_init__(self) -> None:
        """Reject unsupported counts and intervals outside the total run target."""
        if any(
            type(value) is not int for value in (self.gym, self.runs, self.intervals)
        ):
            raise ValueError("Training targets must be whole-number counts")
        if not 0 <= self.gym <= 7 or not 0 <= self.runs <= 7:
            raise ValueError("Gym and running targets must be between 0 and 7")
        if not 0 <= self.intervals <= min(2, self.runs):
            raise ValueError("Intervals must be between 0 and 2 and within total runs")


@dataclass(frozen=True)
class ActivityWeekdays:
    """Allowed weekdays for new gym/running suggestions; Monday is zero."""

    gym: frozenset[int] = frozenset(range(7))
    running: frozenset[int] = frozenset(range(7))

    def __post_init__(self) -> None:
        """Reject weekday values outside the Monday-zero, Sunday-six convention."""
        for days in (self.gym, self.running):
            if not isinstance(days, frozenset) or any(
                type(day) is not int or not 0 <= day <= 6 for day in days
            ):
                raise ValueError("Allowed weekdays must be a frozenset of integers 0-6")

    def allows(self, day: date, activity: Activity) -> bool:
        """Apply recurring restrictions to gym and every running workout category."""
        if activity == Activity.GYM:
            return day.weekday() in self.gym
        if activity.value.endswith("_run") or activity == Activity.RACE:
            return day.weekday() in self.running
        return True
