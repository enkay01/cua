from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from PIL import Image

from clef_adapter import ClefChoiceResult, ClefClient
from grid import (
    CropBox,
    CellGeometry,
    are_adjacent,
    clamp_crop_window,
    get_cell_geometry,
    render_grid_overlay,
)


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
    iterations: tuple[IterationRecord, ...] = ()
    reason: str | None = None


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
    ) -> None:
        self.client = client
        self.num_levels = num_levels
        self.zoom_factor = zoom_factor
        self.custom_crop_sizes = list(custom_crop_sizes) if custom_crop_sizes else None
        self.min_confidence = min_confidence
        self.ambiguity_margin = ambiguity_margin

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
        debug_dir: Path | str | None = None,
    ) -> LocalizationResult:
        """Execute coarse-to-fine visual grid localization over num_levels iterations."""
        root_w, root_h = image.size
        active_center_x = root_w / 2.0
        active_center_y = root_h / 2.0
        records: list[IterationRecord] = []

        debug_path = Path(debug_dir) if debug_dir else None
        if debug_path:
            debug_path.mkdir(parents=True, exist_ok=True)

        for level in range(1, self.num_levels + 1):
            crop_w, crop_h = self._determine_crop_dimensions(level, root_w, root_h, root_w, root_h)
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

            # Render 5x5 grid overlay onto crop so model sees cell divisions and labels
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
                    iterations=tuple(records),
                    reason=f"Top candidate {top_cell} confidence {top_conf:.3f} below floor {self.min_confidence}",
                )

            # Check ambiguity margin between non-adjacent cells
            runner_up = eval_result.runner_up_candidate
            if runner_up:
                runner_cell, runner_conf = runner_up
                prob_delta = top_conf - runner_conf
                if prob_delta < self.ambiguity_margin and not are_adjacent(top_cell, runner_cell):
                    return LocalizationResult(
                        success=False,
                        status="abstained_ambiguous",
                        target_description=target_description,
                        iterations=tuple(records),
                        reason=(
                            f"Ambiguous top cells {top_cell} ({top_conf:.3f}) and {runner_cell} "
                            f"({runner_conf:.3f}) separated by margin {prob_delta:.3f} < {self.ambiguity_margin}"
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
            iterations=tuple(records),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Hierarchical visual grid localizer using Cloudflare Clef")
    parser.add_argument("--image", required=True, help="Path to input screenshot image")
    parser.add_argument("--prompt", required=True, help="Target description to localize")
    parser.add_argument("--levels", type=int, default=3, help="Number of zoom iterations (default: 3)")
    parser.add_argument("--model", default=None, help="Clef model name: 'clef' or 'clef-flash'")
    parser.add_argument("--mock-fixtures", nargs="*", default=None, help="Paths to mock JSON fixtures")
    parser.add_argument("--debug-dir", default=None, help="Directory to save overlay crops")
    parser.add_argument("--crop-desktop", action="store_true", help="Crop to bottom desktop in reference graphic (y >= 1254)")
    args = parser.parse_args()

    img = Image.open(args.image)
    if args.crop_desktop:
        w, h = img.size
        img = img.crop((0, 1254, w, h))
        print(f"Cropped to desktop viewport: {img.size}")

    fixture_paths = args.mock_fixtures
    if not fixture_paths and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        # Auto-fallback to local golden fixtures if offline
        base_fixture_dir = Path(__file__).parent.parent / "fixtures"
        fixture_paths = [
            base_fixture_dir / "clef-localization-level1.json",
            base_fixture_dir / "clef-localization-level2.json",
            base_fixture_dir / "clef-localization-level3.json",
        ]
        print("No Cloudflare credentials found. Using local golden fixtures for offline verification.")

    client_kwargs = {}
    if args.model:
        client_kwargs["model"] = args.model
    client = ClefClient(mock_fixture_paths=fixture_paths, **client_kwargs)
    localizer = ClefGridLocalizer(client, num_levels=args.levels)

    print(f"Localizing target: {args.prompt!r} in {args.image} ({img.size[0]}x{img.size[1]})...")
    result = localizer.localize(img, args.prompt, debug_dir=args.debug_dir)

    print(f"\nLocalization Result: {result.status.upper()}")
    for rec in result.iterations:
        print(
            f"  Level {rec.level}: Winning Cell={rec.winning_cell} (Confidence={rec.confidence:.3f}) | "
            f"Crop={rec.crop_box.as_tuple()} | Root Center=({rec.cell_geometry.root_center_x:.1f}, {rec.cell_geometry.root_center_y:.1f})"
        )

    if result.success:
        print(f"\nFinal Click Target: X={result.click_x:.1f}, Y={result.click_y:.1f}")
    else:
        print(f"\nLocalization failed / abstained: {result.reason}")


if __name__ == "__main__":
    main()
