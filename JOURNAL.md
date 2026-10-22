# Journal

## 2026-10-22: Correct the description of the study agents #incident

The 2026-10-21 entry described the source and native agents as policies calibrated under each ruleset, and the adapted agent as fine-tuned from a source checkpoint. None of that happened. All three are the heuristic agent with a different hand-written Protect score, and no training run or checkpoint exists. `adaptation_progress` is a weight someone sets, and at the 1.0 used by `compare-agents` the adapted agent scores exactly like the native one.

The comparison harness is still useful plumbing, but its numbers compare hand-written rules, not learned behavior. "Transfer loss" and "adaptation recovery" from these agents measure the gap between two scoring rules. They are not evidence about training, and the showcase must not present them as habit recovery. The entry and the docstrings in `agents/variants.py` now say what the code does.

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
