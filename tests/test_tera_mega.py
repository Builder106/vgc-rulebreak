"""Study T activation legality, budget equality, initialization and real mechanics."""

import copy
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak import tera_mega as tm
from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import EvaluationBattleResult, run_evaluation_battle
from vgc_rulebreak.full_transfer import SIMULATOR_REVISION, FullTransferConfig, summarize_transfer
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.simulator.process import ShowdownProcess


def request(mechanic: str, hp: str = "100/100") -> dict[str, Any]:
    return {
        "active": [
            {
                mechanic: True,
                "trapped": True,
                "moves": [{"id": "thunderbolt", "target": "normal", "pp": 10}],
            }
            for _ in range(2)
        ],
        "side": {
            "pokemon": [{"ident": "p1: Raichu", "condition": hp, "active": True} for _ in range(2)]
        },
    }


@pytest.mark.parametrize(
    "mechanic,suffix", [("canMegaEvo", "mega"), ("canTerastallize", "terastallize")]
)
def test_activation_timing_is_shared_and_once_per_team(mechanic: str, suffix: str) -> None:
    agent = tm.ActivationAgent(0.5)
    original = request(mechanic)
    saved = copy.deepcopy(original)
    assert suffix not in agent.choose_action(original)
    assert original == saved
    action = agent.choose_action(request(mechanic, "40/100"))
    assert action.count(suffix) == 1
    assert agent.opportunities == 2
    assert agent.activations == 1
    agent.reset()
    assert agent.activations == agent.opportunities == 0


def test_no_illegal_activation_on_preview_force_switch_or_unavailable_requests() -> None:
    agent = tm.ActivationAgent(1)
    assert agent.choose_action({"teamPreview": True}).startswith("team ")
    assert agent.choose_action({"forceSwitch": [True, False], "side": {"pokemon": []}}) == (
        "pass, pass"
    )
    assert agent.choose_action({}) == "default"
    data = request("unavailable")
    assert "mega" not in agent.choose_action(data)
    assert "terastallize" not in agent.choose_action(data)
    assert agent.activations == agent.opportunities == 0


