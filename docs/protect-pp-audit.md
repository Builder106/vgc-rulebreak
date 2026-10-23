# Protect PP study audit, 2026-10-23

## What the recorded games establish

The counts below come from `web/data/battles/*.json.gz`. The static export contains 1,188 held-out games from 99 checkpoint runs: 396 source games under standard Gen 9, and 396 each for native and adapted agents under the Champions mod. Its recorded “Protect” metric actually groups Protect, Detect, Spiky Shield, and other protection moves: 425 uses in 10,721 legal opportunities (4.0%). For the move Protect alone, replay decisions show 252 uses in 7,329 legal opportunities (3.4%). Future study metrics now count that move alone. The median game lasted eight turns. A candidate used Protect at most three times with one species in a game, leaving at least five PP in the 8 PP games. In 198 of the 792 games under 8 PP, one candidate Pokémon had at least eight legal Protect opportunities; the policy rarely took them. No game recorded Protect depletion. Seven games stalled before turn 1.

These are descriptive counts over a small, repeated set of checkpoints and test teams. Games from the same checkpoint are dependent. The source, native, and adapted policies are different, so their win rates cannot be read as the effect of changing PP.

## A second control failure

The experiment specification declares that only Protect's maximum PP changes, but the earlier evaluation code mapped `protect-16` to `gen9doublescustomgame` and `protect-8` to `gen9championsdoublescustomgame`. The pinned Champions mod changes more than Protect: its [scripts](https://github.com/smogon/pokemon-showdown/blob/9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e/data/mods/champions/scripts.ts) change stat calculation and PP calculation, and its [move definitions](https://github.com/smogon/pokemon-showdown/blob/9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e/data/mods/champions/moves.ts) include other move behavior. A comparison between those formats cannot isolate Protect PP even if the same checkpoint, teams, opponents, and random seed are used.

The specification validator checks the declared rules, not the effective simulator format. The existing mechanics fixtures verify several differences between Gen 9 and Champions; they do not prove a Protect-only intervention. Do not use the current cross-format results as a causal estimate of the Protect change.

## Next experiment gate

1. Done: `gen9rulebreakprotect16` and `gen9rulebreakprotect8` copy the pinned Gen 9 Doubles Custom Game format at runtime. The 8 PP format changes Protect slots from 16 to 8 at battle start, including the stored slots used after switching. The pinned Showdown checkout is unchanged. The full Champions format remains a separate transfer experiment.
2. The live format fixture checks identical base format settings, Gen 9 mod, representative Speed stats, and every non-Protect move's starting PP, with 16 versus 8 Protect PP. A battle-stream fixture verifies the PP shown to the agent. Broader paired checks for Rage Fist, damage, and switch restoration remain useful before a causal outcome claim.
3. Run a cheap behavioral pilot on held-out teams. Record Protect choices per legal opportunity, per-Pokémon minimum PP, depletion, game length, and stalls. Stop before another training run unless Protect scarcity occurs often enough to distinguish the caps.
4. If the pilot passes, train source and target-native policies with equal budgets, then evaluate each frozen checkpoint under both formats with identical battle seeds and mirrored seats. Estimate paired outcome differences over independent training seeds and enough held-out battles to resolve the proposed effect. Keep any repeated-rollout decision-cost analysis separate from the ordinary replay viewer.

The current export remains a useful replay and negative-result dataset. It was produced before the format correction and must keep its original format IDs and interpretation. It does not support the planned Blunder Replay or Habit Recovery claims.
