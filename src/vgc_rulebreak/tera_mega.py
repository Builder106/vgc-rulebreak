"""Study T: bidirectional learned activation timing with matched native budgets."""

import hashlib
import json
import math
import random
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.base import get_active_unfainted_slots
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.evaluation import build_test_matchups, run_evaluation_battle
from vgc_rulebreak.full_transfer import (
    REGULATION_PATH,
    SIMULATOR_REVISION,
    FullTransferConfig,
    summarize_transfer,
)
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.records import GameContext, GameRecorder, game_outcome
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.training import MIN_STD, training_battle_seed

MANIFEST_PATH = Path("experiments/teams/tera-mega.json")
FORMATS = {"tera": "gen9doublescustomgame", "mega": "gen9championsdoublescustomgame"}
MEGA_ITEMS = {
    "Gyarados": "Gyaradosite",
    "Charizard": "Charizardite Y",
    "Lucario": "Lucarionite",
    "Slowbro": "Slowbronite",
    "Tyranitar": "Tyranitarite",
}


class ActivationAgent(HeuristicAgent):
    """Learn one shared HP threshold; move choice and recipient order stay heuristic."""

    def __init__(self, threshold: float, name: str = "ActivationCandidate") -> None:
        super().__init__(name)
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("activation threshold must be finite and in [0, 1]")
        self.threshold = threshold
        self.opportunities = 0
        self.activations = 0

    def reset(self) -> None:
        super().reset()
        self.opportunities = 0
        self.activations = 0

    def choose_action(self, request: dict[str, Any]) -> str:
        # Suppress the inherited fixed Mega bonus so neither mechanic changes move ranking.
        plain = {
            **request,
            "active": [
                dict(slot, canMegaEvo=False) if slot else slot for slot in request.get("active", [])
            ],
        }
        action = super().choose_action(plain)
        if request.get("teamPreview") or request.get("forceSwitch"):
            return action
        choices = action.split(", ")
        pokemon = request.get("side", {}).get("pokemon", [])
        # Heuristic emits choices in the order of surviving active slots (including gaps).
        slots = get_active_unfainted_slots(request)
        eligible: list[tuple[int, str, float]] = []
        for index, (slot_idx, slot) in enumerate(slots):
            if index >= len(choices) or not choices[index].startswith("move "):
                continue
            mechanic = (
                "mega"
                if slot.get("canMegaEvo")
                else ("terastallize" if slot.get("canTerastallize") else "")
            )
            if not mechanic:
                continue
            condition = str(pokemon[slot_idx]["condition"]).split()[0]
            current, maximum = condition.split("/")
            hp = float(current) / max(float(maximum), 1.0)
            eligible.append((index, mechanic, hp))
        # One decision opportunity per request, never two uses of a once-per-team mechanic.
        if eligible:
            self.opportunities += 1
        for index, mechanic, hp in eligible:
            if hp <= self.threshold:
                choices[index] += f" {mechanic}"
                self.activations += 1
                break
        return ", ".join(choices)


def domain_teams(manifest: TeamManifest, domain: str) -> dict[str, str]:
    """Keep all sets fixed except the explicitly declared Mega stone."""
    if domain not in FORMATS:
        raise ValueError("unknown mechanic domain")
    teams: dict[str, str] = {}
    families: dict[str, str] = {}
    for team_id, team in manifest.teams.items():
        if team.family in families and families[team.family] != team.split:
            raise ValueError("team families must be disjoint across splits")
        families[team.family] = team.split
        packed = team.packed.split("]")
        if len(packed) != len(team.pokemon):
            raise ValueError("packed teams disagree with declared members")
        stones = 0
        for member, encoded in zip(team.pokemon, packed, strict=True):
            if member.item:
                raise ValueError("Tera fixtures must have no held items")
            if member.nature != "Serious" or member.evs != dict.fromkeys(
                ("hp", "atk", "def", "spa", "spd", "spe"), 0
            ):
                raise ValueError("fixtures require neutral nature and zero investment")
            expected = (
                f"{member.species}|||{member.ability}|{','.join(member.moves)}|Serious|"
                f"0,0,0,0,0,0||||50|,,,,,{member.tera_type}"
            )
            if encoded != expected:
                raise ValueError("packed teams disagree with declared members")
            if member.species in MEGA_ITEMS:
                stones += 1
        if stones != 1:
            raise ValueError("each fixture needs exactly one declared Mega recipient")
        if domain == "mega":
            for index, member in enumerate(team.pokemon):
                if member.species in MEGA_ITEMS:
                    fields = packed[index].split("|")
                    fields[2] = MEGA_ITEMS[member.species]
                    packed[index] = "|".join(fields)
        teams[team_id] = "]".join(packed)
    return teams


