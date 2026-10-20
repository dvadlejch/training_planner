"""Validated JSON contracts kept separate from the framework-free domain."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from training_planner.domain.models import (
    Activity,
    GymSplit,
    MuscleGroup,
    Status,
    validate_muscle_groups,
)
from training_planner.domain.running import validate_zone_target


class SessionInput(BaseModel):
    """Validate sessions and unsaved proposals; blank metrics are null."""

    model_config = ConfigDict(extra="forbid")
    day: date
    activity: Activity
    status: Status = Status.PLANNED
    duration_min: int | None = Field(default=None, ge=0, le=1440)
    actual_duration_min: float | None = Field(default=None, ge=0, le=1440)
    distance_km: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    average_hr_bpm: int | None = Field(default=None, ge=1, le=300)
    elevation_gain_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    active_calories_kcal: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    effort: int | None = Field(default=None, ge=1, le=10)
    notes: str = ""
    muscle_groups: list[MuscleGroup] = Field(default_factory=list)
    hr_zone_min: int | None = Field(default=None, ge=1, le=5)
    hr_zone_max: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def validate_targets(self) -> "SessionInput":
        """Check related zone bounds and gym-only muscle selections."""
        validate_zone_target(self.hr_zone_min, self.hr_zone_max)
        validate_muscle_groups(self.activity, self.muscle_groups)
        return self


class SessionStatusInput(BaseModel):
    """Change only the saved workout status without replacing its other fields."""

    model_config = ConfigDict(extra="forbid")
    status: Status


class SessionResponse(SessionInput):
    """Serialize sessions or previews with an optional database identifier."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int | None = None


class ProposalMoveInput(BaseModel):
    """Describe an explicitly positioned, unsaved planned workout."""

    model_config = ConfigDict(extra="forbid")
    original_day: date
    session: SessionInput


class TrainingTargetsInput(BaseModel):
    """Simple weekly targets; interval runs are included in total runs."""

    model_config = ConfigDict(extra="forbid")
    gym: int = Field(default=3, ge=0, le=7, strict=True)
    runs: int = Field(default=2, ge=0, le=7, strict=True)
    intervals: int = Field(default=0, ge=0, le=2, strict=True)

    @model_validator(mode="after")
    def validate_mix(self) -> "TrainingTargetsInput":
        """Keep interval sessions within the total run count."""
        if self.intervals > self.runs:
            raise ValueError("Interval target cannot exceed total runs")
        return self


Weekday = Annotated[int, Field(strict=True, ge=0, le=6)]


class ActivityWeekdaysInput(BaseModel):
    """Recurring allowed gym/running weekdays; an empty set disables suggestions."""

    model_config = ConfigDict(extra="forbid")
    gym: frozenset[Weekday] = frozenset(range(7))
    running: frozenset[Weekday] = frozenset(range(7))


class ProposalKeyInput(BaseModel):
    """Identify one automatic suggestion without excluding other same-day events."""

    model_config = ConfigDict(extra="forbid")
    day: date
    activity: Activity


class GymSplitInput(BaseModel):
    """Configure optional accessory groups for each of the three gym sessions."""

    model_config = ConfigDict(extra="forbid")
    chest: tuple[MuscleGroup, ...] = GymSplit().chest
    back: tuple[MuscleGroup, ...] = GymSplit().back
    legs: tuple[MuscleGroup, ...] = GymSplit().legs

    @model_validator(mode="after")
    def validate_accessories(self) -> "GymSplitInput":
        """Apply the same unique accessory restriction as domain callers."""
        GymSplit(chest=self.chest, back=self.back, legs=self.legs)
        return self


class PlanningRequest(BaseModel):
    """Describe a fixed 28-day request; week_start may be any weekday."""

    model_config = ConfigDict(extra="forbid")
    week_start: date
    weeks: Literal[4] = 4
    targets: TrainingTargetsInput = Field(default_factory=TrainingTargetsInput)
    weekdays: ActivityWeekdaysInput = Field(default_factory=ActivityWeekdaysInput)
    gym_split: GymSplitInput = Field(default_factory=GymSplitInput)
    excluded: list[ProposalKeyInput] = Field(default_factory=list)
    blocked: set[date] = Field(default_factory=set)
    moves: list[ProposalMoveInput] = Field(default_factory=list)
    dismissed: set[date] = Field(default_factory=set)


class AcceptanceRequest(PlanningRequest):
    """Carry the original planning inputs and selected, unmodified proposals."""

    proposals: list[SessionInput]
    confirm: bool = False
