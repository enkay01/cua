from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from PIL import Image

from clef_adapter import ClefClient, load_env_files
from grid_localizer import ClefGridLocalizer

if importlib.util.find_spec("mcp.server.mcpserver") is not None:
    # mcp>=2 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
else:
    from mcp.server.fastmcp import FastMCP

__all__ = [
    "mcp",
    "locate_visual_target",
    "main",
]


mcp = FastMCP("clef-visual-localization")


def _unconfigured_credentials_error() -> dict:
    return {
        "success": False,
        "status": "unconfigured_credentials",
        "click_x": None,
        "click_y": None,
        "confidence": None,
        "winning_cell": None,
        "capture_id": None,
        "pid": None,
        "window_id": None,
        "reason": (
            "Cloudflare credentials missing. Set CLOUDFLARE_API_TOKEN and "
            "CLOUDFLARE_ACCOUNT_ID environment variables or entries in a local "
            ".env / .env.local file."
        ),
    }


@mcp.tool()
def locate_visual_target(
    image_path: str,
    prompt: str,
    capture_id: str | None = None,
    pid: int | None = None,
    window_id: int | None = None,
    model: str | None = None,
    min_confidence: float = 0.25,
    ambiguity_margin: float = 0.05,
    deadline_seconds: float = 30.0,
    mock_fixture_paths: list[str] | None = None,
) -> dict:
    """Locate a visual target in a saved screenshot with hierarchical grid search.

    Args:
        image_path: Absolute or relative path to a screenshot PNG/JPEG on disk.
        prompt: Natural-language description of the element to find.
        capture_id: Driver capture id the screenshot came from (passed through).
        pid: Target process id for observation binding (passed through).
        window_id: Target window id for observation binding (passed through).
        model: Clef model name (defaults to CLEF_MODEL env or @cf/cloudflare/clef).
        min_confidence: Confidence floor below which localization abstains.
        ambiguity_margin: Margin below which non-adjacent competitors abstain.
        deadline_seconds: Total inference deadline in seconds.
        mock_fixture_paths: Optional fixture JSON paths for offline verification.

    Returns:
        Structured dict with success, status, click_x, click_y, confidence,
        winning_cell, capture_id, pid, window_id, and reason on failure.
    """
    load_env_files()

    if not image_path or not str(image_path).strip():
        return {
            "success": False,
            "status": "invalid_image",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": "image_path must be a non-empty file path.",
        }

    if not prompt or not str(prompt).strip():
        return {
            "success": False,
            "status": "invalid_prompt",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": "prompt must be a non-empty target description.",
        }

    screenshot = Path(str(image_path))
    if not screenshot.is_file():
        return {
            "success": False,
            "status": "invalid_image",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": f"Screenshot file not found: {image_path}",
        }

    try:
        image = Image.open(screenshot)
        image.load()
    except Exception as exc:
        return {
            "success": False,
            "status": "invalid_image",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": f"Unable to load screenshot {image_path}: {exc}",
        }

    fixtures = list(mock_fixture_paths) if mock_fixture_paths else None
    if fixtures is None:
        env_fixtures = os.environ.get("CLEF_MOCK_FIXTURES")
        if env_fixtures:
            fixtures = [p for p in env_fixtures.split(os.pathsep) if p.strip()]

    client_kwargs: dict = {}
    if model:
        client_kwargs["model"] = model
    if fixtures:
        client_kwargs["mock_fixture_paths"] = fixtures

    client = ClefClient(**client_kwargs)
    if not fixtures and not client.is_live_configured:
        return {
            "success": False,
            "status": "unconfigured_credentials",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": _unconfigured_credentials_error()["reason"],
        }

    localizer = ClefGridLocalizer(
        client,
        min_confidence=min_confidence,
        ambiguity_margin=ambiguity_margin,
        deadline_seconds=deadline_seconds,
    )

    try:
        result = localizer.localize(
            image,
            str(prompt).strip(),
            capture_id=capture_id,
            pid=pid,
            window_id=window_id,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "credentials missing" in message.lower():
            payload = _unconfigured_credentials_error()
            payload["capture_id"] = capture_id
            payload["pid"] = pid
            payload["window_id"] = window_id
            return payload
        return {
            "success": False,
            "status": "inference_error",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": message,
        }
    except Exception as exc:
        return {
            "success": False,
            "status": "inference_error",
            "click_x": None,
            "click_y": None,
            "confidence": None,
            "winning_cell": None,
            "capture_id": capture_id,
            "pid": pid,
            "window_id": window_id,
            "reason": str(exc),
        }

    if result.success:
        final = result.iterations[-1] if result.iterations else None
        return {
            "success": True,
            "status": "success",
            "click_x": result.click_x,
            "click_y": result.click_y,
            "confidence": final.confidence if final else None,
            "winning_cell": final.winning_cell if final else None,
            "capture_id": result.capture_id,
            "pid": result.target_pid,
            "window_id": result.target_window_id,
            "screenshot_w": result.screenshot_w,
            "screenshot_h": result.screenshot_h,
            "reason": None,
        }

    return {
        "success": False,
        "status": result.status,
        "click_x": None,
        "click_y": None,
        "confidence": None,
        "winning_cell": None,
        "capture_id": result.capture_id,
        "pid": result.target_pid,
        "window_id": result.target_window_id,
        "screenshot_w": result.screenshot_w,
        "screenshot_h": result.screenshot_h,
        "reason": result.reason,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
