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
        Optional planned duration in minutes; None means unknown.
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
