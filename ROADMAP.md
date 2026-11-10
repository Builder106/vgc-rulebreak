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
- [x] Pin a dated Champions regulation and validate the complete ruleset. Studies A, F, and T need it.
- [x] Add Mega Evolution to the agents' actions. Studies A and T need it.

A random agent is useful for plumbing but is insufficient as the only strength baseline.

## Showcase

- [x] Title screen, Study P, Battle Log, team sheets, and one replay page per evaluated game.
- [x] Keyboard and mobile replay navigation.
- [x] Deploy the site from `main`.
- [x] List every study on the Regulations screen, including planned ones.
- [ ] TODO(frontend): Blunder Replay with PP, damage, Speed, and outcome evidence.
- [ ] TODO(frontend): Habit Recovery charts with uncertainty and opportunity counts.
- [ ] TODO(frontend): Matchup Desk with cross-play results, configuration, and provenance beside the team sheets.
- [ ] TODO(frontend): Give each study a page when it has results.

See [the showcase brief](docs/showcase.md) for what each screen must show.

## Study P: Protect PP

In progress. See [the research plan](RESEARCH.md#first-experiment-protect-pp) and [the audit](docs/protect-pp-audit.md).

- [x] Define the study and its research controls.
- [x] Build and fixture-check two formats that differ only in Protect PP; the earlier standard Gen 9 versus Champions comparison changed other mechanics.
- [x] Pilot evaluation size and set the compute budget.
- [x] Freeze test teams, opponent policies, and seeds.
- [x] Compare unchanged source, adapted, and target-native agents. These games used the earlier format pair, so they can't isolate Protect PP.
- [x] Pilot a setup in which Protect reaches the 8 PP limit before repeating training. (Behavioral scarcity pilot verified that 8 PP does not bind in standard games without artificial stall incentives).
- [x] Rerun training and evaluation on the Protect-only formats.
- [x] Evaluate multiple training seeds and report confidence intervals.
- [x] Normalize candidate mistakes by eligible decision opportunities.
- [x] Produce one replay explanation with repeated-rollout evidence.
- [x] Compare original and adapted checkpoints without inferring unsupported internal beliefs.

Exit with a reproducible result and a replay whose explanation matches the aggregate evidence. A null or negative result is publishable when the experiment can resolve a useful effect.

## Study A: Anti-meta teams

In progress. See [the plan](docs/anti-meta.md). Uses the pinned Champions regulation and Mega Evolution from the shared foundation.

- [x] Pin a dated Champions usage snapshot, record its terms, and fix the staple-ban threshold.
- [x] Build the meta pool and split it into search and held-out sets by team family.
- [x] Give team preview and move choice a plan for slow sand and Trick Room teams.
- [x] Rebuild the video's Hippowdon team as a labeled reference.
- [x] Search support slots around the anchor and compare with a random-support baseline.
- [x] Measure the anchored team against held-out meta teams, with intervals.
- [x] Compare meta-tuned and broadly tuned agents against the anchored team.
- [x] Repeat against a later usage snapshot.

Exit when the anchored team's held-out result has intervals that can resolve a useful effect, and the pilot plays the reference team without benching its anchor.

## Study R: Rage Fist

Fixed-policy interaction evaluation completed. See [the protocol and result](docs/rage-fist-interaction.md). The hit-counter fixtures pass.

- [x] Build a format pair that differs only in whether Rage Fist's hit counter resets on switching.
- [x] Estimate the decision cost of switches, normalized by opportunities to switch.
- [x] After Study P has a result, run a 2-by-2 with Protect PP to measure the interaction.

## Study S: Speed

Completed within the fixed-fixture and certified-public-evidence scope. See [the Speed protocol](docs/speed.md).

- [x] Compare move order and pivot decisions under equivalent legal builds in both stat systems.
- [x] Report uncertainty about opponent Speed without exposing hidden state.

## Study F: Full transfer

The [held-out synthetic-team pilots and legal sourced OTS references](docs/full-transfer.md) are available. The reference pool validates Regulation M-B separately from the earlier custom-game pilots; policy transfer on those references remains to measure.

- [x] Measure transfer loss and recovery on held-out teams.
- [x] Compare fixed and new opponent pools.
- [x] Build legal OTS reference matchups and record their sources.

## Study T: Tera and Mega

The [bidirectional activation-timing pilot](docs/tera-mega.md) compares both directions and native training budgets. Controlled mechanic attribution remains to measure.

- [x] Compare both transfer directions and equal-budget native references.
- [x] Document common species and unavoidable item/form differences.
- [ ] Separate mechanic changes from unrelated rule changes.
- [ ] Publish the limits of conclusions about human skill and metagame optimality.

## Adding a study

1. Pick an unused letter and write the plan in `docs/`.
2. Add a row to the study tables in `README.md` and `RESEARCH.md`.
3. Add a section here with its checklist and exit condition, and move any work another study also needs to the shared foundation.
4. Add a slot to the Regulations screen in `web/src/pages/studies/index.astro`.
5. Record the decision in `JOURNAL.md`.
