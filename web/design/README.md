# Design sources

Original artwork for the public showcase. Nothing here depicts a Pokémon or uses Nintendo, Game Freak, or The Pokémon Company art, logos, or trade dress. Species appear as names and stat sigils only. See `JOURNAL.md` (2026-10-22) for why.

## Stat sigils (`sigils/`)

Each species' six base stats drawn as a hexagon on a shared honeycomb cell, with HP at the top and then Attack, Defense, Speed, Sp. Def, and Sp. Atk clockwise. That is the order of the in-game summary hexagon. The fill splits down the HP–Speed axis into the species' first and second type colors, and a lime spoke marks Speed.

| File | Contents |
| --- | --- |
| `species-stats.json` | Base stats and types for the 21 species in the Protect team manifest, read with `Dex.mod("gen9")` from the pinned simulator revision. The Champions mod has no pokedex override at that revision. |
| `build_sigils.py` | Computes the geometry. Writes `sigils.json` and `glaxnimate-elements.json`. Standard library only. |
| `sigils.json` | Runtime geometry: polygon points, Speed tip, type colors, and the type palette. The site composes sigils from this file. |
| `glaxnimate-elements.json` | Element list passed to `glaxnimate_create_svg`. |
| `sigils.svg` | The Glaxnimate drawing: a sprite with one `<symbol>` per species (`#sigil-<slug>`) plus the shared `#sigil-cell`. |

Stats cap at 160 for the radius, so the polygons read as a chart as well as a mark. The two Ogerpon forms share stats, as do the two Urshifu forms. Their shapes match, and only the second type color separates them, so always show the name with the sigil.

To add species, extend `species-stats.json`, run `python3 build_sigils.py`, and redraw `sigils.svg` from `glaxnimate-elements.json` with the Glaxnimate MCP.

Planned motion (GSAP on the page clock, drawn from the same geometry): the shape shrinks toward the center as HP falls, the cell pulses when Protect is used, and the shape drains to an outline on a knockout. Under reduced motion, show the end state only.

## Agents (`agents/`)

The three study agents as original toy-robot coaches, built in Blender from `build_agents.py`. Each wears a honeycomb rack on its chest with one hex cell per maximum Protect PP.

| Agent | Rules | Rack | Tells |
| --- | --- | --- | --- |
| SourceAgent | Scarlet/Violet, 16 PP | 4 by 4, all 16 lit amber | Stocky amber body, headset, flat bar eyes |
| AdaptedAgent | Source refitted for Champions | 4 by 4, 8 lit cyan, 8 capped | Source body with a lavender arm, one bar eye and one hex eye, the native antenna |
| NativeAgent | Champions, 8 PP | 4 by 2, all 8 lit cyan | Slender lavender body, hex eyes, hex antenna |

| File | Contents |
| --- | --- |
| `build_agents.py` | Builds the `vgc-agents` scene. Run it inside Blender with `exec`, then call `render_all(<this folder>)`. |
| `agents.blend` | The scene alone, saved with `bpy.data.libraries.write`. |
| `agents-lineup.png` | 1800 by 1100 lineup, Source to Native, transparent background with contact shadows. |
| `agent-source.png`, `agent-adapted.png`, `agent-native.png` | 900 by 1200 portraits for trainer slots. |

The renders use Cycles, the Standard view transform, and a shadow catcher, so they sit on any ground. They are masters. Convert to WebP during the site build.

The racks show rule capacity, not a live PP count. The battle board shows the live count.

## Protect shield and UI kit (`ui/`)

The shield is a hexagon split down a zigzag seam. Its face holds 16 hex cells, 8 per half: one per Protect PP under Scarlet/Violet rules. Under `protect-8`, the right half cracks away on the game's first Protect, leaving the 8 cells Champions allows. Under `protect-16` it stays whole. The cells can also go dark one at a time as the live PP count falls.

| File | Contents |
| --- | --- |
| `build_ui.py` | Computes the shield and kit geometry. Writes `shield-elements.json` and `kit-elements.json`. Standard library only. |
| `shield.svg` | The Glaxnimate drawing. Groups `shield-left` and `shield-right` each hold a face, a rim, and 8 cells (`shield-cell-01` to `-08` on the left, `-09` to `-16` on the right), plus the faint `shield-seam` shown only while whole. |
| `kit.svg` | A sprite of battle-screen symbols: `cursor-arrow` (lime selection arrow), `pp-pip-full` and `pp-pip-empty`, and `keycap` (a 12° slanted key frame; the key's label stays HTML text). |

Motion (GSAP, design pattern A): to crack, hide the seam, then move `shield-right` 14 px right and 10 px down and turn it 9° about (108, 80) while it fades to 35% opacity. Under reduced motion, show the cracked end state. Panel frames are CSS `clip-path` parallelograms, not drawings.

The empty pip uses the muted color because it carries meaning and needs 3:1 contrast against the ground. To change a shape, edit `build_ui.py`, run `python3 build_ui.py`, and redraw the SVG from its element list with the Glaxnimate MCP.