@dataclass(frozen=True)
class ActivationTask:
    threshold: float
    format_id: str
    own: str
    other: str
    role: str
    seed: tuple[int, int, int, int]
    showdown_dir: str


def _training_game(task: ActivationTask) -> dict[str, float]:
    agent = ActivationAgent(task.threshold)
    result = run_evaluation_battle(
        agent,
        ActivationAgent(1.0, "ImmediateActivationBaseline"),
        task.format_id,
        task.own,
        task.other,
        task.role,
        task.seed,
        task.showdown_dir,
        skip_build=True,
    )
    outcome = game_outcome(result)
    if outcome == "unfinished":
        raise ValueError("unfinished training game; refusing to score it as a draw")
    return {
        "points": {"win": 1.0, "tie": 0.5, "loss": 0.0}[outcome],
        "opportunities": float(agent.opportunities),
        "activations": float(agent.activations),
    }


def _train(
    config: FullTransferConfig,
    manifest: TeamManifest,
    teams: dict[str, str],
    root: Path,
    domain: str,
    seed: int,
    sd: Path,
    *,
    init: Path | None = None,
) -> list[Path]:
    """One-dimensional CEM over activation timing; held-out results never select a model."""
    initial = json.loads(init.read_text())["threshold"] if init else 0.75
    mean, std = float(initial), 0.1 if init else 0.25
    rng = random.Random(seed)
    generations = config.generations if init else 2 * config.generations
    label = f"adapted-to-{domain}" if init else f"fresh-{domain}"
    matchups = build_test_matchups(manifest, manifest.splits["training"])
    paths: list[Path] = []
    games_per_generation = config.population * len(matchups) * config.pairs * 2

    def save(generation: int, stats: dict[str, object]) -> None:
        path = root / "checkpoints" / f"{label}-s{seed}-g{generation:02d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "study": "tera-mega",
                    "agent": label,
                    "training_seed": seed,
                    "generation": generation,
                    "threshold": mean,
                    "unit_std": std,
                    "format_id": FORMATS[domain],
                    "training_teams": manifest.splits["training"],
                    "training_games": generation * games_per_generation,
                    "init_checkpoint": str(init) if init else None,
                    "init_sha256": hashlib.sha256(init.read_bytes()).hexdigest() if init else None,
                    "initial_threshold": initial,
                    "training": stats,
                    "config": asdict(config),
                },
                indent=2,
            )
            + "\n"
        )
        paths.append(path)

    with ProcessPoolExecutor(max_workers=config.workers) as pool:
        for generation in range(generations):
            candidates = [mean] + [
                min(1.0, max(0.0, rng.gauss(mean, std))) for _ in range(config.population - 1)
            ]
            tasks = [
                ActivationTask(
                    value,
                    FORMATS[domain],
                    teams[own],
                    teams[other],
                    role,
                    training_battle_seed(seed, generation, m, pair),
                    str(sd),
                )
                for value in candidates
                for m, (a, _, b, _) in enumerate(matchups)
                for pair in range(config.pairs)
                for own, other, role in ((a, b, "p1"), (b, a, "p2"))
            ]
            games = list(pool.map(_training_game, tasks))
            size = len(games) // len(candidates)
            scores = [
                sum(g["points"] for g in games[i : i + size]) / size
                for i in range(0, len(games), size)
            ]
            save(
                generation, {"candidate_thresholds": candidates, "fitness": scores, "games": games}
            )
            ranked = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
            elite = [candidates[i] for i in ranked[: config.elites]]
            mean = sum(elite) / len(elite)
            std = max(MIN_STD, math.sqrt(sum((v - mean) ** 2 for v in elite) / len(elite)))
        save(generations, {})
    return paths


