# Showcase design

The plan for the public showcase: brief, concept, art direction, structure, and the data it needs. The research brief is [`docs/showcase.md`](../docs/showcase.md). Original asset sources are in [`design/`](design/README.md).

## Brief

- **Subject.** VGC Rulebreak, a study of whether habits learned under one ruleset cost games under another. The first study changes one rule: Protect drops from 16 PP (Scarlet/Violet) to 8 PP (Champions).
- **Audience.** VGC players who know Showdown and Champions, and researchers who read RL transfer work. Both will check the numbers.
- **Job.** Let a reader watch real evaluated games, see what each agent could do on every turn, and trace every number to its artifact.
- **What the data says now.** In 1,188 held-out games across 33 checkpoints, no agent ran out of Protect PP. Agents used Protect on about 5% of the turns where it was legal, so the 8 PP cap never bound and there was no habit to recover (`JOURNAL.md`, 2026-10-23). The site leads with that finding. It does not draw recovery curves.
- **Constraints.** No Pokémon art, sprites, logos, Poké Ball, or the game's font (`JOURNAL.md`, 2026-10-22). Species appear as names and stat sigils. A visible "unofficial fan research" note sits in the colophon and the battle screen footer.

## Concepts

| Concept | Territory | Anchor | Structure | Orig | Fit | Build | Port (low is good) | Struct |
|---|---|---|---|---|---|---|---|---|
| **The Champions client** | The subject's own material | Players read Champions battles through its slanted doubles HUD, move panels with large PP counts, and a button-hint row | The site is a game client. Screens replace pages | 4 | 5 | 4 | 1 | 5 |
| The PP ledger | A formal system | The study is about one counter: Protect PP | One long ledger of every Protect press, one row per use, scrolled like a match log | 4 | 3 | 5 | 2 | 3 |
| The regulation calendar | Place and time | VGC moves through dated regulations | A season calendar. Each study is a regulation slot | 3 | 3 | 4 | 3 | 4 |

**Pick: the Champions client.** It is the only concept a VGC player recognizes in the first second, and its screens map one to one onto the brief's three parts. The ledger is kept as the Battle Log escape hatch.

## Concept card

```
Idea:         A fan-made Champions client that plays back the study's real games and tells you what they showed.
Metaphor:     The game client: title screen, battle screen, team select, battle log, regulation select.
Signature:    The rule switch on the Protect button. "16/16" splits into "8/8" and the hex shield cracks in two,
              then the counter keeps playing the real game and never drops past what was used. On every game so far
              it stops well short of zero.
Emotion:      The first 3 seconds feel like booting a match you are about to watch, then a plain sentence lands.
Motion verb:  Snap like a menu cursor. Panels slide in on their slant, the cursor arrow jumps and settles, counters tick.
Screenshot:   The doubles battle screen mid-turn: four sigils on the field, the Protect panel reading 7/8, the yellow
              arrow on the agent's actual choice, and the provenance panel open beside it.
Structure:    The site is a client. You move with menus, the cursor, and the hint row (real keys). One unit is a game;
              opening it boots the battle screen at turn 1.
Escape hatch: Battle Log, a plain table of every evaluated game with real links, filterable by agent, ruleset, seed,
              and checkpoint. One key (L) and one tap away on every screen.
```

## Structure plan

### Desktop

