from __future__ import annotations

import json
from pathlib import Path
import pytest
from PIL import Image

from clef_adapter import (
    ALL_CELLS,
    ClefClient,
    build_clef_request,
    parse_clef_response,
)


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def test_golden_fixtures_parsing() -> None:
    for level in (1, 2, 3):
        fixture_path = FIXTURES_DIR / f"clef-localization-level{level}.json"
        assert fixture_path.exists(), f"Missing fixture {fixture_path}"

        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = parse_clef_response(data, expected_criteria=ALL_CELLS)
        assert result.choice == "E1"
        assert result.confidence > 0.70
        assert "E1" in result.probabilities
        assert len(result.probabilities) == 25


def test_fixture_replay_clef_client() -> None:
    fixture_paths = [
        FIXTURES_DIR / "clef-localization-level1.json",
        FIXTURES_DIR / "clef-localization-level2.json",
        FIXTURES_DIR / "clef-localization-level3.json",
    ]
    client = ClefClient(mock_fixture_paths=fixture_paths)
    dummy_img = Image.new("RGB", (100, 100), (0, 0, 0))

    r1 = client.evaluate_grid(dummy_img, "Find icon")
    r2 = client.evaluate_grid(dummy_img, "Find icon")
    r3 = client.evaluate_grid(dummy_img, "Find icon")

    assert r1.choice == "E1"
    assert r2.choice == "E1"
    assert r3.choice == "E1"


def test_non_adjacent_competitor_lookup() -> None:
    data = {
        "result": {
            "answers": {
                "target_cell": {
                    "choice": "C3",
                    "probabilities": {
                        "C3": 0.50,
                        "C2": 0.30,  # adjacent (up)
                        "B3": 0.15,  # adjacent (left)
                        "A1": 0.05,  # non-adjacent
                    },
                }
            }
        }
    }
    result = parse_clef_response(data, expected_criteria=ALL_CELLS)
    assert result.top_candidate == ("C3", 0.50)
    assert result.runner_up_candidate == ("C2", 0.30)
    # The non-adjacent competitor must skip C2 and B3 and find A1
    non_adj = result.top_non_adjacent_candidate()
    assert non_adj == ("A1", 0.05)


def test_build_clef_request() -> None:
    req = build_clef_request("aW1hZ2U=", "Locate button", model="@cf/cloudflare/clef")
    assert req["model"] == "clef"
    assert "Locate button" in req["questions"]["target_cell"]["instructions"]
    assert len(req["questions"]["target_cell"]["criteria"]) == 25


def test_malformed_responses_without_network() -> None:
    # Not a dict
    with pytest.raises(ValueError, match="Invalid response payload"):
        parse_clef_response("not-a-dict")  # type: ignore[arg-type]

    # Result not a dict
    with pytest.raises(ValueError, match="Invalid 'result' field"):
        parse_clef_response({"result": "invalid"})

    # Unknown cell score
    with pytest.raises(ValueError, match="Unknown cell score"):
        parse_clef_response({
            "result": {
                "answers": {
                    "target_cell": {
                        "choice": "A1",
                        "probabilities": {"Z9": 0.9},
                    }
                }
            }
        }, expected_criteria=ALL_CELLS)

    # Non-numeric probability
    with pytest.raises(ValueError, match="Non-numeric probability"):
        parse_clef_response({
            "result": {
                "answers": {
                    "target_cell": {
                        "choice": "A1",
                        "probabilities": {"A1": "invalid-num"},
                    }
                }
            }
        }, expected_criteria=ALL_CELLS)

    # Non-finite probability (nan / inf)
    with pytest.raises(ValueError, match="Non-finite probability"):
        parse_clef_response({
            "result": {
                "answers": {
                    "target_cell": {
                        "choice": "A1",
                        "probabilities": {"A1": float("nan")},
                    }
                }
            }
        }, expected_criteria=ALL_CELLS)

    # Out of range probability
    with pytest.raises(ValueError, match="Probability out of range"):
        parse_clef_response({
            "result": {
                "answers": {
                    "target_cell": {
                        "choice": "A1",
                        "probabilities": {"A1": -0.5},
                    }
                }
            }
        }, expected_criteria=ALL_CELLS)

    # Empty choice and empty probabilities
    with pytest.raises(ValueError, match="Malformed response"):
        parse_clef_response({
            "result": {
                "answers": {
                    "target_cell": {}
                }
            }
        }, expected_criteria=ALL_CELLS)


def test_evaluate_grid_non_positive_timeout_raises_timeout_error() -> None:
    client = ClefClient(account_id="fake-account", api_token="fake-token")
    img = Image.new("RGB", (50, 50))
    with pytest.raises(TimeoutError, match="Inference timed out"):
        client.evaluate_grid(img, "find element", timeout=0)
    with pytest.raises(TimeoutError, match="Inference timed out"):
        client.evaluate_grid(img, "find element", timeout=-1.5)

