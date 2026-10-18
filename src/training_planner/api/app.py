"""FastAPI entry point; start with uvicorn training_planner.api.app:app --reload."""

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from training_planner.api.schemas import (
    AcceptanceRequest,
    PlanningRequest,
    SessionInput,
    SessionResponse,
    SessionStatusInput,
)
from training_planner.application.services import (
    ProposalConflict,
    accept_proposals,
    change_session_status,
    create_session,
    generate_proposals,
    get_sessions,
    remove_session,
    update_session,
)
from training_planner.domain.models import (
    ActivityWeekdays,
    ProposalMove,
    Session,
    TrainingTargets,
)
from training_planner.storage.db import DEFAULT_DB


def create_app(
    database_path: Path | None = None, frontend_path: Path | None = None
) -> FastAPI:
    """Construct the HTTP application without opening or modifying the database.

    Parameters
    ----------
    database_path : Path or None
        Database override for tests or embedding. Otherwise TRAINING_PLANNER_DB
        is used, falling back to data/training.db relative to the launch directory.
    frontend_path : Path or None
        Optional built frontend directory, mounted after the API routes.

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

    @application.put("/api/sessions/{session_id}", response_model=SessionResponse)
    def edit_session(session_id: int, payload: SessionInput) -> Session:
        """Replace a saved workout with validated input, or return 404 if missing."""
        try:
            return update_session(path, session_id, Session(**payload.model_dump()))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.patch(
        "/api/sessions/{session_id}/status", response_model=SessionResponse
    )
    def update_status(session_id: int, payload: SessionStatusInput) -> Session:
        """Change a saved workout's status without overwriting its other details."""
        try:
            return change_session_status(path, session_id, payload.status)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.delete("/api/sessions/{session_id}", status_code=204)
    def delete_saved_session(session_id: int) -> Response:
        """Delete a saved workout, returning 404 if the identifier does not exist."""
        try:
            remove_session(path, session_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    @application.post("/api/proposals", response_model=list[SessionResponse])
    def propose(payload: PlanningRequest) -> list[Session]:
        """Generate unsaved suggestions for explicit user review.

        Parameters
        ----------
        payload : PlanningRequest
            Inclusive horizon start date and whole-day restrictions.

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
        return generate_proposals(
            path,
            payload.week_start,
            payload.blocked,
            payload.weeks,
            [
                ProposalMove(move.original_day, Session(**move.session.model_dump()))
                for move in payload.moves
            ],
            payload.dismissed,
            targets=TrainingTargets(**payload.targets.model_dump()),
            weekdays=ActivityWeekdays(**payload.weekdays.model_dump()),
            excluded={(item.day, item.activity) for item in payload.excluded},
        )

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
            payload.weeks,
            [
                ProposalMove(move.original_day, Session(**move.session.model_dump()))
                for move in payload.moves
            ],
            payload.dismissed,
            confirm=payload.confirm,
            targets=TrainingTargets(**payload.targets.model_dump()),
            weekdays=ActivityWeekdays(**payload.weekdays.model_dump()),
            excluded={(item.day, item.activity) for item in payload.excluded},
        )

    if frontend_path is not None:
        application.mount("/", StaticFiles(directory=frontend_path, html=True))

    return application


app = create_app()