```
                         ┌─────────────────────────┐
                         │  TITLE  /               │   the finding as one sentence,
                         │  Press start            │   agent lineup, three menu items
                         └───────────┬─────────────┘
         ┌───────────────────────────┼────────────────────────────┐
         ▼                           ▼                            ▼
 ┌───────────────┐         ┌──────────────────┐         ┌──────────────────┐
 │ REGULATIONS   │         │ BATTLE LOG       │◀──L─────│ any screen       │
 │ /studies      │         │ /log             │         └──────────────────┘
 │ Study P open, │         │ table, filters   │
 │ R, Speed,     │         │ 1,188 rows       │
 │ full transfer │         └────────┬─────────┘
 │ locked        │                  │ Enter / click a row
 └──────┬────────┘                  ▼
        │ Enter          ┌──────────────────────────┐
        ▼                │ BATTLE  /game/<id>       │  ←/→ turn, P switch side,
 ┌───────────────┐       │ ?turn=N deep-links       │  I provenance, Esc back
 │ STUDY P       │──────▶│ text account beside board│
 │ /studies/p    │ games └──────────┬───────────────┘
 │ the finding,  │                  │ T
 │ PP-use chart  │                  ▼
 └──────┬────────┘       ┌──────────────────────────┐
        │ Teams          │ TEAM SELECT /teams/<id>  │  open team sheets, sigils,
        └───────────────▶│ matchup results          │  cross-play table
                         └──────────────────────────┘
 Colophon /about: method, data downloads, licences, "unofficial fan research". Reached from the title menu and the hint row.
 404: a battle screen with an empty field. "This game was never played."
```

Esc always goes back one screen, the browser back button does the same, and every screen has its own URL with server-rendered HTML. The current screen's name sits top left in the panel slant, in the game's own terms, such as "Battle 0412, turn 6".

### Phone (390 px)

```
┌──────────────────────┐
│ screen name     [≡]  │  ≡ opens the client menu: Title, Study P, Battle Log, Teams, About
├──────────────────────┤
│ opponent pair        │  two sigils, HP bars
│ ──────────────────── │
│ candidate pair       │
├──────────────────────┤
│ move panel (PP big)  │  shows the slot whose decision is current
├──────────────────────┤
│ text account, turn N │  scrolls
├──────────────────────┤
│  ◀ turn   ▶  (i)  L  │  fixed bottom bar: 48 px targets, replaces the hint row
└──────────────────────┘
```

The board stacks vertically. Swipe left and right also steps turns. The Battle Log becomes cards, one game per card, with the same filters in a sheet.

## Views

### Title

```
┌───────────────────────────────────────────────────────────────────────┐
│ VGC RULEBREAK                                         unofficial fan  │
│                                                       research        │
│  In 1,188 held-out games, no agent ran                                │
│  out of Protect.                          [ lineup render: Source,    │
│                                             Adapted, Native ]         │
│  Cutting Protect from 16 PP to 8 changed                              │
│  nothing we could measure. Here is why.                               │
│                                                                       │
│  ▶ Study P: Protect PP                                                │
│    Battle Log                                                         │
│    About this study                                                   │
├───────────────────────────────────────────────────────────────────────┤
│ ↑↓ Select   Enter Open   L Battle Log                                 │
└───────────────────────────────────────────────────────────────────────┘
```

The headline is the `<h1>` and the LCP element. The lineup is an `<img>` (WebP from `agents-lineup.png`). The cursor arrow idles with a 2 px bob on the page clock.

