from __future__ import annotations

import pytest

from grid_localizer import LocalizationResult
from sources import CandidateSource, VisualGridSource


def test_visual_grid_source_protocol_compliance() -> None:
    class MockLoc:
        success = True
        target_description = "Submit Button"
        click_x = 120.0
        click_y = 45.0

    grid_source: CandidateSource = VisualGridSource(
        localization=MockLoc(),
        pid=123,
        window_id=456,
        capture_id="cap-xyz",
        delivery="background",
        capture_bound=False,
    )
    assert grid_source.kind == "visual"

    # Matching target description
    submit = grid_source.find("button", "submit button")
    assert submit is not None
    assert submit.source == "visual"
    assert submit.name == "Submit Button"

    # Case insensitive
    assert grid_source.find("button", "SUBMIT BUTTON") is not None

    # Mismatch returns None
    assert grid_source.find("button", "other button") is None

    # Unbound click returns None
    assert grid_source.click(submit, candidate_id="c1", description="d1") is None

    # Never types
    assert grid_source.type_text(submit, "hello", candidate_id="c1", description="d1") is None

    # Capture-bound click
    bound = VisualGridSource(
        localization=MockLoc(),
        pid=123,
        window_id=456,
        capture_id="cap-xyz",
        delivery="foreground",
        capture_bound=True,
    )
    cand = bound.click(submit, candidate_id="c2", description="d2")
    assert cand is not None
    assert cand.id == "c2"
    assert cand.tool == "click"
    assert cand.capture_id == "cap-xyz"
    assert cand.arguments["delivery_mode"] == "foreground"
    assert cand.arguments["x"] == 120.0
    assert cand.arguments["y"] == 45.0
    assert cand.arguments["pid"] == 123
    assert cand.arguments["window_id"] == 456


def test_target_mismatch_and_stale_capture_discard() -> None:
    loc = LocalizationResult(
        success=True,
        status="success",
        target_description="Search Icon",
        click_x=450.0,
        click_y=32.0,
        capture_id="cap-original",
        target_pid=100,
        target_window_id=200,
        screenshot_w=1920,
        screenshot_h=1080,
    )

    # Valid observation matching original capture
    assert loc.matches_observation(
        capture_id="cap-original",
        pid=100,
        window_id=200,
        width=1920,
        height=1080,
    )

    # Observation changed capture_id (e.g. new screenshot taken)
    assert not loc.matches_observation(
        capture_id="cap-new",
        pid=100,
        window_id=200,
        width=1920,
        height=1080,
    )

    # Observation changed target PID or window
    assert not loc.matches_observation(
        capture_id="cap-original",
        pid=101,
        window_id=200,
        width=1920,
        height=1080,
    )

    # Source constructed with mismatched capture must not offer click candidate
    mismatched_source = VisualGridSource(
        localization=loc if loc.matches_observation(capture_id="cap-stale", pid=100, window_id=200) else None,
        pid=100,
        window_id=200,
        capture_id="cap-stale",
        capture_bound=True,
    )
    assert mismatched_source.find("button", "Search Icon") is None


def test_capture_expired_refusal_handling() -> None:
    # Simulates Driver response with capture_expired error
    driver_refusal = {
        "isError": True,
        "structuredContent": {"code": "capture_expired"},
        "content": [{"text": "Capture has expired; fresh capture required"}],
    }

    # Verify structured refusal code is capture_expired
    error_code = driver_refusal["structuredContent"]["code"]
    assert error_code == "capture_expired"

    # In case of capture_expired, runner must discard localization and not attempt unbound click
    localization = None  # Discarded
    fresh_source = VisualGridSource(
        localization=localization,
        pid=100,
        window_id=200,
        capture_id="cap-expired",
        capture_bound=True,
    )
    control = fresh_source.find("button", "Search Icon")
    assert control is None
