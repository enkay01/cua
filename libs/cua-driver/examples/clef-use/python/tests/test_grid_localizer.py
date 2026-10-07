from __future__ import annotations

import time
from pathlib import Path
import pytest
from PIL import Image

from clef_adapter import ClefChoiceResult, ClefClient
from grid_localizer import ClefGridLocalizer


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def test_three_level_hierarchical_zoom_success() -> None:
    f1 = FIXTURES_DIR / "clef-localization-level1.json"
    f2 = FIXTURES_DIR / "clef-localization-level2.json"
    f3 = FIXTURES_DIR / "clef-localization-level3.json"

    client = ClefClient(mock_fixture_paths=[f1, f2, f3])
    localizer = ClefGridLocalizer(
        client,
        num_levels=3,
        custom_crop_sizes=[(1290, 803), (387, 240), (115, 71)],
    )

    test_image = Image.new("RGB", (1290, 803), color=(40, 40, 40))
    result = localizer.localize(
        test_image,
        "monitor icon in the menu bar",
        capture_id="cap-123",
        pid=42,
        window_id=1,
    )

    assert result.success is True
    assert result.status == "success"
    assert len(result.iterations) == 3
    assert result.capture_id == "cap-123"
    assert result.target_pid == 42
    assert result.target_window_id == 1
    assert result.screenshot_w == 1290
    assert result.screenshot_h == 803

    # Level 1
    it1 = result.iterations[0]
    assert it1.level == 1
    assert it1.winning_cell == "E1"
    assert it1.crop_box.as_tuple() == (0, 0, 1290, 803)

    # Level 2
    it2 = result.iterations[1]
    assert it2.level == 2
    assert it2.winning_cell == "E1"
    assert it2.crop_box.width == 387
    assert it2.crop_box.height == 240
    assert it2.crop_box.right == 1290
    assert it2.crop_box.top == 0

    # Level 3
    it3 = result.iterations[2]
    assert it3.level == 3
    assert it3.winning_cell == "E1"
    assert it3.crop_box.width == 115
    assert it3.crop_box.height == 71
    assert it3.crop_box.right == 1290
    assert it3.crop_box.top == 0

    assert result.click_x is not None
    assert result.click_y is not None
    assert 1200 <= result.click_x <= 1290
    assert 0 <= result.click_y <= 50


def test_abstain_on_low_confidence() -> None:
    def low_conf_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        return ClefChoiceResult(
            choice="C3",
            confidence=0.15,
            probabilities={"C3": 0.15, "A1": 0.05},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=low_conf_handler)
    localizer = ClefGridLocalizer(client, min_confidence=0.30)
    result = localizer.localize(Image.new("RGB", (500, 500)), "nonexistent button")

    assert result.success is False
    assert result.status == "abstained_low_confidence"
    assert result.click_x is None
    assert "below floor" in (result.reason or "")


def test_abstain_on_direct_non_adjacent_ambiguity() -> None:
    # A1 (top-left) and E5 (bottom-right) score nearly identically
    def ambiguous_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        return ClefChoiceResult(
            choice="A1",
            confidence=0.42,
            probabilities={"A1": 0.42, "E5": 0.40},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=ambiguous_handler)
    localizer = ClefGridLocalizer(client, ambiguity_margin=0.05)
    result = localizer.localize(Image.new("RGB", (500, 500)), "ambiguous icon")

    assert result.success is False
    assert result.status == "abstained_ambiguous"
    assert "Ambiguous candidates" in (result.reason or "")


def test_allow_close_scores_when_adjacent_and_non_adjacent_is_far() -> None:
    # B2 and C2 are adjacent; non-adjacent (E5) is far behind (0.10)
    def adjacent_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        return ClefChoiceResult(
            choice="B2",
            confidence=0.42,
            probabilities={"B2": 0.42, "C2": 0.40, "E5": 0.10},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=adjacent_handler)
    localizer = ClefGridLocalizer(client, num_levels=1, ambiguity_margin=0.05)
    result = localizer.localize(Image.new("RGB", (500, 500)), "straddling icon")

    assert result.success is True
    assert result.status == "success"


