# Study S: legal stat builds and pivot exposure

The first Speed milestone compares observed move order and the immediate damage
from two fixed pivot decisions under equivalent legal level-50 builds. It is a
mechanics and decision-exposure study, not an agent-training or win-rate study.
The separate public-evidence report below describes uncertainty about opponent Speed.

## Controls and acceptance criteria

Use clean Showdown revision `9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e`.
`gen9rulebreakspeedev` uses the Gen 9 doubles custom format unchanged.
`gen9rulebreakspeedsp` copies that format and uses only the pinned Champions
`statModify` function. PP, damage, abilities, switching, priority, Trick Room,
and every other mechanic stay Gen 9. These are experimental formats, not official
regulations or a comparison against the full Champions mod.

Both systems use the same species, moves, abilities, natures, level, and positions.
Separate upstream validators use each system's native mod plus Obtainable and
Species Clause. The runner verifies that validation actually enforces the 510 EV
and 66 Stat Point limits. Trusted custom-rule parsing fails loudly instead of
silently falling back to unrestricted Custom Game. Validation uses copies so that
validator normalization cannot change the declared battle teams. This checks
species/set legality, not official six-member VGC roster construction.

For 31 IVs at level 50, a Champions allocation of `n` points corresponds to
`max(0, 8*n - 4)` Gen 9 EVs in that stat. The per-stat point cap is 32. Some legal
66-point spreads exceed 510 EVs after conversion and have no legal equivalent;
the converter rejects those. The fixtures use matchable 65-point spreads.
Copying numeric EVs directly into a Champions set is not an equivalent build.

Acceptance requires legal teams, identical stats and paired move order for
matchable builds, an explicitly labeled minimum-Speed exception, legal action
execution, complete mirrored/seed/action/system evidence, paired damage estimates,
and regression coverage for rejected illegal builds and incomplete evidence.

## Frozen decisions

Incineroar (Blaze, Brave) chooses either Parting Shot into Hippowdon or a hard
switch to Rotom-Wash. Hippowdon (Sand Force, Impish) chooses Crunch into that slot.
Each side's Gyarados partner chooses Protect. There are no items, weather,
Intimidate, transformations, or damage from partner actions.

Three scenarios are frozen before evaluation:

| Scenario | Incineroar Speed: EV / SP | Hippowdon Speed | Meaning |
| --- | --- | --- | --- |
| Matched | 72 / 72 | 67 | Identical stats in both systems |
| Minimum legal Speed | 58 / 72 | 67 | Gen 9 permits 0 Speed IV; Champions requires 31 |
| Speed tie | 72 / 72 | 72 | Identical stats, with five opponent Speed points |

The minimum-Speed comparison preserves all non-Speed stats and investments.
It compares equivalent minimum-Speed intentions within the legal constraints;
it is explicitly **not** an exact-stat match. The other scenarios are exact matches.

Each scenario runs with normal conditions, pre-existing Trick Room, pre-existing
candidate Tailwind, and opponent Protect instead of Crunch. The field conditions
are fixture starting states, not a simulation of setup choices. Protect's higher
priority blocks Parting Shot, so that attempted pivot must be recorded as incomplete.

Sixteen independent four-part battle seeds come from Python RNG seed 79. Every
seed is shared across systems and action alternatives, with both candidate seats.
This produces 1,536 one-turn branches and 384 paired decision opportunities.
These are scripted complete-information probes. No policy receives hidden Speed,
and no inference about an agent's beliefs is made.

## Estimands and evidence

For each scenario and field condition, report the paired move-order change rate,
the fraction of Parting Shot attempts acting first, and the completion rate.
Report `pivot - hard switch` damage to the incoming Pokémon as a fraction of its
maximum HP. A negative value means the pivot preserves more incoming HP. Also
report the sum of outgoing and incoming damage fractions, each divided by that
Pokémon's own maximum HP, so transferring damage to Incineroar stays visible.
The cross-system contrast is `SP pivot effect - EV pivot effect`.

Pair actions and systems before averaging mirrored seats for each seed. The
existing percentile bootstrap computes 95% intervals over these 16 seed means
with 1,000 resamples and bootstrap seed 42. It preserves action/system/seat pairing.
Critical hits and damage rolls remain enabled; matched seeds do not guarantee
identical random draws after action paths diverge. These intervals describe this
fixed fixture cohort, not unseen teams, trained policies, hidden Speed, or human
skill. A zero interval in a deterministic control is not broad evidence of no effect.

`results.json` records full builds, seeds, configuration, counts, source hashes,
summary intervals, and the evidence checksum. `decisions.json.gz` retains every
branch's initial stats and PP, requests, choices, pivot completion, damage, and
full simulator log. Existing output directories with evidence are never overwritten.

## Reproduce

Point `SHOWDOWN_PATH` at a clean checkout of the pinned revision with its locked
dependencies installed. The command builds that checkout once, then runs fixtures:

```sh
uv run vgc-rulebreak compare-speed --trials 16 --seed 79 \
  --output-dir runs/study-s-comparison-legal-20261108
```

Run `uv run pytest tests/test_speed.py` for conversion, legality, pairing, CLI,
and live mechanics regressions. Reports and raw evidence stay under ignored `runs/`.

