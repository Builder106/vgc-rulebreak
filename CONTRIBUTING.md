# Contributing

Start with [RESEARCH.md](RESEARCH.md) and [ROADMAP.md](ROADMAP.md). The first experiment isolates Protect PP. Keep changes small enough to evaluate independently.

## Setup and checks

Use Python 3.12 and uv 0.12.5. Install the locked development environment:

```sh
uv sync --frozen --group dev
uv run vgc-rulebreak check experiments/protect-pp.json
```

Run the same checks as CI:

```sh
uv run mypy
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
uv run --isolated --no-project --with ./dist/vgc_rulebreak-0.1.0-py3-none-any.whl vgc-rulebreak check experiments/protect-pp.json
uv export --quiet --frozen --all-groups --no-emit-project --output-file /tmp/vgc-rulebreak-requirements.txt
uv run pip-audit --strict --disable-pip --require-hashes --cache-dir /tmp/vgc-rulebreak-audit-cache --requirement /tmp/vgc-rulebreak-requirements.txt
```

`check` validates the specification and reports missing declarations. `--require-ready` exits with code 1 while declarations are missing. It does not launch a simulator, inspect a team manifest, or establish that mechanic fixtures passed. Invalid input exits with code 2.

## Research guardrails

Pin simulator and data versions. Keep test teams and seeds separate from tuning. Log rule changes, budgets, and source checkpoints. Add a test for any new decision, parser, or statistical invariant. Simulator code needs process integration and mechanic fixtures. Browser code needs interaction checks.

Keep datasets, raw replays, checkpoints, build output, and secrets outside Git. Small synthetic fixtures can live under `tests/` when their provenance is clear. Do not weaken checks or turn a selected replay into an unsupported aggregate claim.

## Pull requests

Use a short topic branch from `main` and a Conventional Commit title. Explain the behavioral change and how it was checked. Required CI must pass before merge. Squash completed topic branches and delete them after merge.

Training, team optimization, historical video reconstruction, and a production demo are not implemented by this scaffold. Add them only through the roadmap with an explicit evaluation question and data source.
