# Research plan

## Public premise

Teach an agent to play Scarlet/Violet, move it to Champions rules, and measure which habits cost it games and how it recovers. The public story follows individual decisions and matchups. Every headline must point to an experiment, replay, or measured result.

## Questions and controls

| Question | Controlled comparison | Evidence |
| --- | --- | --- |
| Does lower Protect PP change defensive play? | 16 versus 8 maximum PP, with all other rules fixed | Win-rate difference, exhaustion frequency, and costly Protect decisions per opportunity |
| Does Rage Fist resetting change useful switch patterns? | Persist versus reset the hit counter, with fixed teams | Estimated decision cost of switches, damage changes, and matchup results |
| How does the stat system affect slow pivots? | Equivalent legal builds under the two stat systems | Move-order differences and pivot decision costs, including uncertainty about opponent Speed |
| How much does an SV agent lose in Champions? | Unchanged source agent, adapted checkpoints, and a Champions-native reference | Transfer loss and recovery across held-out teams |
| Does experience with Tera transfer to Mega? | Transfer in both directions, plus native references trained with equal budgets | Transfer loss, recovery, and mechanic-specific decisions |
| How quickly do useful strategies emerge? | Successive checkpoints against fixed and additional opponent pools | Learning curves and behavior changes that survive new matchups |

An agent's recovery speed depends on the architecture, training method, prior experience, and available actions. It does not establish which mechanic requires more human skill. Effective behavior against a finite opponent pool does not prove the metagame is solved.

## First experiment: Protect PP

Use a controlled doubles format with identical species, teams, items, information, timings, opponent mixtures, and other mechanics. Change only Protect's maximum PP, from 16 to 8. These are experimental formats, not official regulations.

First verify each variant through simulator fixtures. Then reproduce a competent source agent. Measure its performance immediately after the rule change and after further training. Train a reference directly in the target format with the same budget. Record training matches, decisions, wall time, and hardware so equal match counts do not conceal unequal compute costs.

The draft specification is `experiments/protect-pp.json`. It pins the upstream simulator revision but leaves the team manifest, mechanics verification, evaluation sample size, and compute budget unset until a pilot establishes them. Configuration validation does not establish simulator fidelity.

Start with Protect alone. Add Rage Fist next, then use a 2-by-2 experiment to measure the interaction between PP and hit-counter persistence. Avoid changing every rule at once and attributing the total loss to one mechanic.

## Evaluation protocol

1. Pin the simulator revision and the exact custom rules or published regulation. Record species, items, moves, timings, team selection, and information available to each player.
2. Maintain separate training, validation, and test team manifests. Split by team family and opponent policy where possible. Do not put near-duplicate teams or matches from the same series across splits.
3. Use at least three independent training seeds. Freeze the test opponents and evaluation seeds before tuning against results.
4. Choose evaluation size after a pilot and record the effect size the study can resolve. Report uncertainty by training replicate and matchup, not just across pooled matches.
5. Compare source, adapted, native, and competent reproducible baseline agents. Show the full cross-play matrix because strength can depend on the opponent.
6. Report win-rate changes, decision errors per opportunity, legality, runtime, and sample efficiency. Keep new-opponent evaluations separate from the fixed reference pool.
7. Publish the configuration, team manifest, checkpoint identity, evaluation seeds, and replay selection method with each result.

Use open team sheets for the first study. Team sheets reveal only the fields specified by the selected rules. Do not expose private state such as an opponent's unobserved Speed, action, or internal policy. Closed-sheet ladder-style evaluation is a separate extension.

## Evidence for a blunder

A candidate detector identifies decisions worth inspecting. A harmful decision needs evidence: branch from the same state, compare legal alternatives under the same rules, sample hidden information from a justified distribution, and repeat rollouts against multiple opponent policies. Report the estimated outcome difference and its uncertainty. Diverging simulations need repeated trials even when they start from matched random seeds.

Switching Annihilape after it takes hits can still be correct. Running out of Protect does not establish that an earlier use was wrong. Do not claim that an agent expected a particular damage value unless its recorded estimator actually made that prediction. Describe observable decisions when internal beliefs are unavailable.

Normalize habit frequencies by opportunities. Fewer costly Annihilape switches means little if the agent stops selecting Annihilape. Keep aggregate results alongside selected replay examples.

## Full transfer and mechanic comparison

Full Champions transfer changes the complete pinned ruleset. Its result describes the combined change. Controlled studies isolate individual factors, with selected interactions reported separately.

For Tera/Mega experiments, use a shared base-species pool where possible and document item, form, and team differences that the mechanic requires. Use one action schema that can represent both mechanics. Record what each source policy encountered during training. An action head that never learned Mega is itself a transfer limitation. Include both transfer directions and independently trained references before comparing recovery speed.

Fixed-team studies measure battle decisions. Claims about Annihilape's overall viability, partner slots, or an optimal team require later team-selection experiments.

## Sources and provenance

- [Showdown Champions move definitions](https://github.com/smogon/pokemon-showdown/blob/9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e/data/mods/champions/moves.ts) encode Protect's lower base PP and refer to Rage Fist's hit-counter reset.
- [Showdown Champions scripts](https://github.com/smogon/pokemon-showdown/blob/9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e/data/mods/champions/scripts.ts) encode PP calculation, stat calculation, and the hit-counter reset.
- [VGC-Bench](https://arxiv.org/abs/2506.10326) provides research on agents and generalization across team strategies. Review its reproducible baselines before choosing the source agent.
- [poke-env](https://github.com/hsahovic/poke-env) provides a Python interface to Showdown. Add a pinned dependency when the simulator adapter is implemented.

The Showdown Champions mod is a community implementation. Validate targeted mechanics against documented game behavior and identify any known mismatch. Label simulator results accordingly.

Keep source provenance and licenses with every team pool and dataset. Raw replays, datasets, checkpoints, and generated reports belong outside Git. The MIT license covers this project's original code, not third-party Pokemon content. Review each artifact's terms before redistribution.

## Test scope

The scaffold tests the specification parser and CLI. The simulator adapter adds process integration and mechanic fixtures. Statistical aggregation adds unit and property tests for paired results and missing data. The public demo adds browser tests for replay navigation and result provenance. Performance checks begin when a measured runtime claim exists.
