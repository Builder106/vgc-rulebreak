"""Matched 2-by-2 evaluation of Protect PP and Rage Fist persistence."""

import hashlib
import json
import math
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any

from vgc_rulebreak.evaluation import (
    build_test_matchups,
    create_candidate_agent,
    create_opponent_agent,
    run_evaluation_battle,
    verify_frozen_evaluation,
)
from vgc_rulebreak.manifest import TeamManifest
from vgc_rulebreak.protect_multi_seed import calculate_ci
from vgc_rulebreak.records import GameContext, GameRecorder
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.spec import ExperimentSpec
from vgc_rulebreak.switch_cost import switch_opportunities

FORMATS = {
    f"{pp}-{mode}": f"gen9rulebreakprotect{pp}ragefist{mode}"
    for pp, mode in product((16, 8), ("persist", "reset"))
}


def factorial_contrasts(points: dict[str, float]) -> dict[str, float]:
    """Signed reset and PP effects, then reset-at-8 minus reset-at-16."""
    if set(points) != set(FORMATS) or any(
        not math.isfinite(value) or not 0 <= value <= 1 for value in points.values()
    ):
        raise ValueError("Need all four cells with finite points in [0, 1]")
    reset16 = points["16-reset"] - points["16-persist"]
    reset8 = points["8-reset"] - points["8-persist"]
    return {
        "reset_at_16": reset16,
        "reset_at_8": reset8,
        "pp_at_persist": points["8-persist"] - points["16-persist"],
        "pp_at_reset": points["8-reset"] - points["16-reset"],
        "interaction": reset8 - reset16,
    }


