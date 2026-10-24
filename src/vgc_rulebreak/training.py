"""Train the Protect policy's parameters against game outcomes with the cross-entropy method.

Each generation plays the current mean and sampled candidates on the same battle seeds,
refits the sampling distribution to the best candidates, and saves the mean it played as
that generation's checkpoint. Only training-split teams are used.
"""

import hashlib
import json
import math
import random
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.trained import (
    HEURISTIC_PARAMS,
    ProtectParams,
    TrainedProtectAgent,
    load_checkpoint,
)
from vgc_rulebreak.evaluation import FORMAT_BY_PP, build_test_matchups, run_evaluation_battle
from vgc_rulebreak.manifest import TeamManifest
from vgc_rulebreak.spec import ExperimentSpec

SCHEMA_VERSION = 1
AGENT_RULESETS: dict[str, str] = {
    "source": "protect-16",
    "native": "protect-8",
    "adapted": "protect-8",
}
TRAINING_OPPONENT = "HeuristicBaseline"
# Sampling spread in unit-scaled parameter space: wide from scratch, narrow when adapting.
FRESH_STD = 0.25
ADAPT_STD = 0.1
MIN_STD = 0.02

# Given candidate parameters and the generation index, return stats per candidate,
# each with a "fitness" key. Training uses real battles; tests can pass a cheap function.
FitnessFn = Callable[[list[ProtectParams], int], list[dict[str, float]]]


@dataclass(frozen=True)
class TrainingConfig:
    agent: str
    training_seed: int
    generations: int = 12
    population: int = 12
    elites: int = 4
    pairs: int = 1
    workers: int = 4

    @property
    def ruleset(self) -> str:
        return AGENT_RULESETS[self.agent]


@dataclass(frozen=True)
class GameTask:
    params: dict[str, float]
    format_id: str
    candidate_team: str
    opponent_team: str
    candidate_role: str
    seed: tuple[int, int, int, int]
    showdown_dir: str | None


def training_battle_seed(
    training_seed: int, generation: int, matchup: int, pair: int
) -> tuple[int, int, int, int]:
    """Derive the Showdown seed for one mirrored training pair.

    Both games of a pair use this seed with the seats swapped, and every candidate in a
    generation plays the same seeds. With a fixed seed the seat decides a mirror match
    between identical policies, so a policy that plays like the opponent scores exactly
    one point per pair and only differences in play move its fitness.
    """
    key = f"train:{training_seed}:{generation}:{matchup}:{pair}".encode()
    digest = hashlib.sha256(key).digest()
    a, b, c, d = (int.from_bytes(digest[i : i + 2], "big") for i in (0, 2, 4, 6))
    return (a, b, c, d)


def play_training_game(task: GameTask) -> dict[str, float]:
    """Play one training game against the heuristic baseline and summarize it."""
    result = run_evaluation_battle(
        candidate_agent=TrainedProtectAgent(ProtectParams(**task.params), name="Candidate"),
        opponent_agent=HeuristicAgent(TRAINING_OPPONENT),
        format_id=task.format_id,
        candidate_team=task.candidate_team,
        opponent_team=task.opponent_team,
        candidate_role=task.candidate_role,
        seed=task.seed,
        showdown_dir=task.showdown_dir,
    )
    if result.candidate_won:
        points = 1.0
    elif result.winner is not None:
        points = 0.0
    else:
        points = 0.5
    return {
        "points": points,
        "protect_uses": float(result.candidate_protect_uses),
        "protect_opportunities": float(result.candidate_protect_opportunities),
        "protect_depleted": float(result.protect_depleted),
        "turns": float(result.turns),
    }


def summarize_games(games: Sequence[dict[str, float]]) -> dict[str, float]:
    """Fitness is mean points per game; Protect use is per legal opportunity."""
    total = len(games)
    uses = sum(g["protect_uses"] for g in games)
    chances = sum(g["protect_opportunities"] for g in games)
    return {
        "fitness": sum(g["points"] for g in games) / max(total, 1),
        "games": float(total),
        "protect_use_rate": uses / chances if chances else 0.0,
        "protect_uses_per_game": uses / max(total, 1),
        "depletion_rate": sum(g["protect_depleted"] for g in games) / max(total, 1),
        "avg_turns": sum(g["turns"] for g in games) / max(total, 1),
    }


def run_cem(
    config: TrainingConfig,
    fitness_fn: FitnessFn,
    init_mean: list[float],
    init_std: float,
    on_checkpoint: Callable[[int, list[float], list[float], dict[str, object]], None],
) -> list[float]:
    """Run the cross-entropy method in unit-scaled parameter space and return the final mean.

    Candidate 0 of every generation is the current mean, so each checkpoint's stats come
    from the same games as the candidates it was compared with.
    """
    if not 1 <= config.elites <= config.population:
        raise ValueError("elites must be between 1 and the population size")
    rng = random.Random(config.training_seed)
    mean = [min(max(m, 0.0), 1.0) for m in init_mean]
    std = [init_std] * len(mean)

    for generation in range(config.generations):
        samples = [list(mean)]
        for _ in range(config.population - 1):
            samples.append(
                [
                    min(max(m + s * rng.gauss(0.0, 1.0), 0.0), 1.0)
                    for m, s in zip(mean, std, strict=True)
                ]
            )
        stats = fitness_fn([ProtectParams.from_unit(s) for s in samples], generation)
        ranked = sorted(range(len(samples)), key=lambda k: stats[k]["fitness"], reverse=True)
        elite = [samples[k] for k in ranked[: config.elites]]
        on_checkpoint(
            generation,
            mean,
            std,
            {
                "mean_stats": stats[0],
                "best_fitness": stats[ranked[0]]["fitness"],
                "elite_fitness": sum(stats[k]["fitness"] for k in ranked[: config.elites])
                / config.elites,
            },
        )
        mean = [sum(column) / len(elite) for column in zip(*elite, strict=True)]
        std = [
            max(MIN_STD, math.sqrt(sum((v - m) ** 2 for v in column) / len(elite)))
            for column, m in zip(zip(*elite, strict=True), mean, strict=True)
        ]

    on_checkpoint(config.generations, mean, std, {})
    return mean


