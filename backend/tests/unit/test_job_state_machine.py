"""Tests for the ingestion job state machine."""

from __future__ import annotations

from itertools import pairwise

import pytest

from rag_backend.domain.jobs import (
    ACTIVE_STATUSES,
    PIPELINE_ORDER,
    InvalidTransitionError,
    JobStatus,
    can_transition,
    is_terminal,
    next_stage,
    progress_fraction,
    validate_transition,
)


def test_happy_path_order_matches_the_plan():
    assert PIPELINE_ORDER == (
        JobStatus.QUEUED,
        JobStatus.PARSING,
        JobStatus.CHUNKING,
        JobStatus.EMBEDDING,
        JobStatus.COMMITTING,
        JobStatus.COMPLETE,
    )


def test_each_pipeline_stage_advances_to_the_next():
    for current, expected in pairwise(PIPELINE_ORDER):
        assert next_stage(current) is expected


def test_next_stage_from_complete_is_rejected():
    with pytest.raises(InvalidTransitionError):
        next_stage(JobStatus.COMPLETE)


@pytest.mark.parametrize("status", [*sorted(ACTIVE_STATUSES), JobStatus.QUEUED])
def test_any_unfinished_job_can_fail_or_cancel(status):
    assert can_transition(status, JobStatus.FAILED)
    assert can_transition(status, JobStatus.CANCELLED)


def test_skipping_a_stage_is_rejected():
    assert not can_transition(JobStatus.QUEUED, JobStatus.EMBEDDING)
    assert not can_transition(JobStatus.PARSING, JobStatus.COMMITTING)


def test_moving_backwards_is_rejected():
    assert not can_transition(JobStatus.EMBEDDING, JobStatus.PARSING)


def test_terminal_states_are_terminal():
    assert is_terminal(JobStatus.COMPLETE)
    assert is_terminal(JobStatus.FAILED)
    assert is_terminal(JobStatus.CANCELLED)
    assert not is_terminal(JobStatus.QUEUED)
    assert not is_terminal(JobStatus.EMBEDDING)


def test_failed_jobs_can_be_requeued_but_cancelled_ones_cannot():
    # Retry is for failures; a cancellation was a deliberate user action.
    assert can_transition(JobStatus.FAILED, JobStatus.QUEUED)
    assert not can_transition(JobStatus.CANCELLED, JobStatus.QUEUED)


def test_complete_is_final():
    assert not can_transition(JobStatus.COMPLETE, JobStatus.QUEUED)


def test_validate_transition_raises_with_both_states():
    with pytest.raises(InvalidTransitionError) as excinfo:
        validate_transition(JobStatus.QUEUED, JobStatus.COMPLETE)

    assert excinfo.value.current is JobStatus.QUEUED
    assert excinfo.value.target is JobStatus.COMPLETE


def test_progress_increases_monotonically_along_the_pipeline():
    values = [progress_fraction(s) for s in PIPELINE_ORDER]

    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert values == sorted(values)


def test_failed_and_cancelled_report_no_progress():
    # A stalled bar is more misleading than an empty one.
    assert progress_fraction(JobStatus.FAILED) == 0.0
    assert progress_fraction(JobStatus.CANCELLED) == 0.0