def summarize_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Bootstrap evaluation-seed means, keeping cells, seats and matchups together."""
    if not blocks:
        raise ValueError("Cannot summarize an empty cohort")
    grouped: dict[int, list[dict[str, float]]] = defaultdict(list)
    for block in blocks:
        grouped[block["eval_seed"]].append(factorial_contrasts(block["points"]))
    keys = next(iter(grouped.values()))[0].keys()
    seed_means = {
        seed: {key: sum(row[key] for row in rows) / len(rows) for key in keys}
        for seed, rows in sorted(grouped.items())
    }
    return {
        "paired_seat_blocks": len(blocks),
        "seed_means": seed_means,
        "contrasts": {
            key: asdict(calculate_ci([row[key] for row in seed_means.values()])) for key in keys
        },
        "cells": {
            cell: {
                "games": len(blocks),
                "points_per_game": sum(b["points"][cell] for b in blocks) / len(blocks),
            }
            for cell in FORMATS
        },
    }


def _policy_seed(identity: tuple[object, ...], label: str) -> int:
    payload = json.dumps([*identity, label], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _exposure(replay: dict[str, Any], role: str) -> dict[str, int]:
    opportunities = switch_opportunities(replay["decisions"], role)
    return {
        "rage_fist_switch_opportunities": len(opportunities),
        "rage_fist_switches": sum(o.chose_switch for o in opportunities),
        "rage_fist_uses": sum(
            line.startswith(f"|move|{role}") and "|Rage Fist|" in line for line in replay["log"]
        ),
    }


def run_interaction(
    spec: ExperimentSpec,
    manifest: TeamManifest,
    study_p_result: Path,
    output_dir: Path,
    pairs: int = 3,
    max_turns: int = 100,
    showdown_dir: Path | str | None = None,
    workers: int = 4,
) -> dict[str, Any]:
    """Run fixed heuristic/random policies on every cell with fresh matched RNGs.

    No training or tuning occurs. Random is a switching diagnostic, separate from
    the competent heuristic. Every game retains its requests and compressed replay.
    """
    verify_frozen_evaluation(spec, manifest)
    assert spec.evaluation is not None
    if pairs < 1 or max_turns < 1 or workers < 1:
        raise ValueError("pairs, max_turns and workers must be positive")
    seeds = spec.evaluation.evaluation_seeds
    if len(set(seeds)) != len(seeds):
        raise ValueError("Evaluation seeds must be distinct")
    prerequisite = json.loads(study_p_result.read_text(encoding="utf-8"))
    if (
        not isinstance(prerequisite, dict)
        or prerequisite.get("spec") != spec.name
        or prerequisite.get("simulator_revision") != spec.simulator_revision
        or prerequisite.get("formats")
        != {"protect-16": "gen9rulebreakprotect16", "protect-8": "gen9rulebreakprotect8"}
        or type(prerequisite.get("total_evaluation_games")) is not int
        or prerequisite["total_evaluation_games"] <= 0
        or not prerequisite.get("findings")
    ):
        raise ValueError("Need a completed Protect-only Study P result at the pinned revision")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; existing evidence is never overwritten")
    simulator = ShowdownProcess._resolve_showdown_dir(showdown_dir)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=simulator, check=True, capture_output=True, text=True
    ).stdout.strip()
    clean = subprocess.run(
        ["git", "diff", "--quiet", "HEAD"], cwd=simulator, check=False
    ).returncode
    if revision != spec.simulator_revision or clean != 0:
        raise ValueError("Simulator must be a clean checkout of the pinned revision")
    subprocess.run(["node", "build"], cwd=simulator, check=True, capture_output=True)
    recorder = GameRecorder(output_dir, {key: team.packed for key, team in manifest.teams.items()})
    matchups = build_test_matchups(manifest, spec.evaluation.test_teams)
    blocks: list[dict[str, Any]] = []
    for candidate, opponent, matchup, eval_seed, pair in product(
        ("heuristic", "random"),
        spec.evaluation.opponent_policies,
        matchups,
        seeds,
        range(pairs),
    ):
        candidate_team, candidate_packed, opponent_team, opponent_packed = matchup
        # Same seed for both seats; candidate retains its team when seats reverse.
        identity = (candidate, opponent, candidate_team, opponent_team, eval_seed, pair)
        battle_number = _policy_seed(identity, "battle")
        battle_seed = tuple((battle_number >> (16 * i)) & 0xFFFF for i in range(4))
        assert len(battle_seed) == 4
        candidate_seed = _policy_seed(identity, "candidate")
        opponent_seed = _policy_seed(identity, "opponent")
        for seat_index, seat in enumerate(("p1", "p2")):
            points: dict[str, float] = {}
            game_ids: dict[str, str] = {}
            agents = {
                cell: create_candidate_agent(candidate, seed=candidate_seed) for cell in FORMATS
            }
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    cell: executor.submit(
                        run_evaluation_battle,
                        agents[cell],
                        create_opponent_agent(opponent, seed=opponent_seed),
                        format_id,
                        candidate_packed,
                        opponent_packed,
                        candidate_role=seat,
                        seed=battle_seed,
                        showdown_dir=simulator,
                        max_turns=max_turns,
                        skip_build=True,
                    )
                    for cell, format_id in FORMATS.items()
                }
                results = {cell: future.result() for cell, future in futures.items()}
            for cell, format_id in FORMATS.items():
                result = results[cell]
                if result.end_reason not in {"win", "tie", "turn-limit"} or result.replay is None:
                    raise RuntimeError("Incomplete factorial game; refusing a fabricated tie")
                context = GameContext(
                    "interaction",
                    cell,
                    format_id,
                    eval_seed,
                    battle_seed,
                    agents[cell].name,
                    opponent,
                    candidate_team,
                    opponent_team,
                    seat,
                    pair,
                    seat_index,
                )
                game_ids[cell] = recorder.record(context, result)
                recorder.games[-1].update(
                    candidate_policy_seed=candidate_seed,
                    opponent_policy_seed=opponent_seed,
                    **_exposure(result.replay, seat),
                )
                points[cell] = (
                    0.5
                    if result.end_reason in {"tie", "turn-limit"}
                    else float(result.candidate_won)
                )
            blocks.append(
                {
                    "candidate": candidate,
                    "opponent": opponent,
                    "candidate_team": candidate_team,
                    "opponent_team": opponent_team,
                    "eval_seed": eval_seed,
                    "pair": pair,
                    "seat": seat,
                    "game_ids": game_ids,
                    "points": points,
                    "contrasts": factorial_contrasts(points),
                }
            )
    source_root = Path(__file__).parent
    report: dict[str, Any] = {
        "schema_version": 1,
        "design": {
            "formats": FORMATS,
            "pairs": pairs,
            "max_turns": max_turns,
            "workers": workers,
            "candidate_policies": ["heuristic", "random"],
            "evaluation_seeds": seeds,
            "opponents": spec.evaluation.opponent_policies,
            "matchups": [[m[0], m[2]] for m in matchups],
            "scoring": "win=1, loss=0, tie/turn-limit=0.5; stalled games fail",
            "interaction": "(8-reset - 8-persist) - (16-reset - 16-persist)",
            "uncertainty": "95% percentile bootstrap of evaluation-seed means; 1000 draws, seed=42",
            "limitations": (
                "Fixed policies; no training-seed or human-skill inference. Three evaluation "
                "seeds give limited precision. Zero exposure cannot establish absence of "
                "interaction. Degenerate intervals describe this cohort only."
            ),
        },
        "provenance": {
            "simulator_revision": revision,
            "spec": asdict(spec),
            "manifest": asdict(manifest),
            "study_p_result": str(study_p_result),
            "study_p_sha256": hashlib.sha256(study_p_result.read_bytes()).hexdigest(),
            "study_p_findings": prerequisite["findings"],
            "source_sha256": {
                str(path.relative_to(source_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(source_root.rglob("*"))
                if path.suffix in {".py", ".cjs"}
            },
        },
        "total_games": len(recorder.games),
        "by_candidate": {
            candidate: summarize_blocks([b for b in blocks if b["candidate"] == candidate])
            for candidate in ("heuristic", "random")
        },
        "strata": [],
        "blocks": blocks,
    }
    for candidate, opponent, matchup in product(
        ("heuristic", "random"), spec.evaluation.opponent_policies, matchups
    ):
        cohort = [
            b
            for b in blocks
            if (b["candidate"], b["opponent"], b["candidate_team"], b["opponent_team"])
            == (candidate, opponent, matchup[0], matchup[2])
        ]
        stratum: dict[str, Any] = {
            "candidate": candidate,
            "opponent": opponent,
            "candidate_team": matchup[0],
            "opponent_team": matchup[2],
            **summarize_blocks(cohort),
            "exposure": {},
            "termination": {},
        }
        for cell in FORMATS:
            ids = {b["game_ids"][cell] for b in cohort}
            games = [g for g in recorder.games if g["game_id"] in ids]
            stratum["exposure"][cell] = {
                field: sum(g[field] for g in games)
                for field in (
                    "protect_depleted",
                    "candidate_protect_uses",
                    "candidate_protect_opportunities",
                    "rage_fist_uses",
                    "rage_fist_switch_opportunities",
                    "rage_fist_switches",
                )
            }
            stratum["termination"][cell] = {
                reason: sum(g["end_reason"] == reason for g in games)
                for reason in ("win", "tie", "turn-limit")
            }
        report["strata"].append(stratum)
    recorder.finish({"command": "rage-fist-interaction", "simulator_revision": revision}, report)
    (output_dir / "interaction_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report
