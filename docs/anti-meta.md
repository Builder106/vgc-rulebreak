# Study A: Anti-meta teams

Study P changes a rule and asks whether old habits cost games. This study changes the opponent instead. Agents and teams tuned on the metagame assume certain things about what they will face, and a team built outside the meta breaks those assumptions. The study asks how strong such a team can get, and whether meta-tuned agents pay for what they assumed.

## Where the idea comes from

In [The Anti-Meta Mindset](https://www.youtube.com/watch?v=71H6o7-_dSo&t=268s) (AnAverageRyan, uploaded 2026-06-15; the Pokémon Champions chapter starts at 4:28), the player skips the most-used Pokémon and builds a Champions doubles team around Hippowdon. He names Mega Charizard Y and Mega Floette as the most used, with Archaludon, Sneasler, Basculegion, and Incineroar as their usual partners. An earlier Mega Sharpedo team stalled in Great Ball tier. The Hippowdon team then won a streak from Great Ball rank 1 to the top of Ultra Ball tier.

The team sheet on screen:

| Pokémon | Item | Details shown |
| --- | --- | --- |
| Hippowdon | Leftovers | Brave, Sand Force, Attack maxed (32 of 66 stat points); Body Press, Heavy Slam, Earthquake, Protect (8 PP) |
| Tyranitar | Tyranitarite | Moves and stats not shown |
| Farigiraf | Focus Sash | Moves and stats not shown |
| Sinistcha | Sitrus Berry | Moves and stats not shown |
| Decidueye | White Herb | Moves and stats not shown |
| Rotom-Heat | Passho Berry | Form read from battle footage |

A ranked win streak is an anecdote. It can't separate the team's strength from the player's skill or from opponents who hadn't prepared for it, and the video reports no win rate. This study keeps his process (pick an anchor, avoid the staples, build support around the anchor) and measures the result.

## Questions

| Question | Comparison | Evidence |
| --- | --- | --- |
| How strong can an anchored team get without the staples? | Searched anchored teams against a frozen meta pool, with the same pilot on both sides | Points per game against held-out meta teams, with intervals across seeds and matchups |
| Do meta-tuned agents pay extra against it? | An agent tuned on the meta pool and one tuned on a broader pool, both facing the anchored team | The gap between them, beyond what the team's results against neutral agents predict |
| What does adapting cost? | A meta-tuned agent before and after more training against the anchored team | Recovery against the anchored team, and any loss against the meta pool |
| Does the edge survive a meta shift? | The same anchored team against meta teams from a later usage snapshot | The change in points per game between snapshots |

## Definitions

- **Meta pool.** Teams built from a dated usage snapshot of the pinned Champions regulation. Record the source, date, and terms. Split the pool by team family into search and held-out sets, as Study P splits its team manifest.
- **Staple ban.** Species above a usage threshold can't appear on the anchored team. Fix the threshold before the search and record it with the snapshot.
- **Anchor.** One species below the threshold that every candidate team must include. Hippowdon comes first because the video documents its set.
- **Support search.** The search fills the other five slots from legal, unbanned species and their common sets. Candidates are scored only against the search split.
- **Reference team.** The video's six, rebuilt as a hand-made baseline. Only Hippowdon's set appears in full, so the other five sets come from the usage snapshot and are labeled as reconstructions.

## Controls

- One agent pilots every team in a comparison. Otherwise a better result could come from better piloting.
- Matches use mirrored pairs with a shared battle seed. That practice removed seat bias from the Study P training runs.
- Team sheets are open, as in Study P. Anti-meta teams often win by surprise, and closed sheets would be a separate extension that measures it.
- Record the search budget in matches and wall time. Compare the searched team with one that has the same anchor and ban and random support.

## Prerequisites

- Pin and validate a dated Champions regulation. Studies F and T need this too, so it sits in the roadmap's shared foundation.
- Choose a Champions usage source and record its date and terms.
- Add Mega Evolution to the agents' actions. The reference team runs Tyranitarite, and both top meta threats in the video are Megas. Study T needs this too.
- Fix team preview for slow teams. `HeuristicAgent` orders its team by Speed and offense, and only the first four play, so it would bench a slow sand or Trick Room core such as Hippowdon and Farigiraf. It also has no Trick Room logic. A pilot that can't play the team would measure the pilot.

## Limits of the claims

A frozen meta pool is a rough model of the ladder. Beating it doesn't show a team would climb, and agent-piloted games don't measure human play. A strong anchored team shows that one team beat one pool with one pilot. It doesn't show that the anchor species is underrated. As in Study P, a null result is worth publishing when the evaluation could have detected a useful effect.

## Showcase

The study will appear as Study A on the Regulations screen. That screen's heading says each study changes one rule, and this one doesn't, so the copy needs to change when Study A is added.
