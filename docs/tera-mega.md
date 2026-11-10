# Study T: bidirectional Tera/Mega transfer

This backend pilot compares learned mechanic activation timing in both directions:
Gen 9 Tera to Champions Mega and Champions Mega to Gen 9 Tera. It uses the pinned
Showdown revision `9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e`. The original `full`
mode uses the complete `gen9doublescustomgame` / `gen9championsdoublescustomgame`
rulesets. The `mechanic-only` mode holds the Champions background fixed while
varying mechanic availability and declared stones. Both use synthetic custom-game
fixtures and do not certify official regulation legality.

## Protocol and acceptance

```sh
uv run vgc-rulebreak compare-tera-mega --rules-mode full --output-dir runs/tera-mega-2026-11-10
```

Use an empty directory. `--showdown-dir` overrides simulator discovery; tracked
changes or a revision other than the pinned one fail before creating outputs.
`--generations`, `--population`, `--elites`, `--pairs` and `--workers` record an
explicitly chosen budget. Freeze these before inspecting held-out results.

The separate frozen `experiments/teams/tera-mega.json` has two training families
(rain/sun), reserved validation (tailwind), and two held-out families (bulky/sand).
It copies Study F's synthetic sets, independently of subsequent changes to that
study. Every member is level 50, neutral nature, zero EV/SP investment, default
IVs. Base species, moves, abilities and Tera types stay identical across domains.
The Tera domain has no held items. The Mega domain adds Gyaradosite to rain's
Gyarados, Charizardite Y to sun's Charizard, Lucarionite to validation's Lucario,
Slowbronite to bulky's Slowbro, and Tyranitarite to sand's Tyranitar. The private
packed sets for both domains are recorded in `protocol.json`. Detailed species,
form and item accounting is below. The controlled formats use these same sets.

`ActivationAgent` learns one scalar, an HP-fraction threshold in [0, 1]. It uses
its own requests and public log messages. After choosing moves with the existing
heuristic, it activates the available mechanic on the first eligible active slot
whose current HP fraction is at or below the threshold. Each request adds at
most one modifier (`mega` or `terastallize`) to a move choice. It suppresses the
inherited fixed Mega move bonus. Preview and forced switches do not activate.
The same scalar and action rule transfer unchanged across domains; there is no
new untrained action head after transfer. Tera can select any member, whereas
Mega eligibility requires the declared stone holder. Move choice, recipient
order, builds, Tera types and the opponent remain fixed heuristics. This policy
can learn activation timing only, not broad strategic competence.

The opponent uses the same policy with threshold 1 (immediate activation on the
first eligible slot). Training uses CEM with fresh mean 0.75, standard deviation
0.25, an incumbent candidate and clipped Gaussian samples. Fitness is points per
game; stable ties retain the incumbent. Adaptation starts from the exact source
checkpoint scalar, with sampling standard deviation 0.1. Each checkpoint retains
training outcomes, sampled thresholds, fitness and activation opportunities/uses.
Unfinished training games fail instead of becoming draws.

Default training seeds are 11/29/47; independent evaluation seeds are
101/202/303. With G generations, population P and M mirrored pairs, one training
stage B costs `G × P × 3 training matchups × M × 2 seats` games per seed. At
defaults G=1, P=2, M=1, B=12 games. For each direction:

- Source trains from scratch in its domain for B games.
- Unchanged source is evaluated in both source and target domains.
- Adapted starts from that source and trains for another B target games.
- Native target-budget reference trains from scratch in the target for B games.
- Native total-budget reference trains from scratch in the target for 2B games.

Native references are checkpoints on one fresh target-domain trajectory at B and
2B; they share no learned initialization with the transferred policy. The fresh
B checkpoint also serves as the reverse direction's source. This reuse avoids
identical repeated training; native and source estimates across directions are
correlated, not additional independent replicates. The two fresh 2B trajectories
and two adapted B trajectories cost 216 unique training games at defaults.
Adaptation has twice the total experience of the native B reference. Only the
native 2B comparison matches its total budget at the final adapted generation.
At earlier generations the fixed final native references have larger budgets;
do not use those gaps to claim equal-budget recovery speed.