def test_abstain_when_adjacent_runner_up_has_close_third_place() -> None:
    # Winner: B2 (0.42)
    # Adjacent runner-up: C2 (0.40) - adjacent, tolerated
    # Third-place competitor: E5 (0.39) - non-adjacent! Lead is 0.42 - 0.39 = 0.03 < margin 0.05
    def third_place_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        return ClefChoiceResult(
            choice="B2",
            confidence=0.42,
            probabilities={"B2": 0.42, "C2": 0.40, "E5": 0.39},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=third_place_handler)
    localizer = ClefGridLocalizer(client, num_levels=1, ambiguity_margin=0.05)
    result = localizer.localize(Image.new("RGB", (500, 500)), "bimodal icon with straddle")

    assert result.success is False
    assert result.status == "abstained_ambiguous"
    assert "Ambiguous candidates" in (result.reason or "")
    assert "E5" in (result.reason or "")


def test_timeout_deadline_exceeded() -> None:
    def slow_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        time.sleep(0.05)
        return ClefChoiceResult(
            choice="C3",
            confidence=0.80,
            probabilities={"C3": 0.80},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=slow_handler)
    # Deadline 0.02s will expire before level 2
    localizer = ClefGridLocalizer(client, num_levels=3, deadline_seconds=0.02)
    result = localizer.localize(Image.new("RGB", (500, 500)), "slow target")

    assert result.success is False
    assert result.status == "abstained_timeout"
    assert "deadline" in (result.reason or "")


def test_timeout_deadline_zero_returns_abstained_timeout() -> None:
    call_count = 0

    def dummy_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        nonlocal call_count
        call_count += 1
        return ClefChoiceResult(
            choice="C3",
            confidence=0.80,
            probabilities={"C3": 0.80},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=dummy_handler)
    localizer = ClefGridLocalizer(client, num_levels=1, deadline_seconds=0.0)
    result = localizer.localize(Image.new("RGB", (100, 100)), "target")

    assert result.success is False
    assert result.status == "abstained_timeout"
    assert call_count == 0


def test_remaining_time_clamped_to_positive_value() -> None:
    observed_timeout: float | None = None

    class MockClient(ClefClient):
        def evaluate_grid(self, image: Image.Image, instructions: str, *, criteria=None, timeout=None):
            nonlocal observed_timeout
            observed_timeout = timeout
            return ClefChoiceResult(
                choice="C3",
                confidence=0.80,
                probabilities={"C3": 0.80},
                model="mock",
                raw_response={},
            )

    client = MockClient()
    localizer = ClefGridLocalizer(client, num_levels=1, deadline_seconds=5.0)
    result = localizer.localize(Image.new("RGB", (100, 100)), "target")

    assert result.success is True
    assert observed_timeout is not None
    assert observed_timeout > 0



def test_capture_and_target_binding_and_mismatch() -> None:
    f1 = FIXTURES_DIR / "clef-localization-level1.json"
    client = ClefClient(mock_fixture_paths=[f1])
    localizer = ClefGridLocalizer(client, num_levels=1)

    test_image = Image.new("RGB", (800, 600), (0, 0, 0))
    result = localizer.localize(
        test_image,
        "test button",
        capture_id="capture-abc",
        pid=1001,
        window_id=2002,
    )

    assert result.success is True
    assert result.capture_id == "capture-abc"
    assert result.target_pid == 1001
    assert result.target_window_id == 2002
    assert result.screenshot_w == 800
    assert result.screenshot_h == 600

    # Matching observation
    assert result.matches_observation(
        capture_id="capture-abc",
        pid=1001,
        window_id=2002,
        width=800,
        height=600,
    )

    # Capture mismatch
    assert not result.matches_observation(
        capture_id="capture-different",
        pid=1001,
        window_id=2002,
        width=800,
        height=600,
    )

    # PID mismatch
    assert not result.matches_observation(
        capture_id="capture-abc",
        pid=9999,
        window_id=2002,
        width=800,
        height=600,
    )

    # Window ID mismatch
    assert not result.matches_observation(
        capture_id="capture-abc",
        pid=1001,
        window_id=9999,
        width=800,
        height=600,
    )

    # Dimensions mismatch
    assert not result.matches_observation(
        capture_id="capture-abc",
        pid=1001,
        window_id=2002,
        width=1024,
        height=768,
    )


def test_oversized_crop_rejection() -> None:
    client = ClefClient(mock_handler=lambda img, p: ClefChoiceResult(
        choice="C3",
        confidence=0.8,
        probabilities={"C3": 0.8},
        model="mock",
        raw_response={},
    ))
    # Image is 200x200, but level 2 configured crop is 500x500
    localizer = ClefGridLocalizer(
        client,
        num_levels=2,
        custom_crop_sizes=[(200, 200), (500, 500)],
    )

    with pytest.raises(ValueError, match="exceeds screenshot dimensions"):
        localizer.localize(Image.new("RGB", (200, 200)), "test")
