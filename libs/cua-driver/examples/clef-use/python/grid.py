from __future__ import annotations

from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont


COLUMNS: tuple[str, ...] = ("A", "B", "C", "D", "E")
ROWS: tuple[str, ...] = ("1", "2", "3", "4", "5")
ALL_CELLS: list[str] = [f"{c}{r}" for r in ROWS for c in COLUMNS]


@dataclass(frozen=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True)
class CellGeometry:
    name: str
    col: str
    row: str
    col_idx: int
    row_idx: int
    crop_x0: int
    crop_y0: int
    crop_x1: int
    crop_y1: int
    crop_center_x: float
    crop_center_y: float
    root_center_x: float
    root_center_y: float


def parse_cell_name(cell_name: str) -> tuple[int, int]:
    name = cell_name.strip().upper()
    if len(name) != 2:
        raise ValueError(f"Invalid cell name: {cell_name!r}. Must be 2 characters (e.g. 'A1', 'E5').")
    col_char, row_char = name[0], name[1]
    if col_char not in COLUMNS:
        raise ValueError(f"Invalid column: {col_char!r} in cell {cell_name!r}. Allowed: {COLUMNS}")
    if row_char not in ROWS:
        raise ValueError(f"Invalid row: {row_char!r} in cell {cell_name!r}. Allowed: {ROWS}")
    return COLUMNS.index(col_char), ROWS.index(row_char)


def are_adjacent(cell1: str, cell2: str) -> bool:
    c1, r1 = parse_cell_name(cell1)
    c2, r2 = parse_cell_name(cell2)
    return abs(c1 - c2) <= 1 and abs(r1 - r2) <= 1


def clamp_crop_window(
    center_x: float | int,
    center_y: float | int,
    crop_w: int,
    crop_h: int,
    image_w: int,
    image_h: int,
) -> CropBox:
    """Position a crop window centered at (center_x, center_y) clamped to image boundaries.

    Ensures that crop dimensions maintain constant dimensions and rejects oversized crops.
    """
    if image_w <= 0 or image_h <= 0:
        raise ValueError(f"Image dimensions must be positive, got ({image_w}, {image_h})")

    if crop_w <= 0 or crop_h <= 0:
        raise ValueError(f"Crop dimensions must be positive, got ({crop_w}, {crop_h})")

    if crop_w > image_w or crop_h > image_h:
        raise ValueError(
            f"Configured crop size ({crop_w}, {crop_h}) exceeds image dimensions ({image_w}, {image_h})"
        )

    if crop_w == image_w:
        new_left = 0
    else:
        new_left = max(0, min(int(round(center_x - crop_w / 2.0)), image_w - crop_w))

    if crop_h == image_h:
        new_top = 0
    else:
        new_top = max(0, min(int(round(center_y - crop_h / 2.0)), image_h - crop_h))

    new_right = new_left + crop_w
    new_bottom = new_top + crop_h
    return CropBox(left=new_left, top=new_top, right=new_right, bottom=new_bottom)


def get_cell_geometry(
    cell_name: str,
    crop_box: CropBox,
) -> CellGeometry:
    col_idx, row_idx = parse_cell_name(cell_name)
    w = crop_box.width
    h = crop_box.height

    x0 = int(round(col_idx * w / 5.0))
    x1 = int(round((col_idx + 1) * w / 5.0))
    y0 = int(round(row_idx * h / 5.0))
    y1 = int(round((row_idx + 1) * h / 5.0))

    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    return CellGeometry(
        name=cell_name.strip().upper(),
        col=COLUMNS[col_idx],
        row=ROWS[row_idx],
        col_idx=col_idx,
        row_idx=row_idx,
        crop_x0=x0,
        crop_y0=y0,
        crop_x1=x1,
        crop_y1=y1,
        crop_center_x=cx,
        crop_center_y=cy,
        root_center_x=crop_box.left + cx,
        root_center_y=crop_box.top + cy,
    )


def get_all_cell_geometries(crop_box: CropBox) -> dict[str, CellGeometry]:
    return {cell: get_cell_geometry(cell, crop_box) for cell in ALL_CELLS}


def render_grid_overlay(
    image: Image.Image,
    *,
    line_color: tuple[int, int, int] = (0, 255, 120),
    line_width: int = 1,
    draw_labels: bool = True,
    label_color: tuple[int, int, int] = (0, 255, 120),
    highlight_cell: str | None = None,
    highlight_color: tuple[int, int, int] = (255, 60, 60),
) -> Image.Image:
    """Render a 5x5 grid overlay on an image crop."""
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size

    # Vertical division lines
    for c in range(1, 5):
        x = int(round(c * w / 5.0))
        draw.line([(x, 0), (x, h)], fill=line_color, width=line_width)

    # Horizontal division lines
    for r in range(1, 5):
        y = int(round(r * h / 5.0))
        draw.line([(0, y), (w, y)], fill=line_color, width=line_width)

    # Highlight cell if specified
    if highlight_cell:
        col_idx, row_idx = parse_cell_name(highlight_cell)
        x0 = int(round(col_idx * w / 5.0))
        x1 = int(round((col_idx + 1) * w / 5.0))
        y0 = int(round(row_idx * h / 5.0))
        y1 = int(round((row_idx + 1) * h / 5.0))
        draw.rectangle([x0, y0, x1, y1], outline=highlight_color, width=max(2, line_width + 1))

    # Cell labels
    if draw_labels:
        font = ImageFont.load_default()
        for cell_name in ALL_CELLS:
            col_idx, row_idx = parse_cell_name(cell_name)
            x0 = int(round(col_idx * w / 5.0))
            y0 = int(round(row_idx * h / 5.0))
            text_color = highlight_color if highlight_cell == cell_name else label_color
            draw.text((x0 + 3, y0 + 3), cell_name, fill=text_color, font=font)

    return canvas