Evaluation freezes all checkpoints. No held-out result tunes or selects them.
All three unique held-out team pairings, including self matches, play both
seats, using the same battle seed across domains, checkpoints and directions.
At defaults there are 540 evaluation games: three training seeds, three eval
seeds, three matchups, two seats, five cells, two directions. All games retain
per-game results and compressed replay evidence; the raw records keep
domain-qualified team IDs and activation choices/opportunities. The counters
measure requested activations, with actual execution inspectable in replays.

Within each direction, the five cells define one paired block. An unfinished
game excludes the entire block, including both native references. Missing,
duplicate or inconsistently seeded cells, missing mirrored seats, differing
training-seed schedules, or a team without completed support from every training
seed fail summarization. The report gives each candidate team and the full pool:

- Transfer loss = source score at home minus unchanged source on target.
- Recovery at g = adapted target score at g minus unchanged source on target.
- Native gap at g = native B target score minus adapted target score at g.
- Native total gap at g = native 2B target score minus adapted target score at g.

Wins score 1, ties 0.5 and losses 0 points. Positive loss means worse after
transfer; positive recovery means improvement; positive gaps favor the native
reference. Compute differences within blocks, then means within training seeds,
then equally weighted seed means and 5,000 deterministic bootstrap resamples for
95% intervals. The uncertainty unit is the training seed, conditional on this
finite team pool and evaluation schedule. No unpaired cross-direction recovery
difference is inferred.

Acceptance requires tests of shared legal activation, exact adaptation
initialization, independent native training and both budget definitions, split
isolation, completed-block statistics including native 2B, seed-level intervals,
and real simulator Tera/Mega execution. A real pinned-simulator run must retain
`protocol.json`, `checkpoints/`, `results.json`, `replays/` and
`transfer_report.json` under ignored `runs/`, with input and implementation hashes.
Report negative or null pilot results without generalizing beyond this policy
and these fixtures. No frontend implementation is part of this milestone.

## Limits: human skill and metagame optimality

The published estimates describe one learned HP activation threshold, fixed
move/preview heuristics, a fixed immediate-activation opponent, two held-out
synthetic team families and the recorded seed/budget schedule. They measure
points per game and changes in those points after transfer or adaptation.
Native references are fresh training trajectories within this same restricted
policy class; "native" does not mean expert or optimal play.

No human participants, player ratings, human learning curves or human decision
quality were measured. Agent recovery therefore cannot rank Tera and Mega by
human difficulty, skill floor, skill ceiling or ease of human transfer. It
depends on the policy representation, fixed recipient order, search method,
source experience and budget. Equal training-game counts do not establish equal
compute costs or comparable human practice. A claim about human skill would
require a separate human study with defined skill measures, matched experience,
controlled rules and uncertainty across players.

Performance against this finite opponent/team pool does not establish metagame
optimality, a solved format, an unexploitable policy, optimal team composition,
species viability or ladder/tournament strength. The pilot does not optimize
teams, builds, ordinary items, Tera types, recipient selection or the opponent's
responses. It includes no best-response search, exploitability bound or
equilibrium certificate. A native gap measures the recorded reference's score
minus the adapted score; it is not distance from optimal play. Broader strength
claims would need legal dated teams, stronger diverse opponents, team-selection
experiments and independent evaluation on new opponents and metagame snapshots.
Such evaluations would still bound the tested scope rather than prove global
optimality.

The full-rules result combines mechanic and background changes. The controlled
result isolates the declared mechanic package on the fixed Champions
background, including stone, recipient and form differences; it cannot rank the
mechanics independently of that background or those constructions. Neither
custom-game pool certifies official regulation legality or real-game fidelity.

The 95% intervals resample only three training seeds, conditional on the frozen
teams and evaluation schedule. They omit uncertainty from new teams, opponent
policies, rules versions and alternative policy classes. Zero recovery and
zero-width intervals describe this pilot; they do not establish equivalence,
absence of transferable knowledge or lack of benefit from larger budgets.
The reused source/native checkpoints also prevent treating the two directions
as independent evidence that one mechanic is easier. Report the observed
conditional score differences alongside these limits, including null or
negative results.

New `transfer_report.json` artifacts carry human-skill and metagame-optimality
limits in their `limitations` list in both rules modes. The archived pilots
retain their original artifacts and hashes; this section supplies the
interpretive limits for those results too.

## Common species and item/form accounting

