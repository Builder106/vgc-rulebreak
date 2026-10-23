# Public showcase brief

The first screen reports what the Protect study found: across 1,188 held-out games, no agent ran out of Protect. A reader can replay a game and trace its choices and scores to the recorded artifacts. Claims about costly alternatives still need repeated rollouts.

## Blunder Replay

Show the board before a candidate mistake, the original agent's action, and an alternative backed by repeated rollouts. Show remaining Protect PP, Rage Fist power, relevant Speed ranges, and damage calculations from the pinned mechanics. Label estimated outcome differences and their uncertainty. Avoid presenting a divergent replay as proof from a single lucky outcome.

Every annotation links to a match ID, checkpoint, ruleset, and result artifact. Select examples through a documented process and show aggregate results beside the reel. Display actual evaluated games. There are no invented recovery milestones or scores.

## Habit Recovery

Plot mistake frequency per eligible opportunity and estimated decision cost across checkpoints. Show uncertainty across training seeds, the number of eligible decisions, and whether the curve uses held-out or training opponents. Keep plain-language captions close to each chart.

## Matchup Desk

Show legal, dated reference teams with open team sheets. Include complete cross-play results, replay downloads, team provenance, and source versus adapted comparisons. Present closed-sheet ladder-style matches separately if they are added. Do not call a fixed team pool human ladder consensus without evidence.

## Interaction and release gates

The interface needs readable battle states, keyboard replay navigation, useful mobile controls, and a link from every score to its provenance. Provide a text account of replay events alongside the visual board. Keep explanations grounded in recorded behavior rather than invented agent thoughts.

The local Astro showcase now has battle replay, a Protect-use chart, team sheets, and a filterable game log. Browser interaction and automated accessibility checks are in `web/tests/`. The repeated-rollout explanations above and a hosted demo remain open.
