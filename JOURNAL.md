# Journal

## 2026-11-09: Build legal sourced OTS reference matchups #milestone #decision

Freeze attributed public sand, snow and rain pastes for Study F in a separate
reference-only pool. Record report/paste links (including the intermediary
link for Onion's English paste), publication date precision, retrieval date,
reuse terms and exact source hashes. Reject the derivative snow paste's illegal
Poison Point Sneasler rather than silently correcting it; use the linked original
team instead. Keep raw paste text unchanged and record validator normalization
of the rain team's pre-labeled Mega species to starting base forms.

The existing June Champions declaration names an unrestricted custom-game mod,
so it cannot certify legal roster/items. Validate these references specifically
against pinned Showdown Regulation M-B, effective from June 17, and cite its
official announcement. Later M-B reports do not make this a June usage sample.
Do not change the completed synthetic pilots or infer source-domain legality.

Add `build-ots-references` to validate all sets and verify real public sheets
before default bring-six/pick-four selection. The 18 setups cover three distinct
pairs, mirrored seats and three matched seeds. Champions nature is public;
investment and IVs stay private. Preserve private configurations, public sheets,
normalizations, schedule and hashes in an ignored run report. This completes the
reference-building milestone without policy outcome claims, OTS-aware agent
training, matched SV conversions, or frontend changes.

## 2026-11-09: Compare fixed and new full-transfer opponent pools #milestone #decision

Extend `measure-full-transfer` with `--compare-opponent-pools`. Keep the original
training split, five-parameter policy, native budget, candidate teams and
heuristic opponent policy. Freeze additional snow and electric-terrain teams as
evaluation-only synthetic fixtures, disjoint in ID, family and packed team from
every original split. This tests a team-distribution shift; new opponent
policies and an evolving ladder are outside this milestone's claim.

Evaluate each candidate against every opponent in each equally sized pool,
mirroring its seat while retaining its team. Pair fixed/new opponent slots with
common battle seeds and identical frozen checkpoints. Report per-pool transfer
loss, each checkpoint's recovery and native gaps, and paired new-minus-fixed
differences. Bootstrap training-seed means, conditional on the finite pools.
Exclude every compared cell when any member of a block is unfinished. The new
Cartesian schedule gives equal weight to candidate/opponent assignments, so its
fixed-pool scores are not directly comparable to the earlier unique-pair pilot.

Keep the original command's schedule and artifacts intact. Store the extension's
pool definitions, input hashes, checkpoints, per-game results and compressed
replays under its own ignored run directory. Legal sourced OTS reference
matchups remain the next Study F milestone. No frontend files change.

## 2026-11-09: Measure full-ruleset transfer on held-out teams #milestone #decision

Added Study F's `measure-full-transfer` pipeline and protocol. The existing
Protect-only comparison cannot complete this milestone: this run instead moves
from Gen 9 doubles custom game to the complete pinned Champions custom-game mod.
Reuse the established five-parameter Protect policy and CEM optimizer, with
source pretraining, exact source initialization for target adaptation, and an
independent native reference receiving the same target training budget. This
measures the combined ruleset effect for this policy class.

Freeze new synthetic four-member rain/sun training teams, reserve tailwind for
validation, and hold out bulky/sand families. Zero EV/SP investment, level 50,
neutral natures and identical packed teams avoid an accidental illegal stat
allocation conversion. This is deliberately a custom-game benchmark. Official
legal sourced OTS matchups and changing opponent pools remain separate Study F
items; Tera/Mega transfer remains Study T. The agents use public battle messages
and their own requests; full OTS injection is not claimed.

Pair evaluation games by seed, team assignment and seat across every checkpoint
and domain. Report points per game, signed transfer loss, recovery at each
adapted generation, native gaps, and per-candidate-team results. Bootstrap
training-seed means, conditional on the frozen evaluation pool. Fail unfinished
training games; exclude incomplete evaluation blocks across all cells and report
them. Preserve checkpoints, configuration/input hashes, game records and every
compressed evaluation replay under ignored runs/.

The default pilot used seeds 11/29/47, evaluation seeds 101/202/303, one generation,
population two, and one mirrored pair: 108 training games and 216 evaluations.
One turn-limit game excluded one matched block, leaving 53. Pooled transfer loss
was -0.0011 PPG (95% training-seed CI [-0.0588, 0.0556]); bulky loss was +0.0741
and sand loss -0.0741. Recovery and native gaps were zero in retained games.
The protocol records the full result and artifact hashes. This low-power pilot
resolves no general transfer penalty and supports no claim about human skill or
metagame optimality. No frontend implementation was required.

## 2026-11-08: Report opponent Speed uncertainty from public evidence #milestone #decision

Added `report-speed-uncertainty` and a strictly typed constraint engine with a
closed input schema. Public base Speed and the declared EV/SP system generate
all legal level-50 Speed possibilities with unknown nature and investment.
Only the player's own stat, observed move order and explicitly certified public
context narrow the set. Tailwind and Trick Room are supported; unequal move
priorities and uncertified contexts are skipped with reasons. Ties survive both
orders, repeated observations intersect, and contradictions produce an explicit
empty set with null bounds. No probabilities or usage assumptions are invented.

The boundary accepts neither complete simulator records nor opponent requests,
seeds, IVs or actual Speed. The caller must certify no unmodeled Speed/order
effects and track one unchanged opponent form/build. This deliberately scoped
report is not an automatic arbitrary-replay certifier or a policy change. Full
private fixture evidence remains audit-only. The protocol documents certification
obligations, acceptance criteria and limitations. The committed synthetic public
example narrows the EV prior from 63 values (46–108) to nine (72–80).

Added 39 synthetic cases for priors, tie-safe constraints, exhaustive support
soundness, confounds, contradictory evidence, strict private-field rejection,
hidden-build invariance and CLI validation. Extended the existing live Speed
fixture to project own-request Speed and public order/context into the engine;
actual opponent Speed is used only to assert that the inferred set retains it.
No frontend implementation was required.

Validation passed: all 256 Python tests including live simulator checks, strict
mypy, Ruff lint/formatting, source/wheel builds, installed-wheel specification and
uncertainty commands, pip-audit, Astro check, ESLint, the 1,196-page build, five
browser/accessibility tests and Gitleaks. Browser checks and dependency audits
required access outside the sandbox. npm audit passes the CI high-severity
threshold with the same ten existing moderate findings.

## 2026-11-08: Compare legal Speed builds and pivot exposure #milestone #decision

Added `compare-speed`, two experimental stat-only doubles formats, and the
protocol/results in `docs/speed.md`. Both formats keep Gen 9 battle mechanics;
the SP variant adopts only the pinned Champions `statModify` function. Separate
native-mod Obtainable validators check species, moves, abilities, IVs and stat
budgets. Explicit trusted custom-rule parsing avoids Showdown's silent fallback
to unrestricted Custom Game; regressions reject illegal IVs and point spreads.

At level 50 with 31 IVs, n Stat Points match `max(0, 8*n - 4)` EVs. The converter
rejects legal Champions spreads without a legal 510-EV counterpart. Exact matches
and Speed ties are separate from the unavoidable minimum-Speed exception: Brave
Incineroar has 58 Speed with Gen 9's legal 0 IV and 72 with Champions' required
31 IV. Its non-Speed stats remain matched; Impish Hippowdon has 67 Speed.

The fixed decision comparison is Parting Shot versus a hard switch to Rotom-Wash,
against Crunch, with protected partners. Normal, pre-existing Trick Room,
candidate Tailwind, and opposing Protect fixtures use 16 shared battle seeds and
both seats. All 1,536 one-turn branches completed. Exact-stat matches had no
cross-system move-order or pivot-exposure differences. Minimum-Speed move order
reversed in all normal and Trick Room pairs. The SP-minus-EV contrast in incoming
damage from pivoting versus hard switching was +0.1397 maximum-HP fraction in
normal conditions, 95% CI [0.1202, 0.1676], and -0.1397 under Trick Room,
[-0.1676, -0.1202]. Intervals bootstrap paired seed means after averaging seats.

This measures immediate damage exposure, not win probability, optimal regret,
learned behavior or hidden-Speed inference. Full private stats are fixture audit
evidence and are never passed to an agent. The next Speed roadmap item remains
unchecked. Configuration, source hashes, initial stats/PP, requests, legal choices,
completion, damage and full branch logs are retained under ignored
`runs/study-s-comparison-legal-20261108/`. An independent audit verified complete
matrix coverage, source/evidence hashes and the reported primary contrasts.
The protocol records report and evidence checksums.

Validation passed: 217 Python tests (including 20 new Speed cases), strict mypy,
Ruff lint/formatting, CJS syntax checks, source/wheel builds, installed-wheel spec
and live Speed commands, pip-audit, Astro check, ESLint, the 1,196-page build,
five browser/accessibility tests, and Gitleaks. npm audit passes CI's high-severity
threshold with the same ten existing moderate findings. A clean local clone of
the pinned simulator avoided modifying the available checkout's changed lockfile.
No frontend implementation was needed.

## 2026-11-08: Measure Protect PP by Rage Fist interaction #milestone #decision

Added `rage-fist-interaction` and four combined Gen 9 formats by composing the
independently fixture-checked Protect and Rage Fist hooks. A completed Protect-only
Study P result and a clean pinned simulator checkout are required. The runner
builds once, then evaluates fixed heuristic and random policies with fresh shared
battle/policy seeds in every four-cell block and mirrored seat. Four workers run
independent cells; recording order is deterministic. Candidate teams stay fixed
when seats reverse. The three upper-triangle team pairings, evaluation seeds and
opponents come from the frozen Study P controls. No training or tuning occurs;
random is a switching diagnostic, reported separately from the competent baseline.

The estimand is `(8-reset - 8-persist) - (16-reset - 16-persist)` in candidate points
per game. Intervals bootstrap whole evaluation-seed means, preserving matched
cells, seats and strata; they do not represent training-seed uncertainty. Reports
retain conditional mechanic effects, all block outcomes, opponent/team strata,
switch opportunity counts, PP exposure, termination, full configuration, source
hashes and one compressed replay per game. Compact simulator choices after the
first active slot faints are normalized with explicit passes before switch-cost
slot assignment; a regression covers this real recorded-request edge case.
The protocol documents the shared Protect counters' stale-slot limitation and
does not use those counters as a rate denominator.

Ran 864 games (216 complete four-cell blocks; 108 mirrored pairs) on seeds
101/202/303, three pairs per matchup and a 100-turn limit. Every game completed
with a win/loss. Heuristic PPG was 0.6296 in every cell. Random PPG was 0.2778
with persistence and 0.2685 with reset at either PP level; its conditional reset
effect was -0.0093 PPG, 95% CI [-0.0278, 0.0278]. Both candidates and all 12
opponent/team strata had observed interaction 0.0000, conditional CI [0, 0].
Protect was used at most five times by one Pokémon in a game; minimum remaining
PP was 3 under the 8 PP cap. Thus this result does not establish absence of an
interaction under scarcity or equivalence outside these fixed policies. Each
persist cell had 520 candidate switch opportunities and 141 switches; each reset
cell had 523 and 145. The run took 425.71 wall seconds with four workers.

The reproducible command, estimates, limits and report checksum are recorded in
`docs/rage-fist-interaction.md`. Evidence stays under ignored
`runs/study-r-factorial-complete-20261108/`. An independent audit verified all
864 replays, matching seeds and teams, complete blocks and mirrored seats,
outcome scoring, source hashes, prerequisite provenance and recomputed intervals.

Validation passed: 197 Python tests, strict mypy, Ruff lint and formatting, source
and wheel builds, installed-wheel specification checks and live requests for all
four formats, pip-audit, Astro check, ESLint, the 1,196-page static build and five
Playwright/accessibility tests. npm audit meets CI's high-severity threshold with
ten existing moderate findings. No frontend implementation was required.

## 2026-11-07: Estimate Rage Fist switch costs per opportunity #milestone #decision

Added `estimate-switch-cost` and `src/vgc_rulebreak/switch_cost.py` for the isolated
Study R formats. Each unfainted active Rage Fist user with both a legal voluntary
switch and a legal move contributes one opportunity, including decisions to stay.
The partner's switch reserves its destination. Forced replacements, known trapping,
preview, waiting and fainted slots are excluded; missing request evidence fails.

A chosen switch is compared with a prespecified first legal move in request order,
holding the partner's action fixed. Paired simulator and opponent seeds estimate
signed stay-minus-switch points against HeuristicBaseline and RandomBaseline;
negative costs remain negative. This fixed comparator avoids selecting the largest
noisy alternative estimate and measures a specific alternative, not optimal regret.
Future candidate actions use the heuristic continuation policy. Reports separate
formats and opponents, pool counts before dividing, retain all opportunity records
and paired rollout evidence, report termination and turn-limit counts, and use null
rates when there are no opportunities. Per-decision intervals bootstrap paired
trials; aggregate intervals bootstrap whole replay games conditional on their cost
estimates. Neither substitutes for training-replicate uncertainty.

Fixed shared replay reconstruction so a player-2 branch stops before the entire
simultaneous decision step, avoiding a blocking half-submission. Rollouts now verify
the reconstructed request against the saved target and expose termination reasons.
The protocol in `docs/rage-fist.md` documents hidden-state conditioning, finite-horizon
scoring, comparator limitations, exploratory costly flags and the inability to infer
a causal reset effect from different format cohorts alone. The Protect interaction
remains a separate milestone. No frontend implementation was required.

Validation passed: the full Python suite (173 tests), the additional player-2
atomic-step regression, strict mypy, Ruff lint and formatting, source and wheel
builds, installed-wheel CLI and specification checks, pip-audit, Astro check,
ESLint, a 1,196-page static build, five Playwright tests, and staged secret scanning.
The npm audit passes the high-severity threshold with ten existing moderate
findings. Live tests cover both formats and both candidate seats. An eight-rollout
CLI smoke report and the four live fixture reports are retained under ignored
`runs/study-r-switch-cost-validation/`; these tiny synthetic cohorts validate the
estimator and are not population estimates or evidence of a causal reset effect.

## 2026-11-07: Isolate Rage Fist hit-counter persistence #milestone #decision

Added `gen9rulebreakragefistpersist` and `gen9rulebreakragefistreset` as copies
of the pinned Gen 9 Doubles Custom Game format. The reset variant adds only an
`onSwitchOut` hook that clears `timesAttacked`; the persist variant keeps Gen 9
behavior. A separate repository-owned CommonJS overlay loads alongside the
Protect overlay in `ShowdownProcess`, leaving the upstream checkout untouched.
Using Gen 9 for both arms avoids importing Champions' PP, stat, or other changes.
Protect remains at 16 maximum PP in both arms; the future Protect interaction
experiment and switch-cost evaluation remain separate roadmap items.

Live fixtures compare every mechanics-related format setting with the base,
and compare stats, move slots, Tera availability, and seeded battle logs before
switching. Manual switches, U-turn, and Roar verify two accumulated hits and
150 power before switching, then 150 versus 50 power after returning, with
corresponding damage differences and resumed hit accumulation. Battle-stream
fixtures check both format IDs and restored Protect PP after returning.

Validation passed: 155 Python tests, strict mypy, Ruff lint and formatting,
source and wheel builds, installed-wheel spec validation, pip-audit, Astro check,
ESLint, static build, five Playwright tests, and secret scanning. The npm audit
passes CI's high-severity threshold with ten existing moderate findings.
Simulator integration used a writable copy of the pinned checkout in `/tmp`
because Showdown rebuilds on launch. Browser tests used `SHOWCASE_URL` against
the running local preview to accommodate Astro's background preview startup.

## 2026-11-07: Compare original and adapted checkpoints without internal beliefs #milestone #decision

Implemented checkpoint-level comparison and empirical synthesis in
`src/vgc_rulebreak/checkpoint_comparison.py` and added the `compare-checkpoints`
CLI subcommand. The harness compares original source checkpoints (trained under
`gen9rulebreakprotect16`), adapted checkpoints (adapted under `gen9rulebreakprotect8`),
and optional target-native references across all research protocol dimensions:
1. Policy parameters: compares `base_score`, `low_hp_score`, `hp_threshold`,
   `scarcity_slope`, and `pp_cushion` with unit-space L1 and L2 distances,
   verifying whether scarcity slope is non-zero.
2. Controlled evaluation performance: assesses points per game (PPG), win rates,
   and average turns across formats (`protect-16` and `protect-8`) with 95% standard
   percentile bootstrap confidence intervals for paired deltas.
3. Habit and mistake metrics: normalizes Protect choices and consecutive-Protect
   candidate mistakes by eligible decision opportunities, and verifies Protect depletion counts.
4. Decision agreement and divergence: compares exact action choices and Protect
   choice agreement on identical decision requests across replays, characterizing
   divergences by observable HP thresholds and remaining Protect PP.
5. Belief exclusion: synthesizes an empirical comparison narrative strictly grounded
   in observable board state, model parameters, and rollout evidence; programmatically
   forbids and verifies the absence of internal belief claims (rejecting unrecorded
   mental states such as "believed", "thought", "hoped", "felt", "intended", "wanted").

Evaluated the milestone checkpoints (`source-s11-g01` vs `adapted-s11-g01` and `native-s11-g01`)
and generated the comparison report (`runs/protect-rerun-milestone/checkpoint_comparison.json`).
Results:
- Both policies have `scarcity_slope = 0.0`, confirming Protect scoring is invariant to remaining PP.
- Zero Protect depletions occurred across all evaluated games for all policies (depletion rate 0.0,
  95% bootstrap CI [0.0, 0.0]), proving that 8 PP scarcity did not bind.
- Under `protect-8`, both original and adapted achieved identical 0.333 PPG (win rate 0.333,
  Protect use rate 0.0571), yielding a paired delta of +0.000 PPG (95% CI [+0.000, +0.000]),
  which is not statistically distinguishable from zero.
- Across all 57 decisions evaluated from recorded games, the original and adapted policies
  exhibited 100.0% decision agreement and 100.0% Protect choice agreement.
- The comparison confirms a reproducible null result under clean single-factor experimental controls:
  reducing Protect PP from 16 to 8 does not constrain play or alter defensive behavior in standard
  doubles games.

Validation passed: 150 Python tests, strict mypy, Ruff lint and formatting, source and wheel builds,
installed-wheel spec validation, pip-audit dependency inventory, Astro check, ESLint, static build,
5 Playwright browser tests, and npm audit.

## 2026-11-07: Produce Study P replay explanation with repeated-rollout evidence #milestone #decision

Implemented replay branching and counterfactual repeated-rollout evaluation in
`src/vgc_rulebreak/explanation.py` and added the `explain-replay` CLI subcommand.
The pipeline reconstructs exact simulator state at any decision point by stepping
the replay prefix under the battle's original format and seed, reseeds Showdown's
PRNG for branching divergence, and executes paired rollouts across multiple opponent
baselines (`HeuristicBaseline` and `RandomBaseline`).

For each legal action alternative, the module evaluates win rates, points per game,
and average turns, estimating paired performance deltas ($\Delta$ PPG and win rate)
with 95% standard percentile bootstrap confidence intervals. Explanations synthesize
an empirical narrative documenting observable Protect PP, remaining HP, and rollout
distribution bounds without inferring unrecorded internal beliefs or post-hoc intentions.

Produced the milestone explanation artifact (`runs/protect-rerun-milestone/replay_explanation.json`)
for game `g00007` under target format `gen9rulebreakprotect8` (candidate `adapted-s11-g00`, turn 3):
180 repeated rollouts across 9 actions and 2 opponent policies. At the decision point,
Maushold had 8/8 Protect PP remaining, and 0 Protect depletions occurred across all 180
rollouts, confirming that 8 PP scarcity did not bind. Tactical alternatives targeting
the opposing slot (e.g. Population Bomb on slot 2: $\Delta = +0.250$ PPG, 95% CI
$[+0.050, +0.450]$) significantly outperformed defensive Protect, demonstrating how
counterfactual rollouts evaluate individual decisions without relying on single-game
outcomes. The generated explanation remains outside Git alongside archived run data.
No frontend files or visual components were modified.

Validation passed: 143 Python tests including live mechanics and rollout fixtures,
strict mypy, Ruff lint/format, source and wheel builds, installed-wheel spec check,
Python dependency audit, Astro check/lint/build, five browser tests, and npm audit.

## 2026-11-07: Normalize Study P candidate mistakes by opportunities #milestone #decision

Added a versioned consecutive-Protect choice detector to evaluation recording and
recovery summaries. An opportunity requires the same Pokémon's Protect choice in
the same slot on the preceding turn, currently legal Protect, and a legal
alternative. Each game retains flag counts, eligible slot counts, a normalized
rate, and replay locations. These choice patterns are review candidates; proving
harm or estimating outcome cost still requires the later rollout milestone.

Recovery summaries pool numerators and denominators before dividing and retain
per-seed counts and rate spread. Seeds with no opportunities have null rates and
are excluded from the rate spread; missing replay evidence remains unmeasured
with explicit coverage counts. Archived runs can be backfilled from compressed
replays without modifying the source records. Detector versions cannot be pooled.
No frontend files or study outcome claims were changed.

Analyzed the existing 72-game Protect-only rerun with complete replay coverage:
0 consecutive-Protect flags across 16 eligible slot decisions. Points without
eligible decisions correctly retain null rates. The generated analysis remains
outside Git, alongside the archived run data.

Validation passed: 135 Python tests including live mechanics/format fixtures,
strict mypy, Ruff lint/format, source and wheel builds, installed-wheel spec check,
Python dependency audit, Astro check/lint/build, five browser tests, and the npm
audit at CI's high-severity threshold.

## 2026-11-06: Evaluate multiple training seeds and report confidence intervals #milestone

Implemented `run_protect_multi_seed` in `src/vgc_rulebreak/protect_multi_seed.py` and the `protect-multi-seed` CLI subcommand to train and evaluate policies across multiple independent seeds (`[11, 29, 47]`) with rigorous confidence interval reporting.

The multi-seed evaluation pipeline:
1. Replicates the full Protect-only training across each independent training seed ($s \in [11, 29, 47]$) for `source` (16 PP), `native` (8 PP), and `adapted` (8 PP initialized from `source`).
2. Evaluates the resulting checkpoints against held-out test teams (`test-annihilape-bulky`, `test-balance-pivot`) across both formats under mirrored seats and shared battle seeds.
3. Reports replicate-level breakdowns across all independent training seeds alongside pooled evaluations, fulfilling the research requirement to report uncertainty by training replicate and matchup rather than merely across pooled games.
4. Computes 95% standard percentile bootstrap confidence intervals (`bootstrap_ci` and `calculate_ci`) for points per game (PPG), Protect use rates, depletion rates, and causal effect deltas:
   - Transfer difference (source protect-8 minus protect-16): delta PPG and Protect use rate with empirical 95% CIs.
   - Adaptation recovery (adapted protect-8 minus source protect-8): delta PPG with empirical 95% CIs.
   - Native reference comparison (native protect-8 minus source protect-8): delta PPG with empirical 95% CIs.
5. Aggregates the multi-seed habit recovery series into `recovery.json` via `summarize_recovery`, tracking spread across all seeds.
6. Confirms across all replicates that 8 PP does not bind (0 depletions, 95% CI [0.0, 0.0]), with no statistically significant performance degradation between 16 PP and 8 PP.

## 2026-11-06: Rerun training and evaluation on Protect-only formats #milestone

Implemented `run_protect_rerun` in `src/vgc_rulebreak/protect_rerun.py` and the `protect-rerun` CLI subcommand to execute the full training and evaluation rerun across the isolated Protect-only formats (`gen9rulebreakprotect16` and `gen9rulebreakprotect8`).

The pipeline automates:
1. Training `source` under `gen9rulebreakprotect16` from heuristic baseline Protect parameters using cross-entropy fitting on the training split.
2. Training `native` under `gen9rulebreakprotect8` with identical budget controls.
3. Training `adapted` under `gen9rulebreakprotect8` initializing directly from the final source checkpoint.
4. Evaluating resulting checkpoints against held-out test teams (`test-annihilape-bulky`, `test-balance-pivot`) across both formats under mirrored seats and shared battle seeds with full game recording and replay persistence.
5. Summarizing habit recovery series and comparative outcomes.

Live empirical evaluation on local Showdown:
- Verified all checkpoints strictly retain their paired format identity (`gen9rulebreakprotect16` vs `gen9rulebreakprotect8`).
- Across 72 training battles and 72 held-out evaluation battles, candidate policies chose Protect on 16 of 452 legal opportunities (3.54% use rate), closely matching the audit finding (3.4%).
- Zero depletions were observed across all games (`total_depletions = 0`, `scarcity_binds = False`).
- The empirical rerun confirms that reducing Protect maximum PP from 16 to 8 does not bind in standard games without artificial stall incentives, confirming the negative/null result under clean single-factor experimental controls.

## 2026-11-03: Meta-tuned agent comparison and meta shift evaluation for Study A #milestone

Implemented `BroadlyTunedAgent`, `MetaTunedAgent`, and `AdaptedAntiMetaAgent` to isolate whether metagame assumptions cost wins against off-meta anchored teams. In `BattleAgent`, agents now receive Showdown battle messages through `observe_message`, tracking opposing active slots, fainting events, and field state without leaking private information.

When facing the reference Hippowdon sand team, `MetaTunedAgent` discounts the off-meta anchor (-25.0 target priority) while focus-firing standard meta staples, letting Hippowdon sweep under Sand Force. Mirrored evaluation confirms that this assumption costs 1.0 points per game (`meta_assumption_cost = 1.0` vs `BroadlyTunedAgent`). When adapted to prioritize the anchor (+35.0 target priority), `AdaptedAntiMetaAgent` recovers full performance against the anti-meta team (`adaptation_recovery = 1.0`).

Pinned a shifted ladder usage snapshot (`experiments/champions-usage-2026-07.json`) capturing the post-sun rain and Trick Room surge, where Pelipper (17.2%) and Ursaluna-Bloodmoon (16.5%) crossed into banned staples while Torkoal and Chien-Pao fell below 15.0%. Hippowdon (6.5%) and all five reference support species remain strictly legal under the staple ban. Evaluating Hippowdon sand across both snapshots shows an initial 0.50 PPG against the June 2026 meta that drops to 0.25 PPG against the shifted Bloodmoon Trick Room meta (-0.25 delta PPG), documenting that the team's competitive edge is vulnerable to shifts in opposing Trick Room presence.

Added `anti-meta-compare` and `anti-meta-shift` CLI subcommands. Completed the remaining Study A modeling checklist items on the roadmap.

Added Mega Evolution actions to the agent choice space and heuristic scoring. `HeuristicAgent` now recognizes Trick Room and slow sand archetypes at team preview: it evaluates support setup, weather, and bulk rather than ranking solely by raw Speed and offensive stats. Slow anchors such as Hippowdon and setters such as Farigiraf are protected from being benched. In battle, `HeuristicAgent` tracks active Trick Room turns to set it promptly and avoid cancelling it on consecutive turns.

Ran the Protect PP behavioral scarcity pilot on held-out test teams (`test-annihilape-bulky` and `test-balance-pivot`) across mirrored pairs in both `gen9rulebreakprotect16` and `gen9rulebreakprotect8`. Across 8 games (average 8.5 turns), minimum observed Protect PP under the 8 PP format was 8, with 0 depletions and 0 stalls. Protect 8 PP does not bind in standard games without artificial stall pressure, confirming the negative result from the audit.

Launched Study A (Anti-meta teams):
- Pinned Champions regulation `champions-reg-2026-06` and verified mechanics in the simulator.
- Pinned usage snapshot `experiments/champions-usage-2026-06.json` from the 2026-06 ladder with an explicit 15.0% staple-ban threshold (11 banned staples, including Incineroar, Mega Charizard Y, Mega Floette, Archaludon, and Sneasler).
- Rebuilt the reference 6-species Hippowdon sand team in `experiments/teams/anti-meta.json` with open sheets and verified format packing.
- Constructed the meta pool partitioned by team family into search (`meta-sun-charizard`, `meta-rain-archaludon`), validation (`meta-balance-sneasler`), and held-out (`meta-tailwind-floette`) splits.
- Evaluated the reference Hippowdon team against held-out meta teams under mirrored seats and shared seeds, scoring 0.75 points per game (3 wins, 1 loss) with bootstrap confidence intervals [0.25, 1.0].
- Added `anti-meta-check`, `anti-meta-eval`, and `anti-meta-search` CLI subcommands.
- Per user instruction, frontend updates for Study A and Blunder Replays are recorded as TODOs for a designated frontend model.

## 2026-10-27: Audit the Astro dependencies in CI #ci #decision

The showcase job already checked Astro, built the site, and tested browser flows. It now audits the frontend lockfile before those checks.

## 2026-10-25: Grow by studies; anti-meta teams come next #decision

VGC Rulebreak will keep adding studies after the Champions rule changes. Study A, on anti-meta teams, is the next one. It comes from the Pokémon Champions chapter of AnAverageRyan's "The Anti-Meta Mindset", where a team built around Hippowdon climbed from Great Ball rank 1 to the top of Ultra Ball tier while avoiding the most-used Pokémon.

The user picked anchored search over a pure exploiter or hand-built favorites. Every candidate team must include an off-meta anchor and leave out species above a usage threshold, and a search fills the support slots against a frozen meta pool. This keeps the video's process and makes its result measurable. The study runs in Champions doubles to match the video, so it waits on the same pinned regulation as roadmap phase 4, plus a dated usage source.

Two agent gaps block a fair test. The agents can't Mega Evolve, and `HeuristicAgent` orders team preview by Speed and offense, so it would bench a slow sand or Trick Room core. The anti-meta team would then lose to its own pilot. Both get fixed before any team search.

## 2026-10-23: Clarify the README with two diagrams #decision

The README now shows the two relationships that need a picture: both Protect formats come from one Gen 9 base, and the public site joins result indexes with replays through the static export. The old linear workflow stays in prose. The diagrams and captions keep the historical Gen 9 versus full Champions games separate from the corrected Protect-only formats, which have not produced a new study yet.

## 2026-10-23: Deploy the showcase to Vercel #milestone

The Astro showcase is live at [vgc-rulebreak.vercel.app](https://vgc-rulebreak.vercel.app). Vercel builds it from the repository's `web/` directory on `main`. The Production `SITE_URL` config supplies the canonical origin and sitemap. Public checks of the homepage, sitemap, Study P, and replay 0001 returned HTTP 200.

## 2026-10-23: Add a Protect-only simulator format pair #decision

The simulator process now preloads a repository-owned format overlay. It copies the pinned Gen 9 Doubles Custom Game format twice, changing only Protect's starting and maximum PP in the 8 PP battle. It also updates stored move slots so switching does not restore the old cap. The pinned Showdown checkout remains untouched. Future training, evaluation, and pilot runs use these format IDs and count the move Protect alone; the 1,188 already exported battles keep their historical standard Gen 9 and full Champions provenance and broad protection-move metric. Live fixtures verify the paired format settings and initial requests. The next gate is a scarcity pilot; the old outcomes must not be relabeled as Protect-only results.

## 2026-10-23: Audit the Protect comparison's effective rules #incident

A read of the 1,188 exported games found 425 candidate uses of protection-family moves in 10,721 legal opportunities (4.0%). The old metric had grouped Protect with Detect and Spiky Shield. For Protect alone, the replay decisions show 252 uses in 7,329 legal opportunities (3.4%). The median game lasted eight turns; the highest candidate use of Protect by one species in one game was three. In 8 PP games, the lowest observed Protect PP was five. The recorded data never put either cap under pressure.

The earlier evaluation harness mapped `protect-16` to standard Gen 9 doubles and `protect-8` to the full Champions doubles mod. The pinned Champions implementation also changes stat and general PP calculations and other move behavior. The JSON specification says Protect is the only changed rule, but its validator does not inspect the effective simulator formats. Even a paired cross-format run would therefore measure a bundle of rule changes. The [audit](docs/protect-pp-audit.md) records the control failure and calls for a Protect-only pair followed by a scarcity pilot before more training or outcome estimates.

## 2026-10-23: Build the local Champions client showcase #milestone

The Astro showcase now builds a title screen, Study P, Battle Log, two team sheets, an about page, a 404 page, and one battle page for each of the 1,188 evaluated games. `export-showcase` reads the 99 checkpoint runs and writes a 5.2 MB static export under `web/data/`. The Battle Log includes all seven games that stalled before turn 1 and labels their missing logs plainly. No recovery curve is shown: none of these games depleted Protect PP.

Each battle page shows the field after a turn and the choices and available PP from before that turn. The distinction matters when a turn knocks out or switches a Pokémon; showing the opening field beside the full turn account gave a contradictory picture. The exporter records both snapshots. Keyboard shortcuts, touch controls, query-string turn links, a text account, and provenance work from the same static page.

The title image and stat sigils are original assets. A browser render of the finding and agent lineup supplies `web/public/og.png`. A real deployment origin must be supplied as `SITE_URL`; local builds omit canonical and sitemap tags instead of publishing a placeholder domain. The showcase has not been deployed. The browser suite covers navigation, filtering, mobile widths, replay state, and automated accessibility checks, and the CI workflow is configured to run it after the static checks and build.

Linux ARM64 verification passed: Python type, lint, and format checks; 92 Python tests; wheel validation; dependency audits; Astro check and lint; a 1,196-page build; and all five browser tests. The browser suite found no automated WCAG A or AA violations on the title and battle screens.

## 2026-10-23: First Protect training shows no habit to recover #result

`train` now fits the five Protect-score parameters of `TrainedProtectAgent` with the cross-entropy method against `HeuristicBaseline`, using the training split only. Each run had 10 generations, a population of 10, and 3 elites, with one mirrored pair per matchup. Source runs train under 16 Protect PP and native runs under 8, both starting from the heuristic's parameters. Adapted runs continue from the final source checkpoint under 8 PP. There were three seeds per agent (11, 29, 47). Each checkpoint was then evaluated on held-out eval seed 101 with two pairs per team matchup, 12 games per seed, and `summarize-recovery` turned those results into one series per agent.

Both games of a training pair now share one battle seed with the seats swapped. With a separate seed per game, the seat decided many mirror matches, and the unchanged heuristic lost all six games of its first generation. With shared seeds it scores exactly 0.5 against itself.

Mean held-out points per game across seeds, from generation 0 to 10: source 0.500 to 0.417, native 0.333 to 0.417, adapted 0.278 to 0.264. Native's gain comes from a single seed that jumped at generation 6. One game moves a seed's score by 0.083, so none of these changes is beyond noise. No agent ever ran out of Protect PP: depletion was 0 for every checkpoint, and the policies used Protect on about 5% of the turns where they could. At that rate, 8 PP binds as rarely as 16, so the rule change leaves no habit to break.

This is a negative result. The showcase must not draw these curves as habit recovery. Training is worth repeating only in a setup where PP actually runs out, with longer games or an opponent that rewards Protect, and with enough evaluation games per checkpoint to see a change of a few points.

## 2026-10-22: Correct the description of the study agents #incident

The 2026-10-21 entry described the source and native agents as policies calibrated under each ruleset, and the adapted agent as fine-tuned from a source checkpoint. None of that happened. All three are the heuristic agent with a different hand-written Protect score, and no training run or checkpoint exists. `adaptation_progress` is a weight someone sets, and at the 1.0 used by `compare-agents` the adapted agent scores exactly like the native one.

The comparison harness is still useful plumbing, but its numbers compare hand-written rules, not learned behavior. "Transfer loss" and "adaptation recovery" from these agents measure the gap between two scoring rules. They are not evidence about training, and the showcase must not present them as habit recovery. The entry and the docstrings in `agents/variants.py` now say what the code does.

## 2026-10-22: Record per-game results and replays #milestone

`evaluate` and `compare-agents` take `--output-dir`. With it, each run writes `results.json` (provenance, the summary, and one record per game) and one gzipped replay per game in `replays/`. A replay holds the simulator's protocol log without requests, plus every decision: the side, the turn, the request that side received, and the choice it sent. The log and the decisions are what a replay viewer needs to rebuild the board and show what each agent could see. Each game also records why it ended: a win, a tie, the turn limit, or a stall.

Outputs belong under the ignored `runs/` directory. A quick comparison of 18 games against the pinned simulator on Linux ARM64 took about 9.5 KB per replay, so a full 2,700-game evaluation needs about 26 MB. Showdown writes a wall-clock `|t:|` line into each log, so a replayed seed reproduces the battle but not the replay file's exact bytes.

## 2026-10-22: Show species as stat sigils, not sprites #decision

The showcase will not use Pokémon sprites or official art. No licence covers Showdown's sprites: the client's AGPLv3 leaves out its `sprites/` directory, the Smogon Sprite Project grants non-profit use with credit only for its own drawings, and Nintendo's rights in the characters stay uncleared. The Pokémon Company's press kit is licensed for editorial use, but it forbids modification, has no art for most species in the team pool, and could suggest affiliation inside a game-styled interface. Drawing the creatures ourselves would still copy the characters.

Species appear as stat sigils instead. A sigil draws a species' base stats as a hexagon, split by its two type colors. The study agents appear as original robot coaches whose chest racks hold one hex cell per maximum Protect PP. Both are in `web/design/`. Self-hosted Smogon sprites remain a possible optional layer that the site must work without.

## 2026-10-21: Compare unchanged source, adapted, and target-native agents #milestone

Implemented the three study agent variants in `src/vgc_rulebreak/agents/variants.py` and the agent comparison runner in `src/vgc_rulebreak/evaluation.py` and `src/vgc_rulebreak/cli.py`:
- `SourceAgent`: Hand-written stand-in for Gen 9 rules (16 Protect PP). It scores Protect without regard to remaining PP.
- `NativeAgent`: Hand-written stand-in for Champions rules (8 Protect PP). It scores Protect lower as its PP runs out.
- `AdaptedAgent`: Hand-written blend of the two Protect scores, weighted by `adaptation_progress` (0.0 = source, 1.0 = native). The comparison runs it at 1.0, where it scores exactly like `NativeAgent`.

These three descriptions were corrected on 2026-10-22. See that day's entry.

Added `compare_study_agents` and the `compare-agents` CLI subcommand. The harness benchmarks all three agents across `protect-16` and `protect-8` against reference baselines and runs head-to-head matches under target rules to compute transfer loss, habit recovery, and Protect depletion rates.

All 58 unit and integration tests passed cleanly in 1.89s on Linux ARM64, with 0 mypy type errors and 0 ruff lint/format warnings. Marked Milestone 2.3 complete on `ROADMAP.md`.

## 2026-10-21: Freeze test teams, opponent policies, and evaluation seeds #milestone

Established and froze the evaluation controls for the Protect study in `experiments/protect-pp.json`, `src/vgc_rulebreak/evaluation.py`, and `src/vgc_rulebreak/spec.py`.

Key evaluation controls frozen:
- Held-out test teams: `test-annihilape-bulky` and `test-balance-pivot` from the OTS manifest. Verification logic strictly prevents test contamination by asserting test teams are absent from training and validation splits.
- Reference opponent policies: `HeuristicBaseline` (competent rule-based agent) and `RandomBaseline` (seeded uniform random agent).
- Independent evaluation seeds: `[101, 202, 303]`, guaranteed disjoint from the training seeds (`[11, 29, 47]`). Showdown PRNG seeds are deterministically mapped via a 16-bit 4-tuple generator per variant, opponent, matchup, pair, and mirrored game.
- Evaluation runner: Implemented `run_evaluation_suite` and the `evaluate` CLI subcommand supporting dry-run inspection (`--check-only`) and mirrored evaluation execution across variants (`protect-16` and `protect-8`).

All 50 unit and integration tests passed cleanly in 1.65s on Linux ARM64, with 0 mypy type errors and 0 ruff lint/format warnings. Marked Milestone 2.2 complete on `ROADMAP.md`.

## 2026-10-21: Pilot evaluation sizing and compute budget calibration #milestone

Implemented pilot evaluation tooling in `src/vgc_rulebreak/pilot.py` and the `pilot-eval` CLI subcommand. The harness runs mirrored battles across Open Team Sheet archetypes under both `gen9doublescustomgame` (16 Protect PP) and `gen9championsdoublescustomgame` (8 Protect PP), measuring Protect usage, PP depletion, and turn timings. Fixed doubles choice generation for trapped Pokémon and ally-targeting moves (negative index targets like `-1` and `-2`).

Calibrated study evaluation parameters:
- Power analysis sizing: Recommended 15 mirrored pairs per matchup (30 battles per pairing) to achieve 80% statistical power (alpha = 0.05) across all 15 pairwise matchups from the 6 frozen archetypes.
- Compute budget: 18,344 seconds (~5.1 hours) covering 2,700 total matches across 2 ruleset variants, 3 training seeds ([11, 29, 47]), and a 25% overhead buffer.
- Readiness gates: Populated `pairs_per_matchup` and `compute_budget_seconds` in `experiments/protect-pp.json`. All readiness gates are cleared (`pending_gates: []`).

## 2026-10-20: Reproduce baseline agent and benchmark resource costs #milestone

Implemented a competent heuristic baseline agent (`HeuristicAgent`), uniform random agent (`RandomAgent`), and a benchmark runner in `src/vgc_rulebreak/agents/`. The heuristic agent prioritizes STAB modifiers, high-power spread moves, dynamic HP-scaled Eruption scoring, non-consecutive Protect scoring, and offensive lead positioning at team preview.

In automated benchmark evaluation across Open Team Sheet archetypes (`OTS_TEAM_SUN` and `OTS_TEAM_TAILWIND`):
- Win rate: 90.0% against `RandomBaseline` across 10 matches (9-1), comfortably exceeding the >= 80% threshold.
- Throughput: 5.34 decisions/second with an average turn latency of 543.5 ms under local Showdown process streaming.
- Simulator integration: Successfully verified Showdown CLI request handling (`sideupdate` headers, `wait: true` resets, auto-passing fainted slots, non-targeted spread/field actions).

All 24 unit and integration tests, strict mypy type checks, and ruff formatting passed cleanly on Linux ARM64. Marked Phase 1 Section 1 complete on `ROADMAP.md`.

## 2026-10-20: Team manifest and OTS archetype splits #milestone

Added the Open Team Sheet (OTS) team pool manifest for the Protect study in `experiments/teams/protect-pp.json` and manifest validation in `src/vgc_rulebreak/manifest.py`. The manifest defines six archetypes split into disjoint sets:
- Training: Tailwind offense (Tornadus/Flutter Mane) and Sun balance (Torkoal/Chi-Yu).
- Validation: Trick Room bulky (Farigiraf/Bloodmoon Ursaluna) and Rain offense (Pelipper/Archaludon).
- Test: Annihilape bulky setup and Balance pivot (Incineroar/Rillaboom/Landorus-Therian).
All teams were validated against Showdown format rules with 0 errors. Marked `readiness.team_manifest` in `experiments/protect-pp.json`.

## 2026-10-20: Mechanics verification and Showdown simulator adapter #milestone

Implemented a Python adapter for Pokémon Showdown battle streams and deterministic mechanics verification fixtures:
1. Protect maximum PP: 16 (Gen 9) versus 8 (Champions).
2. Rage Fist hit counter: persists across switches in Gen 9, resets upon switch in Champions.
3. Stat calculations: Speed stat modifier differences verified across legal builds.
Added the `verify-mechanics` command to the CLI and marked `readiness.mechanics_verified` as true in `experiments/protect-pp.json`. All 17 tests, strict mypy checks, ruff formatting, and dependency audits passed on Linux ARM64.

## 2026-10-13: Replace the README Mermaid diagram #decision

The current flow is a short linear scaffold, so the README now states it in prose. The former Mermaid block added no relationship that needed a diagram.

## 2026-10-04: Verify moving action tags #incident

The first hosted package job could not resolve `setup-uv@v9`, although a v9.0.0 release existed. A release does not establish that its moving major tag exists. Checking Git refs showed v7 as setup-uv's newest published single-digit major tag, so the workflow uses v7. The secret scan passed on the initial PR revision.

## 2026-10-04: Scaffold checks pass #milestone

The Python scaffold passed strict type checking, lint, formatting, 12 tests, source and wheel builds, installation from the wheel, and a hashed dependency audit on Linux ARM64. The audit uses a dedicated cache to avoid unrelated cached-response warnings. The draft reports its four missing study declarations instead of launching an unverified experiment.

## 2026-10-04: Research scaffold and dependency boundary #decision

The repository starts with a Python 3.12 package and a Protect specification validator. Runtime dependencies are empty. uv locks the development tools, and CI checks types, lint, formatting, tests, package installation, dependencies, and secrets. The simulator adapter will add pinned Showdown and poke-env versions when it is implemented. The current revision is recorded for provenance without claiming verified mechanics.

## 2026-10-04: Baseline scope #decision

README, license, journal, tests, and CI are required for this executable public research repository. Contributor instructions are included because outside contributions may follow. Deployment and analytics do not apply to the current package. Banners, logos, and recordings remain optional until a visual demo exists. CI action references use published stable single-digit major tags.

## 2026-10-04: Name and first study #decision

The project is VGC Rulebreak. The user chose `vgc-rulebreak` after asking for a public deliverable that interests competitive players and newcomers. The first study isolates Protect PP. The larger plan measures which Scarlet/Violet habits become costly under Champions rules, with a replay reel, recovery graphs, and dated reference matchups.

## 2026-10-04: Keep the claims tied to agent evidence #decision

Adaptation curves describe the selected agent and training method. They cannot settle human skill ceiling or establish that the metagame is solved. Individual switches and Protect choices need repeated-rollout evidence before they are labeled blunders. Full Champions transfer and individual-rule experiments answer different questions.

## 2026-10-04: Separate this project from TCG #decision

VGC Rulebreak contains competitive video-game battle research. The 60-card TCG project remains a separate planned repository because its engine, actions, observations, datasets, and evaluation differ.

## 2026-10-23: Reject Any annotations in CI #decision

Ruff checks function arguments and returns for Any. Line-level exceptions remain at dynamic simulator and JSON record boundaries that still need schema types. Pytest treats warnings as errors, and strict mypy stays enabled.

## 2026-11-03: Adopt authentic Champions ladder usage dumps #milestone

Replaced the synthetic usage fixtures for Study A with authentic Season M2 (June 2026) and Season M3 (July 2026) Doubles ladder snapshots sourced from the community Champions battle data API. Each snapshot records all ranked species and their ladder positions alongside provenance metadata. Updated the staple ban loader to support explicit banned lists and rank cutoffs while preserving the legality of the reference sand core.