### Battle (the signature screen)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ╱ Battle 0412, turn 6 of 14 ╱                       protect-8  seed 101  (i) │
│                                                                              │
│              [sigil] Kingambit  ████▒▒ 62%   [sigil] Amoonguss ██████ 100%   │
│                                                                              │
│   [sigil] Incineroar ███▒▒▒ 41%   [sigil] Rillaboom █████▒ 88%               │
│                                                                              │
│ ┌ Incineroar ─────────────────────┐   ┌ Turn 6 ──────────────────────────┐   │
│ │ ▶ Protect              7 / 8    │   │ Native used Protect on           │   │
│ │   Fake Out             10 / 10  │   │ Incineroar. Protect was legal    │   │
│ │   Flare Blitz          14 / 15  │   │ in 2 of 2 slots this turn.       │   │
│ │   Parting Shot         20 / 20  │   │ Rillaboom used Grassy Glide...   │   │
│ └─────────────────────────────────┘   └──────────────────────────────────┘   │
│ ← → Turn   P Switch side   I Provenance   L Battle Log   Esc Back            │
└──────────────────────────────────────────────────────────────────────────────┘
```

- The arrow marks the move the agent actually chose. The panel shows the request that side received, so disabled and zero-PP moves show as the agent saw them. The site never invents a "better" move: the brief's blunder alternatives need repeated rollouts, which do not exist yet.
- The provenance panel (I) slides out on the right: game ID, eval seed, battle seed, checkpoint, agent, ruleset, opponent, simulator revision, and a download link for the replay JSON.
- The text account is an ordered list of the turn's protocol events in plain sentences. It is the accessible form of the board and is in the HTML on first load.
- Sigil motion follows `design/README.md`: shrink with HP, the cell pulses on Protect, drain to an outline on a knockout.

**Rule switch (signature).** On the first Protect of a game under `protect-8`, the counter shows "16/16" for 200 ms, splits along the hex seam into "8/8", and the Glaxnimate hex shield over the slot cracks in two halves that settle apart. Then the counter ticks down with each real use. Under reduced motion it shows "8/8, the Champions cap" as text. Under `protect-16` the shield stays whole.

### Study P

The finding page. One chart and three facts, each with its artifact link.

```
┌──────────────────────────────────────────────────────────────────────┐
│ ╱ Regulations ╱ Study P: Protect PP ╱                                │
│                                                                      │
│ Did 16 PP habits cost games under 8 PP?                              │
│ Not in this setup. The cap never bound.                              │
│                                                                      │
│  Protect use per legal turn, by checkpoint   ┌ Ran out of PP ──────┐ │
│  ▁▂▂▂▂▂▂▂▂▂▂  source   16 PP                 │ 0 of 1,188 games    │ │
│  ▁▁▁▁▁▁▂▂▂▂▂  native    8 PP                 ├ Held-out points ────┤ │
│  ▂▂▂▂▂▂▂▂▂▂▂  adapted   8 PP                 │ source 0.50 → 0.42  │ │
│  bands: min and max across seeds 11/29/47    │ native 0.33 → 0.42  │ │
│  n = legal-Protect turns per point           │ adapted 0.28 → 0.26 │ │
│                                              │ ±0.083 per game     │ │
│  What would make this testable               └─────────────────────┘ │
│  Longer games, an opponent that rewards Protect, more games per      │
│  checkpoint.                                                         │
│                                                                      │
│  ▶ Watch a game   Teams   Download recovery.json                     │
└──────────────────────────────────────────────────────────────────────┘
```

The chart plots Protect use rate, not points, because use rate is what explains the null. It shows seed bands and opportunity counts, and the caption says the opponent is the held-out HeuristicBaseline split. Follow the `dataviz` skill when building it.

### Regulations

A horizontal list of study slots in the regulation-select style: Study P open, Rage Fist, Speed, full Champions transfer, and Tera/Mega locked with "not run yet". Locked slots are real text, not greyed decoration.

### Team select

Open team sheets for both sides with sigils, items, abilities, and moves, then the cross-play results for that matchup with links into its games.

### Battle Log (escape hatch)

A real `<table>`: game, agent, checkpoint, ruleset, seed, result, turns, Protect uses, legal-Protect turns. Sortable headers, filter chips, and query-string state so filters deep-link. Every row links to its battle.

### 404

The battle screen with an empty field and the text account reading "No game with this ID was played." The hint row offers Battle Log and Title.

## Art direction

### Palette

Taken from the Champions reference: deep violet ground, white ink, lime selection. Shifted off the game's exact values. The acid-green-on-dark default is allowed here because the reference uses it; lime appears only on the selection arrow, focus, and the active hint, never as a surface.

| Role | Hex | Use |
|---|---|---|
| ground | `#17112B` | page |
| panel | `#2A2148` | slanted panels, move panel |
| line | `#4A3F73` | panel borders, chart grid |
| ink | `#FFFFFF` | text |
| muted | `#B9B2D6` | secondary text, axis labels |
| select | `#C8F542` | cursor arrow, focus ring, active hint key |
| source | `#FF9F2E` | Source agent data and racks (matches the Blender amber glow) |
| native | `#45D6EE` | Native agent data and racks (matches the Blender cyan glow) |
| adapted | `#E4E1FF` | Adapted agent data (matches the lavender arm) |

