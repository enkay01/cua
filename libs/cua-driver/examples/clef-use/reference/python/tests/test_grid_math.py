from __future__ import annotations

import pytest
from PIL import Image

from grid import (
    ALL_CELLS,
    COLUMNS,
    ROWS,
    CropBox,
    are_adjacent,
    clamp_crop_window,
    get_all_cell_geometries,
    get_cell_geometry,
    parse_cell_name,
    render_grid_overlay,
)


def test_parse_cell_name() -> None:
    assert parse_cell_name("A1") == (0, 0)
    assert parse_cell_name("E5") == (4, 4)
    assert parse_cell_name("c3") == (2, 2)
    assert parse_cell_name(" B4 ") == (1, 3)

    with pytest.raises(ValueError):
        parse_cell_name("F1")
    with pytest.raises(ValueError):
        parse_cell_name("A6")
    with pytest.raises(ValueError):
        parse_cell_name("A")
    with pytest.raises(ValueError):
        parse_cell_name("A11")


def test_are_adjacent() -> None:
    # Same cell is adjacent (distance 0)
    assert are_adjacent("C3", "C3")

    # Cardinal neighbors
    assert are_adjacent("C3", "C2")  # up
    assert are_adjacent("C3", "C4")  # down
    assert are_adjacent("C3", "B3")  # left
    assert are_adjacent("C3", "D3")  # right

    # Diagonal neighbors
    assert are_adjacent("C3", "B2")
    assert are_adjacent("C3", "D4")

    # Non-adjacent cells
    assert not are_adjacent("A1", "C1")
    assert not are_adjacent("A1", "A3")
    assert not are_adjacent("A1", "E5")
    assert not are_adjacent("D1", "A5")


def test_clamp_crop_window_centered() -> None:
    # 1000x800 image, centered request, crop 400x300
    box = clamp_crop_window(center_x=500, center_y=400, crop_w=400, crop_h=300, image_w=1000, image_h=800)
    assert box.left == 300
    assert box.top == 250
    assert box.right == 700
    assert box.bottom == 550
    assert box.width == 400
    assert box.height == 300


def test_clamp_crop_window_top_left_never_shrinks() -> None:
    # Request at (0, 0)
    box = clamp_crop_window(center_x=0, center_y=0, crop_w=300, crop_h=200, image_w=1280, image_h=720)
    assert box.left == 0
    assert box.top == 0
    assert box.right == 300
    assert box.bottom == 200
    assert box.width == 300
    assert box.height == 200

    # Negative coordinates
    neg_box = clamp_crop_window(center_x=-150, center_y=-50, crop_w=300, crop_h=200, image_w=1280, image_h=720)
    assert neg_box.left == 0
    assert neg_box.top == 0
    assert neg_box.right == 300
    assert neg_box.bottom == 200
    assert neg_box.width == 300
    assert neg_box.height == 200


def test_clamp_crop_window_bottom_right_never_shrinks() -> None:
    # Request at (W, H)
    box = clamp_crop_window(center_x=1280, center_y=720, crop_w=300, crop_h=200, image_w=1280, image_h=720)
    assert box.left == 980
    assert box.top == 520
    assert box.right == 1280
    assert box.bottom == 720
    assert box.width == 300
    assert box.height == 200

    # Coordinates beyond boundaries
    over_box = clamp_crop_window(center_x=2000, center_y=1500, crop_w=300, crop_h=200, image_w=1280, image_h=720)
    assert over_box.left == 980
    assert over_box.top == 520
    assert over_box.right == 1280
    assert over_box.bottom == 720
    assert over_box.width == 300
    assert over_box.height == 200


def test_clamp_crop_window_top_right_and_bottom_left() -> None:
    # Top-right corner (W, 0)
    tr = clamp_crop_window(center_x=1920, center_y=0, crop_w=400, crop_h=300, image_w=1920, image_h=1080)
    assert tr.left == 1520
    assert tr.top == 0
    assert tr.right == 1920
    assert tr.bottom == 300
    assert tr.width == 400
    assert tr.height == 300

    # Bottom-left corner (0, H)
    bl = clamp_crop_window(center_x=0, center_y=1080, crop_w=400, crop_h=300, image_w=1920, image_h=1080)
    assert bl.left == 0
    assert bl.top == 780
    assert bl.right == 400
    assert bl.bottom == 1080
    assert bl.width == 400
    assert bl.height == 300


def test_clamp_crop_window_larger_than_image() -> None:
    box = clamp_crop_window(center_x=100, center_y=100, crop_w=2000, crop_h=1500, image_w=1280, image_h=720)
    assert box.left == 0
    assert box.top == 0
    assert box.right == 1280
    assert box.bottom == 720
    assert box.width == 1280
    assert box.height == 720


def test_cell_geometry_and_partition() -> None:
    crop_box = CropBox(left=100, top=200, right=600, bottom=700)
    assert crop_box.width == 500
    assert crop_box.height == 500

    geometries = get_all_cell_geometries(crop_box)
    assert len(geometries) == 25

    # Check A1
    a1 = geometries["A1"]
    assert a1.crop_x0 == 0
    assert a1.crop_x1 == 100
    assert a1.crop_y0 == 0
    assert a1.crop_y1 == 100
    assert a1.crop_center_x == 50.0
    assert a1.crop_center_y == 50.0
    assert a1.root_center_x == 150.0
    assert a1.root_center_y == 250.0

    # Check E5
    e5 = geometries["E5"]
    assert e5.crop_x0 == 400
    assert e5.crop_x1 == 500
    assert e5.crop_y0 == 400
    assert e5.crop_y1 == 500
    assert e5.crop_center_x == 450.0
    assert e5.crop_center_y == 450.0
    assert e5.root_center_x == 550.0
    assert e5.root_center_y == 650.0

    # Check C3 (center cell)
    c3 = geometries["C3"]
    assert c3.crop_x0 == 200
    assert c3.crop_x1 == 300
    assert c3.crop_y0 == 200
    assert c3.crop_y1 == 300


def test_render_grid_overlay() -> None:
    img = Image.new("RGB", (250, 250), color=(30, 30, 30))
    overlaid = render_grid_overlay(img, highlight_cell="E1")
    assert overlaid.size == (250, 250)
    # Check that image was drawn on
    assert overlaid.tobytes() != img.tobytes()
