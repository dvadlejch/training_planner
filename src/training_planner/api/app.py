"""FastAPI entry point; start with uvicorn training_planner.api.app:app --reload."""

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from training_planner.api.schemas import (
    AcceptanceRequest,
    PlanningRequest,
    SessionInput,
    SessionResponse,
)
from training_planner.application.services import (
    ProposalConflict,
    accept_proposals,
    create_session,
    generate_proposals,
    get_sessions,
)
from training_planner.domain.models import Session
from training_planner.storage.db import DEFAULT_DB


def create_app(database_path: Path | None = None) -> FastAPI:
    """Construct the HTTP application without opening or modifying the database.

    Parameters
    ----------
    database_path : Path or None
        Database override for tests or embedding. Otherwise TRAINING_PLANNER_DB
        is used, falling back to data/training.db relative to the launch directory.

    Returns
    -------
    FastAPI
        Application exposing session and proposal endpoints under /api.
    """
    path = (
        database_path
        if database_path is not None
        else Path(os.environ.get("TRAINING_PLANNER_DB", str(DEFAULT_DB)))
    )
    application = FastAPI(title="Adaptive Training Planner", version="0.1.0")

    @application.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Translate application validation failures into client-facing responses.

        Parameters
        ----------
        request : Request
            Request that triggered the failure.
        exc : ValueError
            Domain validation failure or proposal conflict.

        Returns
        -------
        JSONResponse
            Conflict response (409), or invalid-input response (422).
        """
        return JSONResponse(
            status_code=409 if isinstance(exc, ProposalConflict) else 422,
            content={"detail": str(exc)},
        )

    @application.get("/api/health")
    def health() -> dict[str, str]:
        """Report whether the API process is running.

        Returns
        -------
        dict[str, str]
            Process health status; no database operation is performed.
        """
        return {"status": "ok"}

    @application.get("/api/sessions", response_model=list[SessionResponse])
    def read_sessions(start: date, end: date) -> list[Session]:
        """Read an inclusive range of saved workouts.

        Parameters
        ----------
        start : date
            First included date.
        end : date
            Last included date.

        Returns
        -------
        list[Session]
            Saved workouts ordered by date and identifier.

        Raises
        ------
        ValueError
            If the date range or stored session values are invalid.
        OSError
            If the database directory cannot be created.
        sqlite3.Error
            If the database operation fails.
        """
        return get_sessions(path, start, end)

    @application.post("/api/sessions", response_model=SessionResponse, status_code=201)
    def add_session(payload: SessionInput) -> Session:
        """Create a session from validated input without changing the existing calendar.

        Parameters
        ----------
        payload : SessionInput
            Workout details with optional metrics.

        Returns
        -------
        Session
            Committed workout with its generated identifier.

        Raises
        ------
        ValueError
            If session metrics are invalid.
        OSError
            If the database directory cannot be created.
        sqlite3.Error
            If the database operation fails.
        """
        return create_session(path, Session(**payload.model_dump()))

    @application.post("/api/proposals", response_model=list[SessionResponse])
    def propose(payload: PlanningRequest) -> list[Session]:
        """Generate unsaved suggestions for explicit user review.

        Parameters
        ----------
        payload : PlanningRequest
            Monday week start and whole-day restrictions.

        Returns
        -------
        list[Session]
            Unsaved suggestions, possibly empty.

        Raises
        ------
        ValueError
            If the week start or stored session values are invalid.
        OSError
            If the database directory cannot be created.
        sqlite3.Error
            If the database operation fails.
        """
        return generate_proposals(path, payload.week_start, payload.blocked)

    @application.post(
        "/api/proposals/accept", response_model=list[SessionResponse], status_code=201
    )
    def accept(payload: AcceptanceRequest) -> list[Session]:
        """Commit selected proposals after checking the current calendar.

        Parameters
        ----------
        payload : AcceptanceRequest
            Planning inputs and selected, unmodified suggestions.

        Returns
        -------
        list[Session]
            Committed sessions with identifiers.

        Raises
        ------
        ProposalConflict
            If selected suggestions are duplicated, altered, or no longer available.
        ValueError
            If the week start or stored session values are invalid.
        OSError
            If the database directory cannot be created.
        sqlite3.Error
            If the database operation fails; no selected proposal is committed.
        """
        return accept_proposals(
            path,
            payload.week_start,
            payload.blocked,
            [Session(**proposal.model_dump()) for proposal in payload.proposals],
        )

    return application


app = create_app()
