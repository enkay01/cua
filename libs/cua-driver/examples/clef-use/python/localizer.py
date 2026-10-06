from __future__ import annotations

import argparse
import os
from pathlib import Path
from PIL import Image

from clef_adapter import ClefClient
from grid_localizer import (
    ALL_CELLS,
    COLUMNS,
    ROWS,
    CellGeometry,
    ClefGridLocalizer,
    CropBox,
    IterationRecord,
    LocalizationResult,
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
    "ClefGridLocalizer",
    "CropBox",
    "IterationRecord",
    "LocalizationResult",
    "are_adjacent",
    "clamp_crop_window",
    "get_all_cell_geometries",
    "get_cell_geometry",
    "parse_cell_name",
    "render_grid_overlay",
    "main",
]


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
        base_fixture_dir = Path(__file__).resolve().parent.parent / "fixtures"
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
