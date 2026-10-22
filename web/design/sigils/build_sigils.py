"""Compute stat-sigil geometry from species-stats.json.

A sigil is a species' six base stats drawn as a hexagon, split-filled with its
type colors. Writes sigils.json (runtime geometry) and glaxnimate-elements.json
(the element list passed to glaxnimate_create_svg to draw sigils.svg).

Usage: python3 build_sigils.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
SIZE = 120
CENTER = SIZE / 2
RADIUS = 48
STAT_CAP = 160

# Clockwise from the top, matching the in-game summary hexagon.
AXES = [("hp", -90), ("atk", -30), ("def", 30), ("spe", 90), ("spd", 150), ("spa", 210)]

# Original palette, tuned to read on a dark indigo ground.
TYPE_COLORS = {
    "Normal": "#9AA3B5",
    "Fire": "#FF6B3D",
    "Water": "#3D8BFF",
    "Grass": "#3FCF6A",
    "Electric": "#FFD23F",
    "Ice": "#6FE0F0",
    "Fighting": "#C9343A",
    "Poison": "#B04BD9",
    "Ground": "#D9A441",
    "Flying": "#8FA8FF",
    "Psychic": "#FF5C9A",
    "Bug": "#9BC832",
    "Rock": "#B8A06A",
    "Ghost": "#6E5BC9",
    "Dragon": "#5A4BFF",
    "Dark": "#4A4458",
    "Steel": "#8FB3C2",
    "Fairy": "#F59CD9",
}
STROKE = "#FFFFFF"
GUIDE = "#B9B4FF"
SPEED = "#C8F031"


def point(angle_deg: float, r: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return round(CENTER + r * math.cos(a), 2), round(CENTER + r * math.sin(a), 2)


def fmt(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:g},{y:g}" for x, y in points)


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def build() -> None:
    data = json.loads((HERE / "species-stats.json").read_text(encoding="utf-8"))
    cell = fmt([point(angle, RADIUS) for _, angle in AXES])
    spokes = [point(angle, RADIUS) for _, angle in AXES[:3]]
    opposite = [point(angle, RADIUS) for _, angle in AXES[3:]]

    sigils = {}
    defs = []
    symbols = []
    for name, entry in data["species"].items():
        stats = entry["baseStats"]
        types = entry["types"]
        colors = [TYPE_COLORS[t] for t in types]
        shape = fmt(
            [point(angle, RADIUS * min(stats[key], STAT_CAP) / STAT_CAP) for key, angle in AXES]
        )
        speed_tip = point(90, RADIUS * min(stats["spe"], STAT_CAP) / STAT_CAP)
        sid = slug(name)
        sigils[name] = {
            "slug": sid,
            "types": types,
            "colors": colors,
            "points": shape,
            "speedTip": speed_tip,
        }

        first, second = colors[0], colors[-1]
        defs.append(
            {
                "type": "linearGradient",
                "id": f"fill-{sid}",
                "attributes": {
                    "gradientUnits": "userSpaceOnUse",
                    "x1": "0",
                    "y1": "0",
                    "x2": f"{SIZE}",
                    "y2": "0",
                    "spreadMethod": "pad",
                },
                "children": [
                    {
                        "type": "stop",
                        "id": f"fill-{sid}-a",
                        "attributes": {"offset": "0", "stop-color": first},
                    },
                    {
                        "type": "stop",
                        "id": f"fill-{sid}-b",
                        "attributes": {"offset": "0.5", "stop-color": first},
                    },
                    {
                        "type": "stop",
                        "id": f"fill-{sid}-c",
                        "attributes": {"offset": "0.5", "stop-color": second},
                    },
                    {
                        "type": "stop",
                        "id": f"fill-{sid}-d",
                        "attributes": {"offset": "1", "stop-color": second},
                    },
                ],
            }
        )
        symbols.append(
            {
                "type": "symbol",
                "id": f"sigil-{sid}",
                "attributes": {"viewBox": f"0 0 {SIZE} {SIZE}"},
                "children": [
                    {"type": "title", "id": f"sigil-{sid}-title", "text": f"{name} stat sigil"},
                    {
                        "type": "use",
                        "id": f"sigil-{sid}-cell",
                        "attributes": {"href": "#sigil-cell"},
                    },
                    {
                        "type": "polygon",
                        "id": f"sigil-{sid}-shape",
                        "attributes": {
                            "points": shape,
                            "fill": f"url(#fill-{sid})",
                            "stroke": STROKE,
                            "stroke-width": "2.5",
                            "stroke-linejoin": "round",
                        },
                    },
                    {
                        "type": "line",
                        "id": f"sigil-{sid}-speed",
                        "attributes": {
                            "x1": f"{CENTER:g}",
                            "y1": f"{CENTER:g}",
                            "x2": f"{speed_tip[0]:g}",
                            "y2": f"{speed_tip[1]:g}",
                            "stroke": SPEED,
                            "stroke-width": "3",
                            "stroke-linecap": "round",
                        },
                    },
                ],
            }
        )

    (HERE / "sigils.json").write_text(
        json.dumps(
            {
                "size": SIZE,
                "radius": RADIUS,
                "statCap": STAT_CAP,
                "axes": [key for key, _ in AXES],
                "cell": cell,
                "typeColors": TYPE_COLORS,
                "sigils": sigils,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    shared_cell = {
        "type": "symbol",
        "id": "sigil-cell",
        "attributes": {"viewBox": f"0 0 {SIZE} {SIZE}"},
        "children": [
            {
                "type": "polygon",
                "id": "sigil-cell-frame",
                "attributes": {
                    "points": cell,
                    "fill": GUIDE,
                    "fill-opacity": "0.08",
                    "stroke": GUIDE,
                    "stroke-opacity": "0.35",
                    "stroke-width": "1.5",
                    "stroke-linejoin": "round",
                },
            },
            *[
                {
                    "type": "line",
                    "id": f"sigil-cell-axis-{i}",
                    "attributes": {
                        "x1": f"{a[0]:g}",
                        "y1": f"{a[1]:g}",
                        "x2": f"{b[0]:g}",
                        "y2": f"{b[1]:g}",
                        "stroke": GUIDE,
                        "stroke-opacity": "0.18",
                        "stroke-width": "1",
                    },
                }
                for i, (a, b) in enumerate(zip(spokes, opposite, strict=True))
            ],
        ],
    }
    (HERE / "glaxnimate-elements.json").write_text(
        json.dumps(
            [{"type": "defs", "id": "sigil-defs", "children": defs}, shared_cell, *symbols],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