## Result: 2026-11-08

The full run completed all 1,536 branches. Exact-stat matched and tie builds had
identical move order and pivot effects across systems in all four conditions.
The minimum-Speed case changed move order in every normal and Trick Room pair;
Tailwind made Incineroar faster in both systems, and opponent Protect blocked
every Parting Shot attempt in both systems.

| Minimum-Speed condition | EV pivot first | SP pivot first | SP minus EV pivot effect on incoming HP lost (95% CI) |
| --- | --- | --- | --- |
| Normal | 0/32 | 32/32 | +0.1397 [0.1202, 0.1676] |
| Trick Room | 32/32 | 0/32 | -0.1397 [-0.1676, -0.1202] |

Under normal conditions the loss of a legal 0-Speed-IV build exposes Rotom-Wash
to Crunch after Parting Shot; the Gen 9 slow pivot lets Incineroar absorb the hit
before switching. The opposite holds under Trick Room. These are immediate HP
exposure differences conditional on the fixed matchup and actions.

An independent audit checked all matrix cells, unique seeds/seats/actions/systems,
source and evidence hashes, and recomputed move-order and incoming-damage contrasts.
The local `results.json` SHA-256 is
`4cc886c85e512516be4ed04ac91fbf29f2a486f57fb0c10c5ab190777030e5bb`;
the compressed evidence SHA-256 is
`b1718ffc666c3c861cfca198600130cacc02ba70bc93d1558a36c85be8e510e5`.
Compression metadata and simulator timestamps may differ on reruns; the frozen
configuration and estimates are reproducible.

Immediate damage exposure does not establish which pivot decision wins more games.
The fixed opponent, replacement, action pair, and starting states limit the result.
Future outcome rollouts require separate evaluation and must not reuse private
fixture state as agent observations.

## Opponent Speed uncertainty

`report-speed-uncertainty` reports the remaining possible unmodified level-50
opponent Speed stats from a deliberately narrow, player-information input. It
does not ingest complete-information comparison files, opponent requests, seeds,
private builds or raw simulator logs. Extra or missing fields fail validation.
No agent policy or frontend changes are needed for this report.

The public species/form's base Speed and the declared stat system generate the
initial legal possibilities using the formulas from the pinned simulator revision
above. Nature and investment remain unknown. Gen 9 allows 0–31 Speed IVs and
0–252 effective Speed EVs; Champions fixes IVs at 31 and allows 0–32 Speed points.
Each allocation is individually feasible within its system's total budget. The
report makes no assumption about other stats or how frequently builds occur.
The same bound can contain gaps, so the report retains the complete possibility
set as well as its minimum, maximum and count.

Input has exactly `base_speed`, `system` (`ev` or `sp`), and `observations`.
Each observation has exactly the fields shown in the committed synthetic example:

```sh
uv run vgc-rulebreak report-speed-uncertainty experiments/speed-public-example.json
```

The example is invented public evidence, not an evaluated game: the same opposing
Hippowdon acts before a 72-Speed ally, then after an 80-Speed ally on the next
turn. Both pairs use equal-priority moves in normal conditions. Its EV prior is
46–108 (63 possibilities); the intersection is 72–80 (nine possibilities).
These are logical possibilities conditional on the evidence, not a posterior,
credible interval, confidence interval or empirical performance result.

An observation records `turn`, the player's own unmodified `own_speed`, observed
`opponent_first`, both effective move priorities, `trick_room`, both Tailwind
flags, and `speed_order_certified`. The player's Speed can come from their own
request. Public move events establish order; their own build plus revealed move,
ability, item and field information must establish eligibility. Certification
must be false unless the evidence producer can exclude every other Speed/order
effect: boosts, paralysis, weather abilities, Choice Scarf, Quick Claw, lagging
items, Stall, priority abilities, Quash, After You, forced/called moves, missing
actions, and any intervening state change. Unknown context is skipped. This is
an explicit evidence-producer obligation, not an automatic replay certifier.
Differing move priorities are always skipped, including Protect versus Parting
Shot. Skips retain the prior uncertainty and appear with reasons in the report.

For certified equal-priority moves, normal order constrains opponent effective
Speed to be at least the player's if it acts first, and at most if it acts second.
Trick Room reverses these inequalities; Tailwind doubles the corresponding side's
Speed. Equality survives either observed order, including repeated observations.
Sets intersect across observations of one unchanged opponent species/form and
build; start a separate input for another Pokemon or a form/build change.
An empty set is labeled `inconsistent_evidence`, with null bounds, rather than
silently resetting or claiming a known Speed. Certification cannot justify
exposing an unobserved opponent stat.

Acceptance requires no-evidence and inconclusive cases to retain legal uncertainty,
tie-safe normal/Trick Room/Tailwind bounds, explicit contradictions and skip counts,
and strict rejection of private fields. Tests exhaustively retain every possible
true Speed under the supported order model. Live paired fixtures project only
own-request Speed, public order and declared starting context into this input;
hidden opponent Speed is used exclusively in assertions that it survives. Tests
also verify identical reports for identical public observations with distinct
hidden builds. This establishes conditional constraint soundness, not probability
calibration or the safety of an arbitrary future replay parser.
