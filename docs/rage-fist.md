# Study R: opportunity-normalized switch costs

The paired formats `gen9rulebreakragefistpersist` and
`gen9rulebreakragefistreset` share pinned Gen 9 rules and differ only in the
switch-out hit-counter reset. The format fixtures are the prerequisite for this
analysis. The Protect PP interaction is a separate roadmap experiment.

`estimate-switch-cost` analyzes recorded requests and branches from each chosen
voluntary switch by a Rage Fist user. Supply original simulator replay records
(the `GameRecorder` schema, including teams, seed, decisions and requests):

```sh
uv run vgc-rulebreak estimate-switch-cost \
  --replay runs/study-r/replays/g00001.json.gz runs/study-r/replays/g00002.json.gz \
  --candidate-role p1 --trials 20 --seed-base 1000 --max-turns 100 \
  --output runs/study-r/switch-cost-p1.json
```

Analyze the other seat separately with `--candidate-role p2`. Preserve the replay
cohort, checkpoint/policy identity, training replicate, team-family split and seed
selection alongside reports. The command accepts only the isolated Study R
formats. It does not rewrite replays or silently convert historical formats.

## Denominator and comparator

One opportunity is one unfainted active Rage Fist user's decision with both a
legal voluntary switch and a legal move to stay in. Count opportunities even when
the agent stays, whether or not Rage Fist has accumulated hits. The partner's
chosen switch reserves its bench destination. Trapped slots, no living bench,
forced replacements, preview, waiting and pivot moves do not create switch events.
Pivot decisions remain outside this manual-switch estimand. Missing requests or
unsupported choices fail explicitly instead of being reported as zero activity.

Each chosen switch is compared with the first legal move in request order, with
its first enumerated target, holding the partner's action fixed. This comparator
is fixed before any rollout outcomes are seen. It estimates the cost relative to
that particular move; it does not claim to find the best alternative or measure
optimal-action regret. Action execution can still be prevented by game effects.

Both branches replay the original prefix and verify the target request matches.
Simultaneous choices are reconstructed together, including when the candidate
occupies player 2. Paired branches share a fresh simulator seed and fresh opponent
policy seed. Future candidate choices use HeuristicBaseline; opponent policies are
HeuristicBaseline and RandomBaseline, reported separately. These continuation
policies do not reconstruct a learned agent's private state.

## Estimates and limits

Points are 1 for a win, 0 for a loss and 0.5 for a simulator tie or the configured
turn limit. Every branch records its termination reason so censored outcomes are
visible; stalled rollouts fail. The signed decision cost is the mean of paired
`stay points - switch points`. A beneficial switch has negative cost. Reports
retain paired trial seeds and outcomes, replay paths, teams, original battle seeds,
decision indices, turns, slots and Pokémon identities.

Per format and opponent, pool costs and counts before dividing:

- `cost_per_opportunity = sum(decision costs) / eligible opportunities`.
- `switch_rate = chosen switches / eligible opportunities`.
- `costly_switch_rate = switches with cost CI lower bound > 0 / eligible opportunities`.
- `cost_per_switch` describes switches alone and retains its separate denominator.

Zero opportunities produce null rates and intervals. Eligible games without any
chosen switches contribute zero cost and all their opportunities. Negative costs
are retained rather than clipped. Do not sum repeated denominator counts across
opponent-policy reports.

Per-decision 95% percentile bootstrap intervals resample paired rollout deltas.
Aggregate cost-per-opportunity intervals resample whole replay games, preserving
decision dependence within games. They condition on estimated decision costs,
exclude rollout noise, and are not intervals over training seeds or mirrored
pairs. Report training replicate and matchup strata separately for study claims.
Single-game intervals cannot establish population precision. Costly flags have no
multiple-comparison correction and are exploratory.

Rollouts condition on the reconstructed simulator state. They do not sample a
justified distribution of hidden opponent information, establish human mistakes,
or prove what an agent believed. Different format cohorts can visit different
states, so differences between their summaries alone do not identify a causal
reset effect. A controlled paired cohort and adequate replication are required
before making that claim.

## Acceptance checks

`tests/test_switch_cost.py` verifies opportunity exclusions, stays in the
denominator, reserved bench targets, signed paired costs, pooled ratios, null
rates, deterministic seeds, format validation, CLI behavior and saved reports.
Live simulator tests reconstruct both seats under both formats after Rage Fist
has dealt a hit and evaluate switch/stay branches against both opponents.
`tests/test_rage_fist_formats.py` independently verifies the mechanic contrast.
