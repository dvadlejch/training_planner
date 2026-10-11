"""Validated JSON contracts kept separate from the framework-free domain."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from training_planner.domain.models import Activity, Status


class SessionInput(BaseModel):
    """Validate manually entered sessions and unsaved proposals; blank metrics are null."""

    model_config = ConfigDict(extra="forbid")
    day: date
    activity: Activity
    status: Status = Status.PLANNED
    duration_min: int | None = Field(default=None, ge=0, le=1440)
    effort: int | None = Field(default=None, ge=1, le=10)
    notes: str = ""


class SessionResponse(SessionInput):
    """Serialize saved sessions or previews, including an optional database identifier."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int | None = None


class PlanningRequest(BaseModel):
    """Describe a single-week request with optional whole-day unavailability."""

    model_config = ConfigDict(extra="forbid")
    week_start: date
    blocked: set[date] = Field(default_factory=set)


class AcceptanceRequest(PlanningRequest):
    """Carry the original planning inputs and selected, unmodified proposals."""

    proposals: list[SessionInput]
