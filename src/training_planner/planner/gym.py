"""Assign configurable gym targets while keeping leg work away from endurance."""

from dataclasses import replace
from datetime import date

from training_planner.domain.models import (
    GYM_PRIMARY_GROUPS,
    Activity,
    GymSplit,
    MuscleGroup,
    Session,
    Status,
)
from training_planner.domain.running import leg_endurance_conflict


def _advance(order: list[MuscleGroup], groups: list[MuscleGroup]) -> None:
    """Move trained primary groups to the back, retaining any deferred leg target."""
    for group in GYM_PRIMARY_GROUPS:
        if group in groups:
            order.remove(group)
            order.append(group)


def _rotation_order(history: list[Session]) -> list[MuscleGroup]:
    """Seed from prior primary work, preserving which group has waited longest."""
    order = list(GYM_PRIMARY_GROUPS)
    if history:
        latest = [group for group in order if group in history[-1].muscle_groups][-1]
        after = order.index(latest) + 1
        order = order[after:] + order[:after]
    for session in history:
        _advance(order, session.muscle_groups)
    return order


def assign_gym_targets(
    proposals: list[Session], existing: list[Session], split: GymSplit, *, start: date
) -> list[Session]:
    """Assign muscles after dates, bringing legs forward or deferring them safely.

    Gym dates and saved targets are preserved. Primary groups wait in rotation
    order; only a trained group moves to the back. Bring legs forward when all
    slots before their turn are unsafe, or substitute upper body when legs are
    unsafe today. Identical transitions for saved work and proposals preserve
    the remaining targets when individual suggestions are confirmed in any order.
    """
    active = [s for s in existing if s.status != Status.SKIPPED]
    history = sorted(
        [
            s
            for s in active
            if s.day < start
            and s.activity == Activity.GYM
            and any(group in s.muscle_groups for group in GYM_PRIMARY_GROUPS)
        ],
        key=lambda s: (s.day, s.id or 0),
    )
    order = _rotation_order(history)
    result = [s for s in proposals if s.activity != Activity.GYM]
    timeline = sorted(
        [(s, False) for s in active if s.day >= start and s.activity == Activity.GYM]
        + [(s, True) for s in proposals if s.activity == Activity.GYM],
        key=lambda item: (item[0].day, item[0].id or 0),
    )
    endurance = active + result

    def legs_allowed(day: date) -> bool:
        legs = Session(day, Activity.GYM, muscle_groups=[MuscleGroup.LEGS])
        return not any(leg_endurance_conflict(legs, s) for s in endurance)

    for index, (session, proposed) in enumerate(timeline):
        if proposed:
            can_train_legs = legs_allowed(session.day)
            primary = next(
                group for group in order if group != MuscleGroup.LEGS or can_train_legs
            )
            # The next rotation turn may land beside an outing. Use the last
            # safe slot now so a three-session week can still include leg work.
            legs_turn = order.index(MuscleGroup.LEGS)
            upcoming = timeline[index + 1 : index + 1 + legs_turn]
            if (
                can_train_legs
                and legs_turn
                and len(upcoming) == legs_turn
                and all(
                    not legs_allowed(next_session.day) for next_session, _ in upcoming
                )
            ):
                primary = MuscleGroup.LEGS
            session = replace(session, muscle_groups=split.groups_for(primary))
            result.append(session)
        _advance(order, session.muscle_groups)
    return sorted(result, key=lambda s: (s.day, s.activity.value))
