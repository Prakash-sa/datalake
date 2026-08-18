"""Ingestion job state machine.

Implements the lifecycle the production plan specifies:

    queued -> parsing -> chunking -> embedding -> committing -> complete
                                              \\-> failed / cancelled

Transitions are validated here, as pure logic with no I/O, so illegal moves are
rejected before anything touches the database.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Every state an ingestion job can occupy."""

    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMMITTING = "committing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: States from which no further transition is possible.
TERMINAL_STATUSES = frozenset({JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED})

#: States in which work is actively in progress.
ACTIVE_STATUSES = frozenset(
    {
        JobStatus.PARSING,
        JobStatus.CHUNKING,
        JobStatus.EMBEDDING,
        JobStatus.COMMITTING,
    }
)

#: The happy path, in order.
PIPELINE_ORDER: tuple[JobStatus, ...] = (
    JobStatus.QUEUED,
    JobStatus.PARSING,
    JobStatus.CHUNKING,
    JobStatus.EMBEDDING,
    JobStatus.COMMITTING,
    JobStatus.COMPLETE,
)

# Any non-terminal state may fail or be cancelled; forward progress otherwise
# follows PIPELINE_ORDER exactly.
_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.PARSING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.PARSING: frozenset({JobStatus.CHUNKING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.CHUNKING: frozenset({JobStatus.EMBEDDING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.EMBEDDING: frozenset({JobStatus.COMMITTING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.COMMITTING: frozenset({JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.COMPLETE: frozenset(),
    # A failed job is retried by returning it to the queue; a cancelled one is
    # not resumed, matching "resumable retry" for failures only.
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.CANCELLED: frozenset(),
}


class InvalidTransitionError(ValueError):
    """Raised when a job is moved between incompatible states."""

    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        super().__init__(f"Cannot move job from {current} to {target}")
        self.current = current
        self.target = target


def is_terminal(status: JobStatus) -> bool:
    """Whether a job in this state has finished for good."""
    return status in TERMINAL_STATUSES


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    """Whether moving from ``current`` to ``target`` is legal."""
    return target in _ALLOWED[current]


def validate_transition(current: JobStatus, target: JobStatus) -> None:
    """Raise :class:`InvalidTransitionError` unless the move is legal."""
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)


def next_stage(current: JobStatus) -> JobStatus:
    """The next state on the happy path.

    Raises :class:`InvalidTransitionError` for terminal states, which have no next.
    """
    if current not in PIPELINE_ORDER or current is JobStatus.COMPLETE:
        raise InvalidTransitionError(current, JobStatus.COMPLETE)
    return PIPELINE_ORDER[PIPELINE_ORDER.index(current) + 1]


def progress_fraction(status: JobStatus) -> float:
    """Rough completion fraction, for progress display.

    Failed and cancelled jobs report 0.0 rather than a partial value, since a
    stalled bar is more misleading than an empty one.
    """
    if status is JobStatus.COMPLETE:
        return 1.0
    if status in {JobStatus.FAILED, JobStatus.CANCELLED}:
        return 0.0
    return PIPELINE_ORDER.index(status) / (len(PIPELINE_ORDER) - 1)
