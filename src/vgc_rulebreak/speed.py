"""Study S: matched legal stat builds, move order and one-turn pivot exposure."""

import gzip
import hashlib
import json
import random
import subprocess
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vgc_rulebreak.protect_multi_seed import calculate_ci
from vgc_rulebreak.simulator.process import ShowdownProcess

SIMULATOR_REVISION = "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e"
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
CONTEXTS = ("normal", "trick_room", "tailwind", "opponent_protect")


def equivalent_evs(points: dict[str, int]) -> dict[str, int]:
    """Smallest Gen 9 EV spread matching L50 Champions stats with all IVs 31.

    A first Stat Point costs 4 EVs, subsequent points cost 8. Some legal
    66-point spreads have no equivalent legal EV spread; reject those.
    """
    if set(points) - set(STATS) or any(
        type(value) is not int or not 0 <= value <= 32 for value in points.values()
    ):
        raise ValueError("Stat Points must be integers in [0, 32] for known stats")
    evs = {stat: max(0, points.get(stat, 0) * 8 - 4) for stat in STATS}
    if sum(points.values()) > 66 or sum(evs.values()) > 510:
        raise ValueError("Spread has no equivalent legal Gen 9 EV allocation")
    return evs


def _build(
    species: str, ability: str, moves: list[str], nature: str, points: dict[str, int]
) -> dict[str, Any]:
    return {
        "species": species,
        "ability": ability,
        "moves": moves,
        "nature": nature,
        "level": 50,
        "gender": "M" if species != "Rotom-Wash" else "N",
        "evs": {stat: points.get(stat, 0) for stat in STATS},
        "ivs": dict.fromkeys(STATS, 31),
    }


def comparison_config(trials: int = 16, seed: int = 79) -> dict[str, Any]:
    """Freeze fixture teams and independent four-part seeds before evaluation."""
    if trials < 2:
        raise ValueError("Need at least two paired trials")
    scenarios: list[dict[str, Any]] = []
    for name in ("matched", "minimum_legal_speed", "speed_tie"):
        candidate = [
            _build(
                "Incineroar",
                "Blaze",
                ["partingshot", "protect"],
                "Brave",
                {"hp": 32, "def": 32, "spd": 1},
            ),
            _build("Gyarados", "Moxie", ["protect"], "Hardy", {"hp": 32, "def": 32, "spd": 1}),
            _build("Rotom-Wash", "Levitate", ["protect"], "Hardy", {"hp": 32, "def": 32, "spd": 1}),
        ]
        opponent = [
            _build(
                "Hippowdon",
                "Sand Force",
                ["crunch", "protect"],
                "Impish",
                {"hp": 32, "def": 27, "spd": 1, "spe": 5}
                if name == "speed_tie"
                else {"hp": 32, "def": 32, "spd": 1},
            ),
            _build("Gyarados", "Moxie", ["protect"], "Hardy", {"hp": 32, "def": 32, "spd": 1}),
        ]
        sp_teams = {"candidate": candidate, "opponent": opponent}
        ev_teams = json.loads(json.dumps(sp_teams))
        for team in ev_teams.values():
            for pokemon in team:
                pokemon["evs"] = equivalent_evs(pokemon["evs"])
        if name == "minimum_legal_speed":
            ev_teams["candidate"][0]["ivs"]["spe"] = 0
        scenarios.append(
            {
                "name": name,
                "equivalence": "minimum legal Speed; unavoidable IV difference"
                if name == "minimum_legal_speed"
                else "identical level-50 stats",
                "teams": {"ev": ev_teams, "sp": sp_teams},
            }
        )
    rng = random.Random(seed)
    return {
        "scenarios": scenarios,
        "contexts": list(CONTEXTS),
        "seeds": [[rng.randrange(65536) for _ in range(4)] for _ in range(trials)],
    }