Here, "common" means the same starting base species in both domains of the
frozen [Study T manifest](../experiments/teams/tera-mega.json), not a species'
usage rank or certified availability in both official games. All 20 distinct
base species are shared, in the same four-member team order. No member is
substituted between domains. Each entry below gives the species and its fixed
Tera type; those types remain recorded but cannot activate in the Mega domain.

| Split | Team / family | Shared species (Tera type), in manifest order | Mega recipient |
| --- | --- | --- | --- |
| Training | `train-rain` / rain | Pelipper (Water), Ludicolo (Grass), Raichu (Electric), Gyarados (Water) | Gyarados |
| Training | `train-sun` / sun | Torkoal (Fire), Venusaur (Poison), Arcanine (Fire), Charizard (Flying) | Charizard |
| Validation, reserved | `val-tailwind` / tailwind | Talonflame (Flying), Dragonite (Dragon), Gengar (Ghost), Lucario (Fighting) | Lucario |
| Held-out test | `test-bulky` / bulky | Annihilape (Ghost), Maushold (Normal), Snorlax (Normal), Slowbro (Psychic) | Slowbro |
| Held-out test | `test-sand` / sand | Tyranitar (Rock), Excadrill (Ground), Hippowdon (Ground), Garchomp (Dragon) | Tyranitar |

Starting moves, abilities, nature, level, IVs, zero investment and pre-activation
stats match across domains. The validation family is reserved, with no training
or held-out evaluation games in this pilot. Both the candidate and opponent use
these same domain-specific team constructions, in either transfer direction.

The only packed-set edits are five item fields: one stone per Mega-domain team,
already held before activation. All other 15 Mega-domain members have empty
item slots; all 20 Tera-domain members have empty slots. A compatible stone is
required for each selected Mega form and occupies the holder's single item
slot. Tera requires no held item. Leaving Tera's slots empty and giving no
ordinary items to the other members are experimental choices, not requirements
of Tera or Champions. The pilot therefore does not measure the opportunity cost
against optimized ordinary items. Giving a stone to only one member per team
also fixes Mega's recipient by design; other shared species with Mega forms
receive no stone and cannot Mega Evolve in these fixtures.

The five starting species remain in their base forms until Mega activation.
These are the resulting forms and their unavoidable type/ability changes in
the pinned Champions simulator:

| Stone | Starting species → activated form | Starting types → Mega types | Declared ability → Mega ability |
| --- | --- | --- | --- |
| Gyaradosite | Gyarados → Gyarados-Mega | Water/Flying → Water/Dark | Intimidate → Mold Breaker |
| Charizardite Y | Charizard → Charizard-Mega-Y | Fire/Flying → Fire/Flying | Solar Power → Drought |
| Lucarionite | Lucario → Lucario-Mega | Fighting/Steel → Fighting/Steel | Inner Focus → Adaptability |
| Slowbronite | Slowbro → Slowbro-Mega | Water/Psychic → Water/Psychic | Regenerator → Shell Armor |
| Tyranitarite | Tyranitar → Tyranitar-Mega | Rock/Dark → Rock/Dark | Sand Stream → Sand Stream |

Mega also changes base stats. In HP/Atk/Def/SpA/SpD/Spe order, the Mega-minus-base
deltas are Gyarados `0/+30/+30/+10/+30/0`, Charizard Y
`0/+20/0/+50/+30/0`, Lucario `0/+35/+18/+25/0/+22`, Slowbro
`0/0/+70/+30/0/0`, and Tyranitar `0/+30/+40/0/+20/+10`. These are base-stat
deltas from this pinned mod, not battle-stat increments or claims about another
game version. The same starting stats do not imply equal stats after activation.

Tera instead retains each listed species, ability and base stats while changing
its defensive typing to the declared single Tera type and applying the
simulator's Tera STAB rules. None of these fixtures uses a special Tera form or
Stellar type. Either mechanic uses the team's once-per-battle activation and
persists through switching. Tera can select any of the four members; Mega can
select only that team's stone holder. Thus matching base species cannot match
the recipient choices, item slots or activated types, abilities and stats.
These differences are part of this transfer setup. The complete format change
in `full` mode still includes other rules; this accounting alone does not isolate
a mechanic effect.

