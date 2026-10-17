"""Validated JSON contracts kept separate from the framework-free domain."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from training_planner.domain.models import Activity, Status
from training_planner.domain.running import validate_zone_target


class SessionInput(BaseModel):
    """Validate sessions and unsaved proposals; blank metrics are null."""

    model_config = ConfigDict(extra="forbid")
    day: date
    activity: Activity
    status: Status = Status.PLANNED
    duration_min: int | None = Field(default=None, ge=0, le=1440)
    effort: int | None = Field(default=None, ge=1, le=10)
    notes: str = ""
    hr_zone_min: int | None = Field(default=None, ge=1, le=5)
    hr_zone_max: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def validate_zones(self):
        validate_zone_target(self.hr_zone_min, self.hr_zone_max)
        return self


class SessionStatusInput(BaseModel):
    """Change only the saved workout status without replacing its other fields."""

    model_config = ConfigDict(extra="forbid")
    status: Status


class SessionResponse(SessionInput):
    """Serialize sessions or previews with an optional database identifier."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int | None = None


class PlanningRequest(BaseModel):
    """Describe a one-to-four-week request with optional whole-day unavailability."""

    model_config = ConfigDict(extra="forbid")
    week_start: date
    weeks: int = Field(default=1, ge=1, le=4)
    blocked: set[date] = Field(default_factory=set)


class AcceptanceRequest(PlanningRequest):
    """Carry the original planning inputs and selected, unmodified proposals."""

    proposals: list[SessionInput]
