# Study F: full ruleset transfer

This milestone measures source performance loss and checkpoint recovery on
held-out synthetic teams when moving from `gen9doublescustomgame` to the complete
`gen9championsdoublescustomgame` mod. The target comes from the pinned
`champions-reg-2026-06` declaration. Both use Showdown revision
`9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e`; a different revision or tracked working-tree change is rejected.
These are custom-game fixtures, not a claim of official regulation legality.

## Protocol and acceptance criteria

`experiments/teams/full-transfer.json` freezes five four-member teams: rain and
sun for training, tailwind reserved for validation, and bulky and sand teams for
evaluation. Families and IDs are disjoint across splits. All members are level
50, neutral nature, default IVs, zero EV/SP investment, and no items. Packed
teams are identical in both domains. Their zero-investment stats match across
the two stat formulas. Teams are synthetic test fixtures created for this study;
the sourced OTS reference pool below is kept separate from these pilot teams.

The current policy inherits the competent heuristic and learns its five Protect
parameters with the existing cross-entropy optimizer. Source trains in Gen 9;
native trains independently in Champions with the same number of games. Adapted
starts from the exact final source parameters and trains in Champions. Each
adapted generation is evaluated; generation zero is the unchanged source on
target rules. No held-out outcome selects a checkpoint or changes training.
All other decisions stay heuristic. Native receives the same target training
budget as adaptation; adaptation additionally has the source pretraining budget.

Defaults freeze training seeds 11, 29, 47 and evaluation seeds 101, 202, 303,
one generation, population two, one elite, and one mirrored pair per matchup.
All unique test-team matchups, including self matches, are evaluated against
`HeuristicBaseline`. The candidate takes each team's side in turn. Each pair
shares a battle seed across seats, domains, and checkpoints. The agents observe
public battle messages and their own requests; they receive no opponent private
request or full OTS injection. This scope does not claim OTS-aware play.

Scores are points per game (win 1, draw 0.5, loss 0):

- Transfer loss = final source in source rules minus unchanged source in target rules.
- Recovery at generation g = adapted g in target rules minus unchanged source in target rules.
- Native gap at generation g = native in target rules minus adapted g in target rules.

Positive transfer loss means worse play after transfer; negative values mean
improvement. Recovery can also be negative. Report each candidate team and the
whole pool. First pair corresponding games, then average within each training
seed. Use 5,000 deterministic bootstrap samples of training seeds for 95%
intervals. These intervals describe training-seed variability conditional on the
fixed teams and evaluation seeds; they do not estimate generalization to all
teams. Three replicates and one generation are a plumbing pilot with low power.

Unfinished training games fail the run. An unfinished evaluation excludes its
entire matched block from every compared cell and is counted explicitly. Missing
cells, duplicate cells, missing mirrored seats, mismatched seed schedules, and
missing completed support for any training seed fail summarization. Never score
an unfinished game as a draw. Small or null intervals in this pilot cannot show
that the rulesets are interchangeable.

Acceptance requires an actual pinned-simulator run with a loss/recovery report,
per-team results, independently trained native reference, recorded checkpoints,
per-game results and compressed replays, configuration and input hashes, plus
tests for pairing, interval units, scoring, initialization, and split isolation.
There is no UI change. Sourced legal OTS matchups are covered below; bidirectional
Tera/Mega transfer remains a separate milestone. The opponent-pool comparison extends
this protocol without changing the original command's evaluation schedule.

## Reproduction

```sh
uv run vgc-rulebreak measure-full-transfer --output-dir runs/full-transfer-2026-11-09
```

Use a fresh empty directory. `--showdown-dir` overrides the local simulator
location. `--generations`, `--population`, `--elites`, `--pairs`, and `--workers`
allow an explicitly recorded larger budget; freeze these before inspecting test
outcomes. Each of the three roles trains for
`generations × population × 6 × pairs` games per training seed. At defaults,
there are 108 training and 216 evaluation games.

Outputs include `protocol.json`, `checkpoints/`, `results.json`, `replays/`, and
`transfer_report.json`. Raw data and learned checkpoints stay under ignored
`runs/`, consistent with repository policy. The protocol records simulator and
regulation IDs, exact formats, seed schedule, budgets, and team/regulation hashes.
The results retain checkpoint paths, battle seeds, teams, seats, completion
status, decision opportunities, timing, and replay references.

The result concerns the combined simulator ruleset change. These fixtures have
no Mega stones, and the policy has no learned Tera choices. They cannot answer
Study T, attribute a difference specifically to Protect or Rage Fist, estimate
human skill transfer, or establish an optimal metagame strategy.