@pytest.mark.parametrize("value", [-1, 2, float("nan"), float("inf")])
def test_invalid_thresholds(value: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        tm.ActivationAgent(value)


def test_total_native_participates_in_paired_exclusion_and_gap() -> None:
    rows = [
        {
            "training_seed": seed,
            "eval_seed": 101,
            "matchup": 0,
            "pair_index": 0,
            "game_in_pair": seat,
            "candidate_team": "a",
            "opponent_team": "b",
            "candidate_role": "p1" if seat == 0 else "p2",
            "battle_seed": [1, 2, 3, 4],
            "cell": cell,
            "result": result,
        }
        for seed in (11, 29, 47)
        for seat in (0, 1)
        for cell, result in (
            ("source-source", "win"),
            ("source-target", "loss"),
            ("native-target", "tie"),
            ("native-total-target", "win"),
            ("adapted-g01-target", "tie"),
        )
    ]
    report = summarize_transfer(rows, 1, total_budget_native=True)
    metrics = report["by_candidate_team"]["all"]["metrics"]
    assert metrics["native_gap_g01_ppg"]["mean"] == 0
    assert metrics["native_total_gap_g01_ppg"]["mean"] == 0.5
    assert metrics["native_total_gap_g01_ppg"]["n"] == 3
    rows[3]["result"] = "unfinished"
    report = summarize_transfer(rows, 1, total_budget_native=True)
    assert report["excluded_paired_blocks"] == 1
    assert report["by_candidate_team"]["all"]["paired_blocks"] == 5
    with pytest.raises(ValueError, match="missing"):
        summarize_transfer(
            [r for r in rows if r["cell"] != "native-total-target"], 1, total_budget_native=True
        )


@pytest.mark.parametrize("rules_mode", ["full", "mechanic-only"])
def test_pipeline_keeps_splits_budgets_and_both_directions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rules_mode: str,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def battle(
        candidate: BattleAgent,
        opponent: BattleAgent,
        format_id: str,
        own: str,
        other: str,
        role: str,
        seed: tuple[int, int, int, int],
        sd: Path | str,
        *,
        skip_build: bool,
    ) -> EvaluationBattleResult:
        calls.append((own, other, format_id))
        return EvaluationBattleResult(
            opponent.name, 5, 0.1, 5, 5, 0, 0, False, False, "win", {"log": [], "decisions": []}
        )

    monkeypatch.setattr(tm, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(tm, "run_evaluation_battle", battle)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: SIMULATOR_REVISION)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0))
    report = tm.run_tera_mega(tmp_path, showdown_dir=tmp_path, rules_mode=rules_mode)
    formats = tm.FORMAT_SETS[rules_mode]
    assert report["rules_mode"] == rules_mode
    assert report["formats"] == formats
    assert report["format_overlay_sha256"]
    published = json.loads((tmp_path / "transfer_report.json").read_text())
    assert published["limitations"] == report["limitations"]
    limits = " ".join(published["limitations"])
    for claim_limit in (
        "No human participants or human learning measured",
        "no inference about human skill",
        "no metagame optimality",
        "native gaps are not distance from optimal play",
        "Equal training-game budgets do not establish equal compute",
        "zero-width intervals do not establish equivalence",
    ):
        assert claim_limit in limits
    protocol = json.loads((tmp_path / "protocol.json").read_text())
    assert protocol["rules_mode"] == rules_mode
    assert protocol["formats"] == formats
    if rules_mode == "mechanic-only":
        assert report["rules_background"] == "champions"
        assert not any("no mechanic-only attribution" in s for s in report["limitations"])
    assert report["total_games"] == 540
    assert report["training_games"] == 216
    assert report["games_per_seed"] == {
        "source": 12,
        "adaptation": 12,
        "native_target_budget": 12,
        "native_total_budget": 24,
    }
    assert set(report["directions"]) == {"tera-to-mega", "mega-to-tera"}
    manifest = load_manifest(tm.MANIFEST_PATH)
    assert {fmt for _, _, fmt in calls} == set(formats.values())
    for domain, format_id in formats.items():
        teams = tm.domain_teams(manifest, domain)
        train = {teams[t] for t in manifest.splits["training"]}
        test = {teams[t] for t in manifest.splits["test"]}
        assert all(
            (a in train and b in train) or (a in test and b in test)
            for a, b, fmt in calls
            if fmt == format_id
        )
        for seed in (11, 29, 47):
            source_domain = "tera" if domain == "mega" else "mega"
            initial = json.loads(
                (tmp_path / f"checkpoints/adapted-to-{domain}-s{seed}-g00.json").read_text()
            )
            source = tmp_path / f"checkpoints/fresh-{source_domain}-s{seed}-g01.json"
            assert initial["threshold"] == json.loads(source.read_text())["threshold"]
            assert initial["init_checkpoint"] == str(source)
            assert initial["format_id"] == format_id
            for generation in (1, 2):
                native = json.loads(
                    (
                        tmp_path / f"checkpoints/fresh-{domain}-s{seed}-g0{generation}.json"
                    ).read_text()
                )
                assert native["init_checkpoint"] is None
                assert native["format_id"] == format_id
                assert native["training_games"] == generation * 12
    games = json.loads((tmp_path / "results.json").read_text())["games"]
    assert {g["format_id"] for g in games} == set(formats.values())
    assert len(list((tmp_path / "replays").glob("*.json.gz"))) == len(games)
    assert all(g["replay"] for g in games)
    assert all(
        v["by_candidate_team"]["all"]["paired_blocks"] == 54 for v in report["directions"].values()
    )
    with pytest.raises(ValueError, match="empty"):
        tm.run_tera_mega(tmp_path)


@pytest.mark.parametrize("dirty", [False, True])
def test_pin_rejected_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dirty: bool
) -> None:
    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **k: SIMULATOR_REVISION if dirty else "wrong"
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 1))
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="clean checkout" if dirty else "revision"):
        tm.run_tera_mega(out, showdown_dir=tmp_path)
    assert not out.exists()


def test_cli_budget_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compare-tera-mega", "--output-dir", str(tmp_path), "--pairs", "0"]) == 2
    assert "positive" in capsys.readouterr().err


@pytest.mark.parametrize("domain,event", [("tera", "-terastallize"), ("mega", "-mega")])
@pytest.mark.parametrize("rules_mode", ["full", "mechanic-only"])
def test_real_simulator_activates_requested_mechanic(
    domain: str, event: str, rules_mode: str
) -> None:
    try:
        sd = ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        pytest.skip("Showdown not available")
    manifest = load_manifest(tm.MANIFEST_PATH)
    teams = tm.domain_teams(manifest, domain)
    result = run_evaluation_battle(
        tm.ActivationAgent(1),
        tm.ActivationAgent(1, "Opponent"),
        tm.FORMAT_SETS[rules_mode][domain],
        teams["test-sand"],
        teams["train-sun"],
        "p1",
        (101, 202, 303, 404),
        sd,
        skip_build=True,
    )
    assert result.replay is not None
    log = "\n".join(result.replay["log"])
    assert f"|{event}|p1" in log
    assert f"|{event}|p2" in log
    assert "|error|" not in log
    other_event = "-mega" if domain == "tera" else "-terastallize"
    assert f"|{other_event}|" not in log