The item mapping and exact packed-set invariant are implemented in
[`domain_teams`](../src/vgc_rulebreak/tera_mega.py). At simulator revision
`9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e`, the resolved
`Dex.mod('champions').species` entries supply the Mega types, abilities and base
stats above. Upstream `data/items.ts`, `sim/battle-actions.ts` and
`data/mods/champions/scripts.ts` define stone eligibility and activation/form
behavior. The existing checks can be rerun against a built pinned checkout:

```sh
SHOWDOWN_PATH=/path/to/pinned/pokemon-showdown uv run pytest tests/test_tera_mega.py
```

They reject fixture drift, compare every unpacked set with the manifest, verify
equal starting stats and the four-versus-one eligibility difference for every
team, and execute both mechanics in real simulator battles. The form tables
record the resolved simulator data; they do not certify official team legality.

## Separate the mechanic intervention from the rules background

```sh
uv run vgc-rulebreak compare-tera-mega --rules-mode mechanic-only --output-dir runs/tera-mega-controlled-2026-11-10
```

The controlled pair copies the same pinned Champions Doubles Custom Game format:

| Domain | Experimental format | Availability override |
| --- | --- | --- |
| Tera | `gen9rulebreakchampionstera` | Disable Mega eligibility; restore the base Gen 9 Tera eligibility function |
| Mega | `gen9rulebreakchampionsmega` | Keep native Champions eligibility and execution |

Both retain the Champions Dex, species/form data, moves, abilities, damage
calculation, PP calculation (including 8 maximum Protect PP), stat formulas,
Rage Fist reset, switch behavior, team preview and every other format setting.
Tera execution already exists in the pinned simulator; the overlay restores its
availability without importing a different mod. Both players use the same chosen
domain. The repository-owned preload leaves the simulator checkout untouched.

The experimental intervention includes the five declared stone additions, Mega's
recipient restriction and resulting form/type/ability/stat changes. These are
part of the mechanic package described above. This is not an estimate of
activation alone at identical held items or identical recipient choices.

Both modes run the same bidirectional training/evaluation protocol, split,
budgets, seeds and paired-block statistics. `full` remains the CLI default for
compatibility with the original pilot. Every protocol/report records the mode,
resolved format IDs, rules background, intervention description and overlay
SHA-256; checkpoints and individual games record their actual format IDs. Use
separate empty output directories to keep the two experiments distinct.

The controlled loss/recovery estimates describe transfer of the mechanic package
conditional on the Champions background. The original full-mode estimates still
combine mechanic and unrelated rule changes. Independently trained source
policies can differ between modes, so subtracting these reports does not produce
an additive causal decomposition or a rule-only effect. Testing background
interactions on additional fixed backgrounds would require a further experiment.

Acceptance checks in `tests/test_tera_mega_formats.py` compare all format settings
except identity and eligibility, the resolved Dex/rules/action functions, all
five teams' stats/PP, Champions Rage Fist reset, and identical seeded battle traces
with no activation. `tests/test_tera_mega.py` verifies availability for every team,
real Tera and Mega events through the normal process adapter, and both modes'
training formats, exact adaptation initialization, native budgets, split isolation
and output provenance. These checks isolate the intervention at the simulator
boundary; they do not turn the earlier full-mode result into a controlled result.

## Full-rules pilot result: 2026-11-10

The default pinned-simulator run completed 216 training games and recorded all
540 evaluations, 540 compressed replays and 30 checkpoints in
`runs/tera-mega-2026-11-10/`, using the isolated clean simulator checkout at
`/tmp/vgc-rulebreak-showdown-clean`. Evaluation battle time summed to 664.442
seconds, excluding training and orchestration. One native-B Mega-to-Tera
evaluation stalled before turn one; its whole five-cell block was excluded. Tera-to-Mega
retains 54 blocks, and Mega-to-Tera retains 53. Every team retains all three
training seeds. An audit of every replay found no simulator error, no activation
of the wrong mechanic, and agreement between every requested and executed
activation count. There were no unfinished training games.

Each table entry is points per game, with 95% training-seed bootstrap intervals.
B denotes one training stage, 12 games per seed in this run; 2B denotes 24 games.

