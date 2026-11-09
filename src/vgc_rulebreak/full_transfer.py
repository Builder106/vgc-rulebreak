"""Study F: checkpoint transfer across the complete pinned simulator rulesets."""

import hashlib
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.trained import (
    HEURISTIC_PARAMS,
    ProtectParams,
    TrainedProtectAgent,
    checkpoint_agent,
    load_checkpoint,
)
from vgc_rulebreak.champions import load_champions_regulation
from vgc_rulebreak.evaluation import build_test_matchups, run_evaluation_battle
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.protect_multi_seed import calculate_ci
from vgc_rulebreak.records import GameContext, GameRecorder, game_outcome
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.training import (
    ADAPT_STD,
    FRESH_STD,
    GameTask,
    TrainingConfig,
    run_cem,
    summarize_games,
    training_battle_seed,
)

SIMULATOR_REVISION = "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e"
SOURCE_FORMAT = "gen9doublescustomgame"
MANIFEST_PATH = Path("experiments/teams/full-transfer.json")
REGULATION_PATH = Path("experiments/champions-regulation.json")


@dataclass(frozen=True)
class FullTransferConfig:
    training_seeds: tuple[int, ...] = (11, 29, 47)
    evaluation_seeds: tuple[int, ...] = (101, 202, 303)
    generations: int = 1
    population: int = 2
    elites: int = 1
    pairs: int = 1
    workers: int = 4

    def validate(self) -> None:
        for seeds in (self.training_seeds, self.evaluation_seeds):
            if len(seeds) < 3 or len(set(seeds)) != len(seeds):
                raise ValueError("at least three distinct training and evaluation seeds required")
        if set(self.training_seeds) & set(self.evaluation_seeds):
            raise ValueError("training and evaluation seeds must be disjoint")
        if min(self.generations, self.population, self.elites, self.pairs, self.workers) < 1:
            raise ValueError("training budgets, pairs, and workers must be positive")
        if self.elites > self.population:
            raise ValueError("elites must not exceed population")


def _training_game(task: GameTask) -> dict[str, float]:
    result = run_evaluation_battle(
        TrainedProtectAgent(ProtectParams(**task.params), name="Candidate"),
        HeuristicAgent("HeuristicBaseline"),
        task.format_id,
        task.candidate_team,
        task.opponent_team,
        task.candidate_role,
        task.seed,
        task.showdown_dir,
        skip_build=True,
    )
    outcome = game_outcome(result)
    if outcome == "unfinished":
        raise ValueError("unfinished training game; refusing to score it as a draw")
    return {
        "points": {"win": 1.0, "loss": 0.0, "tie": 0.5}[outcome],
        "protect_uses": float(result.candidate_protect_uses),
        "protect_opportunities": float(result.candidate_protect_opportunities),
        "protect_depleted": float(result.protect_depleted),
        "turns": float(result.turns),
    }


