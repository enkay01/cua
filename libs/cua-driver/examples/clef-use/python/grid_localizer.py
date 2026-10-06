from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from PIL import Image

from clef_adapter import ClefChoiceResult, ClefClient
from grid import (
    ALL_CELLS,
    COLUMNS,
    ROWS,
    CellGeometry,
    CropBox,
    are_adjacent,
    clamp_crop_window,
    get_all_cell_geometries,
    get_cell_geometry,
    parse_cell_name,
    render_grid_overlay,
)

__all__ = [
    "ALL_CELLS",
    "COLUMNS",
    "ROWS",
    "CellGeometry",
    "CropBox",
    "are_adjacent",
    "clamp_crop_window",
    "get_all_cell_geometries",
    "get_cell_geometry",
    "parse_cell_name",
    "render_grid_overlay",
    "IterationRecord",
    "LocalizationResult",
    "ClefGridLocalizer",
]


@dataclass(frozen=True)
class IterationRecord:
    level: int
    crop_box: CropBox
    winning_cell: str
    confidence: float
    probabilities: dict[str, float]
    cell_geometry: CellGeometry
    result: ClefChoiceResult


@dataclass(frozen=True)
class LocalizationResult:
    success: bool
    status: str
    target_description: str
    click_x: float | None = None
    click_y: float | None = None
    capture_id: str | None = None
    target_pid: int | None = None
    target_window_id: int | None = None
    screenshot_w: int | None = None
    screenshot_h: int | None = None
    iterations: tuple[IterationRecord, ...] = ()
    reason: str | None = None

    def matches_observation(
        self,
        *,
        capture_id: str | None,
        pid: int | None = None,
        window_id: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> bool:
        """Check if this localization result matches a given observation capture and target."""
        if not self.success:
            return False
        if self.capture_id is not None and capture_id != self.capture_id:
            return False
        if self.target_pid is not None and pid is not None and pid != self.target_pid:
            return False
        if self.target_window_id is not None and window_id is not None and window_id != self.target_window_id:
            return False
        if self.screenshot_w is not None and width is not None and width != self.screenshot_w:
            return False
        if self.screenshot_h is not None and height is not None and height != self.screenshot_h:
            return False
        return True


class ClefGridLocalizer:
    """Hierarchical probabilistic grid localizer using Cloudflare Clef."""

    def __init__(
        self,
        client: ClefClient,
        *,
        num_levels: int = 3,
        zoom_factor: float = 3.33,
        custom_crop_sizes: Sequence[tuple[int, int]] | None = None,
        min_confidence: float = 0.25,
        ambiguity_margin: float = 0.05,
        deadline_seconds: float = 30.0,
    ) -> None:
        self.client = client
        self.num_levels = num_levels
        self.zoom_factor = zoom_factor
        self.custom_crop_sizes = list(custom_crop_sizes) if custom_crop_sizes else None
        self.min_confidence = min_confidence
        self.ambiguity_margin = ambiguity_margin
        self.deadline_seconds = deadline_seconds

    def _determine_crop_dimensions(
        self,
        level: int,
        parent_w: int,
        parent_h: int,
        root_w: int,
        root_h: int,
    ) -> tuple[int, int]:
        """Compute the width and height for a zoom level."""
        if level == 1:
            return root_w, root_h

        if self.custom_crop_sizes and level <= len(self.custom_crop_sizes):
            return self.custom_crop_sizes[level - 1]

        scale = self.zoom_factor ** (level - 1)
        w = max(40, int(round(root_w / scale)))
        h = max(30, int(round(root_h / scale)))
        return w, h

    def localize(
        self,
        image: Image.Image,
        target_description: str,
        *,
        capture_id: str | None = None,
        pid: int | None = None,
        window_id: int | None = None,
        debug_dir: Path | str | None = None,
        timeout: float | None = None,
    ) -> LocalizationResult:
        """Execute coarse-to-fine visual grid localization over num_levels iterations."""
        root_w, root_h = image.size
        active_center_x = root_w / 2.0
        active_center_y = root_h / 2.0
        records: list[IterationRecord] = []

        effective_timeout = timeout if timeout is not None else self.deadline_seconds
        start_time = time.monotonic()
        deadline = start_time + effective_timeout if effective_timeout > 0 else float("inf")

        debug_path = Path(debug_dir) if debug_dir else None
        if debug_path:
            debug_path.mkdir(parents=True, exist_ok=True)

        for level in range(1, self.num_levels + 1):
            if time.monotonic() > deadline:
                return LocalizationResult(
                    success=False,
                    status="abstained_timeout",
                    target_description=target_description,
                    capture_id=capture_id,
                    target_pid=pid,
                    target_window_id=window_id,
                    screenshot_w=root_w,
                    screenshot_h=root_h,
                    iterations=tuple(records),
                    reason=f"Inference deadline {effective_timeout:.1f}s exceeded before level {level}",
                )

            crop_w, crop_h = self._determine_crop_dimensions(level, root_w, root_h, root_w, root_h)

            if crop_w > root_w or crop_h > root_h:
                raise ValueError(
                    f"Configured crop size ({crop_w}, {crop_h}) exceeds screenshot dimensions ({root_w}, {root_h})"
                )

            crop_box = clamp_crop_window(
                active_center_x,
                active_center_y,
                crop_w=crop_w,
                crop_h=crop_h,
                image_w=root_w,
                image_h=root_h,
            )

            # Extract active crop from original full-resolution image
            crop_image = image.crop(crop_box.as_tuple())

            # Render 5x5 grid overlay onto crop
            grid_crop = render_grid_overlay(crop_image)

            # Evaluate with Clef
            prompt = f"Select the grid cell containing {target_description}"
            eval_result = self.client.evaluate_grid(grid_crop, prompt)

            # Check confidence floor
            top_cell, top_conf = eval_result.top_candidate
            if top_conf < self.min_confidence:
                return LocalizationResult(
                    success=False,
                    status="abstained_low_confidence",
                    target_description=target_description,
                    capture_id=capture_id,
                    target_pid=pid,
                    target_window_id=window_id,
                    screenshot_w=root_w,
                    screenshot_h=root_h,
                    iterations=tuple(records),
                    reason=f"Top candidate {top_cell} confidence {top_conf:.3f} below floor {self.min_confidence}",
                )

            # Check ambiguity margin against the highest-scoring non-adjacent competitor
            non_adj = eval_result.top_non_adjacent_candidate(reference_cell=top_cell)
            if non_adj is not None:
                non_adj_cell, non_adj_conf = non_adj
                margin = top_conf - non_adj_conf
                if margin < self.ambiguity_margin:
                    return LocalizationResult(
                        success=False,
                        status="abstained_ambiguous",
                        target_description=target_description,
                        capture_id=capture_id,
                        target_pid=pid,
                        target_window_id=window_id,
                        screenshot_w=root_w,
                        screenshot_h=root_h,
                        iterations=tuple(records),
                        reason=(
                            f"Ambiguous candidates: top cell {top_cell} ({top_conf:.3f}) and "
                            f"non-adjacent competitor {non_adj_cell} ({non_adj_conf:.3f}) separated by "
                            f"margin {margin:.3f} < {self.ambiguity_margin}"
                        ),
                    )

            # Cell geometry inside crop and translated to root
            geom = get_cell_geometry(top_cell, crop_box)

            # Save debug visualization if requested
            if debug_path:
                overlay = render_grid_overlay(crop_image, highlight_cell=top_cell)
                overlay.save(debug_path / f"level_{level}_crop_overlay.png")

            record = IterationRecord(
                level=level,
                crop_box=crop_box,
                winning_cell=top_cell,
                confidence=top_conf,
                probabilities=eval_result.probabilities,
                cell_geometry=geom,
                result=eval_result,
            )
            records.append(record)

            # Update center for next zoom level
            active_center_x = geom.root_center_x
            active_center_y = geom.root_center_y

        # Final iteration winning cell geometric center is the click target
        final_record = records[-1]
        final_x = final_record.cell_geometry.root_center_x
        final_y = final_record.cell_geometry.root_center_y

        return LocalizationResult(
            success=True,
            status="success",
            target_description=target_description,
            click_x=final_x,
            click_y=final_y,
            capture_id=capture_id,
            target_pid=pid,
            target_window_id=window_id,
            screenshot_w=root_w,
            screenshot_h=root_h,
            iterations=tuple(records),
        )
