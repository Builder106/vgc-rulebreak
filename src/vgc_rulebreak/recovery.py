"""Turn checkpoint evaluations into habit-recovery series for analysis and the showcase."""

import gzip
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from vgc_rulebreak.mistakes import DETECTOR, DETECTOR_VERSION, candidate_mistakes

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


def mistake_stats(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool counts, keeping unavailable measurements distinct from zero events."""
    measured = [
        game["candidate_mistakes"][DETECTOR]
        for game in games
        if game.get("candidate_mistakes") is not None and DETECTOR in game["candidate_mistakes"]
    ]
    if any(metric["detector_version"] != DETECTOR_VERSION for metric in measured):
        raise ValueError("Cannot pool different candidate-mistake detector versions")
    events = sum(metric["events"] for metric in measured)
    opportunities = sum(metric["eligible_opportunities"] for metric in measured)
    return {
        "events": events,
        "eligible_opportunities": opportunities,
        "rate": events / opportunities if opportunities else None,
        "measured_games": len(measured),
        "unmeasured_games": len(games) - len(measured),
    }


def mistake_point(seeds: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    per_seed = {str(seed): mistake_stats(games) for seed, games in sorted(seeds.items())}
    rates = [stats["rate"] for stats in per_seed.values() if stats["rate"] is not None]
    return {
        DETECTOR: {
            "detector_version": DETECTOR_VERSION,
            **mistake_stats([game for games in seeds.values() for game in games]),
            "seeds": per_seed,
            "rate_across_seeds": (
                {"mean": sum(rates) / len(rates), "min": min(rates), "max": max(rates)}
                if rates
                else None
            ),
            "seeds_with_opportunities": len(rates),
        }
    }


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
            # Backfill old runs from complete decision records without rewriting them.
            if "candidate_mistakes" not in game and game.get("replay"):
                replay_path = path.parent / game["replay"]
                if replay_path.is_file():
                    replay = json.loads(gzip.decompress(replay_path.read_bytes()))
                    game["candidate_mistakes"] = candidate_mistakes(
                        replay["decisions"], game["candidate_role"]
                    )
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
                    "candidate_mistakes": mistake_point(seeds),
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