## Pilot result: 2026-11-09

The default command completed 108 training and 216 evaluation games, with 216
compressed replay files. One evaluation game reached the turn limit; its matched
block was excluded from all four cells. This leaves 53 matched blocks (26 bulky,
27 sand). All three training replicates retain completed support. Evaluation
battle time summed to 244.173 seconds, excluding training and orchestration.

Each value below is the equally weighted mean of training-seed means. Intervals
are 95% training-seed bootstrap intervals, conditional on this frozen pool.

| Candidate team | Source on SV PPG | Source on Champions PPG | Transfer loss PPG [95% CI] | Recovery after one generation PPG [95% CI] |
| --- | --- | --- | --- | --- |
| Whole pool | 0.5490 | 0.5501 | -0.0011 [-0.0588, 0.0556] | 0.0000 [0.0000, 0.0000] |
| Bulky | 0.4676 | 0.3935 | 0.0741 [0.0000, 0.1111] | 0.0000 [0.0000, 0.0000] |
| Sand | 0.6296 | 0.7037 | -0.0741 [-0.1111, 0.0000] | 0.0000 [0.0000, 0.0000] |

Native and adapted target scores matched the unchanged source in every retained
game, giving native gaps of zero for both teams. There is no measured adaptation
recovery in this pilot. The pooled transfer interval includes zero, with team
estimates in opposite directions. This small fixture experiment does not resolve
a general transfer penalty or demonstrate that adaptation is unnecessary. Zero
recovery intervals reflect identical observed outcomes, not certainty about
unseen teams, larger training budgets, or other policy classes.

Artifacts remain in `runs/full-transfer-clean-2026-11-09/`. The recorded run used
`SHOWDOWN_PATH=/tmp/vgc-rulebreak-showdown-clean`, an isolated clean build of
the pinned revision; the pre-existing shared checkout was left untouched. The frozen manifest SHA-256
is `94c4d3e1e055adf759898e47039e16ebf884529aadc9a90db9d8f86077d410ca`;
the completed `transfer_report.json` SHA-256 is
`4927633cf69f3671f24e814d7fec12e20f4ac875a8bec5a1cac2e7c988b91f40`.

## Fixed and new opponent pools

```sh
uv run vgc-rulebreak measure-full-transfer --compare-opponent-pools \
  --output-dir runs/full-transfer-pools-2026-11-09
```

This extension tests whether the measured transfer and recovery persist against
additional team families. Candidate teams remain bulky and sand. The fixed
opponent pool contains those same two teams; the new pool contains snow and
electric-terrain fixtures frozen in
`experiments/teams/full-transfer-new-opponents.json`. Both pools use the same
`HeuristicBaseline` policy. This measures an opponent **team** distribution
change; it does not test a new opponent policy or an evolving ladder. All teams
retain the original synthetic, level-50, zero-investment custom-game scope.
New IDs, families, and packed teams must be disjoint from every original split,
and new teams never enter training or checkpoint selection.

Train each role once per training seed, with the original budget, then evaluate
the same checkpoints against both pools. Each pool uses the Cartesian product
of two candidate teams and two opponent teams, with each candidate playing both
seats. Thus the fixed-pool schedule here weights candidate/opponent assignments
equally, unlike the earlier unique-pair schedule. Its fixed-pool numbers should
not be subtracted directly from the earlier pilot's numbers.

Pool entries are paired by their frozen manifest order: bulky with snow, sand
with terrain. This pairing supplies common random numbers, not a claim that the
paired teams are strategically equivalent. Each evaluation seed, candidate
team, opponent slot, pair, and seat defines a block containing both pools and
all checkpoint/domain cells. Battle seeds match throughout that block. A game
that does not finish excludes all eight cells (at one generation), and the
report counts excluded blocks and unfinished games. Every candidate team must
retain support from all three training seeds.

The report gives `fixed/` and `new/` scores, transfer loss, checkpoint recovery,
and native gaps, plus signed `new_minus_fixed/` differences of every metric.
Differences are computed within completed blocks before averaging within each
training seed. The same 5,000-resample training-seed bootstrap supplies 95%
intervals for both pool metrics and their differences; these are conditional on
the frozen teams and evaluation seeds. A positive recovery difference means
more measured recovery on the new pool; a positive transfer-loss difference
means a larger transfer penalty there. A new-pool score difference also reflects
opponent difficulty and cannot by itself establish transfer failure.

