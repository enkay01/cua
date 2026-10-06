from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from server import locate_visual_target


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"
GOLDEN_FIXTURES = [
    str(FIXTURES_DIR / "clef-localization-level1.json"),
    str(FIXTURES_DIR / "clef-localization-level2.json"),
    str(FIXTURES_DIR / "clef-localization-level3.json"),
]


def _write_image(path: Path, size: tuple[int, int] = (1290, 803)) -> str:
    Image.new("RGB", size, color=(40, 40, 40)).save(path)
    return str(path)


def test_successful_fixture_localization(tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "screenshot.png")
    result = locate_visual_target(
        image_path,
        "monitor icon in the menu bar",
        capture_id="cap-123",
        pid=42,
        window_id=1,
        mock_fixture_paths=GOLDEN_FIXTURES,
    )

    assert result["success"] is True
    assert result["status"] == "success"
    assert result["click_x"] is not None
    assert result["click_y"] is not None
    assert 1200 <= result["click_x"] <= 1290
    assert 0 <= result["click_y"] <= 50
    assert result["confidence"] is not None and result["confidence"] > 0.70
    assert result["winning_cell"] == "E1"
    assert result["capture_id"] == "cap-123"
    assert result["pid"] == 42
    assert result["window_id"] == 1


def test_unconfigured_credentials_refusal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLEF_MOCK_FIXTURES", raising=False)
    # Isolate from any repo .env.local: load_env_files() walks up from cwd.
    monkeypatch.chdir(tmp_path)

    image_path = _write_image(tmp_path / "screenshot.png", size=(800, 600))
    result = locate_visual_target(image_path, "Terminal close button")

    assert result["success"] is False
    assert result["status"] == "unconfigured_credentials"
    assert result["click_x"] is None
    assert result["click_y"] is None
    assert "CLOUDFLARE_API_TOKEN" in (result["reason"] or "")


def test_invalid_image_file_path(tmp_path: Path) -> None:
    missing = str(tmp_path / "does-not-exist.png")
    result = locate_visual_target(
        missing,
        "Terminal close button",
        capture_id="cap-xyz",
        mock_fixture_paths=GOLDEN_FIXTURES,
    )

    assert result["success"] is False
    assert result["status"] == "invalid_image"
    assert result["click_x"] is None
    assert result["click_y"] is None
    assert "not found" in (result["reason"] or "")
    assert result["capture_id"] == "cap-xyz"


def test_abstention_reporting(tmp_path: Path) -> None:
    low_conf_fixture = tmp_path / "low-confidence.json"
    low_conf_fixture.write_text(
        json.dumps(
            {
                "result": {
                    "answers": {
                        "target_cell": {
                            "choice": "C3",
                            "probabilities": {"C3": 0.10, "A1": 0.05},
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    image_path = _write_image(tmp_path / "screenshot.png", size=(500, 500))
    result = locate_visual_target(
        image_path,
        "nonexistent button",
        mock_fixture_paths=[str(low_conf_fixture)],
    )

    assert result["success"] is False
    assert result["status"] == "abstained_low_confidence"
    assert result["click_x"] is None
    assert result["click_y"] is None
    assert "below floor" in (result["reason"] or "")
