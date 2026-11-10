# Study T: bidirectional Tera/Mega transfer

This backend pilot compares learned mechanic activation timing in both directions:
Gen 9 Tera to Champions Mega and Champions Mega to Gen 9 Tera. It uses the pinned
Showdown revision `9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e` and the complete
`gen9doublescustomgame` / `gen9championsdoublescustomgame` rulesets. These are
synthetic custom-game fixtures. They do not certify official regulation legality
or isolate the mechanic from the other ruleset changes.

## Protocol and acceptance

```sh
uv run vgc-rulebreak compare-tera-mega --output-dir runs/tera-mega-2026-11-10
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
form and item accounting is below; controlled mechanic-only formats remain a
subsequent roadmap task.

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
still includes other rules; this accounting does not isolate a mechanic effect.

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

## Pilot result: 2026-11-10

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
