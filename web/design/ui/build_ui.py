"""Compute geometry for the Protect shield and the battle-screen UI kit.

The shield is a pointy-top hexagon split down a zigzag seam into two halves.
Each half carries 8 of the 16 hex cells, one per Protect PP under Scarlet/Violet
rules, so cracking off the right half leaves the 8 that Champions allows.

Writes shield-elements.json and kit-elements.json, the element lists passed to
glaxnimate_create_svg to draw shield.svg and kit.svg.

Usage: python3 build_ui.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent

SHIELD_SIZE = 160
CENTER = SHIELD_SIZE / 2
SHIELD_RADIUS = 64
CELL_RADIUS = 7
# The seam runs top vertex to bottom vertex, jagging left and right of center.
SEAM = [(80, 16), (88, 38), (73, 58), (87, 80), (72, 102), (86, 124), (80, 144)]
# Cell centers in the left half, honeycomb rows; the right half mirrors them.
LEFT_CELLS = [(62, 50), (46, 50), (54, 70), (38, 70), (62, 90), (46, 90), (54, 110), (38, 110)]

SHIELD = "#45D6EE"
SELECT = "#C8F542"
PANEL = "#2A2148"
LINE = "#4A3F73"
# An empty pip carries meaning, so it needs 3:1 against the ground; LINE has 1.95.
MUTED = "#B9B2D6"

# Hint-row keycap: a parallelogram with the panels' 12 degree slant.
KEY_W, KEY_H = 32, 24
SLANT_DEG = 12


def hex_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Pointy-top hexagon, clockwise from the top vertex."""
    return [
        (round(cx + r * math.cos(math.radians(a)), 2), round(cy + r * math.sin(math.radians(a)), 2))
        for a in (-90, -30, 30, 90, 150, 210)
    ]


def fmt(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:g},{y:g}" for x, y in points)


def mirror(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(round(SHIELD_SIZE - x, 2), y) for x, y in points]


def shield_half(side: str) -> dict:
    top, upper_right, lower_right, bottom, lower_left, upper_left = hex_points(
        CENTER, CENTER, SHIELD_RADIUS
    )
    if side == "left":
        outline = [*SEAM, lower_left, upper_left]
        rim = [bottom, lower_left, upper_left, top]
        cells = LEFT_CELLS
        first = 1
    else:
        outline = [top, upper_right, lower_right, *reversed(SEAM)]
        rim = [top, upper_right, lower_right, bottom]
        cells = mirror(LEFT_CELLS)
        first = 9
    children = [
        {
            "type": "polygon",
            "id": f"shield-{side}-face",
            "attributes": {"points": fmt(outline), "fill": SHIELD, "fill-opacity": "0.16"},
        },
        {
            "type": "polyline",
            "id": f"shield-{side}-rim",
            "attributes": {
                "points": fmt(rim),
                "fill": "none",
                "stroke": SHIELD,
                "stroke-width": "4",
                "stroke-linejoin": "miter",
            },
        },
    ]
    for i, (cx, cy) in enumerate(cells):
        children.append(
            {
                "type": "polygon",
                "id": f"shield-cell-{first + i:02d}",
                "attributes": {"points": fmt(hex_points(cx, cy, CELL_RADIUS)), "fill": SHIELD},
            }
        )
    return {"type": "g", "id": f"shield-{side}", "children": children}


def shield_elements() -> list[dict]:
    return [
        shield_half("left"),
        shield_half("right"),
        {
            "type": "polyline",
            "id": "shield-seam",
            "attributes": {
                "points": fmt(SEAM),
                "fill": "none",
                "stroke": SHIELD,
                "stroke-width": "1.5",
                "stroke-opacity": "0.5",
            },
        },
    ]


def kit_elements() -> list[dict]:
    slant = round(KEY_H * math.tan(math.radians(SLANT_DEG)), 2)
    keycap = [(slant, 0), (KEY_W, 0), (KEY_W - slant, KEY_H), (0, KEY_H)]
    pip = hex_points(6, 6, 5)
    return [
        {
            "type": "symbol",
            "id": "cursor-arrow",
            "attributes": {"viewBox": "0 0 32 32"},
            "children": [
                {
                    "type": "polygon",
                    "id": "cursor-arrow-shape",
                    "attributes": {"points": "6,4 28,16 6,28 12,16", "fill": SELECT},
                }
            ],
        },
        {
            "type": "symbol",
            "id": "pp-pip-full",
            "attributes": {"viewBox": "0 0 12 12"},
            "children": [
                {
                    "type": "polygon",
                    "id": "pp-pip-full-shape",
                    "attributes": {"points": fmt(pip), "fill": SHIELD},
                }
            ],
        },
        {
            "type": "symbol",
            "id": "pp-pip-empty",
            "attributes": {"viewBox": "0 0 12 12"},
            "children": [
                {
                    "type": "polygon",
                    "id": "pp-pip-empty-shape",
                    "attributes": {
                        "points": fmt(hex_points(6, 6, 4.4)),
                        "fill": "none",
                        "stroke": MUTED,
                        "stroke-width": "1.2",
                    },
                }
            ],
        },
        {
            "type": "symbol",
            "id": "keycap",
            "attributes": {"viewBox": f"0 0 {KEY_W} {KEY_H}"},
            "children": [
                {
                    "type": "polygon",
                    "id": "keycap-shape",
                    "attributes": {
                        "points": fmt(keycap),
                        "fill": PANEL,
                        "stroke": LINE,
                        "stroke-width": "1.5",
                    },
                }
            ],
        },
    ]


def main() -> None:
    for name, elements in (("shield", shield_elements()), ("kit", kit_elements())):
        path = HERE / f"{name}-elements.json"
        path.write_text(json.dumps(elements, indent=1) + "\n")
        print(f"Wrote {path.name}")


if __name__ == "__main__":
    main()
