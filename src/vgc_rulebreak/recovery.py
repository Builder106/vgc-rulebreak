"""Turn checkpoint evaluations into habit-recovery series for analysis and the showcase."""

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CHECKPOINT_NAME = re.compile(r"^(?P<agent>source|native|adapted)-s(?P<seed>\d+)-g(?P<gen>\d+)$")
POINTS = {"win": 1.0, "tie": 0.5, "unfinished": 0.5, "loss": 0.0}


def seed_stats(games: list[dict[str, Any]]) -> dict[str, float]:
    """Points per game and Protect habits for one checkpoint's evaluation games."""
    uses = sum(g["candidate_protect_uses"] for g in games)
    chances = sum(g["candidate_protect_opportunities"] for g in games)
    return {
        "games": len(games),
        "points_per_game": sum(POINTS[g["result"]] for g in games) / len(games),
        "protect_uses": uses,
        "protect_opportunities": chances,
        "protect_use_rate": uses / chances if chances else 0.0,
        "depletion_rate": sum(1 for g in games if g["protect_depleted"]) / len(games),
    }


def across_seeds(per_seed: dict[int, dict[str, float]], key: str) -> dict[str, float]:
    values = [stats[key] for stats in per_seed.values()]
    return {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}


def summarize_recovery(results_paths: Iterable[Path]) -> dict[str, Any]:
    """Group evaluated checkpoints by agent, ruleset, and generation.

    Each series point keeps every training seed's numbers next to their mean and range,
    so a chart can show the spread across seeds rather than only pooled games.
    """
    grouped: dict[tuple[str, str], dict[int, dict[int, list[dict[str, Any]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    provenance: dict[str, set[str]] = defaultdict(set)

    for path in sorted(results_paths):
        document = json.loads(path.read_text(encoding="utf-8"))
        match = CHECKPOINT_NAME.match(document["summary"]["candidate_name"])
        if match is None:
            continue
        agent, seed, generation = match["agent"], int(match["seed"]), int(match["gen"])
        for key in ("spec", "simulator_revision"):
            provenance[key].add(document[key])
        for game in document["games"]:
            provenance["opponent"].add(game["opponent"])
            grouped[(agent, game["variant"])][generation][seed].append(game)

    series = []
    for (agent, variant), generations in sorted(grouped.items()):
        points = []
        for generation, seeds in sorted(generations.items()):
            per_seed = {seed: seed_stats(games) for seed, games in sorted(seeds.items())}
            points.append(
                {
                    "generation": generation,
                    "seeds": {str(seed): stats for seed, stats in per_seed.items()},
                    "points_per_game": across_seeds(per_seed, "points_per_game"),
                    "protect_use_rate": across_seeds(per_seed, "protect_use_rate"),
                    "depletion_rate": across_seeds(per_seed, "depletion_rate"),
                    "games": sum(int(s["games"]) for s in per_seed.values()),
                    "protect_opportunities": sum(
                        int(s["protect_opportunities"]) for s in per_seed.values()
                    ),
                }
            )
        series.append({"agent": agent, "variant": variant, "points": points})

    return {
        "schema_version": SCHEMA_VERSION,
        **{key: sorted(values) for key, values in sorted(provenance.items())},
        "series": series,
    }