def summarize_speed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair actions and systems, then average mirrored seats within each seed."""
    blocks: dict[tuple[str, str, tuple[int, ...], str], dict[tuple[str, str], dict[str, Any]]]
    blocks = defaultdict(dict)
    expected = {(system, action) for system in ("ev", "sp") for action in ("pivot", "switch")}
    for row in rows:
        key = (row["scenario"], row["context"], tuple(row["seed"]), row["seat"])
        cell = row["system"], row["action"]
        if cell not in expected or cell in blocks[key] or row["seat"] not in {"p1", "p2"}:
            raise ValueError("Unknown or duplicate comparison cell")
        blocks[key][cell] = row
    grouped: dict[tuple[str, str], dict[tuple[int, ...], list[dict[str, float]]]]
    grouped = defaultdict(lambda: defaultdict(list))
    for (scenario, context, seed, _seat), cells in blocks.items():
        if set(cells) != expected:
            raise ValueError("Incomplete paired action/system block")
        ev, sp = cells[("ev", "pivot")], cells[("sp", "pivot")]
        metrics = {
            "move_order_changed": float(ev["pivot_before_opponent"] != sp["pivot_before_opponent"]),
        }
        for system in ("ev", "sp"):
            pivot, switch = cells[(system, "pivot")], cells[(system, "switch")]
            metrics[f"{system}_pivot_first"] = float(pivot["pivot_before_opponent"])
            metrics[f"{system}_pivot_completed"] = float(pivot["pivot_completed"])
            for metric in ("incoming_damage_fraction", "team_damage_fraction"):
                metrics[f"{system}_pivot_minus_switch_{metric}"] = pivot[metric] - switch[metric]
        for metric in ("incoming_damage_fraction", "team_damage_fraction"):
            metrics[f"sp_minus_ev_pivot_effect_{metric}"] = (
                metrics[f"sp_pivot_minus_switch_{metric}"]
                - metrics[f"ev_pivot_minus_switch_{metric}"]
            )
        grouped[(scenario, context)][seed].append(metrics)
    if not grouped:
        raise ValueError("No comparison evidence")
    summary: list[dict[str, Any]] = []
    for (scenario, context), seeds in grouped.items():
        if len(seeds) < 2 or any(len(seats) != 2 for seats in seeds.values()):
            raise ValueError("Need at least two seeds, each with both mirrored seats")
        keys = next(iter(seeds.values()))[0].keys()
        summary.append(
            {
                "scenario": scenario,
                "context": context,
                "eligible_paired_decisions": len(seeds) * 2,
                "metrics": {
                    key: asdict(
                        calculate_ci(
                            [sum(seat[key] for seat in seats) / 2 for seats in seeds.values()]
                        )
                    )
                    for key in keys
                },
            }
        )
    return summary


def run_speed_comparison(
    output_dir: Path,
    trials: int = 16,
    seed: int = 79,
    showdown_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run the pinned stat-only fixtures and persist every branch's evidence."""
    config = comparison_config(trials, seed)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; evidence is never overwritten")
    simulator = ShowdownProcess._resolve_showdown_dir(showdown_dir)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=simulator, check=True, capture_output=True, text=True
    ).stdout.strip()
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=simulator, check=False)
    if revision != SIMULATOR_REVISION or clean.returncode:
        raise ValueError("Simulator must be a clean checkout of the pinned revision")
    subprocess.run(["node", "build"], cwd=simulator, check=True, capture_output=True)
    probe = Path(__file__).with_name("simulator") / "speed_probe.cjs"
    result = subprocess.run(
        ["node", str(probe)],
        cwd=simulator,
        input=json.dumps(config),
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    rows = json.loads(result.stdout)
    expected_count = len(config["scenarios"]) * len(CONTEXTS) * trials * 8
    if len(rows) != expected_count:
        raise ValueError("Simulator returned incomplete fixture evidence")
    summary = summarize_speed(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = output_dir / "decisions.json.gz"
    with gzip.open(evidence, "wt", encoding="utf-8") as stream:
        json.dump(rows, stream)
    report = {
        "schema_version": 1,
        "simulator_revision": revision,
        "command": "compare-speed",
        "config": config,
        "seed": seed,
        "branches": len(rows),
        "evidence": evidence.name,
        "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), probe, probe.with_name("speed_formats.cjs"))
        },
        "summary": summary,
        "limits": [
            "Scripted complete-information one-turn decisions; no learned or optimal policy claim.",
            "Damage fractions are immediate exposure, not win probabilities or decision regret.",
            "Minimum legal Speed changes only the candidate's unavoidable Speed IV constraint.",
            "Intervals resample paired fixture seeds, not teams, training runs or hidden Speed.",
            "All non-stat mechanics stay Gen 9; this is not full Champions transfer.",
        ],
    }
    (output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