def test_optimizer_selects_training_fitness_and_records_activation_exposure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def game(task: tm.ActivationTask) -> dict[str, float]:
        return {"points": task.threshold, "opportunities": 2.0, "activations": 1.0}

    monkeypatch.setattr(tm, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(tm, "_training_game", game)
    manifest = load_manifest(tm.MANIFEST_PATH)
    paths = tm._train(
        FullTransferConfig(),
        manifest,
        tm.domain_teams(manifest, "tera"),
        tmp_path,
        "tera",
        1,
        tmp_path,
    )
    initial = json.loads(paths[0].read_text())
    selected = json.loads(paths[1].read_text())
    assert selected["threshold"] == max(initial["training"]["candidate_thresholds"])
    assert selected["threshold"] > initial["threshold"]
    assert all(g["activations"] <= g["opportunities"] for g in initial["training"]["games"])
    assert all(0 <= json.loads(p.read_text())["threshold"] <= 1 for p in paths)


def test_unfinished_training_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tm,
        "run_evaluation_battle",
        lambda *a, **k: EvaluationBattleResult(
            None, 60, 0.1, 60, 60, 0, 0, False, False, "turn-limit"
        ),
    )
    task = tm.ActivationTask(0.5, tm.FORMATS["tera"], "a", "b", "p1", (1, 2, 3, 4), "/tmp")
    with pytest.raises(ValueError, match="unfinished training"):
        tm._training_game(task)


@pytest.mark.parametrize("defect", ["family", "packed", "investment", "recipient"])
def test_fixture_drift_is_rejected(tmp_path: Path, defect: str) -> None:
    data = json.loads(tm.MANIFEST_PATH.read_text())
    team = data["teams"]["test-sand"]
    if defect == "family":
        team["family"] = "rain"
    elif defect == "packed":
        team["packed"] = team["packed"].replace("||||50|", "||||100|")
    elif defect == "investment":
        team["pokemon"][0]["evs"]["spe"] = 252
    else:
        team["pokemon"][1]["species"] = "Gyarados"
        team["packed"] = team["packed"].replace("Excadrill", "Gyarados")
    path = tmp_path / "teams.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        tm.domain_teams(load_manifest(path), "mega")


@pytest.mark.parametrize("rules_mode", ["full", "mechanic-only"])
def test_all_domain_sets_match_sheets_stats_and_mechanic_eligibility(rules_mode: str) -> None:
    try:
        sd = ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        pytest.skip("Showdown not available")
    manifest = load_manifest(tm.MANIFEST_PATH)
    inputs = [
        dict(domain=domain, format_id=fmt, team=team_id, packed=packed)
        for domain, fmt in tm.FORMAT_SETS[rules_mode].items()
        for team_id, packed in tm.domain_teams(manifest, domain).items()
    ]
    script = """
    const fs = require('fs');
    const {Battle} = require('./dist/sim/battle.js');
    const {Teams} = require('./dist/sim/teams.js');
    const rows = JSON.parse(fs.readFileSync(0, 'utf8'));
    console.log(JSON.stringify(rows.map(row => {
      const battle = new Battle({formatid: row.format_id, seed: [1, 2, 3, 4]});
      battle.setPlayer('p1', {name: 'Candidate', team: row.packed});
      battle.setPlayer('p2', {name: 'Opponent', team: row.packed});
      return {unpacked: Teams.unpack(row.packed),
        pokemon: battle.p1.pokemon.map(p => ({
          stats: {hp: p.maxhp, ...p.storedStats},
          mega: p.canMegaEvo, tera: p.canTerastallize,
        }))};
    })));
    """
    observed = json.loads(
        subprocess.run(
            [
                "node",
                "--require",
                str(Path(tm.__file__).with_name("simulator") / "tera_mega_formats.cjs"),
                "-e",
                script,
            ],
            cwd=sd,
            input=json.dumps(inputs),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    stats: dict[str, list[dict[str, int]]] = {}
    for row, result in zip(inputs, observed, strict=True):
        domain, team_id = row["domain"], row["team"]
        team = manifest.teams[team_id]
        for member, unpacked in zip(team.pokemon, result["unpacked"], strict=True):
            assert unpacked["species"] == member.species
            assert unpacked["ability"] == member.ability
            assert unpacked["moves"] == list(member.moves)
            assert unpacked["nature"] == member.nature
            assert unpacked["evs"] == member.evs
            assert unpacked["teraType"] == member.tera_type
            assert unpacked["level"] == 50
            assert unpacked["item"] == (
                tm.MEGA_ITEMS.get(member.species, "") if domain == "mega" else ""
            )
        current = [p["stats"] for p in result["pokemon"]]
        if domain == "tera":
            stats[team_id] = current
            assert all(p["tera"] and not p["mega"] for p in result["pokemon"])
        else:
            assert stats[team_id] == current
            assert sum(bool(p["mega"]) for p in result["pokemon"]) == 1
            assert not any(p["tera"] for p in result["pokemon"])
