# Study R: Protect PP by Rage Fist persistence

This experiment crosses Protect's 16 versus 8 maximum PP with Rage Fist's
persist versus reset-on-switch hit counter. All four formats copy the same pinned
Gen 9 Doubles Custom Game rules. The overlay composes the fixture-checked Study P
and Study R hooks; it does not import the Champions mod or change other PP,
stats, items, damage rules or available mechanics.

| Cell | Format |
| --- | --- |
| 16 PP, persist | `gen9rulebreakprotect16ragefistpersist` |
| 16 PP, reset | `gen9rulebreakprotect16ragefistreset` |
| 8 PP, persist | `gen9rulebreakprotect8ragefistpersist` |
| 8 PP, reset | `gen9rulebreakprotect8ragefistreset` |

Run after a completed Protect-only Study P result exists:

```sh
uv run vgc-rulebreak rage-fist-interaction \
  --study-p-result runs/protect-rerun-milestone/rerun_summary.json \
  --showdown-dir /tmp/vgc-factorial-showdown \
  --pairs 3 --max-turns 100 --workers 4 \
  --output-dir runs/study-r-factorial-complete-20261108
```

The input result must contain the pinned revision, the two isolated Protect
format IDs, a positive evaluation-game count and findings. A full Champions
comparison is rejected. The simulator must be a clean checkout of that revision
with its locked runtime dependencies installed. The runner builds it once and
uses `--skip-build` for each game. The output directory must be empty.
Four workers run the independent cells concurrently; reports retain a fixed cell
order. `--workers 1` runs the same design sequentially.

The frozen Study P specification and manifest supply held-out teams, opponents
and evaluation seeds. No search, training or policy tuning occurs. A fixed
HeuristicAgent supplies the competent reference; RandomAgent is a separate
switching diagnostic. These are fixed-policy mechanic comparisons, not learned
transfer or adaptation estimates. No hidden opponent state is passed to either
policy; policies receive their normal simulator requests and messages.

Each candidate/opponent/team pairing/seed/pair combination runs four cells in
each seat. The candidate keeps its team when seats reverse. The three team
pairings are the manifest's sorted upper triangle, so the bulky Annihilape team
faces itself and balance, and balance faces itself. The reverse balance-versus-
Annihilape assignment is outside this design. Every four-cell block and its
mirrored seat share a battle seed and two policy seeds. Fresh policy instances
restore RNG state before each game; calling RandomAgent.reset alone would not.
Seeds are derived with SHA-256 from the full pairing identity, without including
the mechanic cell. This removes format-specific seed offsets and mutable RNG
carryover. Different mechanics can still diverge in their future random draws.

Points are 1 for a candidate win, 0 for a loss, and 0.5 for a simulator tie or
the 100-turn limit. Stalled or missing-replay games fail. Reports retain
termination counts so finite-horizon censoring is visible. The paired contrast is:

```text
reset_at_16 = points(16, reset) - points(16, persist)
reset_at_8  = points(8, reset)  - points(8, persist)
interaction = reset_at_8 - reset_at_16
```

Positive interaction means the reset is more favorable to the candidate at 8 PP;
negative means it is less favorable. Both conditional PP effects are also saved.
Compute contrasts within complete four-cell blocks before aggregation. Average
all mirrored seats, pairs and matchup strata within each evaluation seed, then
bootstrap those seed means (1,000 percentile resamples, seed 42, 95% intervals).
This preserves four-cell pairing and within-seed dependence. These intervals
describe evaluation randomness for fixed policies, not training-seed uncertainty.
Only three evaluation seeds are available; intervals have limited precision.

`results.json` records every game, policy seed and compressed replay path.
`interaction_report.json` retains every four-cell block, seed-level contrasts,
candidate-level estimates and separate opponent/team strata. Each stratum retains
the shared harness's Protect choice/request-slot counters and games with an
observed PP depletion on either side. Protect request-slot counts can include
stale move slots of fainted actives; they are descriptive counters here, not a
rate denominator. Candidate executed Rage Fist uses, voluntary switch opportunities
and selected switches are also reported. Switch denominators exclude fainted
slots and use the existing [Study R definition](rage-fist.md).
These counts show exposure; switches alone do not prove a counter with accumulated
hits was reset. Source hashes, the simulator revision, full frozen manifest and
specification, and the prerequisite result hash/findings preserve provenance.
Raw results and replays remain under ignored `runs/`, following repository policy.