Acceptance requires the paired statistical and contamination tests plus a real
pinned-simulator comparison. At defaults the extension runs 108 training and
576 evaluation games, preserves all compressed replays and checkpoints, and
records both pool memberships and the additional manifest hash in the existing
protocol and report files. Original artifacts remain separate. Small or null
recovery differences cannot establish generalization to unseen opponents.

## Legal sourced OTS reference matchups

```sh
uv run vgc-rulebreak build-ots-references \
  --output-dir runs/ots-reference-2026-11-09
```

`--showdown-dir` selects a clean checkout of the same pinned simulator revision.
The command validates the frozen source pastes offline, constructs every distinct
cross-team pairing, mirrors seats with identical seeds, and verifies actual open
team sheets before selecting four members. It stops at turn one, before any move;
these are reference matchup configurations, not evaluated policy results.

The existing `champions-reg-2026-06` file specifies mechanics on unrestricted
`gen9championsdoublescustomgame`. It does not define an eligible roster or item
pool. These references therefore declare **Regulation M-B** explicitly, using
`gen9championsvgc2026regmb` at the pinned revision. The [official announcement](https://champions-news.pokemon-home.com/en/page/776.html)
dates M-B from June 17 through September 9, 2026. This supplements the June
declaration without relabeling its earlier custom-game results. Teams from later
in M-B are included; this is not a sample of the June metagame.

The small, purposively chosen pool spans sand, snow and rain with Mega options:

| ID | Attribution and report | Source paste | Report date |
| --- | --- | --- | --- |
| `ots-sand` | [Lycopoky, The Dragon's Sand](https://lycopoky.wordpress.com/2026/07/11/the-dragons-sand/) | [79000b4543608f9d](https://pokepast.es/79000b4543608f9d) | 2026-07-11 |
| `ots-snow` | [Onion, Mega Froslass good-stuff](https://onion-poke.hatenablog.com/entry/2026/07/17/183155) | [3f601efc2858f387](https://pokepast.es/3f601efc2858f387) | 2026-07-17 |
| `ots-rain` | [freezai, Day 0 Mega Swampert Rain](https://teamsheet.gg/t/mega-swampert-rain-master-rank-zc4mut) | [a109e64a9539968e](https://pokepast.es/a109e64a9539968e) | 2026-06 (day unspecified) |

The English paste for Onion's original snow team is linked by
[JoeyvanDiepen's derivative-team report](https://teamsheet.gg/t/m-b-mega-froslass-mega-gyarados-radal8).
Use that original paste, not the derivative `99e73d8b17c077d0`, which the pinned
validator rejects for Sneasler's Poison Point ability. No ability is silently
corrected. `experiments/teams/full-transfer-ots.json` records both the original
report and the page establishing the paste link, authors, report date precision,
retrieval date (2026-11-09), local paste path, SHA-256 and reuse terms. The local
files retain the paste text from each public `/json` endpoint, including source
line endings and whitespace. No report prose is copied and no blanket license
is inferred for third-party material.

Acceptance requires all three six-member, four-move teams to pass the regulated
TeamValidator, including learnsets, ability/item availability, species and item
clauses, max IVs and the Champions per-stat/total investment limits. Custom Game
alone is insufficient. Showdown normalizes the rain paste's pre-labeled Mega
Swampert and Mega Venusaur to their starting base species; the report records
these changes alongside the original source hashes. Items, abilities, moves,
natures and investment remain as sourced. No substitution is made for SV.

The 2026-11-09 run passed all three teams and **18 preview setups**: three
cross-team pairs, two seats and three seeds (101, 202, 303). Both complete public
six-member sheets appeared before selection in every setup, followed by four
selected members and two active leads per side. The format replaces optional
`Open Team Sheets` with `Force Open Team Sheets`; this changes disclosure, not
team legality. In the pinned Champions implementation nature is public. Stat
points and IVs are private and must be absent from the public sheet. The probe
checks public species, items, abilities, natures and moves against validated sets.

`ots_references.json` contains the full source metadata, input/code hashes,
validated private teams and packed strings, normalization records, mirrored
schedule, and actual public `showteam` messages. Keep it under ignored `runs/`.
Private configurations are for reproducibility, not opponent observations.
Existing training and evaluation commands do not load this pool; all references
are reserved from training and checkpoint selection. OTS-aware policy evaluation,
SV-compatible conversions, transfer estimates on these teams, and Study T's
bidirectional mechanic comparison require their own protocol. Validator approval
certifies the pinned simulator's M-B interpretation, not agreement with every
detail of the game software or representative tournament strength.
