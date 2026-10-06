from __future__ import annotations

import os
import shutil
from typing import Any
import pytest

from clef_adapter import ClefClient
from grid_localizer import ClefGridLocalizer
from sources import VisualGridSource


@pytest.mark.skipif(
    os.environ.get("CUA_TEST_LIVE_CAPTURE") != "1",
    reason="Opt-in live capture check requires CUA_TEST_LIVE_CAPTURE=1",
)
def test_live_capture_bound_click_on_desktop_target() -> None:
    driver_bin = os.getenv("CUA_DRIVER_BIN", shutil.which("cua-driver") or "cua-driver")
    if not shutil.which(driver_bin) and not os.path.exists(driver_bin):
        pytest.skip(f"cua-driver binary not found at {driver_bin}")

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        pytest.skip("mcp package not installed in environment")

    import asyncio

    async def _run() -> None:
        params = StdioServerParameters(command=driver_bin, args=["mcp"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                def get_structured(result: Any) -> dict[str, Any]:
                    return getattr(result, "structured_content", None) or getattr(result, "structuredContent", None) or {}

                def is_err(result: Any) -> bool:
                    return bool(getattr(result, "is_error", getattr(result, "isError", False)))

                # 1. Discover available onscreen windows
                res = await session.call_tool("list_windows", {})
                windows = get_structured(res).get("windows", [])
                target_window = None
                for w in windows:
                    if w.get("is_on_screen") and w.get("title") and w.get("pid"):
                        target_window = w
                        break

                if not target_window:
                    pytest.skip("No suitable onscreen window available for live capture test")

                pid = int(target_window["pid"])
                window_id = int(target_window["window_id"])

                # 2. Capture window state
                state = await session.call_tool(
                    "get_window_state",
                    {
                        "pid": pid,
                        "window_id": window_id,
                        "include_accessibility_tree": False,
                        "include_screenshot": True,
                    },
                )
                if is_err(state):
                    pytest.skip(f"get_window_state failed: {state.content}")

                state_data = get_structured(state)
                capture_id = state_data.get("capture_id")
                assert capture_id is not None
                width = state_data.get("screenshot_width", 800)
                height = state_data.get("screenshot_height", 600)

                # 3. Localize with VisualGridSource
                from pathlib import Path
                if not os.environ.get("CLOUDFLARE_API_TOKEN"):
                    fixtures_dir = Path(__file__).resolve().parent.parent.parent / "fixtures"
                    fixture_paths = [
                        fixtures_dir / "clef-localization-level1.json",
                        fixtures_dir / "clef-localization-level2.json",
                        fixtures_dir / "clef-localization-level3.json",
                    ]
                    client = ClefClient(mock_fixture_paths=fixture_paths)
                else:
                    client = ClefClient()
                localizer = ClefGridLocalizer(client)
                from PIL import Image
                dummy_img = Image.new("RGB", (width, height), color=(255, 255, 255))
                loc_res = localizer.localize(
                    dummy_img,
                    "Target control",
                    capture_id=capture_id,
                    pid=pid,
                    window_id=window_id,
                )
                assert loc_res.success

                source = VisualGridSource(
                    loc_res,
                    pid=pid,
                    window_id=window_id,
                    capture_id=capture_id,
                    delivery="background",
                    capture_bound=True,
                )

                control = source.find("button", "Target control")
                assert control is not None

                cand = source.click(control, candidate_id="click-target", description="Click target control")
                assert cand is not None
                assert cand.tool == "click"
                assert cand.source == "visual"
                assert cand.arguments["capture_id"] == capture_id

                # 4. Dispatch capture-bound click
                click_res = await session.call_tool(
                    "click",
                    {
                        "pid": cand.arguments["pid"],
                        "window_id": cand.arguments["window_id"],
                        "capture_id": cand.arguments["capture_id"],
                        "x": cand.arguments["x"],
                        "y": cand.arguments["y"],
                        "delivery_mode": cand.arguments["delivery_mode"],
                    },
                )
                assert not is_err(click_res)
                assert get_structured(click_res).get("delivery", {}).get("mode") == "background"

                # 5. Verify reused capture is refused atomically
                stale_click = await session.call_tool(
                    "click",
                    {
                        "pid": cand.arguments["pid"],
                        "window_id": cand.arguments["window_id"],
                        "capture_id": capture_id,
                        "x": cand.arguments["x"],
                        "y": cand.arguments["y"],
                        "delivery_mode": "background",
                    },
                )
                assert is_err(stale_click)
                assert get_structured(stale_click).get("code") == "capture_not_found"

    asyncio.run(_run())