## Interpretation

A zero interaction in games that never exhaust Protect PP cannot show that the
mechanics never interact. It means the observed fixed-policy cohort did not
expose a PP-dependent reset effect. A degenerate bootstrap interval is conditional
on those seeds, teams and policies; it is not an equivalence bound for other play.
Do not manufacture stall incentives and then generalize to ordinary games. Keep
the heuristic and random cohorts, opponents and team pairings visible separately.

## Recorded result: 2026-11-08

The command above evaluated 864 games: 216 four-cell seat blocks, 108 mirrored
pairs, three evaluation seeds (101, 202, 303), two candidates, two opponents and
three team pairings. Every game ended in a win/loss; there were no ties, stalls
or turn-limit outcomes. Each candidate has 108 games per cell.

| Candidate | 16/persist PPG | 16/reset PPG | 8/persist PPG | 8/reset PPG | Interaction PPG (95% seed-bootstrap CI) |
| --- | --- | --- | --- | --- | --- |
| Heuristic | 0.6296 | 0.6296 | 0.6296 | 0.6296 | 0.0000 [0.0000, 0.0000] |
| Random diagnostic | 0.2778 | 0.2685 | 0.2778 | 0.2685 | 0.0000 [0.0000, 0.0000] |

All 12 candidate/opponent/team strata also have zero observed interaction. The
random candidate's conditional reset effect is -0.0093 PPG at either PP level
(95% CI [-0.0278, 0.0278]); the heuristic's is zero. The only stratum with a
nonzero conditional reset estimate is random versus RandomBaseline on bulky
Annihilape mirrors: -0.0556 PPG, CI [-0.1667, 0.1667], at both PP levels.
Neither reset interval excludes zero.

| Cell | Games | Candidate Rage Fist executions | Eligible switch opportunities | Selected switches | Games with observed Protect depletion |
| --- | --- | --- | --- | --- | --- |
| 16/persist | 216 | 111 | 520 | 141 | 0 |
| 16/reset | 216 | 110 | 523 | 145 | 0 |
| 8/persist | 216 | 111 | 520 | 141 | 0 |
| 8/reset | 216 | 110 | 523 | 145 | 0 |

The maximum executed Protect uses by any Pokémon in one game was five in every
cell. The minimum observed remaining Protect PP was 11 in the 16 PP cells and
3 in the 8 PP cells. PP scarcity did not bind. This is an observed fixed-policy
null interaction with switch exposure, not evidence of equivalence in other
teams, policies or games that exhaust Protect. Rage Fist fixture probes verify
the reset mechanic separately; the outcome data do not establish an aggregate
reset penalty or a claim about learned beliefs or human skill.

The run used Python 3.12.3, Node 24.20.0 and four simulator workers. Wall time was
425.71 seconds; summed per-game durations were 1,492.402 seconds (overlapping
workers). Training games: zero. The prerequisite was the existing 72-game
Protect-only rerun result, whose hash and findings are embedded in the report.

The local evidence is `runs/study-r-factorial-complete-20261108/`, including
864 compressed replays, `results.json` and `interaction_report.json`. The latter's
SHA-256 is `f3d076748294b3754c2c257bc70bf83edbeca4238ac7f0e988ecd88cb3b92921`.
An independent audit checked distinct game IDs and replays, all four cells per
block, identical battle/policy seeds and teams, both mirrored seats, outcome
scoring, source/prerequisite hashes and recomputed seed-cluster estimates.

## Acceptance checks

`tests/test_interaction.py` checks signed differences-in-differences, complete
cells, evaluation-seed clustering, fresh matched RNGs, mirrored seats, prerequisite
gates and saved replay provenance. `tests/test_rage_fist_formats.py` checks the
isolated Rage Fist pair and both PP levels of the factorial formats with manual,
pivot and forced switches, including hit counts, move power, damage, stats,
non-Protect PP, and Protect PP after returning through the battle stream.