def train_protect_policy(
    spec: ExperimentSpec,
    manifest: TeamManifest,
    config: TrainingConfig,
    output_dir: Path,
    init_checkpoint: Path | None = None,
    showdown_dir: Path | str | None = None,
) -> list[Path]:
    """Train one agent for one training seed and write a checkpoint per generation."""
    if config.agent not in AGENT_RULESETS:
        raise ValueError(f"agent must be one of {sorted(AGENT_RULESETS)}")
    if config.training_seed not in spec.training_seeds:
        raise ValueError(
            f"training seed {config.training_seed} is not in the spec's training_seeds"
        )
    if (config.agent == "adapted") != (init_checkpoint is not None):
        raise ValueError(
            "the adapted agent needs --init with a source checkpoint; others take none"
        )

    init_meta: dict[str, Any] | None = None
    if init_checkpoint is not None:
        init_params, init_meta = load_checkpoint(init_checkpoint)
        if init_meta.get("agent") != "source":
            raise ValueError("the adapted agent must start from a source checkpoint")
        if init_meta.get("format_id") != FORMAT_BY_PP[16]:
            raise ValueError("the source checkpoint must use the Protect-only 16 PP format")
        init_mean, init_std = init_params.to_unit(), ADAPT_STD
    else:
        init_mean, init_std = HEURISTIC_PARAMS.to_unit(), FRESH_STD

    training_teams = manifest.splits["training"]
    held_out = set(manifest.splits["validation"]) | set(manifest.splits["test"])
    if held_out & set(training_teams):
        raise ValueError("training teams overlap the validation or test split")
    matchups = build_test_matchups(manifest, training_teams)
    format_id = FORMAT_BY_PP[spec.variants[config.ruleset]]
    sd = str(showdown_dir) if showdown_dir is not None else None

    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    games_per_candidate = len(matchups) * config.pairs * 2

    def checkpoint(
        generation: int, mean: list[float], std: list[float], stats: dict[str, object]
    ) -> None:
        path = checkpoint_dir / f"{config.agent}-s{config.training_seed}-g{generation:02d}.json"
        document = {
            "schema_version": SCHEMA_VERSION,
            "agent": config.agent,
            "ruleset": config.ruleset,
            "format_id": format_id,
            "training_seed": config.training_seed,
            "generation": generation,
            "params": asdict(ProtectParams.from_unit(mean)),
            "unit_mean": [round(v, 6) for v in mean],
            "unit_std": [round(v, 6) for v in std],
            "training": {
                **stats,
                "evaluated": bool(stats),
                "games_per_candidate": games_per_candidate,
                "games_before": generation * config.population * games_per_candidate,
            },
            "config": asdict(config),
            "init_checkpoint": init_meta
            and {
                "agent": init_meta["agent"],
                "training_seed": init_meta["training_seed"],
                "generation": init_meta["generation"],
            },
            "opponent": TRAINING_OPPONENT,
            "training_teams": list(training_teams),
            "spec": spec.name,
            "simulator_revision": spec.simulator_revision,
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        fitness = stats.get("mean_stats", {}).get("fitness")
        note = f"mean fitness {fitness:.3f}" if fitness is not None else "final mean"
        print(f"{path.name}: {note}", file=sys.stderr, flush=True)

    def tasks_for(candidate: ProtectParams, generation: int) -> list[GameTask]:
        tasks = []
        for m_idx, (_t1, t1_packed, _t2, t2_packed) in enumerate(matchups):
            for pair in range(config.pairs):
                seed = training_battle_seed(config.training_seed, generation, m_idx, pair)
                for own, other, role in (
                    (t1_packed, t2_packed, "p1"),
                    (t2_packed, t1_packed, "p2"),
                ):
                    tasks.append(GameTask(asdict(candidate), format_id, own, other, role, seed, sd))
        return tasks

    def run_all(tasks: list[GameTask], pool: ProcessPoolExecutor | None) -> list[dict[str, float]]:
        if pool is None:
            return [play_training_game(t) for t in tasks]
        return list(pool.map(play_training_game, tasks))

    def make_fitness(pool: ProcessPoolExecutor | None) -> FitnessFn:
        def fitness(candidates: list[ProtectParams], generation: int) -> list[dict[str, float]]:
            batches = [tasks_for(c, generation) for c in candidates]
            results = run_all([t for batch in batches for t in batch], pool)
            out, start = [], 0
            for batch in batches:
                out.append(summarize_games(results[start : start + len(batch)]))
                start += len(batch)
            return out

        return fitness

    if config.workers > 1:
        with ProcessPoolExecutor(max_workers=config.workers) as pool:
            run_cem(config, make_fitness(pool), init_mean, init_std, checkpoint)
    else:
        run_cem(config, make_fitness(None), init_mean, init_std, checkpoint)
    return written