Type colors come from `design/sigils/sigils.json` and appear only inside sigils and type tags. Check every text pair for WCAG AA during the build.

### Type

- **Display and UI:** Chakra Petch 600 and 700 (Google). Angular, wide, reads as game UI without copying the game's font. Uppercase only for the hint row keys.
- **Data and provenance:** IBM Plex Mono 400 and 500 (Google). Game IDs, seeds, PP counts, revisions.
- **Body:** Chakra Petch 400 at 17 px, line height 1.5.
- Fluid scale: `clamp()` from 390 to 1440 px. Display tracking -0.02em at the headline size, 0 at UI sizes. PP counts are tabular figures.

### Grid, shape, motion

- **Grid:** 12 columns, 24 px gutter on desktop; 4 columns, 16 px on phone. The battle field uses its own two-row doubles layout inside columns 1 to 12.
- **Shape:** one rule. Panels are parallelograms with a 12° slant (`clip-path`), no rounded corners. Sigils keep their hex.
- **Motion:** GSAP on one clock. One ease, `power3.out`, for entries; `steps()` for counters. Panels slide 24 px along their slant in 280 ms, the cursor jumps in 120 ms with a 2 px overshoot, and big panels move slower than small ones. Stagger 40 ms. Page changes slide the outgoing panels off on their slant and the new ones in, with no fade-up. Reduced motion: no slides, instant states, all text visible.
- **Idle:** the cursor arrow bobs, and on the battle screen the active slot's sigil cell breathes at 0.5 Hz. Both stop off screen and under reduced motion.

### Assets

| Asset | Tool | Status |
|---|---|---|
| Stat sigils, 21 species | Glaxnimate | done, `design/sigils/` |
| Agent lineup and portraits | Blender | done, `design/agents/` |
| Hex Protect shield, whole and cracked halves | Glaxnimate | to draw |
| Cursor arrow, panel frames, PP pips, key glyphs for the hint row | Glaxnimate | to draw |
| OG image: the battle screenshot frame | generated from the built page | at ship |

## Stack

Astro with static output and TypeScript, with the battle screen as one island. The site is a content showcase over static data, and every screen needs server-rendered HTML. GSAP for motion, no WebGL. Replays load as static gzip JSON per game.

## Data contract

The site reads files produced by the CLI. Nothing is computed in the browser beyond replaying the log.

| Need | Source | Status |
|---|---|---|
| Per-game record and replay | `evaluate --output-dir`: `results.json`, `replays/gNNNNN.json.gz` | exists for all 99 checkpoint runs |
| Study P curves | `summarize-recovery` output | exists |
| Board state per turn (HP, PP, field) | replay log plus each decision's request | exists; the client parses it |
| Team sheets | team manifest | exists |
| Blunder alternatives with repeated rollouts | not implemented | gap: the site shows actual choices only |
| A curated set of featured games | a documented selection rule | gap: pick by rule (for example, most Protect uses per checkpoint), and print the rule on Study P |

A small export step will copy the selected runs from `runs/` into `web/public/data/` with a manifest. 1,188 replays at about 9.5 KB each is about 11 MB, which is fine for static hosting.

## Genericness test

- **Skeleton:** no navbar, hero, sections, or footer. The site is client screens with a hint row and Esc, and the Battle Log is the list view. Passes.
- **Title:** a generic model would put "Explore the research" over a gradient. Changed to the finding stated as a fact, plus the lineup render.
- **Chart:** a generic model would plot win rate with a rising line. Changed to Protect use rate with depletion at zero, because that is what explains the result.
- **Signature:** a generic model would add a particle shield on hover. Changed to the rule switch, which only fires on a real Protect press in a real game.