def run_tera_mega(
    output_dir: Path,
    config: FullTransferConfig | None = None,
    showdown_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Evaluate both transfer directions with equal target and total game references."""
    config = config or FullTransferConfig()
    config.validate()
    if config.compare_opponent_pools:
        raise ValueError("Study T uses one frozen opponent pool")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty to avoid mixing runs")
    manifest = load_manifest(MANIFEST_PATH)
    teams = {domain: domain_teams(manifest, domain) for domain in FORMATS}
    sd = ShowdownProcess._resolve_showdown_dir(showdown_dir).resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sd, text=True).strip()
    if revision != SIMULATOR_REVISION:
        raise ValueError("simulator revision does not match the pinned revision")
    if subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=sd, check=False).returncode:
        raise ValueError("simulator must be a clean checkout of the pinned revision")
    budget = (
        config.generations
        * config.population
        * config.pairs
        * 2
        * len(build_test_matchups(manifest, manifest.splits["training"]))
    )
    provenance = {
        "study": "tera-mega",
        "simulator_revision": revision,
        "formats": FORMATS,
        "config": asdict(config),
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "mega_items": MEGA_ITEMS,
        "regulation_sha256": hashlib.sha256(REGULATION_PATH.read_bytes()).hexdigest(),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "teams_by_domain": teams,
        "training_teams": manifest.splits["training"],
        "test_teams": manifest.splits["test"],
        "information_mode": "own requests and public log",
        "opponent": "ImmediateActivationBaseline",
        "games_per_seed": {
            "source": budget,
            "adaptation": budget,
            "native_target_budget": budget,
            "native_total_budget": 2 * budget,
        },
        "native_reference_reuse": "fresh trajectory at B is also reverse-direction source; "
        "fresh trajectory at 2B is total-budget reference",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "protocol.json").write_text(json.dumps(provenance, indent=2) + "\n")
    recorder = GameRecorder(
        output_dir,
        {
            f"{domain}/{team}": packed
            for domain, pool in teams.items()
            for team, packed in pool.items()
        },
    )
    for seed in config.training_seeds:
        fresh = {
            domain: _train(config, manifest, pool, output_dir, domain, seed, sd)
            for domain, pool in teams.items()
        }
        for source_domain, target_domain in (("tera", "mega"), ("mega", "tera")):
            direction = f"{source_domain}-to-{target_domain}"
            source = fresh[source_domain][config.generations]
            adapted = _train(
                config,
                manifest,
                teams[target_domain],
                output_dir,
                target_domain,
                seed,
                sd,
                init=source,
            )
            cells = [
                ("source-source", source, source_domain),
                ("source-target", source, target_domain),
                ("native-target", fresh[target_domain][config.generations], target_domain),
                ("native-total-target", fresh[target_domain][-1], target_domain),
                *(
                    (f"adapted-g{g:02d}-target", path, target_domain)
                    for g, path in enumerate(adapted)
                    if g
                ),
            ]
            for cell, checkpoint, domain in cells:
                threshold = json.loads(checkpoint.read_text())["threshold"]
                for eval_seed in config.evaluation_seeds:
                    for m, (a, _, b, _) in enumerate(
                        build_test_matchups(manifest, manifest.splits["test"])
                    ):
                        for pair in range(config.pairs):
                            battle_seed = training_battle_seed(eval_seed, 0, m, pair)
                            for seat, (own, other, role) in enumerate(((a, b, "p1"), (b, a, "p2"))):
                                agent = ActivationAgent(threshold)
                                opponent = ActivationAgent(1.0, "ImmediateActivationBaseline")
                                result = run_evaluation_battle(
                                    agent,
                                    opponent,
                                    FORMATS[domain],
                                    teams[domain][own],
                                    teams[domain][other],
                                    role,
                                    battle_seed,
                                    sd,
                                    skip_build=True,
                                )
                                recorder.record(
                                    GameContext(
                                        "tera-mega",
                                        f"{direction}/{cell}",
                                        FORMATS[domain],
                                        eval_seed,
                                        battle_seed,
                                        agent.name,
                                        opponent.name,
                                        f"{domain}/{own}",
                                        f"{domain}/{other}",
                                        role,
                                        pair,
                                        seat,
                                    ),
                                    result,
                                )
                                recorder.games[-1].update(
                                    {
                                        "training_seed": seed,
                                        "cell": cell,
                                        "direction": direction,
                                        "matchup": m,
                                        "checkpoint": str(checkpoint),
                                        "candidate_family": own,
                                        "opponent_family": other,
                                        "activation_opportunities": agent.opportunities,
                                        "activations": agent.activations,
                                    }
                                )
            recorder.finish(provenance, {"status": "in-progress"})
    directions = {}
    for direction in ("tera-to-mega", "mega-to-tera"):
        # Pair by base fixture identity, retaining domain-qualified IDs in raw records/replays.
        rows = [
            {**g, "candidate_team": g["candidate_family"], "opponent_team": g["opponent_family"]}
            for g in recorder.games
            if g["direction"] == direction
        ]
        directions[direction] = summarize_transfer(
            rows, config.generations, total_budget_native=True
        )
    report = {
        **provenance,
        "directions": directions,
        "total_games": len(recorder.games),
        "training_games": 6 * budget * len(config.training_seeds),
        "limitations": [
            "Synthetic custom-game fixtures, not official legal regulation teams.",
            "Combined Gen 9/Champions rules and stone changes; no mechanic-only attribution.",
            "Only a shared HP activation threshold learns; moves/recipient order stay heuristic.",
            "Tera can select any active member; Mega requires the designated stone holder.",
            "Pilot intervals condition on fixed teams/evaluation seeds; no human-skill inference.",
        ],
    }
    recorder.finish(provenance, report)
    (output_dir / "transfer_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
