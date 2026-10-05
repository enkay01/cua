from __future__ import annotations

from pathlib import Path
from PIL import Image

from clef_adapter import ClefChoiceResult, ClefClient
from localizer import ClefGridLocalizer


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def test_golden_fixtures_parse() -> None:
    f1 = FIXTURES_DIR / "clef-localization-level1.json"
    f2 = FIXTURES_DIR / "clef-localization-level2.json"
    f3 = FIXTURES_DIR / "clef-localization-level3.json"

    client = ClefClient(mock_fixture_paths=[f1, f2, f3])
    dummy_img = Image.new("RGB", (100, 100))

    r1 = client.evaluate_grid(dummy_img, "test")
    assert r1.choice == "E1"
    assert round(r1.confidence, 3) == 0.955
    assert len(r1.probabilities) == 25

    r2 = client.evaluate_grid(dummy_img, "test")
    assert r2.choice == "E1"
    assert round(r2.confidence, 3) == 0.937

    r3 = client.evaluate_grid(dummy_img, "test")
    assert r3.choice == "E1"
    assert round(r3.confidence, 3) == 0.919


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
    result = localizer.localize(test_image, "monitor icon in the menu bar")

    assert result.success is True
    assert result.status == "success"
    assert len(result.iterations) == 3

    # Level 1
    it1 = result.iterations[0]
    assert it1.level == 1
    assert it1.winning_cell == "E1"
    assert it1.crop_box.as_tuple() == (0, 0, 1290, 803)

    # Level 2 (centered on E1 of Level 1 with clamping)
    it2 = result.iterations[1]
    assert it2.level == 2
    assert it2.winning_cell == "E1"
    assert it2.crop_box.width == 387
    assert it2.crop_box.height == 240
    # Clamped to right edge 1290 and top edge 0
    assert it2.crop_box.right == 1290
    assert it2.crop_box.top == 0

    # Level 3 (centered on E1 of Level 2 with clamping)
    it3 = result.iterations[2]
    assert it3.level == 3
    assert it3.winning_cell == "E1"
    assert it3.crop_box.width == 115
    assert it3.crop_box.height == 71
    assert it3.crop_box.right == 1290
    assert it3.crop_box.top == 0

    # Winning click coordinate in Level 3 cell E1
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


def test_abstain_on_ambiguous_non_adjacent_cells() -> None:
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
    assert "Ambiguous top cells" in (result.reason or "")


def test_allow_close_scores_when_adjacent() -> None:
    # B2 and C2 are adjacent; close scores should NOT trigger ambiguity abort
    def adjacent_handler(img: Image.Image, prompt: str) -> ClefChoiceResult:
        return ClefChoiceResult(
            choice="B2",
            confidence=0.42,
            probabilities={"B2": 0.42, "C2": 0.40},
            model="mock",
            raw_response={},
        )

    client = ClefClient(mock_handler=adjacent_handler)
    localizer = ClefGridLocalizer(client, num_levels=1, ambiguity_margin=0.05)
    result = localizer.localize(Image.new("RGB", (500, 500)), "boundary straddling icon")

    assert result.success is True
    assert result.status == "success"