| Direction | Candidate | Transfer loss [95% CI] | Recovery g1 [95% CI] | Native B gap [95% CI] | Native 2B gap [95% CI] |
| --- | --- | --- | --- | --- | --- |
| Tera to Mega | Whole pool | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | -0.0741 [-0.2222, 0.0000] | -0.0741 [-0.2222, 0.0000] |
| Tera to Mega | Bulky | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | -0.1111 [-0.3333, 0.0000] | -0.1111 [-0.3333, 0.0000] |
| Tera to Mega | Sand | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | -0.0370 [-0.1111, 0.0000] | -0.0370 [-0.1111, 0.0000] |
| Mega to Tera | Whole pool | -0.0784 [-0.2353, 0.0000] | 0.0000 [0.0000, 0.0000] | -0.0196 [-0.0588, 0.0000] | -0.0196 [-0.0588, 0.0000] |
| Mega to Tera | Bulky | -0.1250 [-0.3750, 0.0000] | 0.0000 [0.0000, 0.0000] | -0.0417 [-0.1250, 0.0000] | -0.0417 [-0.1250, 0.0000] |
| Mega to Tera | Sand | -0.0370 [-0.1111, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |

Tera-to-Mega pooled source/home, source/target and adapted/target scores are all
0.3889; native B and 2B both score 0.3148. Mega-to-Tera's corresponding scores
are 0.3181, 0.3965, 0.3965, 0.3769 and 0.3769. The latter scores use its own
completed paired blocks, so they cannot be directly substituted into the other
direction's estimates. Native B and 2B differ in some activation decisions but
have identical scores on retained blocks in this run.

There is no measured adaptation recovery in either direction. Negative native
gaps favor the transferred policy on these fixtures, but the intervals include
zero; this does not establish a transfer advantage. Zero recovery/loss intervals
reflect identical observed seed-level differences, not certainty about unseen
teams or larger training budgets. The one-dimensional policy, three seeds,
fixed opponent, recipient asymmetry and combined ruleset change prevent broad
claims about Tera versus Mega skill, recovery speed or human transfer.

Frozen manifest SHA-256:
`124a8738eac25a679e1b32ae7beabfbff1fdd63c4a94d2d0e5f7335000089154`.
Completed `transfer_report.json` SHA-256:
`a81cf43afe4f116ee13b5c9e534352ea58a47fa8c9161d5ac5adf3bc3e2d0ef2`.

## Controlled pilot result: 2026-11-10

The default-budget `mechanic-only` run completed 216 training games and retained
540 evaluations, 540 compressed replays and 30 checkpoints under
`runs/tera-mega-controlled-2026-11-10/`. It used the clean pinned checkout at
`/tmp/vgc-rulebreak-milestone95-showdown`. Evaluation battle time summed to
536.375 seconds, excluding training and orchestration. Game `g00330`, a
Mega-to-Tera native-2B evaluation at training seed 29, stalled before turn one;
its entire five-cell block was excluded. The two directions retain 54 and 53
blocks, respectively, with all three training seeds supporting every team.

| Direction / whole pool | Transfer loss [95% CI] | Recovery g1 [95% CI] | Native B gap [95% CI] | Native 2B gap [95% CI] |
| --- | --- | --- | --- | --- |
| Tera to Mega | 0.1111 [0.1111, 0.1111] | 0.0000 [0.0000, 0.0000] | -0.0741 [-0.2222, 0.0000] | -0.0741 [-0.2222, 0.0000] |
| Mega to Tera | -0.1874 [-0.3333, -0.1111] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |

Scores are points per game with the same training-seed bootstrap as the full
pilot. Tera-to-Mega source/home, source/target and adapted/target score 0.5000,
0.3889 and 0.3889; both native references score 0.3148. Mega-to-Tera's scores on
its retained blocks are 0.3028, 0.4902 and 0.4902; both natives score 0.4902.
There is no measured adaptation recovery. Zero-width intervals mean identical
observed seed differences on this finite schedule, not certainty on unseen
teams. The changed loss relative to the full pilot is not a rule-only effect:
the Tera training/evaluation background differs between experiments.

An audit of all 540 replays found no simulator errors, no wrong-mechanic events,
at most one executed activation per side, and exact agreement between requested
and executed activation counts (538 Tera and 531 Mega across both players).
Training checkpoint records account for all 216 games. The run retains the
executed Python source snapshot as `implementation.py`, matching its protocol
implementation hash, alongside the frozen inputs and overlay hash.
Completed `transfer_report.json` SHA-256:
`d1797bcba66f2fcd2783c26a7a4100259f8266f2107c197632f747aea9d0ad3f`.