def _train(
    config: FullTransferConfig,
    manifest: TeamManifest,
    root: Path,
    agent: str,
    seed: int,
    format_id: str,
    showdown_dir: Path,
    init: Path | None = None,
) -> list[Path]:
    initial = load_checkpoint(init)[0] if init else HEURISTIC_PARAMS
    matchups = build_test_matchups(manifest, manifest.splits["training"])
    budget = TrainingConfig(
        agent,
        seed,
        config.generations,
        config.population,
        config.elites,
        config.pairs,
        config.workers,
    )
    paths: list[Path] = []
    checkpoint_dir = root / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(
        generation: int, mean: list[float], std: list[float], stats: dict[str, object]
    ) -> None:
        path = checkpoint_dir / f"{agent}-s{seed}-g{generation:02d}.json"
        document = {
            "schema_version": 1,
            "study": "full-transfer",
            "agent": agent,
            "training_seed": seed,
            "generation": generation,
            "format_id": format_id,
            "params": asdict(ProtectParams.from_unit(mean)),
            "unit_std": std,
            "training": stats,
            "training_teams": list(manifest.splits["training"]),
            "simulator_revision": SIMULATOR_REVISION,
            "init_checkpoint": str(init) if init else None,
            "config": asdict(config),
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        paths.append(path)

    with ProcessPoolExecutor(max_workers=config.workers) as pool:

        def fitness(candidates: list[ProtectParams], generation: int) -> list[dict[str, float]]:
            tasks = [
                GameTask(
                    asdict(params),
                    format_id,
                    own,
                    other,
                    role,
                    training_battle_seed(seed, generation, index, pair),
                    str(showdown_dir),
                )
                for params in candidates
                for index, (_, team1, _, team2) in enumerate(matchups)
                for pair in range(config.pairs)
                for own, other, role in ((team1, team2, "p1"), (team2, team1, "p2"))
            ]
            games = list(pool.map(_training_game, tasks))
            size = len(tasks) // len(candidates)
            return [summarize_games(games[i : i + size]) for i in range(0, len(games), size)]

        run_cem(budget, fitness, initial.to_unit(), ADAPT_STD if init else FRESH_STD, save)
    return paths


def summarize_transfer(games: list[dict[str, Any]], generations: int) -> dict[str, Any]:
    """Pair cells before seed-level bootstrap; incomplete blocks never become draws."""
    if generations < 1:
        raise ValueError("generations must be positive")
    cells = (
        "source-source",
        "source-target",
        "native-target",
        *(f"adapted-g{g:02d}-target" for g in range(1, generations + 1)),
    )
    blocks: dict[tuple[object, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for game in games:
        key = tuple(
            game[k] for k in ("training_seed", "eval_seed", "matchup", "pair_index", "game_in_pair")
        )
        if game["result"] not in ("win", "loss", "tie", "unfinished"):
            raise ValueError("unknown game result")
        cell = game["cell"]
        if cell not in cells or cell in blocks[key]:
            raise ValueError("unknown or duplicate evaluation cell")
        blocks[key][cell] = game
    if not blocks or any(set(block) != set(cells) for block in blocks.values()):
        raise ValueError("missing paired evaluation cells")
    seats: dict[tuple[object, ...], set[object]] = defaultdict(set)
    schedules: dict[object, set[tuple[object, ...]]] = defaultdict(set)
    for key, block in blocks.items():
        seats[key[:-1]].add(key[-1])
        schedules[key[0]].add(key[1:])
        first = next(iter(block.values()))
        context = ("candidate_team", "opponent_team", "candidate_role", "battle_seed")
        if any(game[field] != first[field] for game in block.values() for field in context):
            raise ValueError("paired cells disagree on team, seat, or battle seed")
    if any(value != {0, 1} for value in seats.values()):
        raise ValueError("both mirrored seats required")
    if any(value != next(iter(schedules.values())) for value in schedules.values()):
        raise ValueError("evaluation schedule must match across training seeds")
    complete = [
        b for b in blocks.values() if all(g["result"] in ("win", "loss", "tie") for g in b.values())
    ]
    if not complete:
        raise ValueError("no completed paired evaluation blocks")
    teams = sorted({str(g["candidate_team"]) for g in games})
    output: dict[str, Any] = {}
    for team in ("all", *teams):
        by_seed: dict[int, list[dict[str, float]]] = defaultdict(list)
        for block in complete:
            first = block[cells[0]]
            if team != "all" and first["candidate_team"] != team:
                continue
            points = {c: {"win": 1.0, "loss": 0.0, "tie": 0.5}[block[c]["result"]] for c in cells}
            metrics = dict(points)
            metrics["transfer_loss_ppg"] = points["source-source"] - points["source-target"]
            for g in range(1, generations + 1):
                metrics[f"recovery_g{g:02d}_ppg"] = (
                    points[f"adapted-g{g:02d}-target"] - points["source-target"]
                )
                metrics[f"native_gap_g{g:02d}_ppg"] = (
                    points["native-target"] - points[f"adapted-g{g:02d}-target"]
                )
            by_seed[first["training_seed"]].append(metrics)
        expected_seeds = {g["training_seed"] for g in games}
        if set(by_seed) != expected_seeds or len(by_seed) < 3:
            raise ValueError(
                "each team needs completed blocks from every training seed (at least 3)"
            )
        names = next(iter(by_seed.values()))[0]
        output[team] = {
            "paired_blocks": sum(len(v) for v in by_seed.values()),
            "metrics": {
                name: asdict(
                    calculate_ci(
                        [sum(row[name] for row in rows) / len(rows) for rows in by_seed.values()],
                        n_resamples=5000,
                    )
                )
                for name in names
            },
        }
    return {
        "by_candidate_team": output,
        "total_games": len(games),
        "excluded_paired_blocks": len(blocks) - len(complete),
        "unfinished_games": sum(g["result"] == "unfinished" for g in games),
        "uncertainty_unit": "training seed; evaluation seeds and team pool held fixed",
    }


def run_full_transfer(
    output_dir: Path,
    config: FullTransferConfig | None = None,
    showdown_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Train on training teams, freeze checkpoints, then measure held-out transfer."""
    config = config or FullTransferConfig()
    config.validate()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty to avoid mixing runs")
    manifest = load_manifest(MANIFEST_PATH)
    families = [
        {manifest.teams[t].family for t in manifest.splits[s]}
        for s in ("training", "validation", "test")
    ]
    if any(a & b for i, a in enumerate(families) for b in families[i + 1 :]):
        raise ValueError("team families must be disjoint across splits")
    regulation = load_champions_regulation(REGULATION_PATH)
    sd = ShowdownProcess._resolve_showdown_dir(showdown_dir).resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sd, text=True).strip()
    if revision != SIMULATOR_REVISION:
        raise ValueError("simulator revision does not match the pinned revision")
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=sd, check=False)
    if clean.returncode:
        raise ValueError("simulator must be a clean checkout of the pinned revision")
    formats = {"source": SOURCE_FORMAT, "target": regulation.base_format}
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance = {
        "study": "full-transfer",
        "candidate_name": "FullTransferStudy",
        "simulator_revision": revision,
        "regulation": regulation.regulation_id,
        "formats": formats,
        "config": asdict(config),
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "regulation_sha256": hashlib.sha256(REGULATION_PATH.read_bytes()).hexdigest(),
        "training_teams": manifest.splits["training"],
        "test_teams": manifest.splits["test"],
        "opponent": "HeuristicBaseline",
        "information_mode": "public battle observations",
    }
    (output_dir / "protocol.json").write_text(json.dumps(provenance, indent=2) + "\n")
    recorder = GameRecorder(output_dir, {t: v.packed for t, v in manifest.teams.items()})
    matchups = build_test_matchups(manifest, manifest.splits["test"])
    for training_seed in config.training_seeds:
        source = _train(
            config, manifest, output_dir, "source", training_seed, formats["source"], sd
        )
        native = _train(
            config, manifest, output_dir, "native", training_seed, formats["target"], sd
        )
        adapted = _train(
            config,
            manifest,
            output_dir,
            "adapted",
            training_seed,
            formats["target"],
            sd,
            source[-1],
        )
        targets = [
            ("source-source", source[-1], "source"),
            ("source-target", source[-1], "target"),
            ("native-target", native[-1], "target"),
        ] + [(f"adapted-g{g:02d}-target", p, "target") for g, p in enumerate(adapted) if g > 0]
        for cell, checkpoint, domain in targets:
            for eval_seed in config.evaluation_seeds:
                for m, (t1, packed1, t2, packed2) in enumerate(matchups):
                    for pair in range(config.pairs):
                        # Same seed and team assignment across every checkpoint/domain and seat.
                        seed = training_battle_seed(eval_seed, 0, m, pair)
                        for seat, (own, other, own_id, other_id, role) in enumerate(
                            (
                                (packed1, packed2, t1, t2, "p1"),
                                (packed2, packed1, t2, t1, "p2"),
                            )
                        ):
                            candidate = checkpoint_agent(checkpoint)
                            opponent = HeuristicAgent("HeuristicBaseline")
                            result = run_evaluation_battle(
                                candidate,
                                opponent,
                                formats[domain],
                                own,
                                other,
                                role,
                                seed,
                                sd,
                                skip_build=True,
                            )
                            recorder.record(
                                GameContext(
                                    "full-transfer",
                                    cell,
                                    formats[domain],
                                    eval_seed,
                                    seed,
                                    candidate.name,
                                    opponent.name,
                                    own_id,
                                    other_id,
                                    role,
                                    pair,
                                    seat,
                                ),
                                result,
                            )
                            recorder.games[-1].update(
                                {
                                    "training_seed": training_seed,
                                    "cell": cell,
                                    "matchup": m,
                                    "checkpoint": str(checkpoint),
                                }
                            )
        recorder.finish(
            provenance, {"status": "in-progress", "candidate_name": "FullTransferStudy"}
        )
    summary = summarize_transfer(recorder.games, config.generations)
    report = {
        **provenance,
        **summary,
        "training_games": (
            3
            * len(config.training_seeds)
            * config.generations
            * config.population
            * config.pairs
            * 2
            * len(build_test_matchups(manifest, manifest.splits["training"]))
        ),
        "limitations": [
            "Synthetic four-member custom-game teams; no official regulation legality claim.",
            "Only five Protect parameters learn; other decisions stay heuristic.",
            "No Mega stones or learned Tera choices; not a Tera/Mega transfer study.",
            "Combined simulator ruleset effect, not an isolated mechanic or human skill claim.",
            "Pilot budgets and three seeds cannot establish metagame optimality.",
        ],
    }
    recorder.finish(provenance, report)
    (output_dir / "transfer_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
