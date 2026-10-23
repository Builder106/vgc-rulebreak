# VGC Rulebreak

[![CI](https://github.com/Builder106/vgc-rulebreak/actions/workflows/ci.yml/badge.svg)](https://github.com/Builder106/vgc-rulebreak/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#license)

Which Scarlet/Violet habits cost you games in Champions?

VGC Rulebreak is a research project about competitive Pokemon agents adapting to changed battle rules. The experiments measure which decisions become costly, how training changes those decisions, and whether improvements hold against opponents the agent did not train against.

The first study isolates Protect's 16-versus-8 PP allowance. Later studies cover Rage Fist, Speed, full Champions transfer, and reciprocal Tera/Mega transfer.

## Project status

The first Protect study has 99 checkpoints and 1,188 held-out games. No agent ran out of Protect PP, so this setup cannot show whether a 16 PP habit hurts under an 8 PP cap. The local [showcase](web/DESIGN.md) presents that result, every recorded game, and the open team sheets. It has not been deployed.

Read the [research plan](RESEARCH.md), [roadmap](ROADMAP.md), and [showcase brief](docs/showcase.md).

## Run the study tools

Use Python 3.12 and uv 0.12.5:

```sh
uv sync --frozen --group dev
uv run vgc-rulebreak check experiments/protect-pp.json
```

The command checks that the study changes only Protect PP, uses an immutable simulator revision, and declares independent training seeds. It reports remaining readiness declarations.

Run deterministic mechanics verification against a local Pokémon Showdown process:

```sh
uv run vgc-rulebreak verify-mechanics --spec experiments/protect-pp.json
```

This verifies 16 versus 8 maximum Protect PP, Rage Fist hit counter reset upon switching, and Speed stat modifier formulas.

Compare the source, adapted, and native agents and keep every game:

```sh
uv run vgc-rulebreak compare-agents --quick --output-dir runs/compare-quick
```

This writes `results.json` and one gzipped replay per game to `runs/compare-quick/`. The three agents are hand-written Protect scoring rules, not trained policies, so their results test the harness rather than the research question.

```sh
uv run vgc-rulebreak check experiments/protect-pp.json --require-ready
```

This exits with code 1 while the draft has missing declarations. See [CONTRIBUTING.md](CONTRIBUTING.md) for all checks and exit codes.

## Run the showcase

The static site is in `web/`. Install its locked dependencies, check the source, build it, and run the browser suite:

```sh
cd web
npm ci
npm run check
npm run lint
npm run build
npx playwright install chromium
npm run test:browser
```

The committed `web/data/` export contains all 1,188 battle records. To regenerate it from evaluation runs, use `vgc-rulebreak export-showcase` with `--runs` pointing at the evaluation directory and `--output web/data`. The export reads move names from the pinned Showdown checkout. Set `SITE_URL` to the public origin when building for deployment; without it, the build omits canonical URLs and the sitemap.

## Current flow

The specification validator and deterministic simulator fixtures verify the rules before training. The training and evaluation commands record checkpoints and games, then `export-showcase` turns those artifacts into the static data that Astro builds into the site.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/vgc_rulebreak/` | Specification validation, simulator adapter, fixtures, and CLI |
| `experiments/` | Versioned study specifications |
| `tests/` | Control-validation and CLI checks |
| `web/` | Static showcase, exported games, and browser checks |
| `RESEARCH.md` | Questions, controls, evaluation, and sources |
| `ROADMAP.md` | Implementation milestones and exit criteria |
| `docs/showcase.md` | Blunder Replay, Habit Recovery, and Matchup Desk brief |
| `JOURNAL.md` | Decisions behind the project |

Training data, checkpoints, raw evaluation replays, and generated reports are ignored by Git. The compact `web/data/` export is kept in the repository so each public battle page can be rebuilt from the recorded games.

## License

Project code is licensed under [MIT](LICENSE). Third-party simulator code, Pokemon assets, datasets, and model weights retain their own terms.
