# Roadmap

VGC Rulebreak adds studies over time. Each study has a letter, a plan, and a section here. Study P is in progress and Study A is the next study to add. Work that more than one study needs goes under the shared foundation.

## Shared foundation

- [x] Choose the public premise and repository name.
- [x] Add the validated study specification and repository checks.
- [x] Connect a local Showdown process through a pinned Python adapter.
- [x] Verify 16 and 8 maximum Protect PP with deterministic fixtures.
- [x] Verify Rage Fist power before switching and after returning.
- [x] Verify equivalent legal Speed builds and move order.
- [x] Freeze the team pool, information rules, and known simulator mismatches.
- [x] Reproduce a competent source agent and record its resource costs.
- [x] Record per-game results and compressed replays for every evaluated game.
- [ ] Pin a dated Champions regulation and validate the complete ruleset. Studies A, F, and T need it.
- [ ] Add Mega Evolution to the agents' actions. Studies A and T need it.

A random agent is useful for plumbing but is insufficient as the only strength baseline.

## Showcase

- [x] Title screen, Study P, Battle Log, team sheets, and one replay page per evaluated game.
- [x] Keyboard and mobile replay navigation.
- [x] Deploy the site from `main`.
- [x] List every study on the Regulations screen, including planned ones.
- [ ] Blunder Replay with PP, damage, Speed, and outcome evidence.
- [ ] Habit Recovery charts with uncertainty and opportunity counts.
- [ ] Matchup Desk with cross-play results, configuration, and provenance beside the team sheets.
- [ ] Give each study a page when it has results.

See [the showcase brief](docs/showcase.md) for what each screen must show.

## Study P: Protect PP

In progress. See [the research plan](RESEARCH.md#first-experiment-protect-pp) and [the audit](docs/protect-pp-audit.md).

- [x] Define the study and its research controls.
- [x] Build and fixture-check two formats that differ only in Protect PP; the earlier standard Gen 9 versus Champions comparison changed other mechanics.
- [x] Pilot evaluation size and set the compute budget.
- [x] Freeze test teams, opponent policies, and seeds.
- [x] Compare unchanged source, adapted, and target-native agents. These games used the earlier format pair, so they can't isolate Protect PP.
- [ ] Pilot a setup in which Protect reaches the 8 PP limit before repeating training.
- [ ] Rerun training and evaluation on the Protect-only formats.
- [ ] Evaluate multiple training seeds and report confidence intervals.
- [ ] Normalize candidate mistakes by eligible decision opportunities.
- [ ] Produce one replay explanation with repeated-rollout evidence.
- [ ] Compare original and adapted checkpoints without inferring unsupported internal beliefs.

Exit with a reproducible result and a replay whose explanation matches the aggregate evidence. A null or negative result is publishable when the experiment can resolve a useful effect.

## Study A: Anti-meta teams

Next. See [the plan](docs/anti-meta.md). Needs the pinned Champions regulation and Mega Evolution from the shared foundation.

- [ ] Pin a dated Champions usage snapshot, record its terms, and fix the staple-ban threshold.
- [ ] Build the meta pool and split it into search and held-out sets by team family.
- [ ] Give team preview and move choice a plan for slow sand and Trick Room teams.
- [ ] Rebuild the video's Hippowdon team as a labeled reference.
- [ ] Search support slots around the anchor and compare with a random-support baseline.
- [ ] Measure the anchored team against held-out meta teams, with intervals.
- [ ] Compare meta-tuned and broadly tuned agents against the anchored team.
- [ ] Repeat against a later usage snapshot.

Exit when the anchored team's held-out result has intervals that can resolve a useful effect, and the pilot plays the reference team without benching its anchor.

## Study R: Rage Fist

Planned. The hit-counter fixtures already pass.

- [ ] Build a format pair that differs only in whether Rage Fist's hit counter resets on switching.
- [ ] Estimate the decision cost of switches, normalized by opportunities to switch.
- [ ] After Study P has a result, run a 2-by-2 with Protect PP to measure the interaction.

## Study S: Speed

Planned. The Speed fixtures already pass.

- [ ] Compare move order and pivot decisions under equivalent legal builds in both stat systems.
- [ ] Report uncertainty about opponent Speed without exposing hidden state.

## Study F: Full transfer

Planned. Needs the pinned Champions regulation.

- [ ] Measure transfer loss and recovery on held-out teams.
- [ ] Compare fixed and new opponent pools.
- [ ] Build legal OTS reference matchups and record their sources.

## Study T: Tera and Mega

Planned. Needs the pinned Champions regulation and Mega Evolution.

- [ ] Compare both transfer directions and equal-budget native references.
- [ ] Document common species and unavoidable item/form differences.
- [ ] Separate mechanic changes from unrelated rule changes.
- [ ] Publish the limits of conclusions about human skill and metagame optimality.

## Adding a study

1. Pick an unused letter and write the plan in `docs/`.
2. Add a row to the study tables in `README.md` and `RESEARCH.md`.
3. Add a section here with its checklist and exit condition, and move any work another study also needs to the shared foundation.
4. Add a slot to the Regulations screen in `web/src/pages/studies/index.astro`.
5. Record the decision in `JOURNAL.md`.
